from __future__ import annotations

import json
import re
from typing import Any

from django.utils.translation import gettext as _

from app_animation.models import Animation, AnimationSong, AnimationVerseOverride
from app_animation.services.playlist import POSITION_START, POSITION_STEP
from app_song.models import Verse

from ..font_catalog import is_allowed_font_family


HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{6})$")


def _normalize_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_optional_hex_color(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not HEX_COLOR_PATTERN.match(text):
        return None
    return text.upper()


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _excerpt(value: str | None, max_length: int = 45) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}…"


def _full_text(value: str | None) -> str:
    return str(value or "").strip()


def _verse_label(verse: Verse) -> str:
    if verse.chorus:
        return _("Refrain")
    if verse.chorus_like:
        return (str(verse.prefix or "").strip() or _("Section spéciale"))
    num = int(verse.num_verse or 0)
    if num > 0:
        return _("Couplet %(number)s") % {"number": num}
    return _("Couplet")


def _effective_song_font_size(animation: Animation, animation_song: AnimationSong) -> int:
    if animation_song.font_size_override is not None:
        return int(animation_song.font_size_override)
    return int(animation.font_size)


def _compute_song_font_delta(animation: Animation, animation_song: AnimationSong) -> int:
    if animation_song.font_size_override is None:
        return 0
    return int(animation_song.font_size_override) - int(animation.font_size)


def _compute_verse_font_delta(animation: Animation, animation_song: AnimationSong, override: AnimationVerseOverride) -> int:
    if override.font_size_override is None:
        return 0
    base_size = _effective_song_font_size(animation, animation_song)
    return int(override.font_size_override) - base_size


def build_main_song_cards(animation: Animation, animation_songs: list[AnimationSong]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for animation_song in animation_songs:
        overrides_by_verse_id = {
            int(override.source_verse_id): override
            for override in animation_song.verse_overrides.all()
        }
        verses: list[dict[str, Any]] = []
        visible_verse_ids: list[int] = []
        verse_styles: dict[str, dict[str, Any]] = {}

        for verse in animation_song.song.verses.all():
            override = overrides_by_verse_id.get(int(verse.verse_id))
            is_selectable = not bool(verse.chorus)
            is_visible = bool(override.is_visible) if override is not None else True
            if verse.chorus:
                is_visible = True
            if is_visible:
                visible_verse_ids.append(int(verse.verse_id))

            style_data = {
                "font_family_override": (str(override.font_family_override).strip() if override and override.font_family_override else ""),
                "font_size_delta": (_compute_verse_font_delta(animation, animation_song, override) if override else 0),
                "text_color_override": (str(override.text_color_override).strip().upper() if override and override.text_color_override else ""),
                "bg_color_override": (str(override.bg_color_override).strip().upper() if override and override.bg_color_override else ""),
            }
            if any(
                [
                    style_data["font_family_override"],
                    style_data["font_size_delta"] != 0,
                    style_data["text_color_override"],
                    style_data["bg_color_override"],
                ]
            ):
                verse_styles[str(verse.verse_id)] = style_data

            if is_selectable:
                verses.append(
                    {
                        "verse_id": int(verse.verse_id),
                        "label": _verse_label(verse),
                        "excerpt": _excerpt(verse.text),
                        "full_text": _full_text(verse.text),
                        "is_visible": is_visible,
                        "font_family_override": style_data["font_family_override"],
                        "font_size_delta": style_data["font_size_delta"],
                        "text_color_override": style_data["text_color_override"],
                        "bg_color_override": style_data["bg_color_override"],
                    }
                )

        song_style = {
            "font_family_override": str(animation_song.font_family_override or "").strip(),
            "font_size_delta": _compute_song_font_delta(animation, animation_song),
            "text_color_override": str(animation_song.text_color_override or "").strip().upper(),
            "bg_color_override": str(animation_song.bg_color_override or "").strip().upper(),
        }
        cards.append(
            {
                "animation_song_id": int(animation_song.animation_song_id),
                "song_id": int(animation_song.song_id),
                "song_title": animation_song.song.display_title,
                "song_style": song_style,
                "visible_verse_ids": visible_verse_ids,
                "verse_styles": verse_styles,
                "verses": verses,
            }
        )
    return cards


def build_songs_payload_initial(main_song_cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": [
            {
                "animation_song_id": int(card["animation_song_id"]),
                "song_id": int(card["song_id"]),
                "visible_verse_ids": [int(verse_id) for verse_id in card["visible_verse_ids"]],
                "song_style": {
                    "font_family_override": str(card["song_style"]["font_family_override"] or ""),
                    "font_size_delta": int(card["song_style"]["font_size_delta"] or 0),
                    "text_color_override": str(card["song_style"]["text_color_override"] or ""),
                    "bg_color_override": str(card["song_style"]["bg_color_override"] or ""),
                },
                "verse_styles": card["verse_styles"],
            }
            for card in main_song_cards
        ]
    }


def serialize_songs_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_songs_payload(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {"items": []}
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return {"items": []}
    if not isinstance(parsed, dict):
        return {"items": []}
    items = parsed.get("items")
    if not isinstance(items, list):
        return {"items": []}
    return {"items": items}


def _set_song_style_overrides(animation: Animation, animation_song: AnimationSong, song_style: dict[str, Any]) -> None:
    font_family_override = _normalize_optional_text(song_style.get("font_family_override"))
    if font_family_override and not is_allowed_font_family(font_family_override):
        font_family_override = None

    font_size_delta = _parse_int(song_style.get("font_size_delta"), default=0)
    if font_size_delta == 0:
        font_size_override = None
    else:
        font_size_override = max(10, int(animation.font_size) + font_size_delta)

    text_color_override = _normalize_optional_hex_color(song_style.get("text_color_override"))
    bg_color_override = _normalize_optional_hex_color(song_style.get("bg_color_override"))

    animation_song.font_family_override = font_family_override
    animation_song.font_size_override = font_size_override
    animation_song.text_color_override = text_color_override
    animation_song.bg_color_override = bg_color_override
    animation_song.save(
        update_fields=[
            "font_family_override",
            "font_size_override",
            "text_color_override",
            "bg_color_override",
        ]
    )


def _set_verse_override(
    *,
    animation_song: AnimationSong,
    verse_id: int,
    is_visible: bool,
    verse_style: dict[str, Any],
    base_font_size: int,
    existing_override: AnimationVerseOverride | None,
) -> None:
    font_family_override = _normalize_optional_text(verse_style.get("font_family_override"))
    if font_family_override and not is_allowed_font_family(font_family_override):
        font_family_override = None
    font_size_delta = _parse_int(verse_style.get("font_size_delta"), default=0)
    text_color_override = _normalize_optional_hex_color(verse_style.get("text_color_override"))
    bg_color_override = _normalize_optional_hex_color(verse_style.get("bg_color_override"))

    font_size_override = None
    if font_size_delta != 0:
        font_size_override = max(10, int(base_font_size) + font_size_delta)

    has_style = any(
        [
            bool(font_family_override),
            font_size_override is not None,
            bool(text_color_override),
            bool(bg_color_override),
        ]
    )

    if is_visible and not has_style:
        if existing_override is not None:
            existing_override.delete()
        return

    target = existing_override
    if target is None:
        target = AnimationVerseOverride(animation_song=animation_song, source_verse_id=verse_id)
    target.is_visible = bool(is_visible)
    target.font_family_override = font_family_override
    target.font_size_override = font_size_override
    target.text_color_override = text_color_override
    target.bg_color_override = bg_color_override
    target.save()


def apply_songs_payload(animation: Animation, payload: dict[str, Any]) -> None:
    items = payload.get("items")
    if not isinstance(items, list):
        return

    current_items = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses", "verse_overrides")
        .order_by("position", "animation_song_id")
    )
    by_animation_song_id = {
        int(item.animation_song_id): item
        for item in current_items
    }

    # Keep positions normalized in case the reorder payload removed intermediate rows.
    for index, row in enumerate(current_items):
        expected = POSITION_START + index * POSITION_STEP
        if int(row.position) != expected:
            row.position = expected
            row.save(update_fields=["position"])

    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        animation_song_id = _parse_int(raw_item.get("animation_song_id"), default=0)
        if animation_song_id <= 0:
            continue
        animation_song = by_animation_song_id.get(animation_song_id)
        if animation_song is None:
            continue

        song_style_raw = raw_item.get("song_style")
        song_style = song_style_raw if isinstance(song_style_raw, dict) else {}
        _set_song_style_overrides(animation, animation_song, song_style)

        verse_style_raw = raw_item.get("verse_styles")
        verse_style_map = verse_style_raw if isinstance(verse_style_raw, dict) else {}
        visible_raw = raw_item.get("visible_verse_ids")
        if not isinstance(visible_raw, list):
            continue
        visible_verse_ids: set[int] = set()
        for value in visible_raw:
            parsed_id = _parse_int(value, default=0)
            if parsed_id > 0:
                visible_verse_ids.add(parsed_id)

        all_song_verses = list(animation_song.song.verses.all())
        valid_verse_ids = {int(verse.verse_id) for verse in all_song_verses}
        chorus_verse_ids = {int(verse.verse_id) for verse in all_song_verses if verse.chorus}
        visible_verse_ids = {value for value in visible_verse_ids if value in valid_verse_ids}
        existing_overrides = {
            int(override.source_verse_id): override
            for override in animation_song.verse_overrides.all()
        }
        base_song_font_size = _effective_song_font_size(animation, animation_song)

        for verse_id in sorted(valid_verse_ids):
            if verse_id in chorus_verse_ids:
                # Refrains are always visible. Keep existing style overrides,
                # only neutralize legacy hidden flags.
                existing_override = existing_overrides.get(verse_id)
                if existing_override is not None and not existing_override.is_visible:
                    existing_override.is_visible = True
                    existing_override.save(update_fields=["is_visible"])
                continue
            raw_style = verse_style_map.get(str(verse_id))
            verse_style = raw_style if isinstance(raw_style, dict) else {}
            _set_verse_override(
                animation_song=animation_song,
                verse_id=verse_id,
                is_visible=(verse_id in visible_verse_ids),
                verse_style=verse_style,
                base_font_size=base_song_font_size,
                existing_override=existing_overrides.get(verse_id),
            )
