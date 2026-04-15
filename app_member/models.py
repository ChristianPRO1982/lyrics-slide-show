from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


SONG_SEARCH_VALIDATION_VALUES = {
    "all",
    "validated_only",
    "non_validated_only",
}


def default_song_search() -> dict[str, object]:
    return {
        "text": "",
        "everywhere": False,
        "match_all_selected_refs": False,
        "genre_ids": [],
        "band_ids": [],
        "artist_ids": [],
        "validation": "all",
        "favorites_only": False,
    }


def validate_song_search(value: object) -> None:
    if not isinstance(value, dict):
        raise ValidationError("song_search must be a JSON object.")

    expected_keys = {
        "text",
        "everywhere",
        "match_all_selected_refs",
        "genre_ids",
        "band_ids",
        "artist_ids",
        "validation",
        "favorites_only",
    }
    unexpected_keys = set(value) - expected_keys
    if unexpected_keys:
        raise ValidationError(
            f"song_search contains unsupported keys: {', '.join(sorted(unexpected_keys))}."
        )

    if not isinstance(value.get("text", ""), str):
        raise ValidationError("song_search.text must be a string.")

    for key in ("everywhere", "match_all_selected_refs", "favorites_only"):
        if not isinstance(value.get(key), bool):
            raise ValidationError(f"song_search.{key} must be a boolean.")

    for key in ("genre_ids", "band_ids", "artist_ids"):
        ids = value.get(key)
        if not isinstance(ids, list):
            raise ValidationError(f"song_search.{key} must be a list.")
        if not all(isinstance(item, int) for item in ids):
            raise ValidationError(f"song_search.{key} must contain integer identifiers only.")

    validation = value.get("validation")
    if validation not in SONG_SEARCH_VALIDATION_VALUES:
        raise ValidationError(
            "song_search.validation must be one of: all, validated_only, non_validated_only."
        )


class MemberPreferences(models.Model):
    member_id = models.UUIDField(primary_key=True, editable=False)
    theme_slug = models.CharField(max_length=32, default="normal")
    song_search = models.JSONField(default=default_song_search, validators=[validate_song_search])

    class Meta:
        db_table = 'lss"."m_preferences'


class MemberRole(models.Model):
    member_id = models.UUIDField(primary_key=True, editable=False)
    is_moderator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = 'lss"."m_member_roles'
        constraints = [
            models.CheckConstraint(
                condition=Q(is_admin=False) | Q(is_moderator=True),
                name="m_member_roles_admin_requires_moderator",
            ),
        ]

