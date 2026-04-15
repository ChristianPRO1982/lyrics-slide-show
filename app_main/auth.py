import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, replace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
from typing import Any

from django.conf import settings
from django.db import connection

from app_main.models import DirectoryUserRecord
from app_member.services import get_member_role_flags_safe

SESSION_USER_KEY = "lss_user"
KEYCLOAK_STATE_SESSION_KEY = "lss_keycloak_state"
VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_TEXT_FIELD_LENGTH = 255
logger = logging.getLogger("app_main.auth")


class AuthError(Exception):
    pass


class InvalidCallbackError(AuthError):
    pass


class UnknownUserError(AuthError):
    pass


class DisabledUserError(AuthError):
    pass


class KeycloakAuthError(AuthError):
    pass


@dataclass(frozen=True)
class DirectoryUser:
    external_id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    enabled: bool
    is_moderator: bool = False
    is_admin: bool = False

    def to_session_dict(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_moderator": self.is_moderator,
            "is_admin": self.is_admin,
        }


@dataclass(frozen=True)
class SessionUser:
    external_id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    is_moderator: bool = False
    is_admin: bool = False

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_username(self) -> str:
        return self.username


@dataclass(frozen=True)
class AnonymousSessionUser:
    username: str = ""
    is_moderator: bool = False
    is_admin: bool = False

    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def is_anonymous(self) -> bool:
        return True

    def get_username(self) -> str:
        return ""


def _validate_identifier(value: str) -> str:
    if not VALID_IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid SQL identifier: {value}")
    return value


def _mark_session_modified(session) -> None:
    if hasattr(session, "modified"):
        session.modified = True


def _signature_payload(data: dict[str, str]) -> str:
    return "\n".join(
        [
            data["external_id"],
            data["username"],
            data.get("email", ""),
            data.get("first_name", ""),
            data.get("last_name", ""),
            data["ts"],
        ]
    )


def sign_callback_data(data: dict[str, str], secret: str) -> str:
    payload = _signature_payload(data)
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_callback_payload(params: dict[str, str]) -> dict[str, str]:
    required_fields = ("external_id", "username", "email", "first_name", "last_name", "ts", "sig")
    missing = [field for field in required_fields if not params.get(field)]
    if missing:
        raise InvalidCallbackError(f"Missing callback fields: {', '.join(missing)}")

    try:
        timestamp = int(params["ts"])
    except (TypeError, ValueError) as exc:
        raise InvalidCallbackError("Invalid callback timestamp.") from exc

    age = abs(int(time.time()) - timestamp)
    if age > settings.AUTH_MOCK_MAX_AGE_SECONDS:
        raise InvalidCallbackError("Expired callback signature.")

    expected_sig = sign_callback_data(params, settings.AUTH_MOCK_SHARED_SECRET)
    if not hmac.compare_digest(expected_sig, params["sig"]):
        raise InvalidCallbackError("Invalid callback signature.")

    try:
        normalized_uuid = str(uuid.UUID(params["external_id"]))
    except (ValueError, TypeError) as exc:
        raise InvalidCallbackError("Invalid external_id format.") from exc

    for field in ("username", "email", "first_name", "last_name"):
        if len(params[field]) > MAX_TEXT_FIELD_LENGTH:
            raise InvalidCallbackError(f"Field too long: {field}.")

    return {
        "external_id": normalized_uuid,
        "username": params["username"],
        "email": params["email"],
        "first_name": params["first_name"],
        "last_name": params["last_name"],
    }


def _keycloak_oidc_base_url() -> str:
    if not settings.KEYCLOAK_SERVER_URL or not settings.KEYCLOAK_REALM:
        raise KeycloakAuthError("Keycloak is not configured for this environment.")
    return f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect"


def build_keycloak_login_url(session) -> str:
    if not settings.KEYCLOAK_CLIENT_ID or not settings.KEYCLOAK_REDIRECT_URI:
        raise KeycloakAuthError("Keycloak client configuration is incomplete.")
    state = secrets.token_urlsafe(32)
    session[KEYCLOAK_STATE_SESSION_KEY] = state
    _mark_session_modified(session)
    query_string = urlencode(
        {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "response_type": "code",
            "scope": settings.KEYCLOAK_SCOPES,
            "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
            "state": state,
        }
    )
    return f"{_keycloak_oidc_base_url()}/auth?{query_string}"


def build_keycloak_logout_url() -> str:
    if not settings.KEYCLOAK_CLIENT_ID or not settings.KEYCLOAK_LOGOUT_REDIRECT_URI:
        raise KeycloakAuthError("Keycloak logout configuration is incomplete.")
    query_string = urlencode(
        {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "post_logout_redirect_uri": settings.KEYCLOAK_LOGOUT_REDIRECT_URI,
        }
    )
    return f"{_keycloak_oidc_base_url()}/logout?{query_string}"


def _load_json_response(request: Request) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            response_body = ""
        logger.warning(
            "keycloak_http_error url=%s status=%s reason=%s body=%s",
            request.full_url,
            exc.code,
            exc.reason,
            response_body[:500],
        )
        raise KeycloakAuthError(f"Keycloak request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        logger.warning("keycloak_url_error url=%s reason=%s", request.full_url, exc.reason)
        raise KeycloakAuthError("Keycloak request failed.") from exc
    except TimeoutError as exc:
        logger.warning("keycloak_timeout url=%s", request.full_url)
        raise KeycloakAuthError("Keycloak request timed out.") from exc
    except json.JSONDecodeError as exc:
        logger.warning("keycloak_invalid_json url=%s", request.full_url)
        raise KeycloakAuthError("Keycloak request failed.") from exc


def _exchange_keycloak_code(code: str) -> dict[str, Any]:
    if not settings.KEYCLOAK_CLIENT_ID or not settings.KEYCLOAK_CLIENT_SECRET or not settings.KEYCLOAK_REDIRECT_URI:
        raise KeycloakAuthError("Keycloak token exchange configuration is incomplete.")
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        }
    ).encode("utf-8")
    request = Request(
        f"{_keycloak_oidc_base_url()}/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    payload = _load_json_response(request)
    if not payload.get("access_token"):
        raise KeycloakAuthError("Keycloak did not return an access token.")
    return payload


def _fetch_keycloak_userinfo(access_token: str) -> dict[str, Any]:
    request = Request(
        f"{_keycloak_oidc_base_url()}/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    return _load_json_response(request)


def validate_keycloak_callback(params: dict[str, str], session) -> dict[str, str]:
    if params.get("error"):
        raise KeycloakAuthError(f"Keycloak login failed: {params['error']}.")

    code = params.get("code", "")
    state = params.get("state", "")
    expected_state = session.get(KEYCLOAK_STATE_SESSION_KEY, "")
    session.pop(KEYCLOAK_STATE_SESSION_KEY, None)
    _mark_session_modified(session)

    if not code or not state:
        raise KeycloakAuthError("Missing Keycloak callback fields.")
    if not expected_state or not secrets.compare_digest(state, expected_state):
        raise KeycloakAuthError("Invalid Keycloak state.")

    token_payload = _exchange_keycloak_code(code)
    userinfo = _fetch_keycloak_userinfo(token_payload["access_token"])

    try:
        external_id = str(uuid.UUID(str(userinfo.get("sub", "")).strip()))
    except (TypeError, ValueError) as exc:
        raise KeycloakAuthError("Invalid Keycloak subject format.") from exc

    return {
        "external_id": external_id,
        "username": None,
        "email": None,
        "first_name": None,
        "last_name": None,
    }


def _user_lookup_sql() -> str:
    schema = _validate_identifier(settings.USER_SCHEMA)
    table = _validate_identifier(settings.USER_TABLE)
    enabled_expr = "enabled" if _user_table_has_column("enabled") else "TRUE AS enabled"
    return (
        f"SELECT id::text, username, email, first_name, last_name, {enabled_expr} "
        f'FROM "{schema}"."{table}" '
        f"WHERE id = %s"
    )


def _user_table_has_column(column_name: str) -> bool:
    schema = _validate_identifier(settings.USER_SCHEMA)
    table = _validate_identifier(settings.USER_TABLE)
    column = _validate_identifier(column_name)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            [schema, table, column],
        )
        return cursor.fetchone() is not None


def _directory_user_from_record(record: DirectoryUserRecord) -> DirectoryUser:
    user = DirectoryUser(
        external_id=str(record.id),
        username=record.username or "",
        email=record.email,
        first_name=record.first_name,
        last_name=record.last_name,
        enabled=record.enabled,
    )

    if not user.enabled:
        raise DisabledUserError("This user is disabled in users.users.")

    return user


def get_directory_user(external_id: str) -> DirectoryUser:
    try:
        normalized_id = uuid.UUID(str(external_id))
    except (TypeError, ValueError) as exc:
        raise UnknownUserError("No matching user found in users.users.") from exc

    if settings.USER_SCHEMA == "users" and settings.USER_TABLE == "users":
        try:
            record = DirectoryUserRecord.objects.get(pk=normalized_id)
        except DirectoryUserRecord.DoesNotExist as exc:
            raise UnknownUserError("No matching user found in users.users.") from exc
        return _directory_user_from_record(record)

    with connection.cursor() as cursor:
        cursor.execute(_user_lookup_sql(), [str(normalized_id)])
        row = cursor.fetchone()

    if row is None:
        raise UnknownUserError("No matching user found in users.users.")

    return _directory_user_from_record(
        DirectoryUserRecord(
            id=uuid.UUID(row[0]),
            username=row[1],
            email=row[2],
            first_name=row[3],
            last_name=row[4],
            enabled=row[5],
        )
    )


def store_session_user(session, user: DirectoryUser) -> None:
    session[SESSION_USER_KEY] = user.to_session_dict()
    _mark_session_modified(session)


def clear_session_user(session) -> None:
    session.pop(SESSION_USER_KEY, None)
    _mark_session_modified(session)


def get_session_user(session) -> dict[str, Any] | None:
    return session.get(SESSION_USER_KEY)


def get_request_user(session) -> SessionUser | AnonymousSessionUser:
    session_user = get_session_user(session)
    if not session_user:
        return AnonymousSessionUser()

    return SessionUser(
        external_id=session_user["external_id"],
        username=session_user["username"],
        email=session_user.get("email"),
        first_name=session_user.get("first_name"),
        last_name=session_user.get("last_name"),
        is_moderator=bool(session_user.get("is_moderator", False) or session_user.get("is_admin", False)),
        is_admin=bool(session_user.get("is_admin", False)),
    )


def refresh_request_user(session) -> SessionUser | AnonymousSessionUser:
    session_user = get_session_user(session)
    if not session_user:
        return AnonymousSessionUser()

    external_id = session_user.get("external_id")
    if not external_id:
        clear_session_user(session)
        return AnonymousSessionUser()

    try:
        user = get_directory_user(external_id)
    except (UnknownUserError, DisabledUserError):
        clear_session_user(session)
        return AnonymousSessionUser()

    roles = get_member_role_flags_safe(external_id)
    user = replace(user, is_moderator=roles.is_moderator, is_admin=roles.is_admin)
    store_session_user(session, user)
    return get_request_user(session)
