from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from typing import Iterable

from django.contrib import messages
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404
from django.utils.translation import gettext as _

from app_main.models import DirectoryUserRecord
from app_member.services import can_manage_groups_globally

from .models import Group, GroupJoinRequest, GroupMembership, GroupStatus


SELECTED_GROUP_ID_SESSION_KEY = "lss_selected_group_id"
SELECTED_GROUP_SECRET_SESSION_KEY = "lss_selected_group_secret"


@dataclass(frozen=True)
class DirectoryUserSummary:
    member_id: str
    username: str
    first_name: str
    last_name: str

    @property
    def display_name(self) -> str:
        full_name = " ".join(part for part in [self.first_name, self.last_name] if part).strip()
        return full_name or self.username or self.member_id


def get_member_id_from_user(user) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    external_id = getattr(user, "external_id", None)
    if not external_id:
        return None
    return str(uuid.UUID(str(external_id)))


def get_business_status(group: Group) -> str:
    if group.status == GroupStatus.PRIVATE and group.secret_ciphertext:
        return "private_with_secret"
    return group.status


def get_status_icon(group: Group) -> str:
    business_status = get_business_status(group)
    if business_status == GroupStatus.OPEN:
        return "🌐"
    if business_status == "private_with_secret":
        return "🔐📱"
    return "🔐"


def get_status_label(group: Group) -> str:
    business_status = get_business_status(group)
    if business_status == GroupStatus.OPEN:
        return _("Ouvert")
    if business_status == "private_with_secret":
        return _("Fermé avec secret")
    return _("Fermé")


def generate_group_secret() -> str:
    return secrets.token_urlsafe(24)


def get_delete_confirmation_word(language_code: str | None) -> str:
    if str(language_code or "").lower().startswith("fr"):
        return "SUPPRIMER"
    return "DELETE"


def normalize_member_id(value: str) -> str:
    return str(uuid.UUID(str(value)))


def fetch_directory_users(member_ids: Iterable[str]) -> dict[str, DirectoryUserSummary]:
    normalized_ids = [normalize_member_id(member_id) for member_id in member_ids]
    if not normalized_ids:
        return {}

    rows = DirectoryUserRecord.objects.filter(id__in=normalized_ids)
    summaries = {
        str(row.id): DirectoryUserSummary(
            member_id=str(row.id),
            username=row.username or str(row.id),
            first_name=row.first_name or "",
            last_name=row.last_name or "",
        )
        for row in rows
    }

    for member_id in normalized_ids:
        summaries.setdefault(
            member_id,
            DirectoryUserSummary(
                member_id=member_id,
                username=member_id,
                first_name="",
                last_name="",
            ),
        )
    return summaries


def user_can_manage_group(user, membership: GroupMembership | None) -> bool:
    if can_manage_groups_globally(user):
        return True
    return bool(getattr(user, "is_authenticated", False) and membership and membership.is_group_admin)


def user_can_select_group(user, group: Group, membership: GroupMembership | None, session_secret: str | None = None) -> bool:
    if group.status == GroupStatus.OPEN:
        return True
    if membership is not None:
        return True
    return bool(group.secret_ciphertext and session_secret and secrets.compare_digest(session_secret, group.secret_ciphertext))


def mark_session_modified(session) -> None:
    if hasattr(session, "modified"):
        session.modified = True


def select_group(session, group: Group, access_secret: str | None = None) -> None:
    session[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
    if access_secret:
        session[SELECTED_GROUP_SECRET_SESSION_KEY] = access_secret
    else:
        session.pop(SELECTED_GROUP_SECRET_SESSION_KEY, None)
    mark_session_modified(session)


def clear_selected_group(session) -> None:
    session.pop(SELECTED_GROUP_ID_SESSION_KEY, None)
    session.pop(SELECTED_GROUP_SECRET_SESSION_KEY, None)
    mark_session_modified(session)


def get_selected_group_state(request) -> tuple[Group | None, bool]:
    selected_group_id = request.session.get(SELECTED_GROUP_ID_SESSION_KEY)
    if not selected_group_id:
        return None, False

    try:
        group = Group.objects.get(group_id=selected_group_id)
    except Group.DoesNotExist:
        clear_selected_group(request.session)
        return None, False

    member_id = get_member_id_from_user(request.user)
    membership = None
    if member_id:
        membership = GroupMembership.objects.filter(group_id=group.group_id, member_id=member_id).first()

    secret = request.session.get(SELECTED_GROUP_SECRET_SESSION_KEY)
    if user_can_select_group(request.user, group, membership, secret):
        return group, bool(secret and not membership)

    clear_selected_group(request.session)
    return None, False


def require_group_manager(user, group: Group, membership: GroupMembership | None) -> None:
    if not user_can_manage_group(user, membership):
        raise Http404


def get_group_or_404(group_id: int) -> Group:
    group = Group.objects.filter(group_id=group_id).first()
    if group is None:
        raise Http404
    return group


def add_duplicate_name_message(request) -> None:
    messages.info(
        request,
        _("Un autre groupe utilise déjà ce nom, même avec une casse différente."),
    )


def is_last_group_admin(group: Group, member_id: str) -> bool:
    if not GroupMembership.objects.filter(group_id=group.group_id, member_id=member_id, is_group_admin=True).exists():
        return False
    return GroupMembership.objects.filter(group_id=group.group_id, is_group_admin=True).count() == 1


def ensure_not_last_group_admin(group: Group, member_id: str) -> None:
    if is_last_group_admin(group, member_id):
        raise ValueError(_("Le dernier responsable du groupe ne peut pas perdre ce rôle."))


def accept_join_request(group: Group, member_id: str) -> None:
    normalized_member_id = normalize_member_id(member_id)
    with transaction.atomic():
        GroupMembership.objects.create(
            group_id=group.group_id,
            member_id=normalized_member_id,
            is_group_admin=False,
        )
        GroupJoinRequest.objects.filter(group_id=group.group_id, member_id=normalized_member_id).delete()


def remove_member(group: Group, member_id: str) -> None:
    normalized_member_id = normalize_member_id(member_id)
    ensure_not_last_group_admin(group, normalized_member_id)
    GroupMembership.objects.filter(group_id=group.group_id, member_id=normalized_member_id).delete()
    GroupJoinRequest.objects.filter(group_id=group.group_id, member_id=normalized_member_id).delete()


def set_group_admin(group: Group, member_id: str, enabled: bool) -> None:
    normalized_member_id = normalize_member_id(member_id)
    membership = GroupMembership.objects.filter(group_id=group.group_id, member_id=normalized_member_id).first()
    if membership is None:
        raise ValueError(_("Ce membre n'appartient pas au groupe."))
    if not enabled:
        ensure_not_last_group_admin(group, normalized_member_id)
    membership.is_group_admin = bool(enabled)
    membership.save(update_fields=["is_group_admin"])


def list_group_memberships(group: Group) -> QuerySet[GroupMembership]:
    return GroupMembership.objects.filter(group_id=group.group_id).order_by("-is_group_admin", "member_id")


def list_group_join_requests(group: Group) -> QuerySet[GroupJoinRequest]:
    return GroupJoinRequest.objects.filter(group_id=group.group_id).order_by("member_id")
