from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

TRANSITION_DIRECT = "direct"
TRANSITION_FADE = "fade"
TRANSITION_WIPE = "wipe"

_MANIFEST_PATH = Path(__file__).with_name("transitions.json")

_LABELS = {
    "transition_direct": _("transition_direct"),
    "transition_fade": _("transition_fade"),
    "transition_wipe": _("transition_wipe"),
}


def _fail(message: str) -> None:
    raise ImproperlyConfigured(f"Invalid animation transitions manifest: {message}")


def _load_raw_manifest() -> dict[str, Any]:
    try:
        with _MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
            payload = json.load(manifest_file)
    except OSError as exc:
        _fail(f"cannot read {_MANIFEST_PATH}: {exc}")
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON in {_MANIFEST_PATH}: {exc}")
    if not isinstance(payload, dict):
        _fail("root must be an object")
    return payload


def _validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    default_id = payload.get("default")
    if not isinstance(default_id, str) or not default_id.strip():
        _fail("'default' must be a non-empty string")
    default_id = default_id.strip()

    transitions = payload.get("transitions")
    if not isinstance(transitions, list):
        _fail("'transitions' must be a list")

    seen_ids: set[str] = set()
    normalized_transitions: list[dict[str, Any]] = []
    for index, item in enumerate(transitions):
        if not isinstance(item, dict):
            _fail(f"transition #{index + 1} must be an object")

        transition_id = item.get("id")
        if not isinstance(transition_id, str) or not transition_id.strip():
            _fail(f"transition #{index + 1} has no valid id")
        transition_id = transition_id.strip()
        if transition_id in seen_ids:
            _fail(f"duplicate transition id '{transition_id}'")
        seen_ids.add(transition_id)

        label_key = item.get("label_key")
        if not isinstance(label_key, str) or label_key not in _LABELS:
            _fail(f"transition '{transition_id}' has no known label_key")

        enabled = item.get("enabled")
        if not isinstance(enabled, bool):
            _fail(f"transition '{transition_id}' has invalid enabled flag")

        order = item.get("order")
        if not isinstance(order, int):
            _fail(f"transition '{transition_id}' has invalid order")

        params = item.get("params")
        if not isinstance(params, dict):
            _fail(f"transition '{transition_id}' has invalid params")

        duration_ms = params.get("duration_ms")
        if not isinstance(duration_ms, int) or duration_ms < 0:
            _fail(f"transition '{transition_id}' has invalid duration_ms")

        if transition_id == TRANSITION_DIRECT and duration_ms != 0:
            _fail("'direct' duration_ms must be 0")
        if transition_id == TRANSITION_WIPE:
            direction = params.get("direction")
            if direction != "left_to_right":
                _fail("'wipe' direction must be left_to_right")

        normalized_transitions.append(
            {
                "id": transition_id,
                "label_key": label_key,
                "enabled": enabled,
                "order": order,
                "params": dict(params),
            }
        )

    by_id = {item["id"]: item for item in normalized_transitions}
    if default_id not in by_id:
        _fail("'default' must reference an existing transition")
    if not by_id[default_id]["enabled"]:
        _fail("'default' transition must be enabled")
    if TRANSITION_DIRECT not in by_id:
        _fail("'direct' transition is required")
    if not by_id[TRANSITION_DIRECT]["enabled"]:
        _fail("'direct' transition must be enabled")

    return {
        "default": default_id,
        "transitions": sorted(
            normalized_transitions,
            key=lambda item: (item["order"], item["id"]),
        ),
    }


@lru_cache(maxsize=1)
def get_transition_manifest() -> dict[str, Any]:
    return _validate_manifest(_load_raw_manifest())


def get_default_transition_id() -> str:
    return str(get_transition_manifest()["default"])


def list_transitions() -> tuple[dict[str, Any], ...]:
    return tuple(deepcopy(item) for item in get_transition_manifest()["transitions"])


def list_enabled_transitions() -> tuple[dict[str, Any], ...]:
    return tuple(item for item in list_transitions() if item["enabled"])


def list_enabled_transition_choices() -> tuple[tuple[str, object], ...]:
    return tuple(
        (item["id"], _LABELS[item["label_key"]]) for item in list_enabled_transitions()
    )


def list_enabled_transition_options() -> tuple[dict[str, str], ...]:
    return tuple(
        {"value": item["id"], "label": str(_LABELS[item["label_key"]])}
        for item in list_enabled_transitions()
    )


def list_enabled_transition_runtime_options() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "id": item["id"],
            "label": str(_LABELS[item["label_key"]]),
            "params": deepcopy(item["params"]),
        }
        for item in list_enabled_transitions()
    )


def is_enabled_transition_id(value: str | None) -> bool:
    transition_id = str(value or "").strip()
    return any(item["id"] == transition_id for item in list_enabled_transitions())


def resolve_enabled_transition_id(value: str | None) -> str:
    transition_id = str(value or "").strip()
    if is_enabled_transition_id(transition_id):
        return transition_id
    return get_default_transition_id()


def get_transition_config(value: str | None) -> dict[str, Any]:
    transition_id = str(value or "").strip()
    for item in list_transitions():
        if item["id"] == transition_id:
            return item
    return get_transition_config(get_default_transition_id())
