import hashlib
import hmac
import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch
from io import BytesIO
from urllib.parse import parse_qs, urlparse

from django.core.management import call_command
from django.contrib.messages import get_messages
from django.template import engines
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_mock.server import load_mock_users
from lyrics_slide_show.settings import env_secret_with_default_file
from app_main.auth import (
    AnonymousSessionUser,
    DISABLED_USER_MESSAGE,
    DirectoryUser,
    DisabledUserError,
    HomeProvisioningError,
    KeycloakAuthError,
    UNKNOWN_USER_MESSAGE,
    UnknownUserError,
    build_home_provision_start_url,
    build_keycloak_logout_url,
    get_directory_user,
    _load_json_response,
    refresh_request_user,
    sign_callback_data,
    validate_keycloak_callback,
    validate_callback_payload,
)
from app_main.lyrics import (
    LYRICS_BLOCK_STYLE_CHORUS,
    LYRICS_BLOCK_STYLE_CHORUS_LIKE,
    LYRICS_BLOCK_STYLE_VERSE,
    build_lyrics_page_context,
    build_lyrics_song_entry,
    build_qr_png_base64,
)
from app_main.mock_accounts import DEV_MOCK_ACCOUNTS, dev_mock_accounts_json
from app_main.models import DirectoryUserRecord, SiteParams
from app_member.models import MemberRole
from app_member.forms import SiteParamsAdminForm
from app_member.services import MemberRoleFlags
from app_song.models import Song, SongMessage, SongStatus, Verse
from app_song.rendering import ChorusRenderMode, SongRenderSettings
from app_main.views import (
    _collect_heavy_images,
    _keycloak_diagnostic_causes,
    _parse_home_cards,
    account,
)


def create_site_params(**overrides):
    defaults = {
        "language": "fr",
        "title": "Lyrics Slide Show",
        "title_h1": "Lyrics Slide Show",
        "signup_url": "",
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


class AuthMockAccountConfigTests(SimpleTestCase):
    def test_load_mock_users_defaults_to_three_supported_profiles(self):
        with patch.dict(os.environ, {"AUTH_MOCK_USERS_JSON": ""}, clear=False):
            users = load_mock_users()

        self.assertEqual(users, DEV_MOCK_ACCOUNTS)
        self.assertEqual(
            [entry["username"] for entry in users],
            [
                "testmock",
                "disabled.user",
                "unknown.user",
                "testmock_moderateur",
                "testmock_simpletuser",
            ],
        )

    def test_env_dev_example_lists_same_mock_accounts_as_python_defaults(self):
        env_file = Path(__file__).resolve().parent.parent / ".env.dev.example"
        content = env_file.read_text(encoding="utf-8")
        auth_mock_users_json = next(
            line.split("=", 1)[1]
            for line in content.splitlines()
            if line.startswith("AUTH_MOCK_USERS_JSON=")
        )

        self.assertEqual(auth_mock_users_json, dev_mock_accounts_json())


class SyncAuthMockAccountsCommandTests(TestCase):
    def test_sync_auth_mock_accounts_upserts_directory_users_and_local_roles(self):
        create_directory_user(
            id="11111111-1111-1111-1111-111111111111",
            username="legacy-admin",
            email="legacy-admin@example.test",
            first_name="Legacy",
            last_name="Admin",
            enabled=False,
        )
        create_directory_user(
            id="33333333-3333-3333-3333-333333333333",
            username="unknown.user",
            email="unknown.user@example.test",
            first_name="Unknown",
            last_name="User",
            enabled=True,
        )
        MemberRole.objects.create(
            member_id="33333333-3333-3333-3333-333333333333",
            is_moderator=True,
            is_admin=False,
        )

        call_command("sync_auth_mock_accounts")

        admin_user = DirectoryUserRecord.objects.get(
            pk="11111111-1111-1111-1111-111111111111"
        )
        disabled_user = DirectoryUserRecord.objects.get(
            pk="22222222-2222-2222-2222-222222222222"
        )
        moderator_user = DirectoryUserRecord.objects.get(
            pk="44444444-4444-4444-4444-444444444444"
        )
        simple_user = DirectoryUserRecord.objects.get(
            pk="55555555-5555-5555-5555-555555555555"
        )

        self.assertEqual(admin_user.username, "testmock")
        self.assertTrue(admin_user.enabled)
        self.assertEqual(disabled_user.username, "disabled.user")
        self.assertFalse(disabled_user.enabled)
        self.assertEqual(moderator_user.username, "testmock_moderateur")
        self.assertEqual(simple_user.username, "testmock_simpletuser")

        admin_role = MemberRole.objects.get(member_id=admin_user.id)
        moderator_role = MemberRole.objects.get(member_id=moderator_user.id)
        self.assertTrue(admin_role.is_admin)
        self.assertTrue(admin_role.is_moderator)
        self.assertFalse(moderator_role.is_admin)
        self.assertTrue(moderator_role.is_moderator)
        self.assertFalse(
            DirectoryUserRecord.objects.filter(
                pk="33333333-3333-3333-3333-333333333333"
            ).exists()
        )
        self.assertFalse(MemberRole.objects.filter(member_id=disabled_user.id).exists())
        self.assertFalse(MemberRole.objects.filter(member_id=simple_user.id).exists())


class CallbackValidationTests(SimpleTestCase):
    def test_env_secret_with_default_file_prefers_explicit_file(self):
        with TemporaryDirectory() as temp_dir:
            explicit_path = Path(temp_dir) / "explicit-secret.txt"
            default_path = Path(temp_dir) / "default-secret.txt"
            explicit_path.write_text("explicit-secret\n", encoding="utf-8")
            default_path.write_text("default-secret\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"HOME_PROVISION_SHARED_SECRET_FILE": str(explicit_path)},
                clear=False,
            ):
                value = env_secret_with_default_file(
                    "HOME_PROVISION_SHARED_SECRET", str(default_path)
                )

        self.assertEqual(value, "explicit-secret")

    def test_env_secret_with_default_file_uses_env_value_before_default_file(self):
        with TemporaryDirectory() as temp_dir:
            default_path = Path(temp_dir) / "default-secret.txt"
            default_path.write_text("default-secret\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "HOME_PROVISION_SHARED_SECRET": "env-secret",
                    "HOME_PROVISION_SHARED_SECRET_FILE": "",
                },
                clear=False,
            ):
                value = env_secret_with_default_file(
                    "HOME_PROVISION_SHARED_SECRET", str(default_path)
                )

        self.assertEqual(value, "env-secret")

    def test_env_secret_with_default_file_uses_default_file_when_env_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            default_path = Path(temp_dir) / "default-secret.txt"
            default_path.write_text("default-secret\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "HOME_PROVISION_SHARED_SECRET": "",
                    "HOME_PROVISION_SHARED_SECRET_FILE": "",
                },
                clear=False,
            ):
                value = env_secret_with_default_file(
                    "HOME_PROVISION_SHARED_SECRET", str(default_path)
                )

        self.assertEqual(value, "default-secret")

    def test_env_secret_with_default_file_uses_default_file_when_explicit_file_is_missing(
        self,
    ):
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing-secret.txt"
            default_path = Path(temp_dir) / "default-secret.txt"
            default_path.write_text("default-secret\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "HOME_PROVISION_SHARED_SECRET": "",
                    "HOME_PROVISION_SHARED_SECRET_FILE": str(missing_path),
                },
                clear=False,
            ):
                value = env_secret_with_default_file(
                    "HOME_PROVISION_SHARED_SECRET", str(default_path)
                )

        self.assertEqual(value, "default-secret")

    @override_settings(
        HOME_PROVISION_START_URL="https://carthographie.fr/provision/start",
        HOME_PROVISION_APP_ID="lss",
        HOME_PROVISION_SHARED_SECRET="shared-secret",
        HOME_PROVISION_RETURN_URL="https://lss.carthographie.fr/provision/complete/",
    )
    @patch("app_main.auth.secrets.token_urlsafe", return_value="nonce-value")
    @patch("app_main.auth.time.time", return_value=1700000100)
    def test_build_home_provision_start_url_signs_expected_payload(
        self, _time_mock, _nonce_mock
    ):
        provision_url = build_home_provision_start_url()

        parsed = urlparse(provision_url)
        params = parse_qs(parsed.query)
        self.assertEqual(
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "https://carthographie.fr/provision/start",
        )
        self.assertEqual(params["app_id"], ["lss"])
        self.assertEqual(
            params["return_url"], ["https://lss.carthographie.fr/provision/complete/"]
        )
        self.assertEqual(params["ts"], ["1700000100"])
        self.assertEqual(params["nonce"], ["nonce-value"])
        expected_sig = hmac.new(
            b"shared-secret",
            "\n".join(
                [
                    "lss",
                    "https://lss.carthographie.fr/provision/complete/",
                    "1700000100",
                    "nonce-value",
                ]
            ).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(params["sig"], [expected_sig])

    @override_settings(
        HOME_PROVISION_START_URL="https://carthographie.fr/provision/start",
        HOME_PROVISION_APP_ID="lss",
        HOME_PROVISION_SHARED_SECRET="shared-secret",
        HOME_PROVISION_RETURN_URL="",
    )
    def test_build_home_provision_start_url_requires_explicit_return_url(self):
        with self.assertRaisesMessage(
            HomeProvisioningError,
            "L'URL HOME_PROVISION_RETURN_URL doit être une URL HTTPS absolue pointant vers /provision/complete/.",
        ):
            build_home_provision_start_url()

    def test_build_home_provision_start_url_rejects_invalid_return_url_targets(self):
        invalid_return_urls = (
            "https://lss.carthographie.fr/",
            "https://lss.carthographie.fr/auth/callback/",
            "https://lss.carthographie.fr/login/?start=1",
            "https://lss.carthographie.fr/provision/complete/#fragment",
            "http://lss.carthographie.fr/provision/complete/",
            "https://lss.carthographie.fr/provision/complete/?step=1",
        )

        for invalid_return_url in invalid_return_urls:
            with self.subTest(return_url=invalid_return_url):
                with override_settings(
                    HOME_PROVISION_START_URL="https://carthographie.fr/provision/start",
                    HOME_PROVISION_APP_ID="lss",
                    HOME_PROVISION_SHARED_SECRET="shared-secret",
                    HOME_PROVISION_RETURN_URL=invalid_return_url,
                ):
                    with self.assertRaisesMessage(
                        HomeProvisioningError,
                        "L'URL HOME_PROVISION_RETURN_URL doit être une URL HTTPS absolue pointant vers /provision/complete/.",
                    ):
                        build_home_provision_start_url()

    @patch("app_main.auth.urlopen")
    def test_keycloak_token_exchange_401_has_actionable_message_and_safe_logs(
        self, urlopen_mock
    ):
        request = MagicMock()
        request.full_url = "https://auth.example.com/realms/carthographie/protocol/openid-connect/token"
        error_body = (
            b'{"error":"invalid_client","error_description":"Invalid client secret"}'
        )
        urlopen_mock.side_effect = HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(error_body),
        )

        with self.assertLogs("app_main.auth", level="WARNING") as logs:
            with self.assertRaisesMessage(
                KeycloakAuthError,
                "La connexion Keycloak a échoué pendant l'échange du code. Vérifiez la configuration du client LSS côté Keycloak.",
            ) as captured:
                _load_json_response(request, stage="token_exchange")

        diagnostic = captured.exception.diagnostic
        self.assertEqual(diagnostic["stage"], "token_exchange")
        self.assertEqual(diagnostic["status_code"], 401)
        self.assertEqual(diagnostic["error"], "invalid_client")
        self.assertEqual(diagnostic["error_description"], "Invalid client secret")
        log_output = "\n".join(logs.output)
        self.assertIn("stage=token_exchange", log_output)
        self.assertIn("status=401", log_output)
        self.assertIn("error=invalid_client", log_output)
        self.assertIn("error_description=Invalid client secret", log_output)
        self.assertNotIn("client_secret=", log_output)
        self.assertNotIn("access_token", log_output)
        self.assertNotIn("code=", log_output)

    def test_keycloak_diagnostic_causes_include_unauthorized_client(self):
        causes = _keycloak_diagnostic_causes(
            {
                "stage": "token_exchange",
                "status_code": 401,
                "error": "unauthorized_client",
            }
        )

        self.assertIn("Secret client Keycloak invalide", causes[0])
        self.assertNotIn("Consultez les logs LSS", causes)

    @patch("app_main.auth.urlopen")
    def test_keycloak_userinfo_401_has_distinct_message(self, urlopen_mock):
        request = MagicMock()
        request.full_url = "https://auth.example.com/realms/carthographie/protocol/openid-connect/userinfo"
        error_body = b'{"error":"invalid_token","error_description":"Token invalid"}'
        urlopen_mock.side_effect = HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(error_body),
        )

        with self.assertLogs("app_main.auth", level="WARNING") as logs:
            with self.assertRaisesMessage(
                KeycloakAuthError,
                "La connexion Keycloak a échoué pendant la lecture du profil utilisateur.",
            ):
                _load_json_response(request, stage="userinfo")

        log_output = "\n".join(logs.output)
        self.assertIn("stage=userinfo", log_output)
        self.assertIn("status=401", log_output)
        self.assertIn("error=invalid_token", log_output)

    @patch("app_main.auth.urlopen")
    def test_keycloak_http_error_log_strips_query_from_url(self, urlopen_mock):
        request = MagicMock()
        request.full_url = (
            "https://auth.example.com/realms/carthographie/protocol/openid-connect/token?"
            "code=auth-code&client_secret=secret-value"
        )
        urlopen_mock.side_effect = HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(
                b'{"error":"invalid_grant","client_secret":"secret-value","access_token":"token-value","code":"auth-code"}'
            ),
        )

        with self.assertLogs("app_main.auth", level="WARNING") as logs:
            with self.assertRaisesMessage(
                KeycloakAuthError,
                "La requête Keycloak a échoué pendant l'échange du code avec HTTP 400.",
            ):
                _load_json_response(request, stage="token_exchange")

        log_output = "\n".join(logs.output)
        self.assertIn(
            "url=https://auth.example.com/realms/carthographie/protocol/openid-connect/token",
            log_output,
        )
        self.assertNotIn("auth-code", log_output)
        self.assertNotIn("secret-value", log_output)
        self.assertNotIn("token-value", log_output)

    @override_settings(
        HOME_PROVISION_START_URL="https://carthographie.fr/provision/start",
        HOME_PROVISION_APP_ID="lss",
        HOME_PROVISION_SHARED_SECRET="",
        HOME_PROVISION_RETURN_URL="https://lss.carthographie.fr/provision/complete/",
    )
    def test_build_home_provision_start_url_requires_secret(self):
        with self.assertRaisesMessage(
            HomeProvisioningError,
            "Le secret de provisioning Home est absent côté serveur Lyrics Slide Show.",
        ):
            build_home_provision_start_url()

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
            with self.assertRaisesMessage(Exception, "Signature de retour invalide."):
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
            with self.assertRaisesMessage(
                Exception, "Format d'identifiant externe invalide."
            ):
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

        with self.assertRaisesMessage(KeycloakAuthError, "État Keycloak invalide."):
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
        side_effect=DisabledUserError(DISABLED_USER_MESSAGE),
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
        self.assertContains(response, 'href="#"')

    def test_homepage_uses_signup_url_from_site_params(self):
        create_site_params(signup_url="https://signup.example.test/register")

        response = self.client.get(reverse("homepage"))

        self.assertContains(response, 'href="https://signup.example.test/register"')

    def test_homepage_shows_expected_marketing_content(self):
        response = self.client.get(reverse("homepage"))

        self.assertContains(response, "Lyrics Slide Show")
        self.assertContains(response, "Politique de confidentialité")
        self.assertContains(
            response,
            "Parfait pour une soirée louange, une animation musicale ou un concert improvisé.",
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
        self.assertContains(response, "🇬🇧 Anglais")
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
        self.assertContains(response, "Connecté en tant que known.user.")
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
        side_effect=UnknownUserError(UNKNOWN_USER_MESSAGE),
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
        self.assertIn(str(UNKNOWN_USER_MESSAGE), messages)
        self.assertNotIn("lss_user", self.client.session)

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.get_directory_user",
        side_effect=UnknownUserError(UNKNOWN_USER_MESSAGE),
    )
    @patch(
        "app_main.views.build_home_provision_start_url",
        return_value=(
            "https://carthographie.fr/provision/start?"
            "app_id=lss&"
            "return_url=https%3A%2F%2Flss.carthographie.fr%2Fprovision%2Fcomplete%2F&"
            "ts=1700000100&"
            "nonce=nonce-value&"
            "sig=sig-value"
        ),
    )
    @patch(
        "app_main.views.validate_keycloak_callback",
        return_value={
            "external_id": "33333333-3333-3333-3333-333333333333",
            "username": None,
            "email": None,
            "first_name": None,
            "last_name": None,
        },
    )
    def test_keycloak_callback_redirects_unknown_user_to_home_provisioning(
        self,
        _validate_keycloak_callback_mock,
        build_home_provision_start_url_mock,
        _get_directory_user_mock,
    ):
        response = self.client.get(
            reverse("auth_callback"),
            {"code": "auth-code", "state": "state"},
            follow=True,
        )

        self.assertRedirects(response, reverse("provision_redirect"))
        self.assertContains(response, "https://carthographie.fr/provision/start?")
        self.assertContains(response, "app_id=lss")
        self.assertContains(
            response,
            "return_url=https%3A%2F%2Flss.carthographie.fr%2Fprovision%2Fcomplete%2F",
        )
        self.assertContains(response, "ts=1700000100")
        self.assertContains(response, "nonce=nonce-value")
        self.assertContains(response, "sig=sig-value")
        self.assertContains(response, "Continuer vers cARThographie")
        self.assertContains(response, "window.location.assign")
        self.assertNotIn("lss_user", self.client.session)
        pending = self.client.session["lss_pending_provision"]
        self.assertEqual(pending["external_id"], "33333333-3333-3333-3333-333333333333")
        self.assertEqual(pending["auth_mode"], "keycloak")
        build_home_provision_start_url_mock.assert_called_once_with()

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.get_directory_user",
        side_effect=UnknownUserError(UNKNOWN_USER_MESSAGE),
    )
    @patch(
        "app_main.views.build_home_provision_start_url",
        side_effect=HomeProvisioningError(
            "Le secret de provisioning Home est absent côté serveur Lyrics Slide Show."
        ),
    )
    @patch(
        "app_main.views.validate_keycloak_callback",
        return_value={
            "external_id": "33333333-3333-3333-3333-333333333333",
            "username": None,
            "email": None,
            "first_name": None,
            "last_name": None,
        },
    )
    def test_keycloak_callback_returns_homepage_when_provisioning_config_fails(
        self,
        _validate_keycloak_callback_mock,
        _build_home_provision_start_url_mock,
        _get_directory_user_mock,
    ):
        session = self.client.session
        session["lss_pending_provision"] = {
            "external_id": "stale-user",
            "created_at": timezone.now().isoformat(),
            "auth_mode": "keycloak",
        }
        session["lss_home_provision_target"] = "https://stale.example.test/"
        session.save()

        response = self.client.get(
            reverse("auth_callback"),
            {"code": "auth-code", "state": "state"},
            follow=True,
        )

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(
            "Le secret de provisioning Home est absent côté serveur Lyrics Slide Show.",
            messages,
        )
        self.assertNotContains(response, "Continuer vers cARThographie")
        self.assertNotIn("lss_user", self.client.session)
        self.assertNotIn("lss_pending_provision", self.client.session)
        self.assertNotIn("lss_home_provision_target", self.client.session)

    def test_provision_redirect_without_session_target_returns_homepage(self):
        response = self.client.get(reverse("provision_redirect"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Aucune synchronisation de compte n'est en attente.", messages)

    def test_provision_complete_without_pending_state_returns_homepage(self):
        response = self.client.get(reverse("provision_complete"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(
            "Aucune finalisation de synchronisation n'est en attente.",
            messages,
        )

    def test_provision_complete_creates_session_when_user_is_now_available(self):
        create_directory_user(id="33333333-3333-3333-3333-333333333333")
        session = self.client.session
        session["lss_pending_provision"] = {
            "external_id": "33333333-3333-3333-3333-333333333333",
            "created_at": timezone.now().isoformat(),
            "auth_mode": "keycloak",
        }
        session["lss_home_provision_target"] = (
            "https://carthographie.fr/provision/start"
        )
        session.save()

        response = self.client.get(reverse("provision_complete"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(
            response,
            "Connecté en tant que known.user après synchronisation du compte.",
        )
        self.assertNotIn("lss_pending_provision", self.client.session)
        self.assertNotIn("lss_home_provision_target", self.client.session)
        self.assertEqual(
            self.client.session["lss_user"]["external_id"],
            "33333333-3333-3333-3333-333333333333",
        )

    @patch(
        "app_main.views.get_directory_user",
        side_effect=UnknownUserError("No matching user found in users.users."),
    )
    def test_provision_complete_renders_retry_page_when_user_is_still_missing(
        self, _get_directory_user_mock
    ):
        session = self.client.session
        session["lss_pending_provision"] = {
            "external_id": "33333333-3333-3333-3333-333333333333",
            "created_at": timezone.now().isoformat(),
            "auth_mode": "keycloak",
        }
        session.save()

        response = self.client.get(reverse("provision_complete"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R\u00e9essayer la synchronisation")
        self.assertContains(response, reverse("provision_complete"))
        self.assertContains(response, reverse("login") + "?start=1")
        self.assertIn("lss_pending_provision", self.client.session)
        self.assertNotIn("lss_user", self.client.session)

    @patch(
        "app_main.views.get_directory_user",
        side_effect=DisabledUserError(DISABLED_USER_MESSAGE),
    )
    def test_provision_complete_clears_pending_state_for_disabled_user(
        self, _get_directory_user_mock
    ):
        session = self.client.session
        session["lss_pending_provision"] = {
            "external_id": "33333333-3333-3333-3333-333333333333",
            "created_at": timezone.now().isoformat(),
            "auth_mode": "keycloak",
        }
        session.save()

        response = self.client.get(reverse("provision_complete"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(str(DISABLED_USER_MESSAGE), messages)
        self.assertNotIn("lss_pending_provision", self.client.session)
        self.assertNotIn("lss_user", self.client.session)

    def test_provision_complete_rejects_expired_pending_state(self):
        session = self.client.session
        session["lss_pending_provision"] = {
            "external_id": "33333333-3333-3333-3333-333333333333",
            "created_at": (timezone.now() - timedelta(minutes=16)).isoformat(),
            "auth_mode": "keycloak",
        }
        session.save()

        response = self.client.get(reverse("provision_complete"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(
            "Aucune finalisation de synchronisation n'est en attente.",
            messages,
        )
        self.assertNotIn("lss_pending_provision", self.client.session)

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.get_directory_user",
        side_effect=DisabledUserError(DISABLED_USER_MESSAGE),
    )
    @patch("app_main.views.build_home_provision_start_url")
    @patch(
        "app_main.views.validate_keycloak_callback",
        return_value={
            "external_id": "44444444-4444-4444-4444-444444444444",
            "username": None,
            "email": None,
            "first_name": None,
            "last_name": None,
        },
    )
    def test_keycloak_callback_does_not_provision_disabled_user(
        self,
        _validate_keycloak_callback_mock,
        build_home_provision_start_url_mock,
        _get_directory_user_mock,
    ):
        response = self.client.get(
            reverse("auth_callback"),
            {"code": "auth-code", "state": "state"},
            follow=True,
        )

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(str(DISABLED_USER_MESSAGE), messages)
        build_home_provision_start_url_mock.assert_not_called()
        self.assertNotIn("lss_user", self.client.session)

    @override_settings(AUTH_MODE="unsupported")
    def test_login_refuses_unsupported_auth_mode(self):
        response = self.client.get(reverse("login"), follow=True)

        self.assertRedirects(response, reverse("homepage"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn(
            "La connexion interactive n'est pas configurée pour cet environnement.",
            messages,
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
        self.assertContains(response, "Connecté en tant que known.user.")
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

    @override_settings(AUTH_MODE="keycloak")
    @patch(
        "app_main.views.validate_keycloak_callback",
        side_effect=KeycloakAuthError(
            "La connexion Keycloak a échoué pendant l'échange du code. Vérifiez la configuration du client LSS côté Keycloak.",
            diagnostic={
                "stage": "token_exchange",
                "status_code": 401,
                "error": "invalid_client",
                "error_description": "Invalid client secret",
                "message": "La connexion Keycloak a échoué pendant l'échange du code. Vérifiez la configuration du client LSS côté Keycloak.",
                "safe_url": "https://auth.example.com/realms/carthographie/protocol/openid-connect/token",
                "server_url": "https://auth.example.com",
                "realm": "carthographie",
                "client_id": "app_lss",
                "redirect_uri": "https://lss.carthographie.fr/auth/callback/",
                "client_secret_configured": True,
                "client_secret_file_configured": True,
                "client_secret_file_exists": False,
                "home_secret_file_exists": True,
                "created_at": "2026-06-08T10:00:00+00:00",
            },
        ),
    )
    def test_keycloak_callback_stores_expert_diagnostic(
        self, _validate_keycloak_callback_mock
    ):
        response = self.client.get(
            reverse("auth_callback"), {"code": "auth-code", "state": "bad"}, follow=True
        )

        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, reverse("keycloak_diagnostic"))
        diagnostic = self.client.session["lss_keycloak_diagnostic"]
        self.assertEqual(diagnostic["stage"], "token_exchange")
        self.assertEqual(diagnostic["status_code"], 401)
        self.assertEqual(diagnostic["error"], "invalid_client")

    def test_keycloak_diagnostic_page_without_session_diagnostic_shows_empty_state(
        self,
    ):
        response = self.client.get(reverse("keycloak_diagnostic"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune tentative Keycloak récente")

    def test_keycloak_diagnostic_page_hides_sensitive_values(self):
        session = self.client.session
        session["lss_keycloak_diagnostic"] = {
            "stage": "token_exchange",
            "status_code": 401,
            "error": "invalid_client",
            "error_description": "Invalid client secret",
            "message": "La connexion Keycloak a échoué pendant l'échange du code.",
            "safe_url": "https://auth.example.com/realms/carthographie/protocol/openid-connect/token",
            "server_url": "https://auth.example.com",
            "realm": "carthographie",
            "client_id": "app_lss",
            "redirect_uri": "https://lss.carthographie.fr/auth/callback/",
            "client_secret_configured": True,
            "client_secret_file_configured": True,
            "client_secret_file_exists": False,
            "home_secret_file_exists": True,
            "created_at": "2026-06-08T10:00:00+00:00",
        }
        session.save()

        response = self.client.get(reverse("keycloak_diagnostic"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "token_exchange")
        self.assertContains(response, "invalid_client")
        self.assertContains(response, "app_lss")
        self.assertContains(response, "Fichier secret client présent")
        self.assertNotContains(response, "client_secret=")
        self.assertNotContains(response, "access_token")
        self.assertNotContains(response, "auth-code")

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
        self.assertContains(response, "data-account-moderation-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertNotContains(response, "Paramètres administrateur")
        self.assertRegex(
            response.content.decode(),
            r'class="site-role-banner song-tag-badge">⚖️\s*Modérateur</p>',
        )
        self.assertNotRegex(
            response.content.decode(),
            r'class="site-role-banner song-tag-badge">👑\s*Administrateur</p>',
        )

    def test_account_page_hides_role_banners_for_plain_member(self):
        create_site_params()
        create_directory_user(id=self.member_id)
        request = self._build_request(is_moderator=False, is_admin=False)

        response = account(request)

        self.assertNotIn('class="site-role-banner"', response.content.decode())

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
        self.assertContains(response, "data-account-moderation-form")
        self.assertContains(response, "data-account-admin-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertContains(response, "Membres du site")
        self.assertRegex(
            response.content.decode(),
            r'class="site-role-banner song-tag-badge">👑\s*Administrateur</p>',
        )
        self.assertRegex(
            response.content.decode(),
            r'class="site-role-banner song-tag-badge">⚖️\s*Modérateur</p>',
        )
        self.assertRegex(
            response.content.decode(),
            r'👑\s*Administrateur</p>\s*<p class="site-role-banner song-tag-badge">⚖️\s*Modérateur',
        )

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
        self.assertIn("⚖️", rendered)
        self.assertIn("site-nav-role-marker--admin", rendered)
        self.assertIn("site-nav-role-marker--moderator", rendered)
        self.assertIn("site-nav-role-marker--top", rendered)
        self.assertIn("site-nav-role-marker--bottom", rendered)

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
        self.assertIn("site-nav-role-marker--moderator", rendered)
        self.assertIn("site-nav-role-marker--bottom", rendered)
        self.assertNotIn("site-nav-role-marker--admin", rendered)

    def test_navigation_uses_signup_url_when_provided(self):
        request = RequestFactory().get("/")
        request.user = type(
            "AnonymousUserStub",
            (),
            {
                "is_authenticated": False,
            },
        )()

        template = engines["django"].get_template("includes/nav.html")
        rendered = template.render(
            {
                "request": request,
                "lss_signup_url": "https://signup.example.test/register",
            }
        )

        self.assertIn('href="https://signup.example.test/register"', rendered)


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


class HomepageModerationCardTests(TestCase):
    user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    def setUp(self):
        create_site_params()
        create_directory_user(
            id=self.user_id,
            username="homepage.moderator",
            email="homepage.moderator@example.test",
        )

    def _login(self, *, moderator=False):
        MemberRole.objects.filter(member_id=self.user_id).delete()
        if moderator:
            MemberRole.objects.create(
                member_id=self.user_id,
                is_moderator=True,
                is_admin=False,
            )
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "homepage.moderator",
            "email": "homepage.moderator@example.test",
            "first_name": "Homepage",
            "last_name": "Moderator",
            "is_moderator": moderator,
            "is_admin": False,
        }
        session.save()

    def test_homepage_shows_moderation_card_for_moderator(self):
        song = Song.objects.create(
            title="Moderation homepage",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        SongMessage.objects.create(
            song=song,
            message="A moderer",
            is_read=False,
            date=timezone.now(),
        )
        self._login(moderator=True)

        response = self.client.get(reverse("homepage"))

        self.assertContains(response, "Chants à modérer")
        self.assertContains(response, "Moderation homepage ✔️⁉️")

    def test_homepage_hides_moderation_card_for_plain_member(self):
        song = Song.objects.create(
            title="Moderation homepage",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        SongMessage.objects.create(
            song=song,
            message="A moderer",
            is_read=False,
            date=timezone.now(),
        )
        self._login(moderator=False)

        response = self.client.get(reverse("homepage"))

        self.assertNotContains(response, "Chants à modérer")


class MainViewHelperCoverageTests(SimpleTestCase):
    def test_home_card_parser_handles_plain_invalid_and_structured_payloads(self):
        self.assertEqual(_parse_home_cards(None), [])
        self.assertEqual(
            _parse_home_cards("Texte historique"),
            [{"title": "", "text": "Texte historique"}],
        )
        self.assertEqual(_parse_home_cards("[]"), [])
        self.assertEqual(_parse_home_cards('{"cards": "bad"}'), [])
        self.assertEqual(
            _parse_home_cards(
                '{"cards": [null, {}, {"title": " T ", "text": " X "}, '
                '{"title": "", "text": ""}]}'
            ),
            [{"title": "T", "text": "X"}],
        )

    def test_collect_heavy_images_filters_sorts_and_builds_both_url_types(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "nested" / "b.PNG").write_bytes(b"png")
            (root / "a.jpg").write_bytes(b"jpg")
            (root / "ignore.txt").write_text("ignore", encoding="utf-8")

            lss_images = _collect_heavy_images(root, source="lss")
            static_images = _collect_heavy_images(root, source="static")

        self.assertEqual(
            [item["relative_path"] for item in lss_images],
            ["a.jpg", "nested/b.PNG"],
        )
        self.assertEqual(lss_images[0]["url"], "/heavy/assets/a.jpg")
        self.assertEqual(static_images[0]["url"], "/static/a.jpg")

    def test_collect_heavy_images_returns_empty_for_missing_or_non_directory(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            file_path = root / "file.jpg"
            file_path.write_bytes(b"jpg")
            self.assertEqual(_collect_heavy_images(file_path, source="lss"), [])
            self.assertEqual(_collect_heavy_images(root / "missing", source="lss"), [])


class SharedLyricsHelperTests(TestCase):
    def test_build_lyrics_song_entry_maps_rendered_blocks_to_expected_styles(self):
        song = Song.objects.create(
            title="Espoir", subtitle="Veillee", status=SongStatus.NOT_VALIDATED
        )
        Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=True,
            text="Refrain commun",
        )
        Verse.objects.create(
            song=song,
            num=4,
            num_verse=1,
            chorus=False,
            text="Couplet simple",
        )
        Verse.objects.create(
            song=song,
            num=6,
            num_verse=2,
            chorus=False,
            chorus_like=True,
            prefix="Pont",
            text="Pont final",
        )

        entry = build_lyrics_song_entry(
            song,
            anchor_id="lyrics-song-1",
            mode=ChorusRenderMode.FULL,
            settings=SongRenderSettings.defaults(),
        )

        self.assertEqual(entry["song_id"], song.song_id)
        self.assertEqual(entry["song_title"], "Espoir - Veillee")
        self.assertEqual(entry["anchor_id"], "lyrics-song-1")
        self.assertEqual(
            entry["blocks"],
            [
                {
                    "prefix": "Refrain",
                    "style": LYRICS_BLOCK_STYLE_CHORUS,
                    "text": "Refrain commun",
                },
                {
                    "prefix": "Couplet 1",
                    "style": LYRICS_BLOCK_STYLE_VERSE,
                    "text": "Couplet simple",
                },
                {
                    "prefix": "Refrain",
                    "style": LYRICS_BLOCK_STYLE_CHORUS,
                    "text": "Refrain commun",
                },
                {
                    "prefix": "Pont",
                    "style": LYRICS_BLOCK_STYLE_CHORUS_LIKE,
                    "text": "Pont final",
                },
                {
                    "prefix": "Refrain",
                    "style": LYRICS_BLOCK_STYLE_CHORUS,
                    "text": "Refrain commun",
                },
            ],
        )

    def test_build_lyrics_page_context_keeps_order_and_duplicate_entries(self):
        songs = [
            {
                "song_id": 4,
                "song_title": "Alpha",
                "song_url": "/songs/4/",
                "anchor_id": "lyrics-song-1",
                "blocks": [],
            },
            {
                "song_id": 4,
                "song_title": "Alpha",
                "song_url": "/songs/4/",
                "anchor_id": "lyrics-song-2",
                "blocks": [],
            },
        ]

        context = build_lyrics_page_context(
            page_title="Session",
            share_url="https://example.test/public",
            songs=songs,
        )

        self.assertEqual(context["page_title"], "Session")
        self.assertEqual(context["share_url"], "https://example.test/public")
        self.assertEqual(context["songs"], songs)
        self.assertTrue(context["has_multiple_songs"])

    def test_build_qr_png_base64_returns_empty_string_when_qrcode_missing(self):
        with patch("app_main.lyrics.qrcode", None):
            self.assertEqual(build_qr_png_base64("https://example.test"), "")


class HeavyAssetCoverageTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_heavy_page_prefers_lss_and_asset_endpoint_serves_images(self):
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            lss_dir = base_dir / "LSS"
            lss_dir.mkdir()
            (lss_dir / "image.png").write_bytes(b"image-bytes")
            (lss_dir / "not-image.txt").write_text("text", encoding="utf-8")

            with override_settings(BASE_DIR=base_dir):
                page = self.client.get(reverse("heavy"))
                asset = self.client.get(
                    reverse("heavy_asset", kwargs={"asset_path": "image.png"})
                )
                missing = self.client.get(
                    reverse("heavy_asset", kwargs={"asset_path": "not-image.txt"})
                )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["image_source"], "LSS")
        self.assertContains(page, "image.png")
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(b"".join(asset.streaming_content), b"image-bytes")
        self.assertTrue(asset.headers["Content-Type"].startswith("image/png"))
        self.assertEqual(missing.status_code, 404)

    @override_settings(DEBUG=False)
    def test_heavy_asset_is_hidden_outside_debug(self):
        response = self.client.get(
            reverse("heavy_asset", kwargs={"asset_path": "image.png"})
        )
        self.assertEqual(response.status_code, 404)


class AccountActionCoverageTests(TestCase):
    admin_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    target_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def setUp(self):
        create_directory_user(
            id=self.admin_id,
            username="admin.user",
            email="admin@example.test",
            first_name="Admin",
            last_name="User",
        )
        create_directory_user(
            id=self.target_id,
            username="target.user",
            email="target@example.test",
            first_name="Target",
            last_name="User",
        )

    def _login(self, *, moderator=False, admin=False):
        MemberRole.objects.filter(member_id=self.admin_id).delete()
        if moderator or admin:
            MemberRole.objects.create(
                member_id=self.admin_id,
                is_moderator=moderator or admin,
                is_admin=admin,
            )
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.admin_id,
            "username": "admin.user",
            "email": "admin@example.test",
            "first_name": "Admin",
            "last_name": "User",
            "is_moderator": moderator or admin,
            "is_admin": admin,
        }
        session.save()

    def _admin_form_payload(self, instance, *, language="fr"):
        form = SiteParamsAdminForm(instance=instance, prefix="admin-settings")
        payload = {"action": "save_site_settings", "language": language}
        for name in form.fields:
            value = form.initial.get(name, "")
            if value is None:
                value = ""
            payload[f"admin-settings-{name}"] = str(value)
        return payload

    def test_account_rejects_privileged_actions_for_plain_member(self):
        self._login()
        for action in (
            "save_moderation_settings",
            "save_site_settings",
            "update_member_role",
        ):
            with self.subTest(action=action):
                response = self.client.post(reverse("account"), {"action": action})
                self.assertEqual(response.status_code, 403)

    def test_moderator_missing_params_redirects_and_valid_form_saves(self):
        self._login(moderator=True)
        missing = self.client.post(
            reverse("account"),
            {
                "action": "save_moderation_settings",
                "member_search": "target",
                "moderation-moderator_message": "Message",
                "moderation-moderator_message_cooldown_minutes": "10",
            },
        )
        self.assertRedirects(missing, reverse("account") + "?member_search=target")

        params = create_site_params()
        saved = self.client.post(
            reverse("account"),
            {
                "action": "save_moderation_settings",
                "moderation-moderator_message": "Nouveau message",
                "moderation-moderator_message_cooldown_minutes": "15",
            },
        )
        self.assertRedirects(saved, reverse("account"))
        params.refresh_from_db()
        self.assertEqual(params.moderator_message, "Nouveau message")
        self.assertEqual(params.moderator_message_cooldown_minutes, 15)

    def test_admin_invalid_forms_render_with_search_results(self):
        params = create_site_params()
        self._login(admin=True)

        invalid_moderation = self.client.post(
            reverse("account"),
            {
                "action": "save_moderation_settings",
                "member_search": "target",
                "moderation-moderator_message": "Message",
                "moderation-moderator_message_cooldown_minutes": "bad",
            },
        )
        self.assertEqual(invalid_moderation.status_code, 200)
        self.assertEqual(len(invalid_moderation.context["member_results"]), 1)

        invalid_admin = self._admin_form_payload(params)
        invalid_admin["member_search"] = "target"
        invalid_admin["admin-settings-title"] = ""
        response = self.client.post(reverse("account"), invalid_admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["member_results"]), 1)
        self.assertIn("title", response.context["admin_form"].errors)

    def test_admin_saves_site_settings_and_searches_members(self):
        params = create_site_params()
        self._login(admin=True)
        payload = self._admin_form_payload(params)
        payload["member_search"] = "target"
        payload["admin-settings-title"] = "Nouveau titre"
        payload["admin-settings-signup_url"] = "https://signup.example.test/register"

        response = self.client.post(reverse("account"), payload)
        self.assertRedirects(response, reverse("account") + "?member_search=target")
        params.refresh_from_db()
        self.assertEqual(params.title, "Nouveau titre")
        self.assertEqual(params.signup_url, "https://signup.example.test/register")

        search = self.client.get(reverse("account"), {"member_search": "target"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.context["member_results"]), 1)

    def test_admin_role_actions_cover_remove_invalid_and_unknown(self):
        create_site_params()
        self._login(admin=True)
        MemberRole.objects.create(
            member_id=self.target_id, is_moderator=True, is_admin=False
        )
        removed = self.client.post(
            reverse("account"),
            {
                "action": "update_member_role",
                "member_id": self.target_id,
                "role_name": "moderator",
                "enabled": "",
                "member_search": "target",
            },
        )
        self.assertRedirects(removed, reverse("account") + "?member_search=target")
        self.assertFalse(MemberRole.objects.filter(member_id=self.target_id).exists())

        invalid = self.client.post(
            reverse("account"),
            {
                "action": "update_member_role",
                "member_id": "invalid",
                "role_name": "invalid",
                "member_search": "target",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(len(invalid.context["member_results"]), 1)

        unknown = self.client.post(
            reverse("account"),
            {"action": "unknown", "member_search": " target "},
        )
        self.assertRedirects(unknown, reverse("account") + "?member_search=target")


class SiteParamsViewCoverageTests(TestCase):
    admin_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    def setUp(self):
        create_directory_user(
            id=self.admin_id,
            username="site.admin",
            email="site.admin@example.test",
            first_name="Site",
            last_name="Admin",
        )

    def _login(self, *, admin):
        MemberRole.objects.filter(member_id=self.admin_id).delete()
        if admin:
            MemberRole.objects.create(
                member_id=self.admin_id, is_moderator=True, is_admin=True
            )
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.admin_id,
            "username": "site.admin",
            "email": "site.admin@example.test",
            "first_name": "Site",
            "last_name": "Admin",
            "is_moderator": admin,
            "is_admin": admin,
        }
        session.save()

    def _payload(self, params, language="en"):
        form = SiteParamsAdminForm(instance=params, prefix="admin-settings")
        payload = {"language": language}
        for name in form.fields:
            value = form.initial.get(name, "")
            payload[f"admin-settings-{name}"] = "" if value is None else str(value)
        return payload

    def test_site_params_requires_admin_and_normalizes_language(self):
        self.assertRedirects(self.client.get(reverse("site_params")), reverse("login"))
        self._login(admin=False)
        self.assertEqual(self.client.get(reverse("site_params")).status_code, 404)

        self._login(admin=True)
        response = self.client.get(reverse("site_params"), {"language": "zz"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-site-params-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertEqual(response.context["selected_language"], "fr")

    def test_site_params_valid_post_creates_language_record(self):
        source = create_site_params(language="FR")
        self._login(admin=True)
        payload = self._payload(source, language="en")
        payload["admin-settings-title"] = "English title"
        payload["admin-settings-signup_url"] = "https://signup.example.test/enroll"

        response = self.client.post(reverse("site_params"), payload)
        self.assertRedirects(
            response,
            reverse("site_params") + "?language=en",
            fetch_redirect_response=False,
        )
        self.assertEqual(SiteParams.objects.get(language="EN").title, "English title")
        self.assertEqual(
            SiteParams.objects.get(language="EN").signup_url,
            "https://signup.example.test/enroll",
        )

    def test_site_params_invalid_post_reports_named_fields(self):
        params = create_site_params(language="FR")
        self._login(admin=True)
        payload = self._payload(params, language="invalid")
        payload["admin-settings-title"] = ""

        response = self.client.post(reverse("site_params"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_language"], "fr")
        self.assertContains(response, "informations manquantes ou invalides")
        self.assertContains(response, "Titre du site")
