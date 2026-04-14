import uuid

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from app_member.models import (
    MemberPreferences,
    default_song_search,
    validate_song_search,
)


class MemberPreferencesModelTests(SimpleTestCase):
    def test_default_song_search_matches_expected_lss_contract(self):
        self.assertEqual(
            default_song_search(),
            {
                "text": "",
                "everywhere": False,
                "match_all_selected_refs": False,
                "genre_ids": [],
                "band_ids": [],
                "artist_ids": [],
                "validation": "all",
                "favorites_only": False,
            },
        )

    def test_model_defaults_match_expected_member_preferences(self):
        preferences = MemberPreferences(id=uuid.UUID("11111111-1111-1111-1111-111111111111"))

        self.assertEqual(preferences.theme_slug, "normal")
        self.assertEqual(preferences.song_search, default_song_search())

    def test_model_does_not_generate_a_local_member_uuid(self):
        preferences = MemberPreferences()

        self.assertIsNone(preferences.id)

    def test_song_search_accepts_expected_payload(self):
        validate_song_search(
            {
                "text": "alleluia",
                "everywhere": True,
                "match_all_selected_refs": True,
                "genre_ids": [1, 2],
                "band_ids": [5],
                "artist_ids": [8, 13],
                "validation": "validated_only",
                "favorites_only": False,
            }
        )

    def test_song_search_rejects_invalid_validation_value(self):
        with self.assertRaisesMessage(
            ValidationError,
            "song_search.validation must be one of: all, validated_only, non_validated_only.",
        ):
            validate_song_search(
                {
                    **default_song_search(),
                    "validation": "approved",
                }
            )

    def test_song_search_rejects_non_integer_reference_ids(self):
        with self.assertRaisesMessage(
            ValidationError,
            "song_search.genre_ids must contain integer identifiers only.",
        ):
            validate_song_search(
                {
                    **default_song_search(),
                    "genre_ids": ["12"],
                }
            )

    def test_song_search_rejects_unsupported_keys(self):
        with self.assertRaisesMessage(
            ValidationError,
            "song_search contains unsupported keys: search_txt.",
        ):
            validate_song_search(
                {
                    **default_song_search(),
                    "search_txt": "legacy",
                }
            )
