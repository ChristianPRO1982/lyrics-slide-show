from __future__ import annotations

import re


GENRE_GROUP_DISPLAY_PREFIX_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*$")


def normalize_genre_group_display_name(value: str | None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    match = GENRE_GROUP_DISPLAY_PREFIX_PATTERN.match(raw_value)
    if not match:
        return raw_value
    return match.group(2).strip()


def build_genre_display_label(group_name: str | None, genre_name: str | None) -> str:
    clean_genre_name = str(genre_name or "").strip()
    clean_group_name = normalize_genre_group_display_name(group_name)
    if clean_group_name:
        return f"{clean_group_name} / {clean_genre_name}"
    return clean_genre_name
