import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone as datetime_timezone
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, urlencode
from urllib.request import Request, urlopen
import uuid
from typing import Any

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app_main.models import DirectoryUserRecord
from app_member.services import get_member_role_flags_safe

SESSION_USER_KEY = "lss_user"
KEYCLOAK_STATE_SESSION_KEY = "lss_keycloak_state"
HOME_PROVISION_TARGET_SESSION_KEY = "lss_home_provision_target"
PENDING_PROVISION_SESSION_KEY = "lss_pending_provision"
KEYCLOAK_DIAGNOSTIC_SESSION_KEY = "lss_keycloak_diagnostic"
VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_TEXT_FIELD_LENGTH = 255
PENDING_PROVISION_TTL_SECONDS = 15 * 60
HOME_PROVISION_RETURN_PATH = "/provision/complete/"
logger = logging.getLogger("app_main.auth")
SENSITIVE_KEYCLOAK_LOG_KEYS = (
    "client_secret",
    "access_token",
    "refresh_token",
    "id_token",
    "code",
)


class AuthError(Exception):
    pass


class InvalidCallbackError(AuthError):
    pass


class UnknownUserError(AuthError):
    pass


class DisabledUserError(AuthError):
    pass


class KeycloakAuthError(AuthError):
    def __init__(self, message: object, *, diagnostic: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


class HomeProvisioningError(AuthError):
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
        raise ValueError(_("Identifiant SQL invalide : %(value)s") % {"value": value})
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
    return hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _home_provision_signature_payload(
    app_id: str, return_url: str, ts: str, nonce: str
) -> str:
    return "\n".join([app_id, return_url, ts, nonce])


def _validate_home_provision_return_url(return_url: str) -> str:
    normalized_return_url = str(return_url or "").strip()
    error_message = _(
        "L'URL HOME_PROVISION_RETURN_URL doit être une URL HTTPS absolue pointant vers /provision/complete/."
    )

    if not normalized_return_url:
        raise HomeProvisioningError(error_message)

    parsed = urlsplit(normalized_return_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path != HOME_PROVISION_RETURN_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise HomeProvisioningError(error_message)

    return normalized_return_url


def build_home_provision_start_url() -> str:
    start_url = str(settings.HOME_PROVISION_START_URL or "").strip()
    app_id = str(settings.HOME_PROVISION_APP_ID or "").strip()
    shared_secret = str(settings.HOME_PROVISION_SHARED_SECRET or "").strip()
    return_url = _validate_home_provision_return_url(settings.HOME_PROVISION_RETURN_URL)

    if not shared_secret:
        raise HomeProvisioningError(
            _(
                "Le secret de provisioning Home est absent côté serveur Lyrics Slide Show."
            )
        )

    if not start_url or not app_id or not return_url:
        raise HomeProvisioningError(
            _("La configuration du provisioning Home est incomplète.")
        )

    ts = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    canonical = _home_provision_signature_payload(app_id, return_url, ts, nonce)
    sig = hmac.new(
        shared_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    query_string = urlencode(
        {
            "app_id": app_id,
            "return_url": return_url,
            "ts": ts,
            "nonce": nonce,
            "sig": sig,
        }
    )
    return f"{start_url}?{query_string}"


def validate_callback_payload(params: dict[str, str]) -> dict[str, str]:
    required_fields = (
        "external_id",
        "username",
        "email",
        "first_name",
        "last_name",
        "ts",
        "sig",
    )
    missing = [field for field in required_fields if not params.get(field)]
    if missing:
        raise InvalidCallbackError(
            _("Champs de retour manquants : %(fields)s")
            % {"fields": ", ".join(missing)}
        )

    try:
        timestamp = int(params["ts"])
    except (TypeError, ValueError) as exc:
        raise InvalidCallbackError(_("Horodatage de retour invalide.")) from exc

    age = abs(int(time.time()) - timestamp)
    if age > settings.AUTH_MOCK_MAX_AGE_SECONDS:
        raise InvalidCallbackError(_("Signature de retour expirée."))

    expected_sig = sign_callback_data(params, settings.AUTH_MOCK_SHARED_SECRET)
    if not hmac.compare_digest(expected_sig, params["sig"]):
        raise InvalidCallbackError(_("Signature de retour invalide."))

    try:
        normalized_uuid = str(uuid.UUID(params["external_id"]))
    except (ValueError, TypeError) as exc:
        raise InvalidCallbackError(_("Format d'identifiant externe invalide.")) from exc

    for field in ("username", "email", "first_name", "last_name"):
        if len(params[field]) > MAX_TEXT_FIELD_LENGTH:
            raise InvalidCallbackError(
                _("Champ trop long : %(field)s.") % {"field": field}
            )

    return {
        "external_id": normalized_uuid,
        "username": params["username"],
        "email": params["email"],
        "first_name": params["first_name"],
        "last_name": params["last_name"],
    }


def _keycloak_oidc_base_url() -> str:
    if not settings.KEYCLOAK_SERVER_URL or not settings.KEYCLOAK_REALM:
        raise KeycloakAuthError(
            _("Keycloak n'est pas configuré pour cet environnement.")
        )
    return f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect"


def build_keycloak_login_url(session) -> str:
    if not settings.KEYCLOAK_CLIENT_ID or not settings.KEYCLOAK_REDIRECT_URI:
        raise KeycloakAuthError(
            _("La configuration du client Keycloak est incomplète.")
        )
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
        raise KeycloakAuthError(
            _("La configuration de déconnexion Keycloak est incomplète.")
        )
    query_string = urlencode(
        {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "post_logout_redirect_uri": settings.KEYCLOAK_LOGOUT_REDIRECT_URI,
        }
    )
    return f"{_keycloak_oidc_base_url()}/logout?{query_string}"


def _safe_request_url(request: Request) -> str:
    parsed = urlsplit(request.full_url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _configured_file_exists(env_name: str, default_path: str = "") -> tuple[bool, bool]:
    file_path = os.environ.get(env_name, "").strip()
    if not file_path and default_path:
        file_path = default_path
    if not file_path:
        return False, False
    return True, Path(file_path).is_file()


def build_keycloak_diagnostic(
    *,
    stage: str,
    message: str,
    status_code: int | None = None,
    error: str = "",
    error_description: str = "",
    safe_url: str = "",
) -> dict[str, Any]:
    client_secret_file_configured, client_secret_file_exists = _configured_file_exists(
        "KEYCLOAK_CLIENT_SECRET_FILE"
    )
    _home_secret_file_configured, home_secret_file_exists = _configured_file_exists(
        "HOME_PROVISION_SHARED_SECRET_FILE",
        settings.HOME_PROVISION_SHARED_SECRET_DEFAULT_FILE,
    )
    return {
        "stage": str(stage or ""),
        "status_code": status_code,
        "error": str(error or ""),
        "error_description": str(error_description or ""),
        "message": str(message or ""),
        "safe_url": str(safe_url or ""),
        "server_url": settings.KEYCLOAK_SERVER_URL,
        "realm": settings.KEYCLOAK_REALM,
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
        "client_secret_configured": bool(settings.KEYCLOAK_CLIENT_SECRET),
        "client_secret_file_configured": client_secret_file_configured,
        "client_secret_file_exists": client_secret_file_exists,
        "home_secret_file_exists": home_secret_file_exists,
        "created_at": timezone.now().isoformat(),
    }


def _parse_keycloak_error_payload(response_body: str) -> tuple[str, str]:
    try:
        payload = json.loads(response_body)
    except (TypeError, json.JSONDecodeError):
        return "", ""

    if not isinstance(payload, dict):
        return "", ""

    return (
        _redact_keycloak_log_text(str(payload.get("error") or ""))[:120],
        _redact_keycloak_log_text(str(payload.get("error_description") or ""))[:300],
    )


def _redact_keycloak_log_text(value: str) -> str:
    output = str(value or "")
    for key in SENSITIVE_KEYCLOAK_LOG_KEYS:
        output = re.sub(
            rf'("{re.escape(key)}"\s*:\s*")[^"]*(")',
            r"\1[redacted]\2",
            output,
            flags=re.IGNORECASE,
        )
        output = re.sub(
            rf"({re.escape(key)}=)[^\s&]+",
            r"\1[redacted]",
            output,
            flags=re.IGNORECASE,
        )
    return output


def _keycloak_stage_label(stage: str) -> str:
    if stage == "token_exchange":
        return _("l'échange du code")
    if stage == "userinfo":
        return _("la lecture du profil utilisateur")
    return _("la requête")


def _keycloak_http_error_message(stage: str, status_code: int) -> str:
    if status_code == 401 and stage == "token_exchange":
        return _(
            "La connexion Keycloak a échoué pendant l'échange du code. Vérifiez la configuration du client LSS côté Keycloak."
        )
    if status_code == 401 and stage == "userinfo":
        return _(
            "La connexion Keycloak a échoué pendant la lecture du profil utilisateur."
        )
    return _("La requête Keycloak a échoué pendant %(stage)s avec HTTP %(code)s.") % {
        "stage": _keycloak_stage_label(stage),
        "code": status_code,
    }


def _load_json_response(request: Request, *, stage: str) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            response_body = ""
        error, error_description = _parse_keycloak_error_payload(response_body)
        message = str(_keycloak_http_error_message(stage, exc.code))
        safe_url = _safe_request_url(request)
        logger.warning(
            "keycloak_http_error stage=%s url=%s status=%s reason=%s error=%s error_description=%s body=%s",
            stage,
            safe_url,
            exc.code,
            exc.reason,
            error,
            error_description,
            _redact_keycloak_log_text(response_body)[:500],
        )
        raise KeycloakAuthError(
            message,
            diagnostic=build_keycloak_diagnostic(
                stage=stage,
                message=message,
                status_code=exc.code,
                error=error,
                error_description=error_description,
                safe_url=safe_url,
            ),
        ) from exc
    except URLError as exc:
        message = str(_("La requête Keycloak a échoué."))
        logger.warning(
            "keycloak_url_error stage=%s url=%s reason=%s",
            stage,
            _safe_request_url(request),
            exc.reason,
        )
        raise KeycloakAuthError(
            message,
            diagnostic=build_keycloak_diagnostic(
                stage=stage, message=message, safe_url=_safe_request_url(request)
            ),
        ) from exc
    except TimeoutError as exc:
        message = str(_("La requête Keycloak a expiré."))
        logger.warning(
            "keycloak_timeout stage=%s url=%s", stage, _safe_request_url(request)
        )
        raise KeycloakAuthError(
            message,
            diagnostic=build_keycloak_diagnostic(
                stage=stage, message=message, safe_url=_safe_request_url(request)
            ),
        ) from exc
    except json.JSONDecodeError as exc:
        message = str(_("La requête Keycloak a échoué."))
        logger.warning(
            "keycloak_invalid_json stage=%s url=%s", stage, _safe_request_url(request)
        )
        raise KeycloakAuthError(
            message,
            diagnostic=build_keycloak_diagnostic(
                stage=stage, message=message, safe_url=_safe_request_url(request)
            ),
        ) from exc


def _exchange_keycloak_code(code: str) -> dict[str, Any]:
    if (
        not settings.KEYCLOAK_CLIENT_ID
        or not settings.KEYCLOAK_CLIENT_SECRET
        or not settings.KEYCLOAK_REDIRECT_URI
    ):
        raise KeycloakAuthError(
            _("La configuration d'échange de jeton Keycloak est incomplète.")
        )
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        }
    ).encode("utf-8")
    logger.info(
        "keycloak_config stage=token_exchange server_url=%s realm=%s client_id=%s redirect_uri=%s client_secret_configured=%s",
        settings.KEYCLOAK_SERVER_URL,
        settings.KEYCLOAK_REALM,
        settings.KEYCLOAK_CLIENT_ID,
        settings.KEYCLOAK_REDIRECT_URI,
        bool(settings.KEYCLOAK_CLIENT_SECRET),
    )
    request = Request(
        f"{_keycloak_oidc_base_url()}/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    payload = _load_json_response(request, stage="token_exchange")
    if not payload.get("access_token"):
        raise KeycloakAuthError(_("Keycloak n'a pas renvoyé de jeton d'accès."))
    return payload


def _fetch_keycloak_userinfo(access_token: str) -> dict[str, Any]:
    request = Request(
        f"{_keycloak_oidc_base_url()}/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    return _load_json_response(request, stage="userinfo")


def validate_keycloak_callback(params: dict[str, str], session) -> dict[str, str]:
    if params.get("error"):
        raise KeycloakAuthError(
            _("La connexion Keycloak a échoué : %(error)s.")
            % {"error": params["error"]}
        )

    code = params.get("code", "")
    state = params.get("state", "")
    expected_state = session.get(KEYCLOAK_STATE_SESSION_KEY, "")
    session.pop(KEYCLOAK_STATE_SESSION_KEY, None)
    _mark_session_modified(session)

    if not code or not state:
        raise KeycloakAuthError(_("Champs de retour Keycloak manquants."))
    if not expected_state or not secrets.compare_digest(state, expected_state):
        raise KeycloakAuthError(_("État Keycloak invalide."))

    token_payload = _exchange_keycloak_code(code)
    userinfo = _fetch_keycloak_userinfo(token_payload["access_token"])

    try:
        external_id = str(uuid.UUID(str(userinfo.get("sub", "")).strip()))
    except (TypeError, ValueError) as exc:
        raise KeycloakAuthError(_("Format de sujet Keycloak invalide.")) from exc

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
        raise DisabledUserError(_("Cet utilisateur est désactivé dans users.users."))

    return user


def get_directory_user(external_id: str) -> DirectoryUser:
    try:
        normalized_id = uuid.UUID(str(external_id))
    except (TypeError, ValueError) as exc:
        raise UnknownUserError(
            _("Aucun utilisateur correspondant n'a été trouvé dans users.users.")
        ) from exc

    if settings.USER_SCHEMA == "users" and settings.USER_TABLE == "users":
        try:
            record = DirectoryUserRecord.objects.get(pk=normalized_id)
        except DirectoryUserRecord.DoesNotExist as exc:
            raise UnknownUserError(
                _("Aucun utilisateur correspondant n'a été trouvé dans users.users.")
            ) from exc
        return _directory_user_from_record(record)

    with connection.cursor() as cursor:
        cursor.execute(_user_lookup_sql(), [str(normalized_id)])
        row = cursor.fetchone()

    if row is None:
        raise UnknownUserError(
            _("Aucun utilisateur correspondant n'a été trouvé dans users.users.")
        )

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


def store_pending_provision_state(
    session, *, external_id: str, auth_mode: str = "keycloak"
) -> None:
    session[PENDING_PROVISION_SESSION_KEY] = {
        "external_id": str(external_id or "").strip(),
        "created_at": timezone.now().isoformat(),
        "auth_mode": str(auth_mode or "").strip(),
    }
    _mark_session_modified(session)


def clear_pending_provision_state(session) -> None:
    session.pop(PENDING_PROVISION_SESSION_KEY, None)
    _mark_session_modified(session)


def get_pending_provision_state(
    session, *, clear_expired: bool = True
) -> dict[str, Any] | None:
    payload = session.get(PENDING_PROVISION_SESSION_KEY)
    if not isinstance(payload, dict):
        return None

    external_id = str(payload.get("external_id") or "").strip()
    auth_mode = str(payload.get("auth_mode") or "").strip()
    created_at_raw = str(payload.get("created_at") or "").strip()
    if not external_id or auth_mode != "keycloak" or not created_at_raw:
        if clear_expired:
            clear_pending_provision_state(session)
        return None

    try:
        created_at = datetime.fromisoformat(created_at_raw)
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at, datetime_timezone.utc)
    except ValueError:
        if clear_expired:
            clear_pending_provision_state(session)
        return None

    age_seconds = (timezone.now() - created_at).total_seconds()
    if age_seconds > PENDING_PROVISION_TTL_SECONDS:
        if clear_expired:
            clear_pending_provision_state(session)
        return None

    return {
        "external_id": external_id,
        "created_at": created_at_raw,
        "auth_mode": auth_mode,
    }


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
        is_moderator=bool(
            session_user.get("is_moderator", False)
            or session_user.get("is_admin", False)
        ),
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
