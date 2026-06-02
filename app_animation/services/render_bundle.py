from __future__ import annotations

from dataclasses import dataclass

from app_song.rendering import ChorusRenderMode, SongRenderSettings, render_song_blocks

from app_animation.models import Animation, AnimationSong, AnimationVerseOverride


@dataclass(frozen=True)
class ResolvedVisualStyle:
    text_color: str
    bg_color: str
    font_family: str
    font_size: int
    horizontal_padding: int
    background_asset_code: str | None


@dataclass(frozen=True)
class RenderedAnimationSlide:
    animation_song_id: int
    song_id: int
    song_title: str
    source_verse_id: int | None
    kind: str
    label: str
    text: str
    style: ResolvedVisualStyle


def _resolve_style(
    animation: Animation,
    animation_song: AnimationSong,
    verse_override: AnimationVerseOverride | None,
) -> ResolvedVisualStyle:
    return ResolvedVisualStyle(
        text_color=(
            verse_override.text_color_override
            if verse_override and verse_override.text_color_override
            else animation_song.text_color_override or animation.text_color
        ),
        bg_color=(
            verse_override.bg_color_override
            if verse_override and verse_override.bg_color_override
            else animation_song.bg_color_override or animation.bg_color
        ),
        font_family=(
            verse_override.font_family_override
            if verse_override and verse_override.font_family_override
            else animation_song.font_family_override or animation.font_family
        ),
        font_size=(
            verse_override.font_size_override
            if verse_override and verse_override.font_size_override is not None
            else animation_song.font_size_override or animation.font_size
        ),
        horizontal_padding=(
            verse_override.horizontal_padding_override
            if verse_override and verse_override.horizontal_padding_override is not None
            else animation_song.horizontal_padding_override
            or animation.horizontal_padding
        ),
        background_asset_code=(
            verse_override.background_asset_code_override
            if verse_override and verse_override.background_asset_code_override
            else animation_song.background_asset_code_override
            or animation.background_asset_code
        ),
    )


def build_animation_render_bundle(animation: Animation) -> list[RenderedAnimationSlide]:
    slides: list[RenderedAnimationSlide] = []
    render_settings = SongRenderSettings.defaults()

    animation_songs = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses", "verse_overrides")
        .order_by("position", "animation_song_id")
    )

    for animation_song in animation_songs:
        chorus_verse_ids = {
            int(verse.verse_id)
            for verse in animation_song.song.verses.all()
            if verse.chorus
        }
        overrides_by_verse_id = {
            override.source_verse_id: override
            for override in animation_song.verse_overrides.all()
        }

        song_blocks = render_song_blocks(
            animation_song.song,
            ChorusRenderMode.FULL,
            settings=render_settings,
            verses=animation_song.song.verses.all(),
        )

        for block in song_blocks:
            source_verse_id = block.source_verse_id
            verse_override = (
                overrides_by_verse_id.get(source_verse_id)
                if source_verse_id is not None
                else None
            )
            if (
                verse_override is not None
                and not verse_override.is_visible
                and source_verse_id not in chorus_verse_ids
            ):
                continue

            style = _resolve_style(animation, animation_song, verse_override)
            slides.append(
                RenderedAnimationSlide(
                    animation_song_id=animation_song.animation_song_id,
                    song_id=animation_song.song_id,
                    song_title=animation_song.song.display_title,
                    source_verse_id=source_verse_id,
                    kind=str(block.kind),
                    label=block.label,
                    text=block.text,
                    style=style,
                )
            )

    return slides
