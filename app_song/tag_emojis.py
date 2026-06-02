from __future__ import annotations

import random


MUSIC_EMOJIS = [
    "🎶",
    "🎵",
    "🎼",
    "𝄞",
    "𝄢",
    "♩",
    "♪",
    "♫",
    "♬",
    "𝄐",
    "𝄑",
    "𝄆",
    "𝄇",
    "𝄋",
    "𝅘𝅥",
    "𝅘𝅥𝅮",
    "𝅘𝅥𝅯",
]

BAND_EMOJIS = [
    "🎸",
    "🥁",
    "🎷",
    "🎺",
    "🎻",
    "🎹",
]

ARTIST_EMOJIS = [
    "🎤",
    "🎙️",
    "🧑‍🎤",
]


def _pick_emoji(emojis: list[str]) -> str:
    if not emojis:
        return ""
    return random.choice(emojis)


def with_music_emoji(name: str) -> str:
    return f"{_pick_emoji(MUSIC_EMOJIS)} {name}".strip()


def with_band_emoji(name: str) -> str:
    return f"{_pick_emoji(BAND_EMOJIS)} {name}".strip()


def with_artist_emoji(name: str) -> str:
    return f"{_pick_emoji(ARTIST_EMOJIS)} {name}".strip()
