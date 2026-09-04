from __future__ import annotations

import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.security.websocket import OriginValidator
from channels.testing import WebsocketCommunicator
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from app_group.models import Group, GroupStatus
from .models import (
    Animation,
    AnimationRemoteConnection,
    AnimationRemoteConnectionRole,
    AnimationRemoteSession,
)
from .routing import websocket_urlpatterns
from .services.remote_sessions import (
    authenticate_remote_session,
    create_remote_session,
    deactivate_remote_session,
    register_master_connection,
)


application = OriginValidator(URLRouter(websocket_urlpatterns), ["http://testserver"])


@override_settings(
    CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    },
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
    def _state(revision: int, *, black_mode: bool = False) -> dict[str, object]:
        return {
            "type": "STATE",
            "state": {
                "revision": revision,
                "current_projection_step": None,
                "next_projection_step": None,
                "current_song": None,
                "previous_song": None,
                "next_song": None,
                "black_mode": black_mode,
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
            ready = await master.receive_json_from()
            self.assertEqual(ready["type"], "READY")
            self.assertEqual(ready["role"], "master")
            self.assertEqual(ready["remote_count"], 0)
            self.assertEqual(ready["next_state_revision"], 0)
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
            received = await master.receive_json_from()
            self.assertEqual(received["type"], "COMMAND")
            self.assertEqual(received["command"], "NEXT_SLIDE")
            await master.send_json_to(
                {
                    "type": "MASTER_COMMAND_RECEIVED",
                    "command_id": received["command_id"],
                }
            )
            accepted = await remote.receive_json_from()
            self.assertEqual(accepted["type"], "COMMAND_ACCEPTED")
            self.assertEqual(accepted["command"], "NEXT_SLIDE")
            self.assertEqual(received["command_id"], accepted["command_id"])
            self.assertEqual(
                await master.receive_json_from(),
                {
                    "type": "MASTER_COMMAND_EXECUTE",
                    "command_id": received["command_id"],
                },
            )

            await master.send_json_to(self._state(1))
            self.assertEqual(await remote.receive_json_from(), self._state(1))
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_multiple_remotes_converge_after_a_shared_cooldown_rejection(self):
        created = self._create_session()

        async def scenario():
            master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await master.receive_json_from()
            first_remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await first_remote.receive_json_from()
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 1}
            )
            second_remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await second_remote.receive_json_from()
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 2}
            )

            await first_remote.send_json_to(
                {"type": "COMMAND", "command": "NEXT_SLIDE"}
            )
            received = await master.receive_json_from()
            await master.send_json_to(
                {
                    "type": "MASTER_COMMAND_RECEIVED",
                    "command_id": received["command_id"],
                }
            )
            accepted = await first_remote.receive_json_from()
            self.assertEqual(accepted["type"], "COMMAND_ACCEPTED")
            await second_remote.send_json_to(
                {"type": "COMMAND", "command": "NEXT_SLIDE"}
            )
            self.assertEqual(
                await second_remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "COOLDOWN"},
            )

            state = self._state(7, black_mode=True)
            await master.send_json_to(state)
            self.assertEqual(await first_remote.receive_json_from(), state)
            self.assertEqual(await second_remote.receive_json_from(), state)
            await first_remote.disconnect()
            await second_remote.disconnect()
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
            self.assertEqual(
                await remote.receive_json_from(), {"type": "MASTER_UNAVAILABLE"}
            )
            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            self.assertEqual(
                await remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "MASTER_UNAVAILABLE"},
            )
            await remote.disconnect()

        async_to_sync(scenario)()

    def test_master_disconnect_rejects_new_commands_without_queueing_them(self):
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
            await master.receive_json_from()
            await master.disconnect()
            self.assertEqual(
                await remote.receive_json_from(), {"type": "MASTER_UNAVAILABLE"}
            )

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            self.assertEqual(
                await remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "MASTER_UNAVAILABLE"},
            )
            await remote.disconnect()

        async_to_sync(scenario)()

    def test_master_rejection_releases_the_reservation_without_acknowledging(self):
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
            await master.receive_json_from()

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            command = await master.receive_json_from()
            await master.send_json_to(
                {
                    "type": "MASTER_COMMAND_REJECTED",
                    "command_id": command["command_id"],
                    "reason": "INVALID_TARGET",
                }
            )
            self.assertEqual(
                await remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "INVALID_TARGET"},
            )

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            retry = await master.receive_json_from()
            await master.send_json_to(
                {
                    "type": "MASTER_COMMAND_RECEIVED",
                    "command_id": retry["command_id"],
                }
            )
            self.assertEqual(
                (await remote.receive_json_from())["type"], "COMMAND_ACCEPTED"
            )
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_missing_master_receipt_invalidates_master_and_rejects_command(self):
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
            await master.receive_json_from()

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            self.assertEqual((await master.receive_json_from())["type"], "COMMAND")
            messages = [
                await remote.receive_json_from(),
                await remote.receive_json_from(),
            ]
            self.assertIn({"type": "MASTER_UNAVAILABLE"}, messages)
            self.assertIn(
                {"type": "COMMAND_REJECTED", "reason": "MASTER_UNAVAILABLE"},
                messages,
            )
            await remote.disconnect()
            await master.disconnect()

        with self.settings(REMOTE_MASTER_COMMAND_ACK_SECONDS=0.01):
            async_to_sync(scenario)()

    def test_replaced_master_cannot_acknowledge_a_pending_command(self):
        created = self._create_session()

        async def scenario():
            first_master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await first_master.receive_json_from()
            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await remote.receive_json_from()
            await first_master.receive_json_from()

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            await first_master.receive_json_from()
            replacement = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await replacement.receive_json_from()
            self.assertEqual(
                await first_master.receive_json_from(), {"type": "MASTER_REPLACED"}
            )
            self.assertEqual(
                await remote.receive_json_from(),
                {"type": "COMMAND_REJECTED", "reason": "MASTER_UNAVAILABLE"},
            )
            await remote.disconnect()
            await replacement.disconnect()

        async_to_sync(scenario)()

    def test_replaced_master_does_not_receive_a_stale_command_event(self):
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
            await master.receive_json_from()
            old_master = await database_sync_to_async(
                lambda: AnimationRemoteConnection.objects.get(
                    session_id=created.session.session_id,
                    role=AnimationRemoteConnectionRole.MASTER,
                )
            )()
            remote_channel_name = await database_sync_to_async(
                lambda: (
                    AnimationRemoteConnection.objects.get(
                        session_id=created.session.session_id,
                        role=AnimationRemoteConnectionRole.REMOTE,
                    ).channel_name
                )
            )()
            self.assertIsNotNone(old_master.channel_name)
            self.assertIsNotNone(remote_channel_name)
            replacement = await database_sync_to_async(register_master_connection)(
                created.session.session_id,
                created.master_token,
                "replacement-master-channel",
            )
            self.assertIsNotNone(replacement)

            await get_channel_layer().send(
                old_master.channel_name,
                {
                    "type": "remote.command",
                    "message": {
                        "type": "COMMAND",
                        "command": "NEXT_SLIDE",
                        "command_id": "stale-command",
                    },
                    "reply_channel": remote_channel_name,
                    "master_connection_id": str(old_master.connection_id),
                },
            )
            self.assertEqual(
                await master.receive_json_from(), {"type": "MASTER_REPLACED"}
            )
            await master.wait()
            await remote.disconnect()

        async_to_sync(scenario)()

    def test_master_heartbeat_reports_a_remote_lease_purged_after_crash(self):
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
            await master.receive_json_from()
            await database_sync_to_async(
                AnimationRemoteConnection.objects.filter(
                    session_id=created.session.session_id,
                    role=AnimationRemoteConnectionRole.REMOTE,
                ).update
            )(last_seen_at=timezone.now() - timedelta(seconds=16))
            await master.send_json_to({"type": "HEARTBEAT"})
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 0}
            )
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_reaper_notifies_remotes_when_a_master_lease_expires(self):
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
            await master.receive_json_from()
            await database_sync_to_async(
                AnimationRemoteConnection.objects.filter(
                    session_id=created.session.session_id,
                    role=AnimationRemoteConnectionRole.MASTER,
                ).update
            )(last_seen_at=timezone.now() - timedelta(seconds=16))

            await database_sync_to_async(call_command)("purge_remote_connections")
            self.assertEqual(
                await remote.receive_json_from(), {"type": "MASTER_UNAVAILABLE"}
            )
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_stale_master_unavailable_event_is_ignored_after_master_replacement(self):
        created = self._create_session()

        async def scenario():
            first_master = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await first_master.receive_json_from()
            remote = await self._connect(
                created.session.session_id, "remote", created.access_token
            )
            await remote.receive_json_from()
            await first_master.receive_json_from()

            replacement = await self._connect(
                created.session.session_id, "master", created.master_token
            )
            await replacement.receive_json_from()
            self.assertEqual(
                await first_master.receive_json_from(), {"type": "MASTER_REPLACED"}
            )
            await get_channel_layer().group_send(
                f"lss.remote.{created.session.session_id.hex}",
                {"type": "remote.master.unavailable"},
            )
            self.assertTrue(await remote.receive_nothing(timeout=0.1))
            await remote.disconnect()
            await replacement.disconnect()

        async_to_sync(scenario)()

    def test_stale_remote_count_event_is_replaced_with_persisted_count(self):
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
            channel_name = await database_sync_to_async(
                lambda: (
                    AnimationRemoteSession.objects.get(
                        session_id=created.session.session_id
                    ).master_channel_name
                )
            )()
            self.assertIsNotNone(channel_name)
            await get_channel_layer().send(
                channel_name, {"type": "remote.connection.count", "count": 0}
            )
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 1}
            )
            await remote.disconnect()
            await master.disconnect()

        async_to_sync(scenario)()

    def test_reaper_notifies_the_master_of_a_purged_remote_count(self):
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
            await master.receive_json_from()
            await database_sync_to_async(
                AnimationRemoteConnection.objects.filter(
                    session_id=created.session.session_id,
                    role=AnimationRemoteConnectionRole.REMOTE,
                ).update
            )(last_seen_at=timezone.now() - timedelta(seconds=16))

            await database_sync_to_async(call_command)("purge_remote_connections")
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 0}
            )
            await remote.disconnect()
            await master.disconnect()

    def test_expired_remote_lease_cannot_send_a_command(self):
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
            await master.receive_json_from()
            await database_sync_to_async(
                AnimationRemoteConnection.objects.filter(
                    session_id=created.session.session_id,
                    role=AnimationRemoteConnectionRole.REMOTE,
                ).update
            )(last_seen_at=timezone.now() - timedelta(seconds=16))

            await remote.send_json_to({"type": "COMMAND", "command": "NEXT_SLIDE"})
            close_event = await remote.receive_output()
            self.assertEqual(close_event["type"], "websocket.close")
            self.assertEqual(close_event["code"], 4408)
            self.assertEqual(
                await master.receive_json_from(), {"type": "REMOTE_COUNT", "count": 0}
            )
            await master.disconnect()

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

    def test_unauthenticated_socket_is_closed_after_the_authentication_timeout(self):
        created = self._create_session()

        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                f"/ws/animations/remote/{created.session.session_id}/remote/",
                headers=[(b"origin", b"http://testserver")],
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            close_event = await communicator.receive_output()
            self.assertEqual(close_event["type"], "websocket.close")
            self.assertEqual(close_event["code"], 4401)

        with self.settings(REMOTE_CONNECTION_AUTH_TIMEOUT_SECONDS=0.01):
            async_to_sync(scenario)()

    def test_invalid_and_deactivated_tokens_are_refused_during_authentication(self):
        invalid = self._create_session()
        deactivated = self._create_session()
        self.assertIsNotNone(
            deactivate_remote_session(
                deactivated.session.session_id, deactivated.master_token
            )
        )

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

        async_to_sync(assert_refused)(invalid.session.session_id, "wrong-token")
        async_to_sync(assert_refused)(
            deactivated.session.session_id, deactivated.access_token
        )

    def test_deactivation_closes_connected_remotes_and_invalidates_access(self):
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
            await master.receive_json_from()
            result = await database_sync_to_async(deactivate_remote_session)(
                created.session.session_id, created.master_token
            )
            self.assertIsNotNone(result)
            await get_channel_layer().group_send(
                f"lss.remote.{created.session.session_id.hex}",
                {"type": "remote.session.disabled"},
            )
            await get_channel_layer().send(
                result.master_channel_name, {"type": "remote.session.disabled"}
            )
            self.assertEqual(
                await remote.receive_json_from(), {"type": "SESSION_DISABLED"}
            )
            self.assertEqual(
                await master.receive_json_from(), {"type": "SESSION_DISABLED"}
            )
            await remote.wait()
            await master.wait()

        async_to_sync(scenario)()
        self.assertIsNone(
            authenticate_remote_session(
                created.session.session_id, created.access_token, now=timezone.now()
            )
        )

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
            self.assertEqual((await second_master.receive_json_from())["type"], "READY")
            self.assertEqual(
                await first_master.receive_json_from(), {"type": "MASTER_REPLACED"}
            )
            await second_master.disconnect()

        async_to_sync(scenario)()
