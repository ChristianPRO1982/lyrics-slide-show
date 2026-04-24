from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from django.utils.html import escape
from django.utils.translation import gettext as _

from app_member.services import get_site_params_for_language

from .models import Song, SongStatus, Verse


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
            chorus_prefix=site_params.chorus_prefix,
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


@dataclass(frozen=True)
class SongTextArtifacts:
    full_title: str
    full_title_with_tags: str
    short_text_html: str
    long_text_html: str


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


def _title_marker(song: Song) -> str:
    if song.status == SongStatus.VALIDATED:
        return "✔️"
    if song.status == SongStatus.VALIDATED_WITH_CONCERN:
        return "✔️⁉️"
    return ""


def build_song_full_title(song: Song) -> str:
    title = str(song.title or "").strip()
    subtitle = str(song.subtitle or "").strip()
    if subtitle:
        return f"{title} - {subtitle}"
    return title


def build_song_full_title_with_tags(song: Song) -> str:
    title = build_song_full_title(song)
    tags = []
    validation_tag = _title_marker(song)
    if validation_tag:
        tags.append(validation_tag)
    if song.licensed:
        tags.append("📄")
    if tags:
        return f"{title} {' '.join(tags)}".strip()
    return title


def _format_html_text(value: str | None) -> str:
    normalized = normalize_lyrics_linebreaks(value).strip()
    if not normalized:
        return ""
    return "<br>".join(escape(line) for line in normalized.split("\n"))


def _append_with_gap(chunks: list[str], content: str) -> None:
    if not content:
        return
    if chunks:
        chunks.append("<br><br>")
    chunks.append(content)


def _build_chorus_html(ordered_verses: list[Verse], settings: SongRenderSettings) -> str:
    chorus_chunks: list[str] = []
    for verse in ordered_verses:
        if not verse.chorus:
            continue
        verse_html = _format_html_text(verse.text)
        if not verse_html:
            continue
        if not chorus_chunks:
            prefix = str(settings.chorus_prefix or "").strip()
            if prefix:
                verse_html = f"<i>{escape(prefix)}</i> {verse_html}"
        chorus_chunks.append(verse_html)

    if not chorus_chunks:
        return ""
    return f"<b>{'<br><br>'.join(chorus_chunks)}</b>"


def _render_non_chorus_verse_html(verse: Verse, settings: SongRenderSettings) -> str:
    text_html = _format_html_text(verse.text)
    if not text_html:
        return ""

    if verse.chorus_like:
        prefix = str(verse.prefix or "").strip()
        prefix_html = f"<i>{escape(prefix)}</i><br>" if prefix else ""
        return f"<b>{prefix_html}{text_html}</b>"

    if verse.notcontinuenumbering:
        return text_html

    label = settings.verse_label(verse.num_verse)
    if not label:
        return text_html
    return f"<i>{escape(label)}</i> {text_html}"


def _render_song_html(
    ordered_verses: list[Verse],
    chorus_html: str,
    mode: ChorusRenderMode,
    settings: SongRenderSettings,
) -> str:
    if not ordered_verses:
        return chorus_html

    rendered_chunks: list[str] = []
    chorus_inserted = False

    for index, verse in enumerate(ordered_verses):
        if verse.chorus:
            if index == 0 and chorus_html and _should_render_chorus_group(mode, chorus_inserted):
                _append_with_gap(rendered_chunks, chorus_html)
                chorus_inserted = True
            continue

        verse_html = _render_non_chorus_verse_html(verse, settings)
        if not verse_html:
            continue

        _append_with_gap(rendered_chunks, verse_html)

        if chorus_html and not verse.followed and _should_render_chorus_group(mode, chorus_inserted):
            _append_with_gap(rendered_chunks, chorus_html)
            chorus_inserted = True

    if not rendered_chunks and chorus_html:
        return chorus_html
    return "".join(rendered_chunks)


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


def build_song_text_artifacts(
    song: Song,
    *,
    settings: SongRenderSettings | None = None,
    verses: Iterable[Verse] | None = None,
) -> SongTextArtifacts:
    render_settings = settings or SongRenderSettings.defaults()
    ordered_verses = _get_ordered_verses(song, verses)
    chorus_html = _build_chorus_html(ordered_verses, render_settings)
    return SongTextArtifacts(
        full_title=build_song_full_title(song),
        full_title_with_tags=build_song_full_title_with_tags(song),
        short_text_html=_render_song_html(ordered_verses, chorus_html, ChorusRenderMode.SINGLE, render_settings),
        long_text_html=_render_song_html(ordered_verses, chorus_html, ChorusRenderMode.FULL, render_settings),
    )


def render_song_text(
    song: Song,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings | None = None,
    include_title: bool = True,
    verses: Iterable[Verse] | None = None,
) -> str:
    artifacts = build_song_text_artifacts(song, settings=settings, verses=verses)
    text_html = artifacts.short_text_html if ChorusRenderMode(mode) == ChorusRenderMode.SINGLE else artifacts.long_text_html
    text = normalize_lyrics_linebreaks(text_html.replace("<br><br>", "\n\n").replace("<br>", "\n"))
    text = (
        text.replace("<i>", "")
        .replace("</i>", "")
        .replace("<b>", "")
        .replace("</b>", "")
    )

    output = []
    if include_title:
        output.extend([artifacts.full_title_with_tags, ""])
    output.append(text.strip())

    return "\n".join(output).strip() + "\n"
