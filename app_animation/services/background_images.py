from __future__ import annotations

import secrets
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.db import connection
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from app_animation.models import (
    Animation,
    AnimationSong,
    AnimationVerseOverride,
    BackgroundImage,
    BackgroundImageGenre,
    BackgroundImageStatus,
)
from app_member.services import get_site_params_for_language


BACKGROUND_IMAGES_DIR = "background-images"


def build_image_validation_config(language_code: str | None) -> dict[str, object]:
    params = get_site_params_for_language(language_code)
    return {
        "max_bytes": int(getattr(params, "bg_img_max_bytes", 2 * 1024 * 1024)),
        "min_w": int(getattr(params, "bg_img_min_w", 800)),
        "min_h": int(getattr(params, "bg_img_min_h", 600)),
        "max_w": int(getattr(params, "bg_img_max_w", 4096)),
        "max_h": int(getattr(params, "bg_img_max_h", 3072)),
        "ratio_min": float(getattr(params, "bg_img_ratio_min", 1.3)),
        "ratio_max": float(getattr(params, "bg_img_ratio_max", 2.0)),
        "allowed_ext": _parse_csv(
            getattr(params, "bg_img_allowed_ext", ".jpg,.jpeg,.png")
        ),
        "allowed_mime": _parse_csv(
            getattr(params, "bg_img_allowed_mime", "image/jpeg,image/png")
        ),
    }


def _parse_csv(value: str) -> list[str]:
    return [
        item.strip().lower() for item in str(value or "").split(",") if item.strip()
    ]


def background_images_root() -> Path:
    return Path(settings.MEDIA_ROOT) / BACKGROUND_IMAGES_DIR


def status_dir(status: str) -> Path:
    normalized = str(status or "").strip().lower()
    if normalized not in {
        BackgroundImageStatus.PENDING,
        BackgroundImageStatus.INACTIVE,
        BackgroundImageStatus.ACTIVE,
    }:
        normalized = BackgroundImageStatus.PENDING
    return background_images_root() / normalized


def ensure_background_image_dirs() -> None:
    for status, _label in BackgroundImageStatus.choices:
        status_dir(status).mkdir(parents=True, exist_ok=True)


def generate_asset_code() -> str:
    return f"bg-{secrets.token_hex(8)}"


def generate_storage_name(original_name: str) -> str:
    extension = Path(str(original_name or "")).suffix.lower()
    return f"{secrets.token_hex(10)}{extension}"


def relative_stored_path(status: str, filename: str) -> str:
    return f"{BACKGROUND_IMAGES_DIR}/{str(status).strip().lower()}/{filename}"


def absolute_stored_path(stored_path: str) -> Path:
    return Path(settings.MEDIA_ROOT) / str(stored_path or "").lstrip("/")


def move_image_to_status(image: BackgroundImage, status: str) -> None:
    source = absolute_stored_path(image.stored_path)
    destination = status_dir(status) / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        source.replace(destination)
    image.stored_path = relative_stored_path(status, source.name)
    image.status = status
    image.moderated_at = timezone.now()
    image.member_id = None
    image.save(update_fields=["stored_path", "status", "moderated_at", "member_id"])


def delete_image_file(image: BackgroundImage) -> None:
    path = absolute_stored_path(image.stored_path)
    if path.exists():
        path.unlink()


def resolve_background_asset_url(background_asset_code: str | None) -> str:
    value = str(background_asset_code or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    image = BackgroundImage.objects.filter(asset_code=value).only("stored_path").first()
    if image is None:
        return f"{settings.MEDIA_URL}{value}"
    path = str(image.stored_path or "").strip().lstrip("/")
    if not path:
        return ""
    return f"{settings.MEDIA_URL}{path}"


def fetch_genre_options() -> list[dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT genre_id, "group", "name"
            FROM "common"."genres"
            ORDER BY "group", "name", genre_id
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "id": int(row[0]),
            "group": str(row[1] or "").strip(),
            "name": str(row[2] or "").strip(),
            "label": " - ".join(
                part
                for part in [str(row[1] or "").strip(), str(row[2] or "").strip()]
                if part
            ),
        }
        for row in rows
    ]


def fetch_genre_labels(genre_ids: set[int]) -> dict[int, str]:
    if not genre_ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT genre_id, "group", "name"
            FROM "common"."genres"
            WHERE genre_id = ANY(%s)
            """,
            [list(sorted(genre_ids))],
        )
        rows = cursor.fetchall()
    output: dict[int, str] = {}
    for row in rows:
        output[int(row[0])] = " - ".join(
            part
            for part in [str(row[1] or "").strip(), str(row[2] or "").strip()]
            if part
        )
    return output


def replace_image_genres(image: BackgroundImage, genre_ids: list[int]) -> None:
    normalized = sorted({int(genre_id) for genre_id in genre_ids if int(genre_id) > 0})
    BackgroundImageGenre.objects.filter(image=image).delete()
    BackgroundImageGenre.objects.bulk_create(
        [
            BackgroundImageGenre(image=image, genre_id=genre_id)
            for genre_id in normalized
        ]
    )


def clear_background_image_references(asset_code: str) -> dict[str, int]:
    cleared_animation = Animation.objects.filter(
        background_asset_code=asset_code
    ).update(background_asset_code=None)
    cleared_song = AnimationSong.objects.filter(
        background_asset_code_override=asset_code
    ).update(background_asset_code_override=None)
    cleared_verse = AnimationVerseOverride.objects.filter(
        background_asset_code_override=asset_code
    ).update(background_asset_code_override=None)
    return {
        "animations": int(cleared_animation),
        "songs": int(cleared_song),
        "verses": int(cleared_verse),
    }


def count_background_image_references(asset_code: str) -> dict[str, int]:
    return {
        "animations": int(
            Animation.objects.filter(background_asset_code=asset_code).count()
        ),
        "songs": int(
            AnimationSong.objects.filter(
                background_asset_code_override=asset_code
            ).count()
        ),
        "verses": int(
            AnimationVerseOverride.objects.filter(
                background_asset_code_override=asset_code
            ).count()
        ),
    }


def list_background_images_for_view(
    *,
    include_all_statuses: bool,
    query: str,
    genre_ids: list[int],
    moderation_quick: bool,
    inactive_quick: bool,
) -> list[dict[str, object]]:
    queryset = BackgroundImage.objects.all().order_by("title", "image_id")
    if not include_all_statuses:
        queryset = queryset.filter(status=BackgroundImageStatus.ACTIVE)
    if moderation_quick:
        queryset = queryset.filter(status=BackgroundImageStatus.PENDING)
    elif inactive_quick:
        queryset = queryset.filter(status=BackgroundImageStatus.INACTIVE)
    if query:
        queryset = queryset.filter(title__icontains=query)
    if genre_ids:
        queryset = queryset.filter(genre_relations__genre_id__in=genre_ids).distinct()
    if include_all_statuses and not moderation_quick and not inactive_quick:
        queryset = queryset.annotate(
            moderation_priority=Case(
                When(status=BackgroundImageStatus.PENDING, then=Value(0)),
                When(status=BackgroundImageStatus.ACTIVE, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by("moderation_priority", "title", "image_id")

    images = list(queryset)
    relation_rows = BackgroundImageGenre.objects.filter(image__in=images).values_list(
        "image_id", "genre_id"
    )
    genre_map: dict[int, list[int]] = {}
    all_genre_ids: set[int] = set()
    for image_id, genre_id in relation_rows:
        genre_map.setdefault(int(image_id), []).append(int(genre_id))
        all_genre_ids.add(int(genre_id))
    labels = fetch_genre_labels(all_genre_ids)
    return [
        {
            "image": image,
            "image_id": int(image.image_id),
            "asset_code": image.asset_code,
            "title": image.title,
            "target": image.target,
            "description": image.description or "",
            "status": image.status,
            "url": resolve_background_asset_url(image.asset_code),
            "genre_ids": tuple(sorted(genre_map.get(int(image.image_id), []))),
            "genres": tuple(
                labels[genre_id]
                for genre_id in sorted(genre_map.get(int(image.image_id), []))
                if genre_id in labels
            ),
        }
        for image in images
    ]


def active_background_image_options() -> list[dict[str, object]]:
    return list_background_images_for_view(
        include_all_statuses=False,
        query="",
        genre_ids=[],
        moderation_quick=False,
        inactive_quick=False,
    )


def normalize_genre_ids(raw_values: list[str]) -> list[int]:
    output: list[int] = []
    for value in raw_values:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            output.append(parsed)
    return sorted(set(output))


def normalize_member_id(member_id: str | None) -> UUID | None:
    if not member_id:
        return None
    return UUID(str(member_id))
