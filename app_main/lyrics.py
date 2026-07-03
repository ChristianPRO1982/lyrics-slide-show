from __future__ import annotations

import base64
import io
from typing import Iterable

try:
    import qrcode
except Exception:  # pragma: no cover - optional dependency in dev envs
    qrcode = None

from django.core.exceptions import DisallowedHost
from django.urls import reverse

from app_song.models import Song, Verse
from app_song.rendering import (
    ChorusRenderMode,
    SongRenderSettings,
    build_song_full_title,
    render_song_blocks,
)

LYRICS_BLOCK_STYLE_CHORUS = 1
LYRICS_BLOCK_STYLE_VERSE = 2
LYRICS_BLOCK_STYLE_CHORUS_LIKE = 3


def build_qr_png_base64(value: str) -> str:
    if not value or qrcode is None:
        return ""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _block_style(kind: str) -> int:
    if kind == "chorus":
        return LYRICS_BLOCK_STYLE_CHORUS
    if kind == "chorus_like":
        return LYRICS_BLOCK_STYLE_CHORUS_LIKE
    return LYRICS_BLOCK_STYLE_VERSE


def build_lyrics_song_entry(
    song: Song,
    *,
    anchor_id: str,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings,
    verses: Iterable[Verse] | None = None,
    song_url: str | None = None,
) -> dict[str, object]:
    blocks = render_song_blocks(song, mode, settings=settings, verses=verses)
    return {
        "song_id": int(song.song_id),
        "song_title": build_song_full_title(song),
        "song_url": song_url or reverse("song", args=[song.song_id]),
        "anchor_id": anchor_id,
        "blocks": [
            {
                "prefix": str(block.label or ""),
                "style": _block_style(str(block.kind)),
                "text": str(block.text or ""),
            }
            for block in blocks
        ],
    }


def build_lyrics_page_context(
    *,
    page_title: str,
    share_url: str,
    songs: list[dict[str, object]],
    animation_title: str | None = None,
    drawer_title: str = "",
    drawer_link_url: str = "",
    drawer_link_label: str = "",
    is_animation_view: bool = False,
) -> dict[str, object]:
    return {
        "page_title": page_title,
        "share_url": share_url,
        "qr_code_png_base64": build_qr_png_base64(share_url),
        "songs": songs,
        "has_multiple_songs": len(songs) > 1,
        "animation_title": animation_title or "",
        "drawer_title": drawer_title,
        "drawer_link_url": drawer_link_url,
        "drawer_link_label": drawer_link_label,
        "is_animation_view": is_animation_view,
    }


def build_request_share_url(request) -> str:
    try:
        return request.build_absolute_uri()
    except DisallowedHost:
        return request.get_full_path()
