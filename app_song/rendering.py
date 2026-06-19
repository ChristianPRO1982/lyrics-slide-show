from __future__ import annotations

import html
import re
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
            chorus_like_default_prefix=site_params.chorus_prefix
            or defaults.chorus_like_default_prefix,
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
    explicit_prefix: str = ""
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


def _get_ordered_verses(
    song: Song, verses: Iterable[Verse] | None = None
) -> list[Verse]:
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


def _should_render_chorus_group(
    mode: ChorusRenderMode, chorus_already_rendered: bool
) -> bool:
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


def _render_table_row(
    *,
    label: str,
    text_html: str,
    kind: RenderedSongBlockKind,
) -> str:
    label_html = escape(label.strip()) if label else ""
    kind_class = kind.value.replace("_", "-")
    return (
        f'<tr class="song-lyrics-row song-lyrics-row--{kind_class}">'
        f'<th scope="row">{label_html}</th>'
        f"<td>{text_html}</td>"
        "</tr>"
    )


def _render_blocks_table_html(blocks: list[RenderedSongBlock]) -> str:
    if not blocks:
        return ""

    rows: list[str] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.kind == RenderedSongBlockKind.CHORUS:
            chorus_chunks: list[str] = []
            while (
                index < len(blocks)
                and blocks[index].kind == RenderedSongBlockKind.CHORUS
                and blocks[index].is_repeated_chorus == block.is_repeated_chorus
            ):
                chorus_text_html = _format_html_text(blocks[index].text)
                if chorus_text_html:
                    chorus_chunks.append(chorus_text_html)
                index += 1
            if chorus_chunks:
                rows.append(
                    _render_table_row(
                        label=block.label,
                        text_html="<br>".join(chorus_chunks),
                        kind=RenderedSongBlockKind.CHORUS,
                    )
                )
            continue

        text_html = _format_html_text(block.text)
        if text_html:
            rows.append(
                _render_table_row(
                    label=block.label, text_html=text_html, kind=block.kind
                )
            )
        index += 1

    if not rows:
        return ""
    return f'<table class="song-lyrics-table"><tbody>{"".join(rows)}</tbody></table>'


def _render_song_html(
    song: Song,
    mode: ChorusRenderMode,
    settings: SongRenderSettings,
    verses: Iterable[Verse] | None = None,
) -> str:
    return _render_blocks_table_html(
        render_song_blocks(song, mode, settings=settings, verses=verses)
    )


def _render_blocks_plain_text(
    blocks: list[RenderedSongBlock], *, chorus_like_label_on_own_line: bool = False
) -> str:
    plain_blocks: list[str] = []
    index = 0

    while index < len(blocks):
        block = blocks[index]
        if block.kind == RenderedSongBlockKind.CHORUS:
            chorus_chunks: list[str] = []
            while (
                index < len(blocks)
                and blocks[index].kind == RenderedSongBlockKind.CHORUS
                and blocks[index].is_repeated_chorus == block.is_repeated_chorus
            ):
                chorus_text = normalize_lyrics_linebreaks(blocks[index].text).strip()
                if chorus_text:
                    chorus_chunks.append(chorus_text)
                index += 1
            if chorus_chunks:
                chorus_block = "\n".join(chorus_chunks)
                if block.label:
                    chorus_block = f"{block.label} {chorus_block}"
                plain_blocks.append(chorus_block.strip())
            continue

        text = normalize_lyrics_linebreaks(block.text).strip()
        if text:
            if (
                chorus_like_label_on_own_line
                and block.kind == RenderedSongBlockKind.CHORUS_LIKE
            ):
                if block.explicit_prefix:
                    plain_blocks.append(f"{block.explicit_prefix}\n{text}")
                else:
                    plain_blocks.append(text)
            elif block.label:
                plain_blocks.append(f"{block.label} {text}".strip())
            else:
                plain_blocks.append(text)
        index += 1

    return "\n\n".join(item.strip() for item in plain_blocks if item.strip()).strip()


def _table_html_to_plain_text(text_html: str) -> str:
    text = normalize_lyrics_linebreaks(text_html)
    text = text.replace("<br><br>", "\n\n").replace("<br>", "\n")
    text = text.replace("</th><td>", " ")
    text = text.replace("</td></tr>", "\n\n")
    text = re.sub(r"</?(table|tbody|tr|th|td)(?:\s[^>]*)?>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
                        label=(verse.prefix or "").strip(),
                        text=text,
                        source_verse_id=verse.verse_id,
                        display_num=verse.num_verse,
                        explicit_prefix=(verse.prefix or "").strip(),
                    )
                )
            elif text:
                blocks.append(
                    RenderedSongBlock(
                        kind=RenderedSongBlockKind.VERSE,
                        label=""
                        if verse.notcontinuenumbering
                        else render_settings.verse_label(verse.num_verse),
                        text=text,
                        source_verse_id=verse.verse_id,
                        display_num=verse.num_verse,
                    )
                )

            if (
                choruses
                and not verse.followed
                and _should_render_chorus_group(render_mode, chorus_already_rendered)
            ):
                blocks.extend(
                    _render_chorus_group(
                        choruses, render_settings, repeated=chorus_already_rendered
                    )
                )
                chorus_already_rendered = True

        elif (
            start_by_chorus
            and choruses
            and _should_render_chorus_group(render_mode, chorus_already_rendered)
        ):
            blocks.extend(
                _render_chorus_group(
                    choruses, render_settings, repeated=chorus_already_rendered
                )
            )
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
    return SongTextArtifacts(
        full_title=build_song_full_title(song),
        full_title_with_tags=build_song_full_title_with_tags(song),
        short_text_html=_render_song_html(
            song, ChorusRenderMode.SINGLE, render_settings, verses=ordered_verses
        ),
        long_text_html=_render_song_html(
            song, ChorusRenderMode.FULL, render_settings, verses=ordered_verses
        ),
    )


def render_song_text(
    song: Song,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings | None = None,
    include_title: bool = True,
    verses: Iterable[Verse] | None = None,
) -> str:
    render_mode = ChorusRenderMode(mode)
    render_settings = settings or SongRenderSettings.defaults()
    blocks = render_song_blocks(
        song, render_mode, settings=render_settings, verses=verses
    )
    text = _render_blocks_plain_text(blocks)
    artifacts = build_song_text_artifacts(song, settings=render_settings, verses=verses)

    output = []
    if include_title:
        output.extend([artifacts.full_title_with_tags, ""])
    output.append(text.strip())

    return "\n".join(output).strip() + "\n"


def render_song_popup_plain_text(
    song: Song,
    mode: ChorusRenderMode | str,
    settings: SongRenderSettings | None = None,
    verses: Iterable[Verse] | None = None,
) -> str:
    render_mode = ChorusRenderMode(mode)
    render_settings = settings or SongRenderSettings.defaults()
    blocks = render_song_blocks(
        song, render_mode, settings=render_settings, verses=verses
    )
    text = _render_blocks_plain_text(blocks, chorus_like_label_on_own_line=True)
    output = []
    output.append(text.strip())

    return "\n".join(output).strip() + "\n"
