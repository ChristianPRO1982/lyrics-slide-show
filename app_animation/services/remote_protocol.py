from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class RemoteMessageType(StrEnum):
    COMMAND = "COMMAND"
    COMMAND_ACCEPTED = "COMMAND_ACCEPTED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    STATE = "STATE"


class RemoteCommand(StrEnum):
    PREVIOUS_SLIDE = "PREVIOUS_SLIDE"
    NEXT_SLIDE = "NEXT_SLIDE"
    PREVIOUS_SONG = "PREVIOUS_SONG"
    NEXT_SONG = "NEXT_SONG"
    TOGGLE_BLACK = "TOGGLE_BLACK"
    GO_TO_SONG = "GO_TO_SONG"
    GO_TO_CHORUS = "GO_TO_CHORUS"
    SET_TRANSITION = "SET_TRANSITION"
    TOGGLE_QR = "TOGGLE_QR"
    GO_TO_PROJECTION_STEP = "GO_TO_PROJECTION_STEP"


class RemoteRejectReason(StrEnum):
    COOLDOWN = "COOLDOWN"
    SESSION_INACTIVE = "SESSION_INACTIVE"
    MASTER_UNAVAILABLE = "MASTER_UNAVAILABLE"
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_TARGET = "INVALID_TARGET"


STATE_FIELDS = frozenset(
    {
        "revision",
        "current_projection_step",
        "next_projection_step",
        "current_song",
        "previous_song",
        "next_song",
        "black_mode",
        "songs",
        "chorus_available",
        "current_transition",
        "available_transitions",
        "qr_mode",
        "master_status",
    }
)


class RemoteProtocolError(ValueError):
    pass


def _as_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RemoteProtocolError(f"{field_name} must be an object")
    return dict(value)


def _as_optional_mapping(value: object, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return _as_mapping(value, field_name)


def _as_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RemoteProtocolError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class RemoteCommandMessage:
    command: RemoteCommand
    target: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: object) -> "RemoteCommandMessage":
        message = _as_mapping(payload, "COMMAND")
        if message.get("type") != RemoteMessageType.COMMAND:
            raise RemoteProtocolError("type must be COMMAND")
        try:
            command = RemoteCommand(str(message.get("command") or ""))
        except ValueError as exc:
            raise RemoteProtocolError("unknown command") from exc
        target = _as_optional_mapping(message.get("target"), "target")
        return cls(command=command, target=target)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": RemoteMessageType.COMMAND,
            "command": self.command,
        }
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(frozen=True)
class RemoteCommandAcceptedMessage:
    command: RemoteCommand

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": RemoteMessageType.COMMAND_ACCEPTED,
            "command": self.command,
        }


@dataclass(frozen=True)
class RemoteCommandRejectedMessage:
    reason: RemoteRejectReason

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": RemoteMessageType.COMMAND_REJECTED,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RemoteStateMessage:
    state: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: object) -> "RemoteStateMessage":
        message = _as_mapping(payload, "STATE")
        if message.get("type") != RemoteMessageType.STATE:
            raise RemoteProtocolError("type must be STATE")
        state = _as_mapping(message.get("state"), "state")
        if set(state) != STATE_FIELDS:
            raise RemoteProtocolError("state has missing or unknown fields")
        _as_non_negative_integer(state["revision"], "state.revision")
        for field_name in (
            "current_projection_step",
            "next_projection_step",
            "current_song",
            "previous_song",
            "next_song",
            "current_transition",
        ):
            _as_optional_mapping(state[field_name], f"state.{field_name}")
        if not isinstance(state["songs"], list):
            raise RemoteProtocolError("state.songs must be a list")
        if not isinstance(state["available_transitions"], list):
            raise RemoteProtocolError("state.available_transitions must be a list")
        for field_name in ("black_mode", "chorus_available", "qr_mode"):
            if not isinstance(state[field_name], bool):
                raise RemoteProtocolError(f"state.{field_name} must be a boolean")
        if not isinstance(state["master_status"], str):
            raise RemoteProtocolError("state.master_status must be a string")
        return cls(state=state)

    @property
    def revision(self) -> int:
        return int(self.state["revision"])

    def to_payload(self) -> dict[str, Any]:
        return {"type": RemoteMessageType.STATE, "state": self.state}
