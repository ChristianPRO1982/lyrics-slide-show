from __future__ import annotations

import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from app_group.models import Group, GroupStatus
from lyrics_slide_show.asgi import application

from .models import Animation
from .services.remote_sessions import create_remote_session


@override_settings(
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }
)
class RemoteTransportConsumerTests(TransactionTestCase):
    def _create_session(self):
        group = Group.objects.create(
            name=f"Remote transport {uuid.uuid4()}", status=GroupStatus.OPEN
        )
        animation = Animation.objects.create(
            group=group,
            title="Remote transport",
            scheduled_at=timezone.now(),
        )
        return create_remote_session(animation)

    @staticmethod
    def _state(revision: int) -> dict[str, object]:
        return {
            "type": "STATE",
            "state": {
                "revision": revision,
                "current_projection_step": None,
                "next_projection_step": None,
                "current_song": None,
                "previous_song": None,
                "next_song": None,
                "black_mode": False,
                "songs": [],
                "chorus_available": False,
                "current_transition": None,
                "available_transitions": [],
                "qr_mode": False,
                "master_status": "MASTER_CONNECTED",
            },
        }

    async def _connect(self, session_id, role: str, token: str):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/animations/remote/{session_id}/{role}/",
            headers=[(b"origin", b"http://testserver")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_json_to({"type": "AUTH", "token": token})
        return communicator

    def test_master_and_remote_authenticate_then_remote_receives_latest_state(self):
        created = self._create_session()

        async def scenario():
            master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            self.assertEqual(
                await master.receive_json_from(),
                {"type": "READY", "role": "master", "remote_count": 0},
            )
            await master.send_json_to(self._state(3))

            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            self.assertEqual(
                await remote.receive_json_from(), {"type": "READY", "role": "remote"}
            )
            self.assertEqual(await remote.receive_json_from(), self._state(3))
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_command_is_accepted_relayed_to_master_and_state_is_broadcast(self):
        created = self._create_session()

        async def scenario():
            master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await master.receive_json_from()
            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await remote.receive_json_from()
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 1}
            )

            command = {"type": "COMMAND", "command": "NEXT_SLIDE"}
            await remote.send_json_to(command)
            accepted = await remote.receive_json_from()
            self.assertEqual(accepted["type"], "COMMAND_ACCEPTED")
            self.assertEqual(accepted["command"], "NEXT_SLIDE")
            received = await master.receive_json_from()
            self.assertEqual(received["type"], "COMMAND")
            self.assertEqual(received["command"], "NEXT_SLIDE")
            self.assertEqual(received["command_id"], accepted["command_id"])

            await master.send_json_to(self._state(1))
            self.assertEqual(await remote.receive_json_from(), self._state(1))
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_remote_connection_count_is_reported_and_session_disable_closes_sockets(
        self,
    ):
        created = self._create_session()

        async def scenario():
            master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await master.receive_json_from()
            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await remote.receive_json_from()
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 1}
            )
            await get_channel_layer().group_send(
                f"lss.remote.{created.session.session_id.hex}",
                {"type": "remote.session.disabled"},
            )
            self.assertEqual(
                await remote.receive_json_from(), {"type": "SESSION_DISABLED"}
            )
            await master.disconnect()

        async_to_sync(scenario)()

    def test_command_is_rejected_when_master_is_unavailable(self):
        created = self._create_session()

        async def scenario():
            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await remote.receive_json_from()
            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            self.assertEqual(
                await remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "MASTER_UNAVAILABLE"},
            )
            await remote.disconnect()

        async_to_sync(scenario)()

    def test_inactive_and_expired_sessions_are_refused_during_authentication(self):
        inactive = self._create_session()
        inactive.session.active = False
        inactive.session.save(update_fields=["active"])
        expired = self._create_session()
        expired.session.expires_at = timezone.now() - timedelta(seconds=1)
        expired.session.save(update_fields=["expires_at"])

        async def assert_refused(session_id, token):
            communicator = WebsocketCommunicator(
                application,
                f"/ws/animations/remote/{session_id}/remote/",
                headers=[(b"origin", b"http://testserver")],
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"type": "AUTH", "token": token})
            close_event = await communicator.receive_output()
            self.assertEqual(close_event["type"], "websocket.close")
            self.assertEqual(close_event["code"], 4403)

        async_to_sync(assert_refused)(
            inactive.session.session_id, inactive.access_token
        )
        async_to_sync(assert_refused)(expired.session.session_id, expired.access_token)

    def test_new_master_replaces_the_previous_connection(self):
        created = self._create_session()

        async def scenario():
            first_master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await first_master.receive_json_from()
            second_master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            self.assertEqual(
                await second_master.receive_json_from(),
                {"type": "READY", "role": "master", "remote_count": 0},
            )
            self.assertEqual(
                await first_master.receive_json_from(), {"type": "MASTER_REPLACED"}
            )
            await second_master.disconnect()

        async_to_sync(scenario)()
