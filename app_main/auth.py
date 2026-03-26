import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import connection


SESSION_USER_KEY = "lss_user"
VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthError(Exception):
    pass


class InvalidCallbackError(AuthError):
    pass


class UnknownUserError(AuthError):
    pass


class DisabledUserError(AuthError):
    pass


@dataclass(frozen=True)
class DirectoryUser:
    external_id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    enabled: bool

    def to_session_dict(self) -> dict[str, Any]:
        return {
            "external_id": self.external_id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }


def _validate_identifier(value: str) -> str:
    if not VALID_IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid SQL identifier: {value}")
    return value


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

    return {
        "external_id": params["external_id"],
        "username": params["username"],
        "email": params["email"],
        "first_name": params["first_name"],
        "last_name": params["last_name"],
    }


def _user_lookup_sql() -> str:
    schema = _validate_identifier(settings.USER_SCHEMA)
    table = _validate_identifier(settings.USER_TABLE)
    return (
        f'SELECT id::text, username, email, first_name, last_name, enabled '
        f'FROM "{schema}"."{table}" '
        f"WHERE id = %s"
    )


def get_directory_user(external_id: str) -> DirectoryUser:
    with connection.cursor() as cursor:
        cursor.execute(_user_lookup_sql(), [external_id])
        row = cursor.fetchone()

    if row is None:
        raise UnknownUserError("No matching user found in users.users.")

    user = DirectoryUser(
        external_id=row[0],
        username=row[1],
        email=row[2],
        first_name=row[3],
        last_name=row[4],
        enabled=row[5],
    )

    if not user.enabled:
        raise DisabledUserError("This user is disabled in users.users.")

    return user


def store_session_user(session, user: DirectoryUser) -> None:
    session[SESSION_USER_KEY] = user.to_session_dict()
    session.modified = True


def clear_session_user(session) -> None:
    session.pop(SESSION_USER_KEY, None)
    session.modified = True


def get_session_user(session) -> dict[str, Any] | None:
    return session.get(SESSION_USER_KEY)
