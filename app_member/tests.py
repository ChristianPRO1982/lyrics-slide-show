import uuid
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from app_main.models import DirectoryUserRecord, SiteParams
from app_member.forms import SiteParamsAdminForm
from app_member.models import (
    MemberPreferences,
    MemberRole,
    default_song_search,
    validate_song_search,
)
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
    get_site_params_for_language,
    search_directory_members,
    set_member_role,
    _search_directory_users_with_sql,
    _user_table_has_column,
    _validate_identifier,
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
        preferences = MemberPreferences(
            member_id=uuid.UUID("11111111-1111-1111-1111-111111111111")
        )

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
            "song_search.validation doit être l'une des valeurs suivantes : all, validated_only, non_validated_only.",
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
            "song_search.genre_ids doit contenir uniquement des identifiants entiers.",
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
            "song_search contient des clés non prises en charge : search_txt.",
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
        self.assertEqual(
            get_member_role_flags("11111111-1111-1111-1111-111111111111"),
            MemberRoleFlags(),
        )

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

        flags = set_member_role(
            "11111111-1111-1111-1111-111111111111", "moderator", False
        )

        self.assertFalse(flags.is_admin)
        self.assertFalse(flags.is_moderator)
        self.assertFalse(
            MemberRole.objects.filter(
                member_id="11111111-1111-1111-1111-111111111111"
            ).exists()
        )

    def test_removing_admin_keeps_moderator_if_already_enabled(self):
        create_directory_user()
        set_member_role("11111111-1111-1111-1111-111111111111", "moderator", True)
        set_member_role("11111111-1111-1111-1111-111111111111", "admin", True)

        flags = set_member_role("11111111-1111-1111-1111-111111111111", "admin", False)

        self.assertFalse(flags.is_admin)
        self.assertTrue(flags.is_moderator)

    @patch(
        "app_member.services.MemberRole.objects.filter",
        side_effect=AssertionError("db blocked"),
    )
    def test_safe_role_lookup_returns_empty_flags_when_db_is_unavailable(
        self, _filter_mock
    ):
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
        admin_user = type(
            "User",
            (),
            {"is_authenticated": True, "is_admin": True, "is_moderator": True},
        )()
        moderator_user = type(
            "User",
            (),
            {"is_authenticated": True, "is_admin": False, "is_moderator": True},
        )()
        member_user = type(
            "User",
            (),
            {"is_authenticated": True, "is_admin": False, "is_moderator": False},
        )()

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


class MemberValidationCoverageTests(SimpleTestCase):
    def test_song_search_rejects_wrong_container_and_scalar_types(self):
        with self.assertRaisesMessage(ValidationError, "objet JSON"):
            validate_song_search([])

        invalid_payloads = (
            ({**default_song_search(), "text": 12}, "chaîne de caractères"),
            ({**default_song_search(), "everywhere": "yes"}, "booléen"),
            ({**default_song_search(), "genre_ids": "1,2"}, "doit être une liste"),
        )
        for payload, message in invalid_payloads:
            with self.subTest(message=message):
                with self.assertRaisesMessage(ValidationError, message):
                    validate_song_search(payload)

    def test_identifier_validation_accepts_safe_names_and_rejects_unsafe_names(self):
        self.assertEqual(_validate_identifier("users_table"), "users_table")
        for value in ("1users", "users-table", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _validate_identifier(value)

    def test_site_params_admin_form_parses_cards_and_builds_clean_payload(self):
        parsed = SiteParamsAdminForm._parse_home_cards(
            '{"cards": [null, {"title": " T ", "text": " X ", "image": "animations"}]}'
        )
        self.assertEqual(parsed, [{"title": "T", "text": "X", "image": "animations"}])
        self.assertEqual(
            SiteParamsAdminForm._parse_home_cards("bad-json"),
            [{"title": "", "text": "bad-json", "image": ""}],
        )
        self.assertEqual(SiteParamsAdminForm._parse_home_cards('{"cards": "bad"}'), [])

        form = SiteParamsAdminForm(
            data={
                "title": "Site",
                "title_h1": "Titre",
                "bloc1_text": "Bloc 1",
                "bloc2_text": "Bloc 2",
                "verse_max_lines": "4",
                "verse_max_characters_for_a_line": "42",
                "chorus_prefix": "R.",
                "verse_prefix1": "C",
                "verse_prefix2": ".",
                "admin_message_cooldown_minutes": "5",
                "moderator_message_cooldown_minutes": "60",
                "bg_img_max_bytes": "2097152",
                "bg_img_min_w": "800",
                "bg_img_min_h": "600",
                "bg_img_max_w": "4096",
                "bg_img_max_h": "3072",
                "bg_img_ratio_min": "1.3",
                "bg_img_ratio_max": "2.0",
                "bg_img_allowed_ext": ".jpg,.png",
                "bg_img_allowed_mime": "image/jpeg,image/png",
                "home_card_1_title": " Carte ",
                "home_card_1_text": " Texte ",
                "home_card_1_image": "animations",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('"title": "Carte"', form.cleaned_data["home_text"])
        self.assertIn('"image": "animations"', form.cleaned_data["home_text"])

    def test_site_params_admin_form_rejects_invalid_home_card_image(self):
        form = SiteParamsAdminForm(
            data={
                "title": "Site",
                "title_h1": "Titre",
                "bloc1_text": "Bloc 1",
                "bloc2_text": "Bloc 2",
                "verse_max_lines": "4",
                "verse_max_characters_for_a_line": "42",
                "chorus_prefix": "R.",
                "verse_prefix1": "C",
                "verse_prefix2": ".",
                "admin_message_cooldown_minutes": "5",
                "moderator_message_cooldown_minutes": "60",
                "bg_img_max_bytes": "2097152",
                "bg_img_min_w": "800",
                "bg_img_min_h": "600",
                "bg_img_max_w": "4096",
                "bg_img_max_h": "3072",
                "bg_img_ratio_min": "1.3",
                "bg_img_ratio_max": "2.0",
                "bg_img_allowed_ext": ".jpg,.png",
                "bg_img_allowed_mime": "image/jpeg,image/png",
                "home_card_1_image": "invalid",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("home_card_1_image", form.errors)

    def test_site_params_admin_form_preserves_prefix_spaces(self):
        form = SiteParamsAdminForm(
            data={
                "title": "Site",
                "title_h1": "Titre",
                "bloc1_text": "Bloc 1",
                "bloc2_text": "Bloc 2",
                "verse_max_lines": "4",
                "verse_max_characters_for_a_line": "42",
                "chorus_prefix": "  R.  ",
                "verse_prefix1": "  C",
                "verse_prefix2": ".  ",
                "admin_message_cooldown_minutes": "5",
                "moderator_message_cooldown_minutes": "60",
                "bg_img_max_bytes": "2097152",
                "bg_img_min_w": "800",
                "bg_img_min_h": "600",
                "bg_img_max_w": "4096",
                "bg_img_max_h": "3072",
                "bg_img_ratio_min": "1.3",
                "bg_img_ratio_max": "2.0",
                "bg_img_allowed_ext": ".jpg,.png",
                "bg_img_allowed_mime": "image/jpeg,image/png",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["chorus_prefix"], "  R.  ")
        self.assertEqual(form.cleaned_data["verse_prefix1"], "  C")
        self.assertEqual(form.cleaned_data["verse_prefix2"], ".  ")


class MemberServiceCompatibilityCoverageTests(TestCase):
    member_id = "99999999-9999-9999-9999-999999999999"

    def test_user_table_column_lookup_executes_information_schema_query(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor_factory = MagicMock()
        cursor_factory.return_value.__enter__.return_value = cursor

        with patch("app_member.services.connection.cursor", cursor_factory):
            self.assertTrue(_user_table_has_column("enabled"))

        cursor.execute.assert_called_once()

    def test_site_params_language_lookup_uses_requested_fallback_and_first_record(self):
        fr = SiteParams.objects.create(
            language="fr",
            title="FR",
            title_h1="FR",
            home_text="",
            bloc1_text="",
            bloc2_text="",
            verse_max_lines=4,
            verse_max_characters_for_a_line=42,
            chorus_prefix="R.",
            verse_prefix1="C",
            verse_prefix2=".",
            admin_message="",
            moderator_message="",
        )
        en = SiteParams.objects.create(
            language="en",
            title="EN",
            title_h1="EN",
            home_text="",
            bloc1_text="",
            bloc2_text="",
            verse_max_lines=4,
            verse_max_characters_for_a_line=42,
            chorus_prefix="C.",
            verse_prefix1="V",
            verse_prefix2=".",
            admin_message="",
            moderator_message="",
        )

        self.assertEqual(get_site_params_for_language("en"), en)
        self.assertEqual(get_site_params_for_language("de"), fr)
        fr.delete()
        self.assertEqual(get_site_params_for_language("de"), en)

        with patch(
            "app_member.services.SiteParams.objects.filter",
            side_effect=RuntimeError("db down"),
        ):
            self.assertIsNone(get_site_params_for_language("fr"))

    @override_settings(USER_SCHEMA="legacy_users", USER_TABLE="legacy_users")
    def test_legacy_sql_member_search_merges_roles(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (
                self.member_id,
                "legacy.user",
                "legacy@example.test",
                "Legacy",
                "User",
                True,
            )
        ]
        role = type(
            "RoleStub",
            (),
            {
                "member_id": uuid.UUID(self.member_id),
                "is_moderator": True,
                "is_admin": True,
            },
        )()
        with (
            patch("app_member.services._user_table_has_column", return_value=True),
            patch("app_member.services.connection.cursor") as cursor_factory,
            patch(
                "app_member.services.MemberRole.objects.filter",
                return_value=[role],
            ),
        ):
            cursor_factory.return_value.__enter__.return_value = cursor
            direct_results = _search_directory_users_with_sql("legacy", 5)
            routed_results = search_directory_members("legacy", limit=5)

        self.assertEqual(direct_results[0].username, "legacy.user")
        self.assertTrue(direct_results[0].is_moderator)
        self.assertTrue(direct_results[0].is_admin)
        self.assertEqual(routed_results, direct_results)
        self.assertEqual(cursor.execute.call_count, 2)

    def test_empty_member_search_returns_no_results(self):
        self.assertEqual(search_directory_members("   "), [])
