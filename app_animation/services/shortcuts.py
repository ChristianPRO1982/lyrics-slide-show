from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Final

from django.utils.translation import gettext as _

from app_animation.models import AnimationRemoteShortcut


SHORTCUT_ACTION_ORDER: Final[list[str]] = [
    "black",
    "prev_slide",
    "next_slide",
    "chorus",
    "open_display",
    "prev_song",
    "next_song",
    "toggle_chorus",
    "toggle_scroll",
    "toggle_qr",
    "next_transition",
    "force_direct",
]

SHORTCUT_ACTION_TO_REMOTE_ACTION: Final[dict[str, str]] = {
    "black": "black",
    "prev_slide": "prev-slide",
    "next_slide": "next-slide",
    "chorus": "chorus",
    "open_display": "open-display",
    "prev_song": "prev-song",
    "next_song": "next-song",
    "toggle_chorus": "toggle-chorus",
    "toggle_scroll": "toggle-scroll",
    "toggle_qr": "toggle-qr",
    "next_transition": "next-transition",
    "force_direct": "force-direct",
}

SITE_SHORTCUT_BINDINGS: Final[dict[str, list[str]]] = {
    "black": ["escape", "m"],
    "prev_slide": ["p", "arrowup"],
    "next_slide": ["space", "arrowdown"],
    "chorus": ["r", "c"],
    "open_display": ["o"],
    "prev_song": ["f", "arrowleft"],
    "next_song": ["enter", "n", "arrowright"],
    "toggle_chorus": ["a", "d"],
    "toggle_scroll": ["l"],
    "toggle_qr": ["q"],
    "next_transition": ["t"],
    "force_direct": ["i"],
}

CUSTOMIZABLE_SITE_SHORTCUT_BINDINGS: Final[dict[str, list[str]]] = {
    **{action: list(tokens) for action, tokens in SITE_SHORTCUT_BINDINGS.items()},
    "black": ["m"],
}

NON_CUSTOMIZABLE_EFFECTIVE_KEYS: Final[dict[str, list[str]]] = {
    "black": ["escape"],
}

ALIASES: Final[dict[str, str]] = {
    "entrée": "enter",
    "entree": "enter",
    "return": "enter",
    "space bar": "space",
    "spacebar": "space",
    "espace": "space",
    "tabulation": "tab",
    "↑": "arrowup",
    "⬆️": "arrowup",
    "↓": "arrowdown",
    "⬇️": "arrowdown",
    "←": "arrowleft",
    "⬅️": "arrowleft",
    "→": "arrowright",
    "➡️": "arrowright",
    "suppr": "delete",
    "retour arrière": "backspace",
    "retour arriere": "backspace",
    "back space": "backspace",
    "page up": "pageup",
    "page down": "pagedown",
    "caps lock": "capslock",
}

FORBIDDEN_TOKENS: Final[set[str]] = {"esc", "escape"}
FORBIDDEN_MODIFIER_TOKENS: Final[set[str]] = {
    "control",
    "ctrl",
    "alt",
    "shift",
    "meta",
    "cmd",
    "command",
}
SPECIAL_ALLOWED_TOKENS: Final[set[str]] = {
    "space",
    "enter",
    "tab",
    "arrowup",
    "arrowdown",
    "arrowleft",
    "arrowright",
    "delete",
    "backspace",
    "home",
    "end",
    "pageup",
    "pagedown",
    "insert",
    "capslock",
}


def build_site_shortcut_bindings() -> dict[str, list[str]]:
    return deepcopy(SITE_SHORTCUT_BINDINGS)


def build_customizable_site_shortcut_bindings() -> dict[str, list[str]]:
    return deepcopy(CUSTOMIZABLE_SITE_SHORTCUT_BINDINGS)


def normalize_stored_bindings(raw_value: object) -> dict[str, list[str]]:
    normalized = {action: [] for action in SHORTCUT_ACTION_ORDER}
    if not isinstance(raw_value, dict):
        return normalized
    taken_tokens: set[str] = set()
    for action in SHORTCUT_ACTION_ORDER:
        action_is_missing = action not in raw_value
        values = raw_value.get(action)
        if action_is_missing:
            values = SITE_SHORTCUT_BINDINGS.get(action, [])
        if not isinstance(values, list):
            continue
        seen: set[str] = set()
        tokens: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            token = item.strip().lower()
            if not token or token in seen or token == "escape":
                continue
            if action_is_missing and token in taken_tokens:
                continue
            seen.add(token)
            taken_tokens.add(token)
            tokens.append(token)
        normalized[action] = tokens[:3]
    return normalized


def load_member_shortcut_bindings(member_id: str | None) -> dict[str, list[str]] | None:
    if not member_id:
        return None
    record = AnimationRemoteShortcut.objects.filter(member_id=member_id).first()
    if not record:
        return None
    return normalize_stored_bindings(record.lyrics_slide_show_bindings)


def build_effective_shortcut_bindings(
    member_bindings: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    if member_bindings is None:
        return build_site_shortcut_bindings()

    effective = normalize_stored_bindings(member_bindings)
    for action, forced_tokens in NON_CUSTOMIZABLE_EFFECTIVE_KEYS.items():
        combined = list(forced_tokens)
        combined.extend(
            token for token in effective.get(action, []) if token not in forced_tokens
        )
        effective[action] = combined
    return effective


def build_form_shortcut_bindings(
    member_bindings: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    if member_bindings is None:
        return build_customizable_site_shortcut_bindings()
    return normalize_stored_bindings(member_bindings)


def should_use_site_defaults(form_bindings: dict[str, list[str]]) -> bool:
    return (
        normalize_stored_bindings(form_bindings)
        == build_customizable_site_shortcut_bindings()
    )


def save_member_shortcut_bindings(
    member_id: str,
    form_bindings: dict[str, list[str]],
    *,
    use_site_defaults: bool | None = None,
) -> bool:
    normalized = normalize_stored_bindings(form_bindings)
    should_delete = (
        should_use_site_defaults(normalized)
        if use_site_defaults is None
        else bool(use_site_defaults)
    )
    if should_delete:
        AnimationRemoteShortcut.objects.filter(member_id=member_id).delete()
        return True
    AnimationRemoteShortcut.objects.update_or_create(
        member_id=member_id,
        defaults={"lyrics_slide_show_bindings": normalized},
    )
    return False


def normalize_input_token(raw_value: str) -> tuple[str | None, str | None]:
    value = str(raw_value or "").strip()
    if not value:
        return None, None
    if "+" in value:
        return None, "combination"

    normalized = ALIASES.get(value.lower(), value.lower())
    if normalized in FORBIDDEN_TOKENS:
        return None, "escape"
    if normalized in FORBIDDEN_MODIFIER_TOKENS:
        return None, "modifier"
    if not normalized:
        return None, None
    if len(normalized) == 1:
        return normalized, None
    if normalized in SPECIAL_ALLOWED_TOKENS:
        return normalized, None
    if normalized.startswith("f") and normalized[1:].isdigit():
        return normalized, None
    if (
        normalized.replace("-", "").replace("_", "").isalnum()
        and " " not in normalized
        and "," not in normalized
    ):
        return normalized, None
    return None, "invalid"


def format_shortcut_token(token: str) -> str:
    normalized = str(token or "").strip().lower()
    labels = {
        "escape": "Esc",
        "space": "Espace",
        "enter": "Enter",
        "tab": "Tab",
        "arrowup": "↑",
        "arrowdown": "↓",
        "arrowleft": "←",
        "arrowright": "→",
        "delete": "Suppr",
        "backspace": "Retour arrière",
        "pageup": "Page Up",
        "pagedown": "Page Down",
        "capslock": "Caps Lock",
    }
    if normalized in labels:
        return labels[normalized]
    if len(normalized) == 1 and normalized.isalpha():
        return normalized.upper()
    if normalized.startswith("f") and normalized[1:].isdigit():
        return normalized.upper()
    return normalized


@dataclass(frozen=True)
class ShortcutValidationResult:
    saved_bindings: dict[str, list[str]]
    field_errors: dict[str, str]
    global_message: str
    used_site_defaults: bool


def validate_shortcut_submission(
    submitted_values: dict[str, str],
    *,
    action_labels: dict[str, str],
) -> ShortcutValidationResult:
    saved_bindings = {action: [] for action in SHORTCUT_ACTION_ORDER}
    field_errors: dict[str, str] = {}
    taken_tokens: dict[str, str] = {}
    summary_parts: list[str] = []

    for action in SHORTCUT_ACTION_ORDER:
        raw_value = str(submitted_values.get(action, "") or "")
        parts = [part for part in raw_value.split(",")]
        accepted: list[str] = []
        seen_in_field: set[str] = set()
        local_errors: list[str] = []

        for part in parts:
            token, error_code = normalize_input_token(part)
            if token is None and error_code is None:
                continue
            if error_code == "combination":
                local_errors.append(_("Aucune combinaison n'est autorisée."))
                continue
            if error_code == "escape":
                local_errors.append(_("Escape n'est pas personnalisable."))
                continue
            if error_code == "modifier":
                local_errors.append(
                    _("Une touche modificatrice seule n'est pas autorisée.")
                )
                continue
            if error_code == "invalid":
                local_errors.append(_("Cette touche n'est pas reconnue."))
                continue
            if token in seen_in_field:
                continue
            if token in taken_tokens:
                local_errors.append(
                    _("La touche %(key)s est déjà utilisée pour %(action)s.")
                    % {
                        "key": format_shortcut_token(token),
                        "action": action_labels.get(
                            taken_tokens[token], taken_tokens[token]
                        ),
                    }
                )
                continue
            if len(accepted) >= 3:
                local_errors.append(_("Maximum 3 touches par action."))
                continue
            seen_in_field.add(token)
            taken_tokens[token] = action
            accepted.append(token)

        saved_bindings[action] = accepted
        if local_errors:
            deduplicated_errors: list[str] = []
            for error in local_errors:
                if error not in deduplicated_errors:
                    deduplicated_errors.append(error)
            field_errors[action] = " ".join(deduplicated_errors)
            summary_parts.append(action_labels.get(action, action))

    used_site_defaults = should_use_site_defaults(saved_bindings)
    if field_errors:
        global_message = _(
            "Certaines touches n'ont pas été enregistrées : %(actions)s."
        ) % {"actions": ", ".join(summary_parts)}
    else:
        global_message = ""

    return ShortcutValidationResult(
        saved_bindings=saved_bindings,
        field_errors=field_errors,
        global_message=global_message,
        used_site_defaults=used_site_defaults,
    )
