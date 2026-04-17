from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from django.utils.translation import gettext as _

from app_member.services import get_site_params_for_language

from .models import Song, Verse


class ChorusRenderMode(StrEnum):
    FULL = "full-chorus"
    SINGLE = "single-chorus"


class RenderedSongBlockKind(StrEnum):
    VERSE = "verse"
    CHORUS = "chorus"
    CHORUS_LIKE = "chorus_like"


@dataclass(frozen=True)
class SongRenderSettings:
    chorus_prefix: str
    verse_prefix1: str
    verse_prefix2: str
    chorus_like_default_prefix: str

    @classmethod
    def defaults(cls) -> "SongRenderSettings":
        return cls(
            chorus_prefix=_("Refrain"),
            verse_prefix1=_("Couplet "),
            verse_prefix2="",
            chorus_like_default_prefix=_("Refrain"),
        )

    @classmethod
    def from_language(cls, language_code: str | None) -> "SongRenderSettings":
        defaults = cls.defaults()
        site_params = get_site_params_for_language(language_code)
        if site_params is None:
            return defaults
        return cls(
            chorus_prefix=site_params.chorus_prefix or defaults.chorus_prefix,
            verse_prefix1=site_params.verse_prefix1 or defaults.verse_prefix1,
            verse_prefix2=site_params.verse_prefix2 or defaults.verse_prefix2,
            chorus_like_default_prefix=site_params.chorus_prefix or defaults.chorus_like_default_prefix,
        )

    def verse_label(self, number: int) -> str:
        return f"{self.verse_prefix1}{number}{self.verse_prefix2}".strip()


@dataclass(frozen=True)
class RenderedSongBlock:
    kind: RenderedSongBlockKind
    label: str
    text: str
    source_verse_id: int | None
    display_num: int | None
    is_repeated_chorus: bool = False


def normalize_lyrics_linebreaks(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _get_ordered_verses(song: Song, verses: Iterable[Verse] | None = None) -> list[Verse]:
    if verses is not None:
        return sorted(verses, key=lambda verse: (verse.num, verse.verse_id or 0))
    return list(song.verses.all().order_by("num", "verse_id"))


def _render_chorus_group(
    choruses: list[Verse],
    settings: SongRenderSettings,
    repeated: bool,
) -> list[RenderedSongBlock]:
    blocks = []
    for index, chorus in enumerate(choruses):
        text = normalize_lyrics_linebreaks(chorus.text).strip()
        if not text:
            continue
        blocks.append(
            RenderedSongBlock(
                kind=RenderedSongBlockKind.CHORUS,
                label=settings.chorus_prefix if index == 0 else "",
                text=text,
                source_verse_id=chorus.verse_id,
                display_num=chorus.num_verse,
                is_repeated_chorus=repeated,
            )
        )
    return blocks


def _should_render_chorus_group(mode: ChorusRenderMode, chorus_already_rendered: bool) -> bool:
    return mode == ChorusRenderMode.FULL or not chorus_already_rendered


def render_song_blocks(
    song: Song,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings | None = None,
    verses: Iterable[Verse] | None = None,
) -> list[RenderedSongBlock]:
    render_mode = ChorusRenderMode(mode)
    render_settings = settings or SongRenderSettings.defaults()
    ordered_verses = _get_ordered_verses(song, verses)
    choruses = [verse for verse in ordered_verses if verse.chorus]
    blocks: list[RenderedSongBlock] = []
    chorus_already_rendered = False
    start_by_chorus = True

    for verse in ordered_verses:
        if not verse.chorus:
            text = normalize_lyrics_linebreaks(verse.text).strip()
            if text and verse.chorus_like:
                blocks.append(
                    RenderedSongBlock(
                        kind=RenderedSongBlockKind.CHORUS_LIKE,
                        label=(verse.prefix or render_settings.chorus_like_default_prefix).strip(),
                        text=text,
                        source_verse_id=verse.verse_id,
                        display_num=verse.num_verse,
                    )
                )
            elif text:
                blocks.append(
                    RenderedSongBlock(
                        kind=RenderedSongBlockKind.VERSE,
                        label="" if verse.notcontinuenumbering else render_settings.verse_label(verse.num_verse),
                        text=text,
                        source_verse_id=verse.verse_id,
                        display_num=verse.num_verse,
                    )
                )

            if choruses and not verse.followed and _should_render_chorus_group(render_mode, chorus_already_rendered):
                blocks.extend(_render_chorus_group(choruses, render_settings, repeated=chorus_already_rendered))
                chorus_already_rendered = True

        elif start_by_chorus and choruses and _should_render_chorus_group(render_mode, chorus_already_rendered):
            blocks.extend(_render_chorus_group(choruses, render_settings, repeated=chorus_already_rendered))
            chorus_already_rendered = True

        start_by_chorus = False

    if not blocks and choruses:
        blocks.extend(_render_chorus_group(choruses, render_settings, repeated=False))

    return blocks


def render_song_text(
    song: Song,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings | None = None,
    include_title: bool = True,
    verses: Iterable[Verse] | None = None,
) -> str:
    blocks = render_song_blocks(song, mode, settings=settings, verses=verses)
    output = []
    if include_title:
        output.extend([song.display_title, ""])

    for block in blocks:
        if block.label:
            output.append(block.label)
        output.append(block.text)
        output.append("")

    return "\n".join(output).strip() + "\n"
