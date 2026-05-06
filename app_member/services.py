import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from app_main.models import DirectoryUserRecord, SiteParams
from app_member.models import MemberRole


MAIN_PAGE_NAMES = {
    "homepage",
    "groups",
    "songs",
    "animations",
}

ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"


@dataclass(frozen=True)
class MemberRoleFlags:
    is_moderator: bool = False
    is_admin: bool = False


@dataclass(frozen=True)
class DirectoryMemberSearchResult:
    member_id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    enabled: bool
    is_moderator: bool
    is_admin: bool


def _normalize_uuid(value: str) -> str:
    return str(uuid.UUID(str(value)))


def _validate_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[:1].isdigit():
        raise ValueError(f"Invalid SQL identifier: {value}")
    return value


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


def get_member_role_flags(member_id: str) -> MemberRoleFlags:
    normalized_id = _normalize_uuid(member_id)
    role = MemberRole.objects.filter(member_id=normalized_id).first()

    if role is None:
        return MemberRoleFlags()

    is_admin = bool(role.is_admin)
    is_moderator = bool(role.is_admin or role.is_moderator)
    return MemberRoleFlags(is_moderator=is_moderator, is_admin=is_admin)


def get_member_role_flags_safe(member_id: str | None) -> MemberRoleFlags:
    if not member_id:
        return MemberRoleFlags()

    try:
        return get_member_role_flags(member_id)
    except Exception:
        return MemberRoleFlags()


def set_member_role(member_id: str, role_name: str, enabled: bool) -> MemberRoleFlags:
    normalized_id = _normalize_uuid(member_id)
    role_name = str(role_name).strip().lower()

    if role_name not in {ROLE_ADMIN, ROLE_MODERATOR}:
        raise ValidationError(_("Rôle de membre non pris en charge."))

    role, _created = MemberRole.objects.get_or_create(member_id=normalized_id)

    if role_name == ROLE_ADMIN:
        role.is_admin = bool(enabled)
        if role.is_admin:
            role.is_moderator = True
    else:
        role.is_moderator = bool(enabled)
        if not role.is_moderator:
            role.is_admin = False

    if not role.is_admin and not role.is_moderator:
        role.delete()
        return MemberRoleFlags()

    role.full_clean()
    role.save()
    return MemberRoleFlags(is_moderator=role.is_moderator or role.is_admin, is_admin=role.is_admin)


def can_manage_site_members(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_admin", False))


def can_manage_site_settings(user) -> bool:
    return can_manage_site_members(user)


def can_manage_global_popup(user) -> bool:
    return can_manage_site_members(user)


def can_manage_moderator_popup(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_moderator", False))


def can_validate_songs(user) -> bool:
    return can_manage_moderator_popup(user)


def can_manage_groups_globally(user) -> bool:
    return can_manage_moderator_popup(user)


def get_site_params_for_language(language_code: str | None) -> SiteParams | None:
    normalized_language = (language_code or settings.LANGUAGE_CODE or "fr")[:2].lower()
    fallback_language = (settings.LANGUAGE_CODE or "fr")[:2].lower()

    try:
        params = SiteParams.objects.filter(language__iexact=normalized_language).first()
        if params is not None:
            return params
        if normalized_language != fallback_language:
            params = SiteParams.objects.filter(language__iexact=fallback_language).first()
            if params is not None:
                return params
        return SiteParams.objects.order_by("language").first()
    except Exception:
        return None


def _build_directory_user_queryset(search_term: str):
    return DirectoryUserRecord.objects.filter(
        Q(username__icontains=search_term)
        | Q(first_name__icontains=search_term)
        | Q(last_name__icontains=search_term)
        | Q(email__icontains=search_term)
    ).order_by("username", "email", "id")


def _search_directory_users_with_sql(search_term: str, limit: int) -> list[DirectoryMemberSearchResult]:
    schema = _validate_identifier(settings.USER_SCHEMA)
    table = _validate_identifier(settings.USER_TABLE)
    like_value = f"%{search_term}%"
    enabled_select = "enabled" if _user_table_has_column("enabled") else "TRUE AS enabled"

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id::text, username, email, first_name, last_name, {enabled_select}
            FROM "{schema}"."{table}"
            WHERE COALESCE(username, '') ILIKE %s
               OR COALESCE(first_name, '') ILIKE %s
               OR COALESCE(last_name, '') ILIKE %s
               OR COALESCE(email, '') ILIKE %s
            ORDER BY username NULLS LAST, email NULLS LAST, id
            LIMIT %s
            """,
            [like_value, like_value, like_value, like_value, limit],
        )
        rows = cursor.fetchall()

    role_map = {
        str(role.member_id): MemberRoleFlags(
            is_moderator=role.is_moderator or role.is_admin,
            is_admin=role.is_admin,
        )
        for role in MemberRole.objects.filter(member_id__in=[row[0] for row in rows])
    }

    return [
        DirectoryMemberSearchResult(
            member_id=row[0],
            username=row[1] or "",
            email=row[2],
            first_name=row[3],
            last_name=row[4],
            enabled=bool(row[5]),
            is_moderator=role_map.get(row[0], MemberRoleFlags()).is_moderator,
            is_admin=role_map.get(row[0], MemberRoleFlags()).is_admin,
        )
        for row in rows
    ]


def search_directory_members(search_term: str, limit: int = 20) -> list[DirectoryMemberSearchResult]:
    normalized_search = str(search_term or "").strip()
    if not normalized_search:
        return []

    if settings.USER_SCHEMA == "users" and settings.USER_TABLE == "users":
        rows = list(_build_directory_user_queryset(normalized_search)[:limit])
        role_map = {
            str(role.member_id): MemberRoleFlags(
                is_moderator=role.is_moderator or role.is_admin,
                is_admin=role.is_admin,
            )
            for role in MemberRole.objects.filter(member_id__in=[row.id for row in rows])
        }
        return [
            DirectoryMemberSearchResult(
                member_id=str(row.id),
                username=row.username or "",
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                enabled=bool(row.enabled),
                is_moderator=role_map.get(str(row.id), MemberRoleFlags()).is_moderator,
                is_admin=role_map.get(str(row.id), MemberRoleFlags()).is_admin,
            )
            for row in rows
        ]

    return _search_directory_users_with_sql(normalized_search, limit)
