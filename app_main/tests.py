from unittest.mock import MagicMock, patch

from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from app_main.auth import (
    DisabledUserError,
    UnknownUserError,
    get_directory_user,
    sign_callback_data,
    validate_callback_payload,
)


class CallbackValidationTests(SimpleTestCase):
    @override_settings(AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300)
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

    @override_settings(AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300)
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

    @override_settings(AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300)
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


class DirectoryUserLookupTests(TestCase):
    def _patch_cursor(self, cursor_factory, fetchone_values):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetchone_values
        cursor_factory.return_value.__enter__.return_value = cursor
        return cursor

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_returns_enabled_user(self, cursor_factory):
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

        with self.settings(USER_SCHEMA="users", USER_TABLE="users"):
            user = get_directory_user("11111111-1111-1111-1111-111111111111")

        self.assertEqual(user.username, "known.user")
        self.assertEqual(cursor.execute.call_count, 2)

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_raises_unknown_user(self, cursor_factory):
        self._patch_cursor(cursor_factory, [(1,), None])

        with self.settings(USER_SCHEMA="users", USER_TABLE="users"):
            with self.assertRaises(UnknownUserError):
                get_directory_user("missing")

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_raises_disabled_user(self, cursor_factory):
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

        with self.settings(USER_SCHEMA="users", USER_TABLE="users"):
            with self.assertRaises(DisabledUserError):
                get_directory_user("22222222-2222-2222-2222-222222222222")

    @patch("app_main.auth.connection.cursor")
    def test_get_directory_user_defaults_to_enabled_when_column_is_missing(self, cursor_factory):
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

        with self.settings(USER_SCHEMA="users", USER_TABLE="users"):
            user = get_directory_user("11111111-1111-1111-1111-111111111111")

        self.assertEqual(user.username, "known.user")


class AuthFlowTests(TestCase):
    def test_homepage_shows_guest_state(self):
        response = self.client.get(reverse("homepage"))

        self.assertContains(response, reverse("login"))
        self.assertContains(response, 'data-django-alias="login"')
        self.assertContains(response, 'data-django-alias="signup"')

    @override_settings(AUTH_MOCK_BASE_URL="http://localhost:8001")
    def test_login_redirects_to_auth_mock(self):
        response = self.client.get(reverse("login") + "?start=1")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://localhost:8001/login?return_to="))

    def test_login_page_shows_mock_entrypoint(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mock SSO")
        self.assertContains(response, reverse("login") + "?start=1")

    @override_settings(AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300)
    @patch("app_main.views.get_directory_user")
    def test_callback_creates_session_for_known_user(self, get_directory_user_mock):
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

    @override_settings(AUTH_MOCK_SHARED_SECRET="shared-secret", AUTH_MOCK_MAX_AGE_SECONDS=300)
    @patch("app_main.views.get_directory_user", side_effect=UnknownUserError("No matching user found in users.users."))
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

    @override_settings(AUTH_MODE="prod")
    def test_login_refuses_unsupported_auth_mode(self):
        response = self.client.get(reverse("login"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Interactive login is not configured for this environment.", messages)

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

    def test_account_page_requires_authenticated_session(self):
        response = self.client.get(reverse("account"))

        self.assertRedirects(response, reverse("login"))

    def test_account_page_uses_session_user_identity(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": "11111111-1111-1111-1111-111111111111",
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
        }
        session.save()

        response = self.client.get(reverse("account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compte de known.user")
        self.assertContains(response, "11111111-1111-1111-1111-111111111111")
