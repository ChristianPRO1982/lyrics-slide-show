from __future__ import annotations

from typing import Iterable

from app_song.models import Song, Verse
from app_song.rendering import SongRenderSettings, SongTextArtifacts, build_song_text_artifacts


def get_song_text_artifacts(
    song: Song,
    *,
    language_code: str | None = None,
    settings: SongRenderSettings | None = None,
    verses: Iterable[Verse] | None = None,
) -> SongTextArtifacts:
    render_settings = settings or SongRenderSettings.from_language(language_code)
    return build_song_text_artifacts(song, settings=render_settings, verses=verses)

