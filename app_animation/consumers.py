from __future__ import annotations

import uuid
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services.remote_protocol import RemoteRejectReason
from .services.remote_sessions import (
    accept_remote_command,
    register_master_connection,
    register_remote_connection,
    store_remote_state,
    unregister_master_connection,
    unregister_remote_connection,
)


def _remote_group_name(session_id: uuid.UUID) -> str:
    return f"lss.remote.{session_id.hex}"


class BaseRemoteSessionConsumer(AsyncJsonWebsocketConsumer):
    connection_role = ""

    async def connect(self) -> None:
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.authenticated = False
        self.connection_id: uuid.UUID | None = None
        self.remote_connection_counted = False
        self.pending_command_channels: dict[str, str] = {}
        await self.accept()

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if not isinstance(content, dict):
            await self.close(code=4400)
            return
        if not self.authenticated:
            await self._authenticate(content)
            return
        await self._receive_authenticated(content)

    async def disconnect(self, close_code: int) -> None:
        del close_code
        if not getattr(self, "authenticated", False):
            return
        if self.connection_role == "remote":
            await self.channel_layer.group_discard(
                _remote_group_name(self.session_id), self.channel_name
            )
            if self.remote_connection_counted:
                update = await self._unregister_remote(self.session_id)
                if update is not None:
                    await self._notify_master_remote_count(update)
            return
        if self.connection_id is not None:
            await self._unregister_master(self.session_id, self.connection_id)

    async def _authenticate(self, content: dict[str, Any]) -> None:
        if content.get("type") != "AUTH":
            await self.close(code=4401)
            return
        token = content.get("token")
        if not isinstance(token, str) or not token:
            await self.close(code=4401)
            return
        if self.connection_role == "master":
            registration = await self._register_master(
                self.session_id, token, self.channel_name
            )
            if registration is None:
                await self.close(code=4403)
                return
            self.master_token = token
            self.connection_id = registration.connection_id
            self.authenticated = True
            if registration.replaced_channel_name:
                await self.channel_layer.send(
                    registration.replaced_channel_name,
                    {"type": "remote.master.replaced"},
                )
            await self.send_json(
                {
                    "type": "READY",
                    "role": "master",
                    "remote_count": registration.session.remote_connection_count,
                }
            )
            return

        registration = await self._register_remote(self.session_id, token)
        if registration is None:
            await self.close(code=4403)
            return
        self.remote_token = token
        self.authenticated = True
        self.remote_connection_counted = True
        await self.channel_layer.group_add(
            _remote_group_name(self.session_id), self.channel_name
        )
        await self.send_json({"type": "READY", "role": "remote"})
        if registration.session.latest_state_revision >= 0:
            await self.send_json(
                {"type": "STATE", "state": registration.session.latest_state}
            )
        await self._notify_master_remote_count(registration)

    async def _receive_authenticated(self, content: dict[str, Any]) -> None:
        if self.connection_role == "master":
            await self._receive_master(content)
            return
        await self._receive_remote(content)

    async def _receive_remote(self, content: dict[str, Any]) -> None:
        if content.get("type") != "COMMAND":
            await self.send_json(
                {
                    "type": "COMMAND_REJECTED",
                    "reason": RemoteRejectReason.INVALID_COMMAND,
                }
            )
            return
        decision = await self._accept_remote_command(
            self.session_id, self.remote_token, content
        )
        if not decision.accepted or decision.session is None:
            await self.send_json(
                {
                    "type": "COMMAND_REJECTED",
                    "reason": decision.reason or RemoteRejectReason.INVALID_COMMAND,
                }
            )
            return
        command_id = uuid.uuid4().hex
        await self.channel_layer.send(
            decision.session.master_channel_name,
            {
                "type": "remote.command",
                "message": {**content, "command_id": command_id},
                "reply_channel": self.channel_name,
            },
        )
        await self.send_json(
            {
                "type": "COMMAND_ACCEPTED",
                "command": content.get("command"),
                "command_id": command_id,
            }
        )

    async def _receive_master(self, content: dict[str, Any]) -> None:
        if content.get("type") == "STATE":
            result = await self._store_remote_state(
                self.session_id, self.master_token, content
            )
            if result.stored:
                await self.channel_layer.group_send(
                    _remote_group_name(self.session_id),
                    {"type": "remote.state", "message": content},
                )
            return
        if content.get("type") == "MASTER_COMMAND_REJECTED":
            command_id = str(content.get("command_id") or "")
            reply_channel = self.pending_command_channels.pop(command_id, "")
            try:
                reason = RemoteRejectReason(str(content.get("reason") or ""))
            except ValueError:
                reason = RemoteRejectReason.INVALID_TARGET
            if reply_channel:
                await self.channel_layer.send(
                    reply_channel,
                    {"type": "remote.command.rejected", "reason": reason},
                )
            return
        await self.close(code=4400)

    async def remote_state(self, event: dict[str, Any]) -> None:
        await self.send_json(event["message"])

    async def remote_command(self, event: dict[str, Any]) -> None:
        if self.connection_role != "master":
            return
        message = event["message"]
        self.pending_command_channels[str(message["command_id"])] = event[
            "reply_channel"
        ]
        await self.send_json(message)

    async def remote_command_rejected(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "COMMAND_REJECTED", "reason": event["reason"]})

    async def remote_master_replaced(self, event: dict[str, Any]) -> None:
        del event
        await self.send_json({"type": "MASTER_REPLACED"})
        await self.close(code=4409)

    async def remote_connection_count(self, event: dict[str, Any]) -> None:
        if self.connection_role == "master":
            await self.send_json({"type": "REMOTE_COUNT", "count": event["count"]})

    async def remote_session_disabled(self, event: dict[str, Any]) -> None:
        del event
        await self.send_json({"type": "SESSION_DISABLED"})
        await self.close(code=4403)

    async def _notify_master_remote_count(self, update: Any) -> None:
        if update.master_channel_name:
            await self.channel_layer.send(
                update.master_channel_name,
                {
                    "type": "remote.connection.count",
                    "count": update.session.remote_connection_count,
                },
            )

    @database_sync_to_async
    def _register_remote(self, session_id: uuid.UUID, token: str):
        return register_remote_connection(session_id, token)

    @database_sync_to_async
    def _register_master(self, session_id: uuid.UUID, token: str, channel_name: str):
        return register_master_connection(session_id, token, channel_name)

    @database_sync_to_async
    def _unregister_master(self, session_id: uuid.UUID, connection_id: uuid.UUID):
        return unregister_master_connection(session_id, connection_id)

    @database_sync_to_async
    def _unregister_remote(self, session_id: uuid.UUID):
        return unregister_remote_connection(session_id)

    @database_sync_to_async
    def _accept_remote_command(
        self, session_id: uuid.UUID, token: str, content: dict[str, Any]
    ):
        return accept_remote_command(session_id, token, content)

    @database_sync_to_async
    def _store_remote_state(
        self, session_id: uuid.UUID, token: str, content: dict[str, Any]
    ):
        return store_remote_state(session_id, token, content)


class RemoteMasterConsumer(BaseRemoteSessionConsumer):
    connection_role = "master"


class RemoteMobileConsumer(BaseRemoteSessionConsumer):
    connection_role = "remote"
