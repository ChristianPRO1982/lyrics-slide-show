from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from app_animation.models import Animation, AnimationSong
from app_song.models import Song, SongSlideDisplayMode


POSITION_START = 2
POSITION_STEP = 2


@dataclass(frozen=True)
class PlaylistItemToken:
    token_type: str
    token_id: int


@dataclass(frozen=True)
class PlaylistSyncResult:
    created_count: int
    kept_count: int
    deleted_count: int


def parse_ordered_mix(raw_value: str | None) -> list[PlaylistItemToken]:
    tokens: list[PlaylistItemToken] = []
    for raw_token in str(raw_value or "").split("|"):
        token = raw_token.strip()
        if not token or ":" not in token:
            continue

        token_type, raw_id = token.split(":", 1)
        token_type = token_type.strip().lower()
        if token_type not in {"asid", "sid"}:
            continue
        try:
            token_id = int(raw_id.strip())
        except (TypeError, ValueError):
            continue
        if token_id <= 0:
            continue
        tokens.append(PlaylistItemToken(token_type=token_type, token_id=token_id))
    return tokens


def normalize_animation_song_positions(animation: Animation) -> None:
    songs = list(
        animation.animation_songs.all().order_by("position", "animation_song_id")
    )
    for index, animation_song in enumerate(songs):
        normalized_position = POSITION_START + index * POSITION_STEP
        if animation_song.position != normalized_position:
            animation_song.position = normalized_position
            animation_song.save(update_fields=["position"])


def sync_animation_playlist(
    animation: Animation,
    ordered_tokens: list[PlaylistItemToken],
    allowed_song_ids: set[int],
) -> PlaylistSyncResult:
    existing_items = list(
        AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
            "position", "animation_song_id"
        )
    )
    existing_by_id = {item.animation_song_id: item for item in existing_items}

    ordered_entries: list[tuple[str, AnimationSong | int]] = []
    used_existing_ids: set[int] = set()

    for token in ordered_tokens:
        if token.token_type == "asid":
            item = existing_by_id.get(token.token_id)
            if item is None or item.animation_song_id in used_existing_ids:
                continue
            used_existing_ids.add(item.animation_song_id)
            ordered_entries.append(("asid", item))
            continue

        if token.token_type == "sid" and token.token_id in allowed_song_ids:
            ordered_entries.append(("sid", token.token_id))

    new_song_ids = {
        payload for token_type, payload in ordered_entries if token_type == "sid"
    }
    slide_display_mode_by_song_id = {
        int(song_id): slide_display_mode
        for song_id, slide_display_mode in Song.objects.filter(
            song_id__in=new_song_ids
        ).values_list("song_id", "slide_display_mode")
    }

    with transaction.atomic():
        deleted_count = 0
        for existing_item in existing_items:
            if existing_item.animation_song_id not in used_existing_ids:
                existing_item.delete()
                deleted_count += 1

        kept_items = [
            payload for token_type, payload in ordered_entries if token_type == "asid"
        ]

        # Move kept rows to temporary unique positions first to avoid unique
        # collisions when reordering (e.g. swapping 2 <-> 4).
        for index, kept_item in enumerate(kept_items):
            temporary_position = -1 * (index + 1)
            if kept_item.position != temporary_position:
                kept_item.position = temporary_position
                kept_item.save(update_fields=["position"])

        created_count = 0
        for index, (token_type, payload) in enumerate(ordered_entries):
            new_position = POSITION_START + index * POSITION_STEP
            if token_type == "asid":
                kept_item = payload
                if kept_item.position != new_position:
                    kept_item.position = new_position
                    kept_item.save(update_fields=["position"])
                continue

            song_id = payload
            AnimationSong.objects.create(
                animation_id=animation.animation_id,
                song_id=song_id,
                position=new_position,
                slide_display_mode=slide_display_mode_by_song_id.get(
                    song_id, SongSlideDisplayMode.SINGLE
                ),
            )
            created_count += 1

    return PlaylistSyncResult(
        created_count=created_count,
        kept_count=len(used_existing_ids),
        deleted_count=deleted_count,
    )
