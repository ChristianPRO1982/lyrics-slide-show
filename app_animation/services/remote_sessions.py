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

from app_animation.models import Animation, AnimationRemoteSession
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


def _now(value: datetime | None = None) -> datetime:
    return value or timezone.now()


def _token_digest(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def get_remote_session_ttl() -> timedelta:
    ttl_seconds = getattr(settings, "REMOTE_SESSION_TTL_SECONDS", 0)
    if (
        isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, int)
        or ttl_seconds <= 0
    ):
        raise ImproperlyConfigured(
            "REMOTE_SESSION_TTL_SECONDS must be a positive integer"
        )
    return timedelta(seconds=ttl_seconds)


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
    if session is None or not isinstance(access_token, str) or not access_token:
        return None
    if not secrets.compare_digest(
        session.access_token_digest, _token_digest(access_token)
    ):
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
    if session is None or not isinstance(master_token, str) or not master_token:
        return None
    if not session.master_token_digest or not secrets.compare_digest(
        session.master_token_digest, _token_digest(master_token)
    ):
        return None
    if not session.active or session.expires_at <= _now(now):
        return None
    return session


def deactivate_remote_session(
    session_id: object, *, now: datetime | None = None
) -> AnimationRemoteSession | None:
    del now
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None:
            return None
        if session.active:
            session.active = False
            session.save(update_fields=["active"])
        return session


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
        if session is None or not isinstance(master_token, str) or not master_token:
            return None
        if not session.master_token_digest or not secrets.compare_digest(
            session.master_token_digest, _token_digest(master_token)
        ):
            return None
        if not session.active or session.expires_at <= connected_at:
            return None
        replaced_channel_name = session.master_channel_name
        connection_id = uuid.uuid4()
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
        )


def unregister_master_connection(
    session_id: object, connection_id: object
) -> AnimationRemoteSession | None:
    with transaction.atomic():
        session = (
            AnimationRemoteSession.objects.select_for_update()
            .filter(session_id=session_id)
            .first()
        )
        if session is None or session.master_connection_id != connection_id:
            return session
        session.master_channel_name = None
        session.master_connection_id = None
        session.save(update_fields=["master_channel_name", "master_connection_id"])
        return session


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
        if session is None or not isinstance(access_token, str) or not access_token:
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        if not secrets.compare_digest(
            session.access_token_digest, _token_digest(access_token)
        ):
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        if not session.active or session.expires_at <= accepted_at:
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=session,
            )
        if not session.master_channel_name:
            return RemoteCommandDecision(
                accepted=False,
                reason=RemoteRejectReason.MASTER_UNAVAILABLE,
                session=session,
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
            )
        session.last_remote_command_at = accepted_at
        session.save(update_fields=["last_remote_command_at"])
        return RemoteCommandDecision(accepted=True, reason=None, session=session)


def store_remote_state(
    session_id: object,
    master_token: str,
    message: object,
    *,
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
        if session is None or not isinstance(master_token, str) or not master_token:
            return RemoteStateStoreResult(
                stored=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        if not session.master_token_digest or not secrets.compare_digest(
            session.master_token_digest, _token_digest(master_token)
        ):
            return RemoteStateStoreResult(
                stored=False,
                reason=RemoteRejectReason.SESSION_INACTIVE,
                session=None,
            )
        if not session.active or session.expires_at <= stored_at:
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
