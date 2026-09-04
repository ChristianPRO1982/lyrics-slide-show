from __future__ import annotations

import asyncio
import uuid
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services.remote_protocol import RemoteRejectReason
from .services.remote_sessions import (
    accept_remote_command,
    cancel_remote_command_reservation,
    get_remote_connection_heartbeat,
    get_remote_connection_count_for_master,
    get_remote_master_command_ack_timeout,
    get_remote_state_snapshot,
    inspect_remote_connection,
    is_remote_master_available,
    RemoteCommandDecision,
    register_master_connection,
    register_remote_connection,
    store_remote_state,
    touch_remote_connection,
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
        self.pending_command_channels: dict[str, tuple[str, uuid.UUID]] = {}
        self.pending_command_receipts: dict[str, asyncio.Future[str | None]] = {}
        self.pending_command_tasks: set[asyncio.Task[None]] = set()
        self.lease_watchdog_task: asyncio.Task[None] | None = None
        await self.accept()

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if not isinstance(content, dict):
            await self.close(code=4400)
            return
        if not self.authenticated:
            await self._authenticate(content)
            return
        if content.get("type") == "HEARTBEAT":
            await self._receive_heartbeat()
            return
        await self._receive_authenticated(content)

    async def disconnect(self, close_code: int) -> None:
        del close_code
        await self._stop_lease_watchdog()
        if not getattr(self, "authenticated", False):
            return
        await self._cancel_pending_command_tasks()
        if self.connection_role == "remote":
            await self.channel_layer.group_discard(
                _remote_group_name(self.session_id), self.channel_name
            )
            if self.remote_connection_counted and self.connection_id is not None:
                update = await self._unregister_remote(
                    self.session_id, self.connection_id
                )
                if update is not None:
                    await self._notify_master_remote_count(update)
                    if update.master_lost:
                        await self._broadcast_master_unavailable()
            return
        if self.connection_id is not None:
            await self._reject_pending_master_commands()
            update = await self._unregister_master(self.session_id, self.connection_id)
            if update is not None and update.master_lost:
                await self._broadcast_master_unavailable()

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
            self._start_lease_watchdog()
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
                    "next_state_revision": registration.next_state_revision,
                }
            )
            return

        registration = await self._register_remote(
            self.session_id, token, uuid.uuid4(), self.channel_name
        )
        if registration is None or registration.connection_id is None:
            await self.close(code=4403)
            return
        self.remote_token = token
        self.connection_id = registration.connection_id
        self.authenticated = True
        self.remote_connection_counted = True
        self._start_lease_watchdog()
        await self.channel_layer.group_add(
            _remote_group_name(self.session_id), self.channel_name
        )
        await self.send_json({"type": "READY", "role": "remote"})
        state_snapshot = await self._get_remote_state_snapshot(
            self.session_id, self.remote_token
        )
        if state_snapshot is not None:
            await self.send_json({"type": "STATE", "state": state_snapshot})
        await self._notify_master_remote_count(registration)
        if registration.master_lost or not registration.master_channel_name:
            await self._broadcast_master_unavailable()

    async def _receive_heartbeat(self) -> None:
        if self.connection_id is None:
            await self.close(code=4403)
            return
        result = await self._touch_connection(
            self.session_id, self.connection_id, self.connection_role
        )
        await self._handle_connection_liveness(result)

    async def _receive_authenticated(self, content: dict[str, Any]) -> None:
        if self.connection_role == "master":
            await self._receive_master(content)
            return
        await self._receive_remote(content)

    def _start_lease_watchdog(self) -> None:
        self.lease_watchdog_task = asyncio.create_task(self._watch_connection_lease())

    async def _stop_lease_watchdog(self) -> None:
        task = self.lease_watchdog_task
        self.lease_watchdog_task = None
        if task is None or task is asyncio.current_task():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _watch_connection_lease(self) -> None:
        try:
            while self.authenticated and self.connection_id is not None:
                await asyncio.sleep(get_remote_connection_heartbeat().total_seconds())
                result = await self._inspect_connection(
                    self.session_id, self.connection_id, self.connection_role
                )
                await self._handle_connection_liveness(result)
                if not result.alive:
                    return
        except asyncio.CancelledError:
            return

    async def _receive_remote(self, content: dict[str, Any]) -> None:
        if self.connection_id is None:
            await self.close(code=4403)
            return
        liveness = await self._inspect_connection(
            self.session_id, self.connection_id, self.connection_role
        )
        await self._handle_connection_liveness(liveness)
        if not liveness.alive:
            return
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
        if decision.master_lost:
            await self._broadcast_master_unavailable()
        if not decision.accepted or decision.session is None:
            await self.send_json(
                {
                    "type": "COMMAND_REJECTED",
                    "reason": decision.reason or RemoteRejectReason.INVALID_COMMAND,
                }
            )
            return

        command_id = uuid.uuid4().hex
        receipt = asyncio.get_running_loop().create_future()
        self.pending_command_receipts[command_id] = receipt
        try:
            await self.channel_layer.send(
                decision.session.master_channel_name,
                {
                    "type": "remote.command",
                    "message": {
                        **content,
                        "command_id": command_id,
                    },
                    "reply_channel": self.channel_name,
                    "master_connection_id": str(decision.master_connection_id),
                },
            )
        except Exception:
            self.pending_command_receipts.pop(command_id, None)
            await self._reject_unavailable_command(decision)
            return
        task = asyncio.create_task(
            self._await_master_receipt(command_id, receipt, decision, content)
        )
        self.pending_command_tasks.add(task)
        task.add_done_callback(self.pending_command_tasks.discard)

    async def _await_master_receipt(
        self,
        command_id: str,
        receipt: asyncio.Future[str | None],
        decision: RemoteCommandDecision,
        content: dict[str, Any],
    ) -> None:
        try:
            reason = await asyncio.wait_for(
                receipt, timeout=get_remote_master_command_ack_timeout()
            )
        except asyncio.CancelledError:
            await self._cancel_remote_command(
                self.session_id,
                decision.accepted_at,
                decision.master_connection_id,
                invalidate_master=False,
            )
            await self._clear_master_command(command_id, decision)
            raise
        except Exception:
            await self._reject_unavailable_command(decision, command_id=command_id)
            return
        finally:
            self.pending_command_receipts.pop(command_id, None)

        if reason is not None:
            await self._cancel_remote_command(
                self.session_id,
                decision.accepted_at,
                decision.master_connection_id,
                invalidate_master=False,
            )
            await self.send_json({"type": "COMMAND_REJECTED", "reason": reason})
            return
        await self.send_json(
            {
                "type": "COMMAND_ACCEPTED",
                "command": content.get("command"),
                "command_id": command_id,
            }
        )

    async def _reject_unavailable_command(
        self, decision: RemoteCommandDecision, *, command_id: str | None = None
    ) -> None:
        update = await self._cancel_remote_command(
            self.session_id,
            decision.accepted_at,
            decision.master_connection_id,
            invalidate_master=True,
        )
        if update is not None and update.master_lost:
            await self._broadcast_master_unavailable()
        if command_id:
            await self._clear_master_command(command_id, decision)
        await self.send_json(
            {
                "type": "COMMAND_REJECTED",
                "reason": RemoteRejectReason.MASTER_UNAVAILABLE,
            }
        )

    async def _clear_master_command(
        self, command_id: str, decision: RemoteCommandDecision
    ) -> None:
        master_channel_name = (
            decision.session.master_channel_name if decision.session else None
        )
        if master_channel_name:
            await self.channel_layer.send(
                master_channel_name,
                {"type": "remote.command.cancelled", "command_id": command_id},
            )

    async def _receive_master(self, content: dict[str, Any]) -> None:
        if not await self._ensure_current_master():
            return
        if content.get("type") == "STATE":
            result = await self._store_remote_state(
                self.session_id, self.master_token, content, self.connection_id
            )
            if result.stored:
                await self.channel_layer.group_send(
                    _remote_group_name(self.session_id),
                    {"type": "remote.state", "message": content},
                )
            return
        if content.get("type") == "MASTER_COMMAND_RECEIVED":
            await self._complete_master_command(
                str(content.get("command_id") or ""), None
            )
            return
        if content.get("type") == "MASTER_COMMAND_REJECTED":
            try:
                reason = RemoteRejectReason(str(content.get("reason") or ""))
            except ValueError:
                reason = RemoteRejectReason.INVALID_TARGET
            await self._complete_master_command(
                str(content.get("command_id") or ""), reason
            )
            return
        await self.close(code=4400)

    async def _ensure_current_master(self) -> bool:
        if self.connection_id is None:
            await self.close(code=4403)
            return False
        result = await self._inspect_connection(
            self.session_id, self.connection_id, self.connection_role
        )
        await self._handle_connection_liveness(result)
        return result.alive

    async def _handle_connection_liveness(self, result: Any) -> None:
        if result.master_lost:
            await self._broadcast_master_unavailable()
        if result.remote_count_changed and result.session is not None:
            await self._send_remote_count(
                result.session.master_channel_name,
                result.session.remote_connection_count,
            )
        if result.alive:
            return
        if result.session_invalid:
            await self.channel_layer.group_send(
                _remote_group_name(self.session_id), {"type": "remote.session.disabled"}
            )
            if (
                result.session is not None
                and result.session.master_channel_name
                and result.session.master_channel_name != self.channel_name
            ):
                await self.channel_layer.send(
                    result.session.master_channel_name,
                    {"type": "remote.session.disabled"},
                )
            if self.connection_role == "master":
                await self.send_json({"type": "SESSION_DISABLED"})
                await self.close(code=4403)
            return
        if result.replaced and self.connection_role == "master":
            await self._reject_pending_master_commands()
            await self.send_json({"type": "MASTER_REPLACED"})
            await self.close(code=4409)
            return
        if result.lease_expired:
            await self.close(code=4408)
            return
        await self.send_json({"type": "SESSION_DISABLED"})
        await self.close(code=4403)

    async def _complete_master_command(
        self, command_id: str, reason: RemoteRejectReason | None
    ) -> None:
        pending = self.pending_command_channels.pop(command_id, None)
        if pending is None:
            return
        reply_channel, expected_connection_id = pending
        if self.connection_id != expected_connection_id:
            await self.channel_layer.send(
                reply_channel,
                {
                    "type": "remote.command.rejected",
                    "command_id": command_id,
                    "reason": RemoteRejectReason.MASTER_UNAVAILABLE,
                },
            )
            return
        event_type = (
            "remote.command.received" if reason is None else "remote.command.rejected"
        )
        payload: dict[str, Any] = {"type": event_type, "command_id": command_id}
        if reason is not None:
            payload["reason"] = reason
        await self.channel_layer.send(reply_channel, payload)
        if reason is None:
            await self.channel_layer.send(
                self.channel_name,
                {
                    "type": "remote.command.execute",
                    "command_id": command_id,
                    "master_connection_id": str(expected_connection_id),
                },
            )

    async def remote_state(self, event: dict[str, Any]) -> None:
        await self.send_json(event["message"])

    async def remote_command(self, event: dict[str, Any]) -> None:
        if self.connection_role != "master":
            return
        message = event["message"]
        expected_connection_id = uuid.UUID(event["master_connection_id"])
        if self.connection_id != expected_connection_id:
            await self.channel_layer.send(
                event["reply_channel"],
                {
                    "type": "remote.command.rejected",
                    "command_id": str(message["command_id"]),
                    "reason": RemoteRejectReason.MASTER_UNAVAILABLE,
                },
            )
            return
        self.pending_command_channels[str(message["command_id"])] = (
            event["reply_channel"],
            expected_connection_id,
        )
        await self.send_json(message)

    async def remote_command_received(self, event: dict[str, Any]) -> None:
        receipt = self.pending_command_receipts.get(str(event.get("command_id") or ""))
        if receipt is not None and not receipt.done():
            receipt.set_result(None)

    async def remote_command_cancelled(self, event: dict[str, Any]) -> None:
        command_id = str(event.get("command_id") or "")
        self.pending_command_channels.pop(command_id, None)
        if self.connection_role == "master":
            await self.send_json(
                {"type": "MASTER_COMMAND_CANCELLED", "command_id": command_id}
            )

    async def remote_command_execute(self, event: dict[str, Any]) -> None:
        if self.connection_role != "master" or not await self._ensure_current_master():
            return
        if self.connection_id != uuid.UUID(event["master_connection_id"]):
            return
        await self.send_json(
            {"type": "MASTER_COMMAND_EXECUTE", "command_id": event["command_id"]}
        )

    async def remote_command_rejected(self, event: dict[str, Any]) -> None:
        receipt = self.pending_command_receipts.get(str(event.get("command_id") or ""))
        if receipt is not None and not receipt.done():
            receipt.set_result(RemoteRejectReason(str(event["reason"])))

    async def remote_master_replaced(self, event: dict[str, Any]) -> None:
        del event
        await self._reject_pending_master_commands()
        await self.send_json({"type": "MASTER_REPLACED"})
        await self.close(code=4409)

    async def remote_master_unavailable(self, event: dict[str, Any]) -> None:
        del event
        if (
            self.connection_role == "remote"
            and not await self._is_remote_master_available(self.session_id)
        ):
            await self.send_json({"type": "MASTER_UNAVAILABLE"})

    async def remote_connection_count(self, event: dict[str, Any]) -> None:
        del event
        if self.connection_role != "master" or self.connection_id is None:
            return
        count = await self._get_remote_connection_count_for_master(
            self.session_id, self.connection_id
        )
        if count is not None:
            await self.send_json({"type": "REMOTE_COUNT", "count": count})

    async def remote_session_disabled(self, event: dict[str, Any]) -> None:
        del event
        await self._cancel_pending_command_tasks()
        await self._reject_pending_master_commands()
        await self.send_json({"type": "SESSION_DISABLED"})
        await self.close(code=4403)

    async def _reject_pending_master_commands(self) -> None:
        pending = self.pending_command_channels
        self.pending_command_channels = {}
        for command_id, (reply_channel, _connection_id) in pending.items():
            await self.channel_layer.send(
                reply_channel,
                {
                    "type": "remote.command.rejected",
                    "command_id": command_id,
                    "reason": RemoteRejectReason.MASTER_UNAVAILABLE,
                },
            )

    async def _cancel_pending_command_tasks(self) -> None:
        tasks = tuple(self.pending_command_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _broadcast_master_unavailable(self) -> None:
        await self.channel_layer.group_send(
            _remote_group_name(self.session_id), {"type": "remote.master.unavailable"}
        )

    async def _notify_master_remote_count(self, update: Any) -> None:
        await self._send_remote_count(
            update.master_channel_name, update.session.remote_connection_count
        )

    async def _send_remote_count(
        self, master_channel_name: str | None, count: int
    ) -> None:
        if master_channel_name:
            await self.channel_layer.send(
                master_channel_name,
                {"type": "remote.connection.count", "count": count},
            )

    @database_sync_to_async
    def _register_remote(
        self,
        session_id: uuid.UUID,
        token: str,
        connection_id: uuid.UUID,
        channel_name: str,
    ):
        return register_remote_connection(
            session_id,
            token,
            connection_id=connection_id,
            channel_name=channel_name,
        )

    @database_sync_to_async
    def _register_master(self, session_id: uuid.UUID, token: str, channel_name: str):
        return register_master_connection(session_id, token, channel_name)

    @database_sync_to_async
    def _unregister_master(self, session_id: uuid.UUID, connection_id: uuid.UUID):
        return unregister_master_connection(session_id, connection_id)

    @database_sync_to_async
    def _unregister_remote(self, session_id: uuid.UUID, connection_id: uuid.UUID):
        return unregister_remote_connection(session_id, connection_id)

    @database_sync_to_async
    def _touch_connection(
        self, session_id: uuid.UUID, connection_id: uuid.UUID, role: str
    ):
        return touch_remote_connection(session_id, connection_id, role)

    @database_sync_to_async
    def _inspect_connection(
        self, session_id: uuid.UUID, connection_id: uuid.UUID, role: str
    ):
        return inspect_remote_connection(session_id, connection_id, role)

    @database_sync_to_async
    def _is_remote_master_available(self, session_id: uuid.UUID):
        return is_remote_master_available(session_id)

    @database_sync_to_async
    def _get_remote_connection_count_for_master(
        self, session_id: uuid.UUID, master_connection_id: uuid.UUID
    ):
        return get_remote_connection_count_for_master(session_id, master_connection_id)

    @database_sync_to_async
    def _get_remote_state_snapshot(self, session_id: uuid.UUID, token: str):
        return get_remote_state_snapshot(session_id, token)

    @database_sync_to_async
    def _accept_remote_command(
        self, session_id: uuid.UUID, token: str, content: dict[str, Any]
    ):
        return accept_remote_command(session_id, token, content)

    @database_sync_to_async
    def _cancel_remote_command(
        self,
        session_id: uuid.UUID,
        accepted_at: Any,
        master_connection_id: uuid.UUID | None,
        *,
        invalidate_master: bool,
    ):
        return cancel_remote_command_reservation(
            session_id,
            accepted_at,
            master_connection_id,
            invalidate_master=invalidate_master,
        )

    @database_sync_to_async
    def _store_remote_state(
        self,
        session_id: uuid.UUID,
        token: str,
        content: dict[str, Any],
        connection_id: uuid.UUID | None,
    ):
        return store_remote_state(
            session_id, token, content, connection_id=connection_id
        )


class RemoteMasterConsumer(BaseRemoteSessionConsumer):
    connection_role = "master"


class RemoteMobileConsumer(BaseRemoteSessionConsumer):
    connection_role = "remote"
