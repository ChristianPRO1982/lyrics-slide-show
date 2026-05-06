from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from app_animation.models import Animation, AnimationSong


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
    songs = list(animation.animation_songs.all().order_by("position", "animation_song_id"))
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
        AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id")
    )
    existing_by_id = {item.animation_song_id: item for item in existing_items}

    kept_items: list[AnimationSong] = []
    new_song_ids: list[int] = []
    used_existing_ids: set[int] = set()

    for token in ordered_tokens:
        if token.token_type == "asid":
            item = existing_by_id.get(token.token_id)
            if item is None or item.animation_song_id in used_existing_ids:
                continue
            used_existing_ids.add(item.animation_song_id)
            kept_items.append(item)
            continue

        if token.token_type == "sid" and token.token_id in allowed_song_ids:
            new_song_ids.append(token.token_id)

    with transaction.atomic():
        deleted_count = 0
        for existing_item in existing_items:
            if existing_item.animation_song_id not in used_existing_ids:
                existing_item.delete()
                deleted_count += 1

        # Move kept rows to temporary unique positions first to avoid unique
        # collisions when reordering (e.g. swapping 2 <-> 4).
        for index, kept_item in enumerate(kept_items):
            temporary_position = -1 * (index + 1)
            if kept_item.position != temporary_position:
                kept_item.position = temporary_position
                kept_item.save(update_fields=["position"])

        for index, kept_item in enumerate(kept_items):
            new_position = POSITION_START + index * POSITION_STEP
            if kept_item.position != new_position:
                kept_item.position = new_position
                kept_item.save(update_fields=["position"])

        created_count = 0
        next_index = len(kept_items)
        for song_id in new_song_ids:
            AnimationSong.objects.create(
                animation_id=animation.animation_id,
                song_id=song_id,
                position=POSITION_START + next_index * POSITION_STEP,
            )
            next_index += 1
            created_count += 1

    return PlaylistSyncResult(
        created_count=created_count,
        kept_count=len(kept_items),
        deleted_count=deleted_count,
    )
