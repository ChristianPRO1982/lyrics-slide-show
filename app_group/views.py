from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .forms import GroupCreateForm, GroupSettingsForm
from .models import Group, GroupJoinRequest, GroupMembership, GroupStatus, normalize_group_name
from .services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
    add_duplicate_name_message,
    accept_join_request,
    clear_selected_group,
    fetch_directory_users,
    generate_group_secret,
    get_business_status,
    get_delete_confirmation_word,
    get_group_or_404,
    get_member_id_from_user,
    get_selected_group_state,
    get_status_icon,
    get_status_label,
    list_group_join_requests,
    list_group_memberships,
    remove_member,
    require_group_manager,
    select_group,
    set_group_admin,
    user_can_manage_group,
    user_can_select_group,
)
from app_member.services import can_manage_groups_globally
from app_animation.models import Animation


def _duplicate_name_exists(name: str, exclude_group_id: int | None = None) -> bool:
    normalized_name = normalize_group_name(name)
    queryset = Group.objects.filter(name__iexact=normalized_name)
    if exclude_group_id is not None:
        queryset = queryset.exclude(group_id=exclude_group_id)
    return queryset.exists()


def _build_group_share_link(request: HttpRequest, group: Group) -> str | None:
    if not group.secret_ciphertext:
        return None
    query = urlencode({"secret": group.secret_ciphertext})
    return request.build_absolute_uri(f"{reverse('groups')}?{query}")


def _build_groups_page_context(request: HttpRequest, create_form: GroupCreateForm | None = None) -> dict[str, object]:
    member_id = get_member_id_from_user(request.user)
    groups = list(Group.objects.all().order_by("name"))
    group_ids = [group.group_id for group in groups]

    memberships_by_group_id: dict[int, GroupMembership] = {}
    pending_request_group_ids: set[int] = set()
    if member_id:
        memberships_by_group_id = {
            membership.group_id: membership
            for membership in GroupMembership.objects.filter(group_id__in=group_ids, member_id=member_id)
        }
        pending_request_group_ids = set(
            GroupJoinRequest.objects.filter(group_id__in=group_ids, member_id=member_id).values_list("group_id", flat=True)
        )

    admin_memberships = list(
        GroupMembership.objects.filter(group_id__in=group_ids, is_group_admin=True).order_by("group_id", "member_id")
    )
    admin_users = fetch_directory_users([membership.member_id for membership in admin_memberships])
    admin_usernames_by_group_id: dict[int, list[str]] = {}
    for membership in admin_memberships:
        admin_usernames_by_group_id.setdefault(membership.group_id, []).append(
            admin_users[str(membership.member_id)].username
        )

    selected_group, selected_via_secret = get_selected_group_state(request)

    group_cards = []
    selected_group_id = request.session.get(SELECTED_GROUP_ID_SESSION_KEY)
    session_secret = request.session.get(SELECTED_GROUP_SECRET_SESSION_KEY)
    for group in groups:
        membership = memberships_by_group_id.get(group.group_id)
        status_icon = get_status_icon(group)
        business_status = get_business_status(group)
        can_manage = user_can_manage_group(request.user, membership)
        active_secret = session_secret if selected_group_id == group.group_id else None
        can_select = user_can_select_group(request.user, group, membership, active_secret)
        is_member = membership is not None
        is_group_admin = bool(membership and membership.is_group_admin)
        can_view_admin_usernames = bool(is_member or can_manage_groups_globally(request.user))
        group_cards.append(
            {
                "group": group,
                "status_icon": status_icon,
                "status_label": get_status_label(group),
                "business_status": business_status,
                "has_secret": bool(group.secret_ciphertext and group.status == GroupStatus.PRIVATE),
                "membership_marker": "👩🏾‍🔧" if is_group_admin else "👥" if is_member else "📩" if group.group_id in pending_request_group_ids else "",
                "membership_label": (
                    _("Responsable") if is_group_admin else _("Membre") if is_member else _("Demande en cours") if group.group_id in pending_request_group_ids else ""
                ),
                "admin_usernames": admin_usernames_by_group_id.get(group.group_id, []) if can_view_admin_usernames else [],
                "can_manage": can_manage,
                "can_select": can_select,
                "can_request_join": bool(
                    member_id and not is_member and group.group_id not in pending_request_group_ids and group.status == GroupStatus.PRIVATE
                ),
                "can_cancel_request": bool(member_id and group.group_id in pending_request_group_ids),
                "can_leave": bool(is_member),
                "needs_secret_prompt": bool(not can_select and business_status == "private_with_secret"),
                "is_selected": bool(selected_group and selected_group.group_id == group.group_id),
            }
        )

    return {
        "create_form": create_form or GroupCreateForm(),
        "group_cards": group_cards,
        "selected_group": selected_group,
        "selected_via_secret": selected_via_secret,
        "selected_group_can_manage": bool(
            selected_group
            and user_can_manage_group(
                request.user,
                memberships_by_group_id.get(selected_group.group_id),
            )
        ),
    }


def _handle_group_link_selection(request: HttpRequest) -> HttpResponse | None:
    selected_group_id = request.GET.get("select_group")
    provided_secret = request.GET.get("secret", "").strip()
    if not selected_group_id and not provided_secret:
        return None

    if selected_group_id:
        group = get_object_or_404(Group, group_id=selected_group_id)
    else:
        group = get_object_or_404(Group, secret_ciphertext=provided_secret, status=GroupStatus.PRIVATE)
    member_id = get_member_id_from_user(request.user)
    membership = None
    if member_id:
        membership = GroupMembership.objects.filter(group_id=group.group_id, member_id=member_id).first()

    if membership is not None:
        select_group(request.session, group)
        messages.success(request, _("Le groupe sélectionné a été mis à jour."))
    elif group.status == GroupStatus.OPEN:
        select_group(request.session, group)
        messages.success(request, _("Le groupe sélectionné a été mis à jour."))
    elif group.secret_ciphertext and provided_secret and provided_secret == group.secret_ciphertext:
        select_group(request.session, group, access_secret=provided_secret)
        messages.success(request, _("Le groupe sélectionné a été mis à jour grâce au secret."))
    else:
        messages.error(request, _("Le secret de groupe fourni est invalide."))

    return redirect("groups")


def groups(request: HttpRequest) -> HttpResponse:
    linked_selection_response = _handle_group_link_selection(request)
    if linked_selection_response is not None:
        return linked_selection_response

    if request.method == "POST":
        action = request.POST.get("action", "")
        member_id = get_member_id_from_user(request.user)
        group_id = request.POST.get("group_id")
        group = Group.objects.filter(group_id=group_id).first() if group_id else None
        membership = None
        if group and member_id:
            membership = GroupMembership.objects.filter(group_id=group.group_id, member_id=member_id).first()

        if action == "create_group":
            if not member_id:
                messages.error(request, _("Vous devez être connecté pour créer un groupe."))
                return redirect("groups")

            create_form = GroupCreateForm(request.POST)
            if create_form.is_valid():
                if _duplicate_name_exists(create_form.cleaned_data["name"]):
                    add_duplicate_name_message(request)
                    create_form.add_error("name", _("Ce nom de groupe existe déjà."))
                else:
                    group = create_form.save(commit=False)
                    group.status = GroupStatus.OPEN
                    try:
                        group.save()
                    except IntegrityError:
                        add_duplicate_name_message(request)
                        create_form.add_error("name", _("Ce nom de groupe existe déjà."))
                    else:
                        GroupMembership.objects.create(
                            group_id=group.group_id,
                            member_id=member_id,
                            is_group_admin=True,
                        )
                        select_group(request.session, group)
                        messages.success(request, _("Le groupe a été créé et sélectionné."))
                        return redirect("modify_group", group_id=group.group_id)
            return render(request, "group/groups.html", _build_groups_page_context(request, create_form=create_form))

        if group is None:
            messages.error(request, _("Le groupe demandé est introuvable."))
            return redirect("groups")

        if action == "select_group":
            submitted_secret = request.POST.get("secret", "").strip()
            if group.status == GroupStatus.OPEN or membership is not None:
                select_group(request.session, group)
                messages.success(request, _("Le groupe sélectionné a été mis à jour."))
            elif group.secret_ciphertext and submitted_secret == group.secret_ciphertext:
                select_group(request.session, group, access_secret=submitted_secret)
                messages.success(request, _("Le groupe sélectionné a été mis à jour grâce au secret."))
            else:
                messages.error(request, _("Ce groupe n'est pas accessible avec les informations fournies."))
            return redirect("groups")

        if action == "request_join":
            if not member_id:
                messages.error(request, _("Vous devez être connecté pour demander à rejoindre un groupe."))
            elif group.status != GroupStatus.PRIVATE:
                messages.error(request, _("Les demandes d'adhésion sont réservées aux groupes fermés."))
            elif membership is not None:
                messages.info(request, _("Vous êtes déjà membre de ce groupe."))
            else:
                GroupJoinRequest.objects.get_or_create(group_id=group.group_id, member_id=member_id)
                messages.success(request, _("La demande d'adhésion a été enregistrée."))
            return redirect("groups")

        if action == "cancel_request":
            if not member_id:
                messages.error(request, _("Vous devez être connecté pour annuler une demande."))
            else:
                GroupJoinRequest.objects.filter(group_id=group.group_id, member_id=member_id).delete()
                messages.success(request, _("La demande d'adhésion a été annulée."))
            return redirect("groups")

        if action == "leave_group":
            if not member_id or membership is None:
                messages.error(request, _("Vous n'êtes pas membre de ce groupe."))
            else:
                try:
                    remove_member(group, member_id)
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    selected_group, _selected_via_secret = get_selected_group_state(request)
                    if selected_group and selected_group.group_id == group.group_id:
                        clear_selected_group(request.session)
                    messages.success(request, _("Vous avez quitté le groupe."))
            return redirect("groups")

    return render(request, "group/groups.html", _build_groups_page_context(request))


def modify_group(request: HttpRequest, group_id: int) -> HttpResponse:
    group = get_group_or_404(group_id)
    member_id = get_member_id_from_user(request.user)
    membership = None
    if member_id:
        membership = GroupMembership.objects.filter(group_id=group.group_id, member_id=member_id).first()

    require_group_manager(request.user, group, membership)
    settings_form = GroupSettingsForm(instance=group)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "save_group_settings":
            settings_form = GroupSettingsForm(request.POST, instance=group)
            if settings_form.is_valid():
                if _duplicate_name_exists(settings_form.cleaned_data["name"], exclude_group_id=group.group_id):
                    add_duplicate_name_message(request)
                    settings_form.add_error("name", _("Ce nom de groupe existe déjà."))
                else:
                    try:
                        settings_form.save()
                    except IntegrityError:
                        add_duplicate_name_message(request)
                        settings_form.add_error("name", _("Ce nom de groupe existe déjà."))
                    else:
                        messages.success(request, _("Les paramètres du groupe ont été enregistrés."))
                        return redirect("modify_group", group_id=group.group_id)

        elif action == "generate_secret":
            group.secret_ciphertext = generate_group_secret()
            group.save(update_fields=["secret_ciphertext"])
            if request.session.get(SELECTED_GROUP_ID_SESSION_KEY) == group.group_id and membership is None:
                clear_selected_group(request.session)
            messages.success(request, _("Le secret du groupe a été généré ou remplacé."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "remove_secret":
            group.secret_ciphertext = None
            group.save(update_fields=["secret_ciphertext"])
            selected_group, selected_via_secret = get_selected_group_state(request)
            if selected_group and selected_group.group_id == group.group_id and selected_via_secret:
                clear_selected_group(request.session)
            messages.success(request, _("Le secret du groupe a été supprimé."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "accept_join_request":
            target_member_id = request.POST.get("member_id", "")
            try:
                accept_join_request(group, target_member_id)
            except Exception:
                messages.error(request, _("La demande n'a pas pu être acceptée."))
            else:
                messages.success(request, _("La demande d'adhésion a été acceptée."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "reject_join_request":
            target_member_id = request.POST.get("member_id", "")
            GroupJoinRequest.objects.filter(group_id=group.group_id, member_id=target_member_id).delete()
            messages.success(request, _("La demande d'adhésion a été refusée."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "promote_member":
            try:
                set_group_admin(group, request.POST.get("member_id", ""), True)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Le rôle de responsable a été attribué."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "demote_member":
            try:
                set_group_admin(group, request.POST.get("member_id", ""), False)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Le rôle de responsable a été retiré."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "remove_member":
            try:
                remove_member(group, request.POST.get("member_id", ""))
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Le membre a été retiré du groupe."))
            return redirect("modify_group", group_id=group.group_id)

        elif action == "delete_group":
            confirmation_word = request.POST.get("confirmation_word", "").strip()
            expected_word = get_delete_confirmation_word(getattr(request, "LANGUAGE_CODE", None))
            if confirmation_word != expected_word:
                messages.error(request, _("Le mot de confirmation est incorrect."))
            else:
                if request.session.get(SELECTED_GROUP_ID_SESSION_KEY) == group.group_id:
                    clear_selected_group(request.session)
                group.delete()
                messages.success(request, _("Le groupe a été supprimé."))
                return redirect("groups")

    memberships = list(list_group_memberships(group))
    join_requests = list(list_group_join_requests(group))
    directory_users = fetch_directory_users(
        [membership.member_id for membership in memberships] + [join_request.member_id for join_request in join_requests]
    )
    group_admin_count = sum(1 for item in memberships if item.is_group_admin)

    member_cards = []
    for item in memberships:
        person = directory_users[str(item.member_id)]
        is_last_admin = bool(item.is_group_admin and group_admin_count == 1)
        member_cards.append(
            {
                "member_id": str(item.member_id),
                "username": person.username,
                "display_name": person.display_name,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "is_group_admin": item.is_group_admin,
                "is_last_admin": is_last_admin,
            }
        )

    join_request_cards = [
        {
            "member_id": str(item.member_id),
            "username": directory_users[str(item.member_id)].username,
            "display_name": directory_users[str(item.member_id)].display_name,
            "first_name": directory_users[str(item.member_id)].first_name,
            "last_name": directory_users[str(item.member_id)].last_name,
        }
        for item in join_requests
    ]

    selected_group, selected_via_secret = get_selected_group_state(request)
    share_link = _build_group_share_link(request, group)
    current_session_secret = (
        request.session.get(SELECTED_GROUP_SECRET_SESSION_KEY)
        if request.session.get(SELECTED_GROUP_ID_SESSION_KEY) == group.group_id
        else None
    )
    context = {
        "group": group,
        "settings_form": settings_form,
        "selected_group": selected_group,
        "selected_via_secret": selected_via_secret,
        "group_status_icon": get_status_icon(group),
        "group_status_label": get_status_label(group),
        "group_business_status": get_business_status(group),
        "share_link": share_link,
        "delete_confirmation_word": get_delete_confirmation_word(getattr(request, "LANGUAGE_CODE", None)),
        "join_request_cards": join_request_cards,
        "member_cards": member_cards,
        "upcoming_animations": list(
            Animation.objects.filter(
                group_id=group.group_id,
                scheduled_at__gte=timezone.now(),
            ).order_by("scheduled_at", "animation_id")
        ),
        "can_select_current_group": user_can_select_group(request.user, group, membership, current_session_secret),
    }
    return render(request, "group/modify_group.html", context)
