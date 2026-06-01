from unittest.mock import MagicMock, patch

from django.contrib.messages import get_messages
from django.template import engines
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from app_main.auth import (
    AnonymousSessionUser,
    DirectoryUser,
    DisabledUserError,
    KeycloakAuthError,
    UnknownUserError,
    build_keycloak_logout_url,
    get_directory_user,
    refresh_request_user,
    sign_callback_data,
    validate_keycloak_callback,
    validate_callback_payload,
)
from app_main.models import DirectoryUserRecord, SiteParams
from app_member.models import MemberRole
from app_member.services import MemberRoleFlags
from app_main.views import account


def create_site_params(**overrides):
    defaults = {
        "language": "fr",
        "title": "Lyrics Slide Show",
        "title_h1": "Lyrics Slide Show",
        "home_text": "Bienvenue",
        "bloc1_text": "Bloc 1",
        "bloc2_text": "Bloc 2",
        "verse_max_lines": 4,
        "verse_max_characters_for_a_line": 42,
        "chorus_prefix": "Ref.",
        "verse_prefix1": "C",
        "verse_prefix2": ".",
        "admin_message": "",
        "moderator_message": "",
        "admin_message_cooldown_minutes": 5,
        "moderator_message_cooldown_minutes": 60,
    }
    defaults.update(overrides)
    return SiteParams.objects.create(**defaults)


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


class CallbackValidationTests(SimpleTestCase):
    @override_settings(
        AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300
    )
    def test_validate_callback_payload_accepts_signed_payload(self):
        payload = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
            "ts": "1700000000",
        }

        with patch("app_main.auth.time.time", return_value=1700000100):
            payload["sig"] = sign_callback_data(payload, "shared-secret")
            result = validate_callback_payload(payload)

        self.assertEqual(result["external_id"], payload["external_id"])

    @override_settings(
        AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300
    )
    def test_validate_callback_payload_rejects_bad_signature(self):
        payload = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
            "ts": "1700000000",
            "sig": "bad-signature",
        }

        with patch("app_main.auth.time.time", return_value=1700000100):
            with self.assertRaisesMessage(Exception, "Invalid callback signature."):
                validate_callback_payload(payload)

    @override_settings(
        AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300
    )
    def test_validate_callback_payload_rejects_invalid_uuid(self):
        payload = {
            "external_id": "not-a-uuid",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
            "ts": "1700000000",
        }

        with patch("app_main.auth.time.time", return_value=1700000100):
            payload["sig"] = sign_callback_data(payload, "shared-secret")
            with self.assertRaisesMessage(Exception, "Invalid external_id format."):
                validate_callback_payload(payload)

    @override_settings(
        KEYCLOAK_SERVER_URL="https://auth.example.com",
        KEYCLOAK_REALM="carthographie",
        KEYCLOAK_CLIENT_ID="app_lss",
        KEYCLOAK_CLIENT_SECRET="secret",
        KEYCLOAK_REDIRECT_URI="https://lss.example.com/auth/callback/",
    )
    @patch("app_main.auth._fetch_keycloak_userinfo")
    @patch("app_main.auth._exchange_keycloak_code")
    def test_validate_keycloak_callback_accepts_valid_userinfo(
        self, exchange_mock, userinfo_mock
    ):
        exchange_mock.return_value = {"access_token": "access-token"}
        userinfo_mock.return_value = {
            "sub": "11111111-1111-1111-1111-111111111111",
        }
        session = {"lss_keycloak_state": "expected-state"}

        payload = validate_keycloak_callback(
            {"code": "auth-code", "state": "expected-state"}, session
        )

        self.assertEqual(payload["external_id"], "11111111-1111-1111-1111-111111111111")
        self.assertIsNone(payload["username"])
        self.assertNotIn("lss_keycloak_state", session)

    def test_validate_keycloak_callback_rejects_invalid_state(self):
        session = {"lss_keycloak_state": "expected-state"}

        with self.assertRaisesMessage(KeycloakAuthError, "Invalid Keycloak state."):
            validate_keycloak_callback(
                {"code": "auth-code", "state": "wrong-state"}, session
            )


class DirectoryUserLookupTests(TestCase):
    @patch("app_main.auth.DirectoryUserRecord.objects.get")
    def test_get_directory_user_returns_enabled_user(self, get_mock):
        get_mock.return_value = type(
            "DirectoryUserRecordStub",
            (),
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "username": "known.user",
                "email": "known.user@example.test",
                "first_name": "Known",
                "last_name": "User",
                "enabled": True,
            },
        )()

        user = get_directory_user("11111111-1111-1111-1111-111111111111")

        self.assertEqual(user.username, "known.user")

    @patch(
        "app_main.auth.DirectoryUserRecord.objects.get", side_effect=Exception("boom")
    )
    def test_get_directory_user_propagates_unexpected_orm_error(self, _get_mock):
        with self.assertRaisesMessage(Exception, "boom"):
            get_directory_user("11111111-1111-1111-1111-111111111111")

    @patch(
        "app_main.auth.DirectoryUserRecord.objects.get",
        side_effect=DirectoryUserRecord.DoesNotExist,
    )
    def test_get_directory_user_raises_unknown_user(self, _get_mock):
        with self.assertRaises(UnknownUserError):
            get_directory_user("11111111-1111-1111-1111-111111111111")

    def _patch_cursor(self, cursor_factory, fetchone_values):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetchone_values
        cursor_factory.return_value.__enter__.return_value = cursor
        return cursor

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_returns_enabled_user_with_sql_fallback(
        self, cursor_factory
    ):
        cursor = self._patch_cursor(
            cursor_factory,
            [
                (1,),
                (
                    "11111111-1111-1111-1111-111111111111",
                    "known.user",
                    "known.user@example.test",
                    "Known",
                    "User",
                    True,
                ),
            ],
        )

        with self.settings(USER_SCHEMA="legacy_users", USER_TABLE="legacy_users"):
            user = get_directory_user("11111111-1111-1111-1111-111111111111")

        self.assertEqual(user.username, "known.user")
        self.assertEqual(cursor.execute.call_count, 2)

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_raises_unknown_user_with_sql_fallback(
        self, cursor_factory
    ):
        self._patch_cursor(cursor_factory, [(1,), None])

        with self.settings(USER_SCHEMA="legacy_users", USER_TABLE="legacy_users"):
            with self.assertRaises(UnknownUserError):
                get_directory_user("missing")

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_raises_disabled_user_with_sql_fallback(
        self, cursor_factory
    ):
        self._patch_cursor(
            cursor_factory,
            [
                (1,),
                (
                    "22222222-2222-2222-2222-222222222222",
                    "disabled.user",
                    "disabled.user@example.test",
                    "Disabled",
                    "User",
                    False,
                ),
            ],
        )

        with self.settings(USER_SCHEMA="legacy_users", USER_TABLE="legacy_users"):
            with self.assertRaises(DisabledUserError):
                get_directory_user("22222222-2222-2222-2222-222222222222")

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_defaults_to_enabled_when_column_is_missing(
        self, cursor_factory
    ):
        self._patch_cursor(
            cursor_factory,
            [
                None,
                (
                    "11111111-1111-1111-1111-111111111111",
                    "known.user",
                    "known.user@example.test",
                    "Known",
                    "User",
                    True,
                ),
            ],
        )

        with self.settings(USER_SCHEMA="legacy_users", USER_TABLE="legacy_users"):
            user = get_directory_user("11111111-1111-1111-1111-111111111111")

        self.assertEqual(user.username, "known.user")


class RequestUserRefreshTests(SimpleTestCase):
    @patch("app_main.auth.get_member_role_flags_safe")
    @patch("app_main.auth.get_directory_user")
    def test_refresh_request_user_reloads_connected_user_from_directory(
        self,
        get_directory_user_mock,
        get_member_role_flags_safe_mock,
    ):
        get_directory_user_mock.return_value = DirectoryUser(
            external_id="11111111-1111-1111-1111-111111111111",
            username="fresh.user",
            email="fresh.user@example.test",
            first_name="Fresh",
            last_name="User",
            enabled=True,
        )
        get_member_role_flags_safe_mock.return_value = MemberRoleFlags(
            is_moderator=True, is_admin=False
        )

        session = {
            "lss_user": {
                "external_id": "11111111-1111-1111-1111-111111111111",
                "username": "stale.user",
            }
        }

        user = refresh_request_user(session)

        self.assertTrue(user.is_authenticated)
        self.assertEqual(user.username, "fresh.user")
        self.assertTrue(user.is_moderator)
        self.assertFalse(user.is_admin)
        self.assertEqual(session["lss_user"]["username"], "fresh.user")

    @patch("app_main.auth.get_member_role_flags_safe")
    @patch(
        "app_main.auth.get_directory_user",
        side_effect=DisabledUserError("This user is disabled in users.users."),
    )
    def test_refresh_request_user_clears_session_when_directory_user_is_disabled(
        self,
        _get_directory_user_mock,
        _get_member_role_flags_safe_mock,
    ):
        session = {
            "lss_user": {
                "external_id": "11111111-1111-1111-1111-111111111111",
                "username": "known.user",
            }
        }

        user = refresh_request_user(session)

        self.assertFalse(user.is_authenticated)
        self.assertNotIn("lss_user", session)


class AuthFlowTests(TestCase):
    def test_homepage_shows_guest_state(self):
        response = self.client.get(reverse("homepage"))

        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("language"))
        self.assertContains(response, 'data-django-alias="login"')
        self.assertContains(response, 'data-django-alias="signup"')

    def test_homepage_shows_expected_marketing_content(self):
        response = self.client.get(reverse("homepage"))

        self.assertContains(response, "Lyrics Slide Show")
        self.assertContains(response, "propulsé par cARThographie !")
        self.assertContains(
            response,
            "Si vous avez des suggestions d'amélioration du site ou des bugs à remonter, merci de le faire ici : déposer un message",
        )
        self.assertContains(response, "Projetez. Chantez. Kiffez.")
        self.assertContains(response, "Pourquoi c’est cool ?")
        self.assertContains(response, "Comment ça marche ?")
        self.assertContains(response, "Ce que tu y gagnes")
        self.assertContains(
            response,
            "Prêt·e ? Ouvre une nouvelle session, colle tes paroles et fais monter la vibe.",
        )

    @override_settings(AUTH_MOCK_BASE_URL="http://localhost:8001")
    def test_login_redirects_to_auth_mock(self):
        response = self.client.get(reverse("login") + "?start=1")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith("http://localhost:8001/login?return_to=")
        )

    def test_login_page_shows_mock_entrypoint(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mock SSO")
        self.assertContains(response, reverse("login") + "?start=1")

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.build_keycloak_login_url",
        return_value="https://auth.example.com/realms/carthographie/protocol/openid-connect/auth?x=1",
    )
    def test_login_redirects_to_keycloak(self, _build_keycloak_login_url_mock):
        response = self.client.get(reverse("login") + "?start=1")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://auth.example.com/realms/carthographie/protocol/openid-connect/auth?x=1",
        )

    @override_settings(AUTH_MODE="keycloak")
    def test_login_page_shows_keycloak_entrypoint(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion sécurisée via Keycloak")
        self.assertContains(response, "Continuer avec Keycloak")

    def test_language_page_shows_fr_and_en_choices(self):
        response = self.client.get(reverse("language"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choix de la langue")
        self.assertContains(response, "🇫🇷 Français")
        self.assertContains(response, "🇬🇧 English")
        self.assertContains(response, reverse("set_language"))

    def test_set_language_redirects_back_to_language_page(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("language")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("language"))

    @override_settings(
        AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300
    )
    @patch("app_main.views.get_directory_user")
    def test_callback_creates_session_for_known_user(self, get_directory_user_mock):
        create_directory_user()
        get_directory_user_mock.return_value.to_session_dict.return_value = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
        }
        get_directory_user_mock.return_value.username = "known.user"

        params = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
            "ts": "1700000000",
        }

        with patch("app_main.auth.time.time", return_value=1700000100):
            params["sig"] = sign_callback_data(params, "shared-secret")
            response = self.client.get(reverse("auth_callback"), params, follow=True)

        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, "Connected as known.user.")
        self.assertContains(response, "known.user")
        self.assertContains(response, 'data-django-alias="logout"')
        self.assertContains(response, 'data-django-alias="account"')
        self.assertNotContains(response, 'data-django-alias="login"')
        self.assertNotContains(response, 'data-django-alias="signup"')

    @override_settings(
        AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300
    )
    @patch(
        "app_main.views.get_directory_user",
        side_effect=UnknownUserError("No matching user found in users.users."),
    )
    def test_callback_rejects_unknown_user(self, _get_directory_user_mock):
        params = {
            "external_id": "33333333-3333-3333-3333-333333333333",
            "username": "unknown.user",
            "email": "unknown.user@example.test",
            "first_name": "Unknown",
            "last_name": "User",
            "ts": "1700000000",
        }

        with patch("app_main.auth.time.time", return_value=1700000100):
            params["sig"] = sign_callback_data(params, "shared-secret")
            response = self.client.get(reverse("auth_callback"), params, follow=True)

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("No matching user found in users.users.", messages)
        self.assertNotIn("lss_user", self.client.session)

    @override_settings(AUTH_MODE="unsupported")
    def test_login_refuses_unsupported_auth_mode(self):
        response = self.client.get(reverse("login"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(
            "Interactive login is not configured for this environment.", messages
        )

    @override_settings(AUTH_MODE="keycloak")
    @patch("app_main.views.get_directory_user")
    @patch("app_main.views.validate_keycloak_callback")
    def test_keycloak_callback_creates_session_for_known_user(
        self,
        validate_keycloak_callback_mock,
        get_directory_user_mock,
    ):
        create_directory_user()
        validate_keycloak_callback_mock.return_value = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
        }
        get_directory_user_mock.return_value.to_session_dict.return_value = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
        }
        get_directory_user_mock.return_value.username = "known.user"
        get_directory_user_mock.return_value.external_id = (
            "11111111-1111-1111-1111-111111111111"
        )

        response = self.client.get(
            reverse("auth_callback"),
            {"code": "auth-code", "state": "state"},
            follow=True,
        )

        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, "Connected as known.user.")
        self.assertContains(response, 'data-django-alias="logout"')

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.validate_keycloak_callback",
        side_effect=KeycloakAuthError("Invalid Keycloak state."),
    )
    def test_keycloak_callback_rejects_invalid_state(
        self, _validate_keycloak_callback_mock
    ):
        response = self.client.get(
            reverse("auth_callback"), {"code": "auth-code", "state": "bad"}, follow=True
        )

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Invalid Keycloak state.", messages)

    def test_logout_clears_session(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
        }
        session.save()

        response = self.client.get(reverse("logout"))

        self.assertRedirects(response, reverse("homepage"))
        self.assertNotIn("lss_user", self.client.session)

    @override_settings(
        AUTH_MODE="keycloak",
        KEYCLOAK_SERVER_URL="https://auth.example.com",
        KEYCLOAK_REALM="carthographie",
        KEYCLOAK_CLIENT_ID="app_lss",
        KEYCLOAK_LOGOUT_REDIRECT_URI="https://lss.example.com/",
    )
    def test_logout_redirects_to_keycloak_when_enabled(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
        }
        session.save()

        response = self.client.get(reverse("logout"))

        self.assertRedirects(
            response, build_keycloak_logout_url(), fetch_redirect_response=False
        )
        self.assertNotIn("lss_user", self.client.session)

    def test_account_page_requires_authenticated_session(self):
        response = self.client.get(reverse("account"))

        self.assertRedirects(response, reverse("login"))

    def test_account_page_uses_session_user_identity(self):
        request = RequestFactory().get(reverse("account"))
        request.session = {
            "lss_user": {
                "external_id": "11111111-1111-1111-1111-111111111111",
                "username": "known.user",
                "email": "known.user@example.test",
                "first_name": "Known",
                "last_name": "User",
            }
        }
        request.user = type(
            "AuthenticatedUserStub",
            (),
            {
                "is_authenticated": True,
                "username": "known.user",
                "email": "known.user@example.test",
                "first_name": "Known",
                "last_name": "User",
                "external_id": "11111111-1111-1111-1111-111111111111",
                "is_moderator": False,
                "is_admin": False,
            },
        )()
        request.LANGUAGE_CODE = "fr"

        response = account(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compte de known.user")
        self.assertContains(response, "11111111-1111-1111-1111-111111111111")

    def test_removed_test_route_returns_404(self):
        response = self.client.get("/test/")

        self.assertEqual(response.status_code, 404)


class AccountRoleTests(TestCase):
    member_id = "11111111-1111-1111-1111-111111111111"

    def _build_request(
        self, method: str = "get", data=None, *, is_moderator=False, is_admin=False
    ):
        factory = RequestFactory()
        request = getattr(factory, method)(reverse("account"), data=data or {})
        request.session = {
            "lss_user": {
                "external_id": self.member_id,
                "username": "known.user",
                "email": "known.user@example.test",
                "first_name": "Known",
                "last_name": "User",
            }
        }
        request.user = type(
            "AuthenticatedUserStub",
            (),
            {
                "is_authenticated": True,
                "username": "known.user",
                "email": "known.user@example.test",
                "first_name": "Known",
                "last_name": "User",
                "external_id": self.member_id,
                "is_moderator": is_moderator,
                "is_admin": is_admin,
            },
        )()
        request.LANGUAGE_CODE = "fr"
        return request

    def test_account_page_shows_moderation_section_for_moderator(self):
        create_site_params(moderator_message="Message moderation")
        create_directory_user(id=self.member_id)
        MemberRole.objects.create(
            member_id=self.member_id, is_moderator=True, is_admin=False
        )
        request = self._build_request(is_moderator=True, is_admin=False)

        response = account(request)

        self.assertContains(response, "Message de modération")
        self.assertNotContains(response, "Paramètres administrateur")

    def test_account_page_shows_admin_and_moderation_sections_for_admin(self):
        create_site_params(
            admin_message="Message admin", moderator_message="Message moderation"
        )
        create_directory_user(id=self.member_id)
        MemberRole.objects.create(
            member_id=self.member_id, is_moderator=True, is_admin=True
        )
        request = self._build_request(is_moderator=True, is_admin=True)

        response = account(request)

        self.assertContains(response, "Message de modération")
        self.assertContains(response, "Paramètres administrateur")
        self.assertContains(response, "Membres du site")

    @patch("app_main.views.messages.success")
    def test_admin_can_update_member_role_from_account_page(
        self, _messages_success_mock
    ):
        create_site_params()
        create_directory_user(id=self.member_id)
        create_directory_user(
            id="22222222-2222-2222-2222-222222222222",
            username="future.user",
            email="future.user@example.test",
            first_name="Future",
            last_name="User",
        )
        MemberRole.objects.create(
            member_id=self.member_id, is_moderator=True, is_admin=True
        )
        request = self._build_request(
            method="post",
            data={
                "action": "update_member_role",
                "member_search": "future.user",
                "member_id": "22222222-2222-2222-2222-222222222222",
                "role_name": "moderator",
                "enabled": "on",
            },
            is_moderator=True,
            is_admin=True,
        )

        response = account(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], reverse("account") + "?member_search=future.user"
        )
        self.assertTrue(
            MemberRole.objects.filter(
                member_id="22222222-2222-2222-2222-222222222222",
                is_moderator=True,
                is_admin=False,
            ).exists()
        )


class BaseTemplatePopupTests(SimpleTestCase):
    def test_homepage_loads_message_box_root_and_script(self):
        response = self.client.get(reverse("homepage"))

        self.assertContains(response, 'id="lss-messagebox-root"')
        self.assertContains(response, "window.LSS_MESSAGE_BOX_CONFIG")
        self.assertContains(response, "/static/js/message_box.js")
        self.assertContains(response, "data-page-loader")
        self.assertContains(response, "data-page-content")
        self.assertContains(response, "window.LSS_PAGE_LOADER_CONFIG")
        self.assertContains(response, "Chargement...")

    def test_base_template_exposes_page_scripts_block_after_shared_popup_script(self):
        request = RequestFactory().get("/")
        request.user = AnonymousSessionUser()

        template = engines["django"].from_string(
            """
            {% extends "base.html" %}
            {% block page_title %}Popup test{% endblock %}
            {% block page_scripts %}<script src="/static/js/page-popup-test.js"></script>{% endblock %}
            """
        )

        rendered = template.render({"request": request, "language_code": "fr"})

        self.assertIn("/static/js/message_box.js", rendered)
        self.assertIn("/static/js/page-popup-test.js", rendered)
        self.assertIn("/static/js/page_loader.js", rendered)
        self.assertLess(
            rendered.index("/static/js/message_box.js"),
            rendered.index("/static/js/page-popup-test.js"),
        )
        self.assertLess(
            rendered.index("/static/js/page-popup-test.js"),
            rendered.index("/static/js/page_loader.js"),
        )

    def test_navigation_marks_logout_links_for_popup_confirmation(self):
        request = RequestFactory().get("/")
        request.user = type(
            "AuthenticatedUserStub",
            (),
            {
                "is_authenticated": True,
                "username": "known.user",
            },
        )()

        template = engines["django"].get_template("includes/nav.html")
        rendered = template.render({"request": request})

        self.assertIn('data-lss-logout-confirm="true"', rendered)

    def test_navigation_shows_admin_role_marker_on_account_link(self):
        request = RequestFactory().get("/")
        request.user = type(
            "AuthenticatedAdminUserStub",
            (),
            {
                "is_authenticated": True,
                "username": "admin.user",
                "is_admin": True,
                "is_moderator": True,
            },
        )()

        template = engines["django"].get_template("includes/nav.html")
        rendered = template.render({"request": request})

        self.assertIn('data-django-alias="account"', rendered)
        self.assertIn("👑", rendered)
        self.assertNotIn("⚖️", rendered)

    def test_navigation_shows_moderator_role_marker_on_account_link(self):
        request = RequestFactory().get("/")
        request.user = type(
            "AuthenticatedModeratorUserStub",
            (),
            {
                "is_authenticated": True,
                "username": "moderator.user",
                "is_admin": False,
                "is_moderator": True,
            },
        )()

        template = engines["django"].get_template("includes/nav.html")
        rendered = template.render({"request": request})

        self.assertIn('data-django-alias="account"', rendered)
        self.assertIn("⚖️", rendered)
        self.assertNotIn("👑", rendered)


class HeavyPageTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_heavy_page_is_available_in_debug_without_navigation_link(self):
        response = self.client.get(reverse("heavy"))
        homepage_response = self.client.get(reverse("homepage"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page lourde")
        self.assertContains(response, "heavy-image-gallery")
        self.assertContains(response, "readyDelayMs: 2000")
        self.assertNotContains(homepage_response, 'href="/heavy/"')

    @override_settings(DEBUG=False)
    def test_heavy_page_returns_404_when_debug_is_disabled(self):
        response = self.client.get(reverse("heavy"))

        self.assertEqual(response.status_code, 404)


class SitePopupContextTests(TestCase):
    def test_homepage_includes_admin_and_moderator_popup_sections(self):
        create_site_params(
            admin_message="Message admin", moderator_message="Message moderation"
        )

        response = self.client.get(reverse("homepage"))

        self.assertContains(response, "lss-site-popup-config")
        self.assertContains(response, "Message admin")
        self.assertContains(response, "Message moderation")

    def test_non_main_page_excludes_moderator_popup_message(self):
        create_site_params(
            admin_message="Message admin", moderator_message="Message moderation"
        )

        response = self.client.get(reverse("privacy_policy"))

        self.assertContains(response, "Message admin")
        self.assertNotContains(response, "Message moderation")
