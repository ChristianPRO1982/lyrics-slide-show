from __future__ import annotations

from django.db import transaction

from app_animation.models import Animation, AnimationSong, AnimationVerseOverride


ANIMATION_COPY_FIELDS = [
    "text_color",
    "bg_color",
    "font_family",
    "font_size",
    "horizontal_padding",
    "background_asset_code",
    "default_transition",
]

ANIMATION_SONG_COPY_FIELDS = [
    "slide_display_mode",
    "text_color_override",
    "bg_color_override",
    "font_family_override",
    "font_size_override",
    "horizontal_padding_override",
    "background_asset_code_override",
]

ANIMATION_VERSE_OVERRIDE_COPY_FIELDS = [
    "is_visible",
    "text_color_override",
    "bg_color_override",
    "font_family_override",
    "font_size_override",
    "horizontal_padding_override",
    "background_asset_code_override",
]


@transaction.atomic
def copy_animation(
    source: Animation,
    *,
    scheduled_at,
    title: str,
    description: str,
) -> Animation:
    target_payload = {
        field_name: getattr(source, field_name) for field_name in ANIMATION_COPY_FIELDS
    }
    target = Animation.objects.create(
        group=source.group,
        title=title,
        description=description,
        scheduled_at=scheduled_at,
        **target_payload,
    )

    source_items = (
        source.animation_songs.select_related("song")
        .prefetch_related("verse_overrides")
        .order_by("position", "animation_song_id")
    )
    for source_item in source_items:
        item_payload = {
            field_name: getattr(source_item, field_name)
            for field_name in ANIMATION_SONG_COPY_FIELDS
        }
        target_item = AnimationSong.objects.create(
            animation=target,
            song=source_item.song,
            position=source_item.position,
            **item_payload,
        )

        for source_override in source_item.verse_overrides.all():
            override_payload = {
                field_name: getattr(source_override, field_name)
                for field_name in ANIMATION_VERSE_OVERRIDE_COPY_FIELDS
            }
            AnimationVerseOverride.objects.create(
                animation_song=target_item,
                source_verse_id=source_override.source_verse_id,
                **override_payload,
            )

    return target
