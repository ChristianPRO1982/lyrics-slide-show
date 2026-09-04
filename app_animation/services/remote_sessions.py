from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from app_animation.models import (
    Animation,
    AnimationRemoteConnection,
    AnimationRemoteConnectionRole,
    AnimationRemoteSession,
)
from app_animation.transitions import list_enabled_transitions

from .remote_protocol import (
    RemoteCommandMessage,
    RemoteProtocolError,
    RemoteRejectReason,
    RemoteStateMessage,
)


@dataclass(frozen=True)
class CreatedRemoteSession:
    session: AnimationRemoteSession
    access_token: str
    master_token: str


@dataclass(frozen=True)
class RemoteCommandDecision:
    accepted: bool
    reason: RemoteRejectReason | None
    session: AnimationRemoteSession | None
    master_connection_id: uuid.UUID | None = None
    accepted_at: datetime | None = None
    master_lost: bool = False


@dataclass(frozen=True)
class RemoteStateStoreResult:
    stored: bool
    reason: RemoteRejectReason | None
    session: AnimationRemoteSession | None


@dataclass(frozen=True)
class MasterConnectionRegistration:
    session: AnimationRemoteSession
    connection_id: uuid.UUID
    replaced_channel_name: str | None
    next_state_revision: int


@dataclass(frozen=True)
class RemoteConnectionUpdate:
    session: AnimationRemoteSession
    master_channel_name: str | None
    connection_id: uuid.UUID | None = None
    master_lost: bool = False


@dataclass(frozen=True)
class ConnectionHeartbeatResult:
    session: AnimationRemoteSession | None
    alive: bool
    master_lost: bool = False
    replaced: bool = False
    lease_expired: bool = False
    session_invalid: bool = False
    remote_count_changed: bool = False


@dataclass(frozen=True)
class RemoteSessionDeactivation:
    session_id: uuid.UUID
    master_channel_name: str | None


def _now(value: datetime | None = None) -> datetime:
    return value or timezone.now()


def _token_digest(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def _positive_integer_setting(name: str) -> int:
    value = getattr(settings, name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value


def get_remote_session_ttl() -> timedelta:
    return timedelta(seconds=_positive_integer_setting("REMOTE_SESSION_TTL_SECONDS"))


def get_remote_connection_heartbeat() -> timedelta:
    return timedelta(
        seconds=_positive_integer_setting("REMOTE_CONNECTION_HEARTBEAT_SECONDS")
    )


def get_remote_connection_stale_after() -> timedelta:
    heartbeat = get_remote_connection_heartbeat()
    stale_after = timedelta(
        seconds=_positive_integer_setting("REMOTE_CONNECTION_STALE_SECONDS")
    )
    if stale_after <= heartbeat:
        raise ImproperlyConfigured(
            "REMOTE_CONNECTION_STALE_SECONDS must exceed REMOTE_CONNECTION_HEARTBEAT_SECONDS"
        )
    return stale_after


def get_remote_master_command_ack_timeout() -> float:
    timeout = getattr(settings, "REMOTE_MASTER_COMMAND_ACK_SECONDS", 0)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ImproperlyConfigured(
            "REMOTE_MASTER_COMMAND_ACK_SECONDS must be a positive number"
        )
    return float(timeout)


def get_remote_command_cooldown() -> timedelta:
    cooldown_ms = getattr(settings, "REMOTE_COMMAND_COOLDOWN_MS", 0)
    if isinstance(cooldown_ms, bool) or not isinstance(cooldown_ms, int):
        raise ImproperlyConfigured("REMOTE_COMMAND_COOLDOWN_MS must be an integer")
    maximum_transition_ms = max(
        int(item["params"]["duration_ms"]) for item in list_enabled_transitions()
    )
    if cooldown_ms <= maximum_transition_ms:
        raise ImproperlyConfigured(
            "REMOTE_COMMAND_COOLDOWN_MS must exceed the longest enabled transition"
        )
    return timedelta(milliseconds=cooldown_ms)


def _is_valid_access_token(session: AnimationRemoteSession, token: object) -> bool:
    return (
        isinstance(token, str)
        and bool(token)
        and secrets.compare_digest(session.access_token_digest, _token_digest(token))
    )


def _is_valid_master_token(session: AnimationRemoteSession, token: object) -> bool:
    return (
        isinstance(token, str)
        and bool(token)
        and bool(session.master_token_digest)
        and secrets.compare_digest(session.master_token_digest, _token_digest(token))
    )


def _sync_live_connections(session: AnimationRemoteSession, now: datetime) -> bool:
    stale_before = now - get_remote_connection_stale_after()
    AnimationRemoteConnection.objects.filter(
        session=session, last_seen_at__lt=stale_before
    ).delete()
    master_is_live = (
        session.master_connection_id is not None
        and AnimationRemoteConnection.objects.filter(
            session=session,
            connection_id=session.master_connection_id,
            role=AnimationRemoteConnectionRole.MASTER,
        ).exists()
    )
    master_lost = (
        bool(session.master_channel_name or session.master_connection_id)
        and not master_is_live
    )
    update_fields: list[str] = []
    if not master_is_live and (
        session.master_channel_name is not None
        or session.master_connection_id is not None
    ):
        session.master_channel_name = None
        session.master_connection_id = None
        session.master_connected_at = None
        update_fields.extend(
            ["master_channel_name", "master_connection_id", "master_connected_at"]
        )
    remote_count = AnimationRemoteConnection.objects.filter(
        session=session, role=AnimationRemoteConnectionRole.REMOTE
    ).count()
    if session.remote_connection_count != remote_count:
        session.remote_connection_count = remote_count
        update_fields.append("remote_connection_count")
    if update_fields:
        session.save(update_fields=update_fields)
    return master_lost


def create_remote_session(
    animation: Animation, *, now: datetime | None = None
) -> CreatedRemoteSession:
    created_at = _now(now)
    access_token = secrets.token_urlsafe(32)
    master_token = secrets.token_urlsafe(32)
    session = AnimationRemoteSession.objects.create(
        animation=animation,
        access_token_digest=_token_digest(access_token),
        master_token_digest=_token_digest(master_token),
        expires_at=created_at + get_remote_session_ttl(),
    )
    return CreatedRemoteSession(
        session=session,
        access_token=access_token,
        master_token=master_token,
    )


def _authenticated_session(
    session_id: object, access_token: str, *, now: datetime
) -> AnimationRemoteSession | None:
    session = AnimationRemoteSession.objects.filter(session_id=session_id).first()
    if session is None or not _is_valid_access_token(session, access_token):
        return None
    if not session.active or session.expires_at <= now:
        return None
    return session


def authenticate_remote_session(
    session_id: object, access_token: str, *, now: datetime | None = None
) -> AnimationRemoteSession | None:
    return _authenticated_session(session_id, access_token, now=_now(now))


def authenticate_master_session(
    session_id: object, master_token: str, *, now: datetime | None = None
) -> AnimationRemoteSession | None:
    session = AnimationRemoteSession.objects.filter(session_id=session_id).first()
    if session is None or not _is_valid_master_token(session, master_token):
        return None
    if not session.active or session.expires_at <= _now(now):
        return None
    return session


def deactivate_remote_session(
    session_id: object,
    master_token: str,
    *,
    now: datetime | None = None,
) -> RemoteSessionDeactivation | None:
    deactivated_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None or not _is_valid_master_token(session, master_token):
            return None
        if not session.active:
            return RemoteSessionDeactivation(
                session_id=session.session_id, master_channel_name=None
            )
        if session.expires_at <= deactivated_at:
            return None
        master_channel_name = session.master_channel_name
        AnimationRemoteConnection.objects.filter(session=session).delete()
        session.active = False
        session.master_connected_at = None
        session.master_channel_name = None
        session.master_connection_id = None
        session.remote_connection_count = 0
        session.save(
            update_fields=[
                "active",
                "master_connected_at",
                "master_channel_name",
                "master_connection_id",
                "remote_connection_count",
            ]
        )
        return RemoteSessionDeactivation(
            session_id=session.session_id,
            master_channel_name=master_channel_name,
        )


def register_remote_connection(
    session_id: object,
    access_token: str,
    *,
    connection_id: uuid.UUID | None = None,
    channel_name: str | None = None,
    now: datetime | None = None,
) -> RemoteConnectionUpdate | None:
    connected_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if (
            session is None
            or not _is_valid_access_token(session, access_token)
            or not session.active
            or session.expires_at <= connected_at
        ):
            return None
        master_lost = _sync_live_connections(session, connected_at)
        remote_connection_id = connection_id or uuid.uuid4()
        AnimationRemoteConnection.objects.create(
            connection_id=remote_connection_id,
            session=session,
            role=AnimationRemoteConnectionRole.REMOTE,
            channel_name=channel_name,
            last_seen_at=connected_at,
        )
        _sync_live_connections(session, connected_at)
        return RemoteConnectionUpdate(
            session=session,
            master_channel_name=session.master_channel_name,
            connection_id=remote_connection_id,
            master_lost=master_lost,
        )


def unregister_remote_connection(
    session_id: object,
    connection_id: uuid.UUID | None = None,
    *,
    now: datetime | None = None,
) -> RemoteConnectionUpdate | None:
    disconnected_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return None
        master_lost = _sync_live_connections(session, disconnected_at)
        connections = AnimationRemoteConnection.objects.filter(
            session=session, role=AnimationRemoteConnectionRole.REMOTE
        )
        if connection_id is not None:
            connections.filter(connection_id=connection_id).delete()
        else:
            first = connections.order_by("created_at").first()
            if first is not None:
                first.delete()
        _sync_live_connections(session, disconnected_at)
        return RemoteConnectionUpdate(
            session=session,
            master_channel_name=session.master_channel_name,
            master_lost=master_lost,
        )


def register_master_connection(
    session_id: object,
    master_token: str,
    channel_name: str,
    *,
    now: datetime | None = None,
) -> MasterConnectionRegistration | None:
    connected_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if (
            session is None
            or not _is_valid_master_token(session, master_token)
            or not session.active
            or session.expires_at <= connected_at
        ):
            return None
        _sync_live_connections(session, connected_at)
        replaced_channel_name = session.master_channel_name
        AnimationRemoteConnection.objects.filter(
            session=session, role=AnimationRemoteConnectionRole.MASTER
        ).delete()
        connection_id = uuid.uuid4()
        AnimationRemoteConnection.objects.create(
            connection_id=connection_id,
            session=session,
            role=AnimationRemoteConnectionRole.MASTER,
            channel_name=channel_name,
            last_seen_at=connected_at,
        )
        session.master_connected_at = connected_at
        session.master_channel_name = channel_name
        session.master_connection_id = connection_id
        session.save(
            update_fields=[
                "master_connected_at",
                "master_channel_name",
                "master_connection_id",
            ]
        )
        return MasterConnectionRegistration(
            session=session,
            connection_id=connection_id,
            replaced_channel_name=replaced_channel_name,
            next_state_revision=max(0, session.latest_state_revision + 1),
        )


def unregister_master_connection(
    session_id: object, connection_id: object, *, now: datetime | None = None
) -> RemoteConnectionUpdate | None:
    disconnected_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return None
        AnimationRemoteConnection.objects.filter(
            session=session,
            connection_id=connection_id,
            role=AnimationRemoteConnectionRole.MASTER,
        ).delete()
        master_lost = session.master_connection_id == connection_id
        if master_lost:
            session.master_channel_name = None
            session.master_connection_id = None
            session.master_connected_at = None
            session.save(
                update_fields=[
                    "master_channel_name",
                    "master_connection_id",
                    "master_connected_at",
                ]
            )
        _sync_live_connections(session, disconnected_at)
        return RemoteConnectionUpdate(
            session=session,
            master_channel_name=session.master_channel_name,
            master_lost=master_lost,
        )


def touch_remote_connection(
    session_id: object,
    connection_id: uuid.UUID,
    role: str,
    *,
    now: datetime | None = None,
) -> ConnectionHeartbeatResult:
    seen_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return ConnectionHeartbeatResult(session=None, alive=False)
        previous_remote_count = session.remote_connection_count
        master_lost = _sync_live_connections(session, seen_at)
        remote_count_changed = session.remote_connection_count != previous_remote_count
        if not session.active or session.expires_at <= seen_at:
            return ConnectionHeartbeatResult(
                session=session,
                alive=False,
                master_lost=master_lost,
                session_invalid=True,
                remote_count_changed=remote_count_changed,
            )
        connection = AnimationRemoteConnection.objects.filter(
            session=session, connection_id=connection_id, role=role
        ).first()
        if connection is None:
            replaced = (
                role == AnimationRemoteConnectionRole.MASTER
                and session.master_connection_id is not None
                and session.master_connection_id != connection_id
            )
            return ConnectionHeartbeatResult(
                session=session,
                alive=False,
                master_lost=master_lost,
                replaced=replaced,
                lease_expired=not replaced,
                remote_count_changed=remote_count_changed,
            )
        connection.last_seen_at = seen_at
        connection.save(update_fields=["last_seen_at"])
        return ConnectionHeartbeatResult(
            session=session,
            alive=True,
            master_lost=master_lost,
            remote_count_changed=remote_count_changed,
        )


def inspect_remote_connection(
    session_id: object,
    connection_id: uuid.UUID,
    role: str,
    *,
    now: datetime | None = None,
) -> ConnectionHeartbeatResult:
    """Check a lease without extending it.

    Consumers use this from their watchdog. Only an explicit client heartbeat
    is allowed to renew a lease.
    """

    inspected_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return ConnectionHeartbeatResult(session=None, alive=False)
        previous_remote_count = session.remote_connection_count
        master_lost = _sync_live_connections(session, inspected_at)
        remote_count_changed = session.remote_connection_count != previous_remote_count
        if not session.active or session.expires_at <= inspected_at:
            return ConnectionHeartbeatResult(
                session=session,
                alive=False,
                master_lost=master_lost,
                session_invalid=True,
                remote_count_changed=remote_count_changed,
            )
        connection = AnimationRemoteConnection.objects.filter(
            session=session, connection_id=connection_id, role=role
        ).first()
        if connection is None:
            replaced = (
                role == AnimationRemoteConnectionRole.MASTER
                and session.master_connection_id is not None
                and session.master_connection_id != connection_id
            )
            return ConnectionHeartbeatResult(
                session=session,
                alive=False,
                master_lost=master_lost,
                replaced=replaced,
                lease_expired=not replaced,
                remote_count_changed=remote_count_changed,
            )
        return ConnectionHeartbeatResult(
            session=session,
            alive=True,
            master_lost=master_lost,
            remote_count_changed=remote_count_changed,
        )


def accept_remote_command(
    session_id: object,
    access_token: str,
    message: object,
    *,
    now: datetime | None = None,
) -> RemoteCommandDecision:
    accepted_at = _now(now)
    try:
        RemoteCommandMessage.from_payload(message)
    except RemoteProtocolError:
        return RemoteCommandDecision(
            accepted=False,
            reason=RemoteRejectReason.INVALID_COMMAND,
            session=None,
        )

    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None or not _is_valid_access_token(session, access_token):
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        master_lost = _sync_live_connections(session, accepted_at)
        if not session.active or session.expires_at <= accepted_at:
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=session,
                master_lost=master_lost,
            )
        if not session.master_channel_name or session.master_connection_id is None:
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.MASTER_UNAVAILABLE,
                session=session,
                master_lost=master_lost,
            )
        cooldown = get_remote_command_cooldown()
        if (
            session.last_remote_command_at is not None
            and accepted_at - session.last_remote_command_at < cooldown
        ):
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.COOLDOWN,
                session=session,
                master_lost=master_lost,
            )
        session.last_remote_command_at = accepted_at
        session.save(update_fields=["last_remote_command_at"])
        return RemoteCommandDecision(
            accepted=True,
            reason=None,
            session=session,
            master_connection_id=session.master_connection_id,
            accepted_at=accepted_at,
        )


def cancel_remote_command_reservation(
    session_id: object,
    accepted_at: datetime,
    master_connection_id: uuid.UUID | None,
    *,
    invalidate_master: bool,
    now: datetime | None = None,
) -> RemoteConnectionUpdate | None:
    cancelled_at = _now(now)
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return None
        if session.last_remote_command_at == accepted_at:
            session.last_remote_command_at = None
            session.save(update_fields=["last_remote_command_at"])
        master_lost = _sync_live_connections(session, cancelled_at)
        if invalidate_master and session.master_connection_id == master_connection_id:
            AnimationRemoteConnection.objects.filter(
                session=session,
                connection_id=master_connection_id,
                role=AnimationRemoteConnectionRole.MASTER,
            ).delete()
            session.master_channel_name = None
            session.master_connection_id = None
            session.master_connected_at = None
            session.save(
                update_fields=[
                    "master_channel_name",
                    "master_connection_id",
                    "master_connected_at",
                ]
            )
            master_lost = True
        return RemoteConnectionUpdate(
            session=session,
            master_channel_name=session.master_channel_name,
            master_lost=master_lost,
        )


def store_remote_state(
    session_id: object,
    master_token: str,
    message: object,
    *,
    connection_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> RemoteStateStoreResult:
    stored_at = _now(now)
    try:
        state_message = RemoteStateMessage.from_payload(message)
    except RemoteProtocolError:
        return RemoteStateStoreResult(
            stored=False,
            reason=RemoteRejectReason.INVALID_TARGET,
            session=None,
        )

    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None or not _is_valid_master_token(session, master_token):
            return RemoteStateStoreResult(
                stored=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        _sync_live_connections(session, stored_at)
        if (
            not session.active
            or session.expires_at <= stored_at
            or (
                connection_id is not None
                and session.master_connection_id != connection_id
            )
        ):
            return RemoteStateStoreResult(
                stored=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=session,
            )
        if state_message.revision <= session.latest_state_revision:
            return RemoteStateStoreResult(stored=False, reason=None, session=session)
        session.latest_state = state_message.state
        session.latest_state_revision = state_message.revision
        session.save(update_fields=["latest_state", "latest_state_revision"])
        return RemoteStateStoreResult(stored=True, reason=None, session=session)
