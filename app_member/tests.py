import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from app_main.models import DirectoryUserRecord
from app_member.models import MemberPreferences, MemberRole, default_song_search, validate_song_search
from app_member.services import (
    MemberRoleFlags,
    can_manage_global_popup,
    can_manage_groups_globally,
    can_manage_moderator_popup,
    can_manage_site_members,
    can_manage_site_settings,
    can_validate_songs,
    get_member_role_flags,
    get_member_role_flags_safe,
    search_directory_members,
    set_member_role,
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
        preferences = MemberPreferences(member_id=uuid.UUID("11111111-1111-1111-1111-111111111111"))

        self.assertEqual(preferences.theme_slug, "normal")
        self.assertEqual(preferences.song_search, default_song_search())

    def test_model_does_not_generate_a_local_member_uuid(self):
        preferences = MemberPreferences()

        self.assertIsNone(preferences.member_id)

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


def create_directory_user(**overrides):
    defaults = {
        "id": "11111111-1111-1111-1111-111111111111",
        "username": "known.user",
        "first_name": "Known",
        "last_name": "User",
        "email": "known.user@example.test",
        "enabled": True,
        "email_verified": False,
    }
    defaults.update(overrides)
    return DirectoryUserRecord.objects.create(**defaults)


class MemberRoleServiceTests(TestCase):
    def test_missing_member_role_defaults_to_simple_member(self):
        self.assertEqual(get_member_role_flags("11111111-1111-1111-1111-111111111111"), MemberRoleFlags())

    def test_assigning_admin_also_assigns_moderator(self):
        create_directory_user()
        flags = set_member_role("11111111-1111-1111-1111-111111111111", "admin", True)

        self.assertTrue(flags.is_admin)
        self.assertTrue(flags.is_moderator)
        role = MemberRole.objects.get(member_id="11111111-1111-1111-1111-111111111111")
        self.assertTrue(role.is_admin)
        self.assertTrue(role.is_moderator)

    def test_removing_moderator_also_removes_admin(self):
        create_directory_user()
        set_member_role("11111111-1111-1111-1111-111111111111", "admin", True)

        flags = set_member_role("11111111-1111-1111-1111-111111111111", "moderator", False)

        self.assertFalse(flags.is_admin)
        self.assertFalse(flags.is_moderator)
        self.assertFalse(MemberRole.objects.filter(member_id="11111111-1111-1111-1111-111111111111").exists())

    def test_removing_admin_keeps_moderator_if_already_enabled(self):
        create_directory_user()
        set_member_role("11111111-1111-1111-1111-111111111111", "moderator", True)
        set_member_role("11111111-1111-1111-1111-111111111111", "admin", True)

        flags = set_member_role("11111111-1111-1111-1111-111111111111", "admin", False)

        self.assertFalse(flags.is_admin)
        self.assertTrue(flags.is_moderator)

    @patch("app_member.services.MemberRole.objects.filter", side_effect=AssertionError("db blocked"))
    def test_safe_role_lookup_returns_empty_flags_when_db_is_unavailable(self, _filter_mock):
        self.assertEqual(
            get_member_role_flags_safe("11111111-1111-1111-1111-111111111111"),
            MemberRoleFlags(),
        )


class DirectoryMemberSearchTests(TestCase):
    @patch("app_member.services.DirectoryUserRecord.objects.filter")
    def test_search_directory_members_merges_local_roles(self, filter_mock):
        filter_mock.return_value.order_by.return_value.__getitem__.return_value = [
            type(
                "DirectoryMemberStub",
                (),
                {
                    "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    "username": "known.user",
                    "email": "known.user@example.test",
                    "first_name": "Known",
                    "last_name": "User",
                    "enabled": True,
                },
            )()
        ]
        create_directory_user()
        set_member_role("11111111-1111-1111-1111-111111111111", "moderator", True)

        results = search_directory_members("known")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, "known.user")
        self.assertTrue(results[0].is_moderator)
        self.assertFalse(results[0].is_admin)


class PermissionHelperTests(SimpleTestCase):
    def test_permission_helpers_follow_role_contract(self):
        admin_user = type("User", (), {"is_authenticated": True, "is_admin": True, "is_moderator": True})()
        moderator_user = type("User", (), {"is_authenticated": True, "is_admin": False, "is_moderator": True})()
        member_user = type("User", (), {"is_authenticated": True, "is_admin": False, "is_moderator": False})()

        self.assertTrue(can_manage_site_members(admin_user))
        self.assertTrue(can_manage_site_settings(admin_user))
        self.assertTrue(can_manage_global_popup(admin_user))
        self.assertTrue(can_manage_moderator_popup(admin_user))

        self.assertFalse(can_manage_site_members(moderator_user))
        self.assertFalse(can_manage_site_settings(moderator_user))
        self.assertFalse(can_manage_global_popup(moderator_user))
        self.assertTrue(can_manage_moderator_popup(moderator_user))
        self.assertTrue(can_validate_songs(moderator_user))
        self.assertTrue(can_manage_groups_globally(moderator_user))

        self.assertFalse(can_manage_moderator_popup(member_user))
