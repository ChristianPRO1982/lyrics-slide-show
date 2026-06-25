from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from app_animation.models import Animation
from app_main.auth import AnonymousSessionUser, SessionUser
from app_main.models import DirectoryUserRecord
from app_member.models import MemberRole

from .forms import GroupCreateForm, GroupSettingsForm
from .models import (
    Group,
    GroupJoinRequest,
    GroupMembership,
    GroupStatus,
    normalize_group_info,
    normalize_group_name,
)
from .services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
    DirectoryUserSummary,
    accept_join_request,
    clear_selected_group,
    ensure_not_last_group_admin,
    fetch_directory_users,
    get_business_status,
    get_delete_confirmation_word,
    get_group_or_404,
    get_member_id_from_user,
    get_selected_group_state,
    get_status_icon,
    get_status_label,
    is_last_group_admin,
    list_group_join_requests,
    list_group_memberships,
    normalize_member_id,
    remove_member,
    require_group_manager,
    select_group,
    set_group_admin,
    user_can_manage_group,
    user_can_select_group,
)
from .views import _build_group_share_link, _duplicate_name_exists


ADMIN_ID = "11111111-1111-1111-1111-111111111111"
MEMBER_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"
MISSING_ID = "44444444-4444-4444-4444-444444444444"


def make_user(external_id=MEMBER_ID, *, moderator=False, admin=False):
    return SessionUser(
        external_id=external_id,
        username="member.user",
        email="member@example.test",
        first_name="Member",
        last_name="User",
        is_moderator=moderator or admin,
        is_admin=admin,
    )


class GroupModelAndFormTests(TestCase):
    def test_normalizers_strip_markup_spaces_and_preserve_lines(self):
        self.assertEqual(
            normalize_group_name("  Groupe   test \n A  "), "Groupe test A"
        )
        self.assertEqual(
            normalize_group_info(" <b>Ligne   une</b>\r\n Ligne\t deux "),
            "Ligne une\nLigne deux",
        )

    def test_group_model_normalizes_values_and_exposes_business_status(self):
        group = Group(
            name="  Groupe   test  ",
            info="<b>Une   info</b>",
            status=GroupStatus.PRIVATE,
            secret_ciphertext="secret",
        )
        group.clean()
        self.assertEqual(group.name, "Groupe test")
        self.assertEqual(group.info, "Une info")
        self.assertEqual(group.business_status, "private_with_secret")
        self.assertEqual(str(group), "Groupe test")

        group.secret_ciphertext = None
        self.assertEqual(group.business_status, GroupStatus.PRIVATE)

    def test_create_form_normalizes_valid_values_and_rejects_empty_name(self):
        form = GroupCreateForm(data={"name": "  Mon   groupe ", "info": "<i>A  B</i>"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "Mon groupe")
        self.assertEqual(form.cleaned_data["info"], "A B")

        empty_form = GroupCreateForm(data={"name": "   ", "info": ""})
        self.assertFalse(empty_form.is_valid())
        self.assertIn("name", empty_form.errors)

    def test_settings_form_initial_and_save_without_commit(self):
        group = Group.objects.create(name="Groupe", status=GroupStatus.PRIVATE)
        form = GroupSettingsForm(instance=group)
        self.assertEqual(form.fields["is_open"].initial, GroupStatus.PRIVATE)

        form = GroupSettingsForm(
            data={"name": " Nouveau ", "info": "", "is_open": GroupStatus.OPEN},
            instance=group,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save(commit=False)
        self.assertEqual(saved.name, "Nouveau")
        self.assertEqual(saved.status, GroupStatus.OPEN)


class GroupServiceUnitTests(SimpleTestCase):
    def test_directory_summary_display_name_fallbacks(self):
        self.assertEqual(
            DirectoryUserSummary(MEMBER_ID, "member", "Marie", "Durand").display_name,
            "Marie Durand",
        )
        self.assertEqual(
            DirectoryUserSummary(MEMBER_ID, "member", "", "").display_name,
            "member",
        )
        self.assertEqual(
            DirectoryUserSummary(MEMBER_ID, "", "", "").display_name,
            MEMBER_ID,
        )

    def test_member_id_and_confirmation_helpers(self):
        self.assertIsNone(get_member_id_from_user(AnonymousSessionUser()))
        user_without_id = type("User", (), {"is_authenticated": True})()
        self.assertIsNone(get_member_id_from_user(user_without_id))
        self.assertEqual(get_member_id_from_user(make_user()), MEMBER_ID)
        self.assertEqual(normalize_member_id(MEMBER_ID), MEMBER_ID)
        self.assertEqual(get_delete_confirmation_word("fr-fr"), "SUPPRIMER")
        self.assertEqual(get_delete_confirmation_word("en"), "DELETE")

    def test_status_and_selection_helpers_cover_all_business_states(self):
        open_group = Group(name="Open", status=GroupStatus.OPEN)
        private_group = Group(name="Private", status=GroupStatus.PRIVATE)
        secret_group = Group(
            name="Secret",
            status=GroupStatus.PRIVATE,
            secret_ciphertext="secret-token",
        )
        membership = GroupMembership(
            group=private_group, member_id=MEMBER_ID, is_group_admin=False
        )

        self.assertEqual(get_business_status(open_group), GroupStatus.OPEN)
        self.assertEqual(get_business_status(secret_group), "private_with_secret")
        self.assertEqual(get_status_icon(open_group), "🌐")
        self.assertEqual(get_status_icon(private_group), "🔐")
        self.assertEqual(get_status_icon(secret_group), "🔐📱")
        self.assertEqual(str(get_status_label(open_group)), "Ouvert")
        self.assertEqual(str(get_status_label(private_group)), "Fermé")
        self.assertEqual(str(get_status_label(secret_group)), "Fermé avec secret")
        self.assertTrue(user_can_select_group(AnonymousSessionUser(), open_group, None))
        self.assertTrue(user_can_select_group(make_user(), private_group, membership))
        self.assertTrue(
            user_can_select_group(
                AnonymousSessionUser(), secret_group, None, "secret-token"
            )
        )
        self.assertFalse(
            user_can_select_group(AnonymousSessionUser(), secret_group, None, "wrong")
        )

    @patch("app_group.services.can_manage_groups_globally")
    def test_group_management_helper_supports_global_and_local_roles(self, global_mock):
        membership = GroupMembership(
            group=Group(name="G"), member_id=MEMBER_ID, is_group_admin=True
        )
        global_mock.return_value = True
        self.assertTrue(user_can_manage_group(make_user(), None))
        global_mock.return_value = False
        self.assertTrue(user_can_manage_group(make_user(), membership))
        membership.is_group_admin = False
        self.assertFalse(user_can_manage_group(make_user(), membership))
        with self.assertRaises(Http404):
            require_group_manager(make_user(), Group(name="G"), membership)

    def test_session_selection_helpers_work_with_plain_dict(self):
        group = Group(group_id=7, name="G")
        session = {}
        select_group(session, group, "secret")
        self.assertEqual(session[SELECTED_GROUP_ID_SESSION_KEY], 7)
        self.assertEqual(session[SELECTED_GROUP_SECRET_SESSION_KEY], "secret")
        select_group(session, group)
        self.assertNotIn(SELECTED_GROUP_SECRET_SESSION_KEY, session)
        clear_selected_group(session)
        self.assertEqual(session, {})


class GroupDatabaseServiceTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="Groupe", status=GroupStatus.PRIVATE)
        for external_id, username, first_name, last_name in (
            (ADMIN_ID, "admin.user", "Admin", "User"),
            (MEMBER_ID, "member.user", "Member", "User"),
            (OTHER_ID, "other.user", "Other", "User"),
        ):
            DirectoryUserRecord.objects.create(
                id=external_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=f"{username}@example.test",
                enabled=True,
                email_verified=False,
            )

    def test_fetch_directory_users_returns_records_and_uuid_fallback(self):
        summaries = fetch_directory_users([MEMBER_ID, MISSING_ID])
        self.assertEqual(summaries[MEMBER_ID].display_name, "Member User")
        self.assertEqual(summaries[MISSING_ID].username, MISSING_ID)
        self.assertEqual(fetch_directory_users([]), {})

    def test_selected_group_state_handles_missing_invalid_open_member_and_secret(self):
        request = RequestFactory().get("/")
        request.user = AnonymousSessionUser()
        request.session = {}
        self.assertEqual(get_selected_group_state(request), (None, False))

        request.session[SELECTED_GROUP_ID_SESSION_KEY] = 999999
        self.assertEqual(get_selected_group_state(request), (None, False))
        self.assertNotIn(SELECTED_GROUP_ID_SESSION_KEY, request.session)

        self.group.status = GroupStatus.OPEN
        self.group.save(update_fields=["status"])
        request.session[SELECTED_GROUP_ID_SESSION_KEY] = self.group.group_id
        self.assertEqual(get_selected_group_state(request), (self.group, False))

        self.group.status = GroupStatus.PRIVATE
        self.group.secret_ciphertext = "secret"
        self.group.save(update_fields=["status", "secret_ciphertext"])
        request.session[SELECTED_GROUP_SECRET_SESSION_KEY] = "secret"
        self.assertEqual(get_selected_group_state(request), (self.group, True))

        request.user = make_user()
        GroupMembership.objects.create(group=self.group, member_id=MEMBER_ID)
        self.assertEqual(get_selected_group_state(request), (self.group, False))

    def test_membership_services_enforce_last_admin_and_manage_requests(self):
        admin = GroupMembership.objects.create(
            group=self.group, member_id=ADMIN_ID, is_group_admin=True
        )
        member = GroupMembership.objects.create(
            group=self.group, member_id=MEMBER_ID, is_group_admin=False
        )
        GroupJoinRequest.objects.create(group=self.group, member_id=OTHER_ID)

        self.assertTrue(is_last_group_admin(self.group, ADMIN_ID))
        self.assertFalse(is_last_group_admin(self.group, MEMBER_ID))
        with self.assertRaisesMessage(ValueError, "dernier responsable"):
            ensure_not_last_group_admin(self.group, ADMIN_ID)

        set_group_admin(self.group, MEMBER_ID, True)
        member.refresh_from_db()
        self.assertTrue(member.is_group_admin)
        self.assertFalse(is_last_group_admin(self.group, ADMIN_ID))

        set_group_admin(self.group, MEMBER_ID, False)
        member.refresh_from_db()
        self.assertFalse(member.is_group_admin)
        with self.assertRaisesMessage(ValueError, "n'appartient pas"):
            set_group_admin(self.group, OTHER_ID, True)

        remove_member(self.group, MEMBER_ID)
        self.assertFalse(
            GroupMembership.objects.filter(
                group=self.group, member_id=MEMBER_ID
            ).exists()
        )

        accept_join_request(self.group, OTHER_ID)
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, member_id=OTHER_ID
            ).exists()
        )
        self.assertFalse(
            GroupJoinRequest.objects.filter(
                group=self.group, member_id=OTHER_ID
            ).exists()
        )
        memberships = list(list_group_memberships(self.group))
        self.assertEqual(str(memberships[0].member_id), str(admin.member_id))
        self.assertTrue(memberships[0].is_group_admin)
        self.assertEqual(list(list_group_join_requests(self.group)), [])

    def test_get_group_or_404_and_duplicate_lookup(self):
        self.assertEqual(get_group_or_404(self.group.group_id), self.group)
        with self.assertRaises(Http404):
            get_group_or_404(999999)
        self.assertTrue(_duplicate_name_exists("  groupe "))
        self.assertFalse(
            _duplicate_name_exists("Groupe", exclude_group_id=self.group.group_id)
        )


class GroupViewsTests(TestCase):
    def setUp(self):
        self.admin = self._create_directory_user(ADMIN_ID, "admin.user")
        self.member = self._create_directory_user(MEMBER_ID, "member.user")
        self.other = self._create_directory_user(OTHER_ID, "other.user")

    def _create_directory_user(self, external_id, username):
        return DirectoryUserRecord.objects.create(
            id=external_id,
            username=username,
            first_name=username.split(".")[0].title(),
            last_name="User",
            email=f"{username}@example.test",
            enabled=True,
            email_verified=False,
        )

    def _login(self, external_id=MEMBER_ID, *, moderator=False, admin=False):
        if moderator or admin:
            MemberRole.objects.update_or_create(
                member_id=external_id,
                defaults={"is_moderator": True, "is_admin": admin},
            )
        record = DirectoryUserRecord.objects.get(pk=external_id)
        session = self.client.session
        session["lss_user"] = {
            "external_id": str(record.id),
            "username": record.username,
            "email": record.email,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "is_moderator": moderator or admin,
            "is_admin": admin,
        }
        session.save()

    def _select(self, group, secret=None):
        session = self.client.session
        session[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
        if secret:
            session[SELECTED_GROUP_SECRET_SESSION_KEY] = secret
        session.save()

    def test_groups_get_builds_guest_member_pending_and_manager_cards(self):
        open_group = Group.objects.create(name="Open", status=GroupStatus.OPEN)
        private_group = Group.objects.create(
            name="Private", status=GroupStatus.PRIVATE, secret_ciphertext="secret"
        )
        GroupMembership.objects.create(
            group=open_group, member_id=ADMIN_ID, is_group_admin=True
        )
        GroupJoinRequest.objects.create(group=private_group, member_id=MEMBER_ID)

        guest_response = self.client.get(reverse("groups"))
        self.assertEqual(guest_response.status_code, 200)
        guest_cards = guest_response.context["group_cards"]
        self.assertEqual(
            [card["group"].name for card in guest_cards], ["Open", "Private"]
        )
        self.assertEqual(guest_cards[0]["admin_usernames"], [])
        self.assertTrue(guest_cards[0]["can_select"])
        self.assertTrue(guest_cards[1]["needs_secret_prompt"])

        self._login()
        member_response = self.client.get(reverse("groups"))
        private_card = next(
            card
            for card in member_response.context["group_cards"]
            if card["group"] == private_group
        )
        self.assertEqual(private_card["membership_marker"], "📩")
        self.assertTrue(private_card["can_cancel_request"])

        self._login(ADMIN_ID, moderator=True)
        manager_response = self.client.get(reverse("groups"))
        open_card = next(
            card
            for card in manager_response.context["group_cards"]
            if card["group"] == open_group
        )
        self.assertEqual(open_card["admin_usernames"], ["admin.user"])
        self.assertTrue(open_card["can_manage"])

    def test_link_selection_supports_open_member_secret_and_rejects_invalid_secret(
        self,
    ):
        open_group = Group.objects.create(name="Open", status=GroupStatus.OPEN)
        response = self.client.get(
            reverse("groups"), {"select_group": open_group.group_id}
        )
        self.assertRedirects(response, reverse("groups"))
        self.assertEqual(
            self.client.session[SELECTED_GROUP_ID_SESSION_KEY], open_group.group_id
        )

        private_group = Group.objects.create(
            name="Private", status=GroupStatus.PRIVATE, secret_ciphertext="secret"
        )
        response = self.client.get(reverse("groups"), {"secret": "secret"})
        self.assertRedirects(response, reverse("groups"))
        self.assertEqual(
            self.client.session[SELECTED_GROUP_SECRET_SESSION_KEY], "secret"
        )

        self._login()
        GroupMembership.objects.create(group=private_group, member_id=MEMBER_ID)
        response = self.client.get(
            reverse("groups"),
            {"select_group": private_group.group_id, "secret": "wrong"},
        )
        self.assertRedirects(response, reverse("groups"))
        self.assertNotIn(
            SELECTED_GROUP_SECRET_SESSION_KEY,
            self.client.session,
        )

        GroupMembership.objects.filter(
            group=private_group, member_id=MEMBER_ID
        ).delete()
        response = self.client.get(
            reverse("groups"),
            {"select_group": private_group.group_id, "secret": "wrong"},
            follow=True,
        )
        self.assertContains(response, "Le secret de groupe fourni est invalide.")

    def test_group_creation_requires_login_validates_and_creates_admin_membership(self):
        response = self.client.post(
            reverse("groups"), {"action": "create_group", "name": "Guest group"}
        )
        self.assertRedirects(response, reverse("groups"))
        self.assertFalse(Group.objects.filter(name="Guest group").exists())

        self._login()
        invalid = self.client.post(
            reverse("groups"), {"action": "create_group", "name": " "}
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("name", invalid.context["create_form"].errors)

        response = self.client.post(
            reverse("groups"),
            {"action": "create_group", "name": "  New   Group ", "info": "<b>Info</b>"},
        )
        group = Group.objects.get(name="New Group")
        self.assertRedirects(response, reverse("modify_group", args=[group.group_id]))
        self.assertEqual(group.info, "Info")
        self.assertTrue(
            GroupMembership.objects.filter(
                group=group, member_id=MEMBER_ID, is_group_admin=True
            ).exists()
        )
        self.assertEqual(
            self.client.session[SELECTED_GROUP_ID_SESSION_KEY], group.group_id
        )

    @patch("app_group.views._duplicate_name_exists", return_value=True)
    def test_group_creation_reports_case_insensitive_duplicate(self, _duplicate):
        self._login()
        response = self.client.post(
            reverse("groups"),
            {"action": "create_group", "name": "Fresh name"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un autre groupe utilise déjà ce nom")
        self.assertIn("name", response.context["create_form"].errors)

    def test_group_actions_handle_missing_group_and_selection_paths(self):
        response = self.client.post(
            reverse("groups"), {"action": "select_group", "group_id": "999999"}
        )
        self.assertRedirects(response, reverse("groups"))

        open_group = Group.objects.create(name="Open", status=GroupStatus.OPEN)
        private_group = Group.objects.create(
            name="Private", status=GroupStatus.PRIVATE, secret_ciphertext="secret"
        )
        response = self.client.post(
            reverse("groups"),
            {"action": "select_group", "group_id": open_group.group_id},
        )
        self.assertRedirects(response, reverse("groups"))

        response = self.client.post(
            reverse("groups"),
            {
                "action": "select_group",
                "group_id": private_group.group_id,
                "secret": "secret",
            },
        )
        self.assertRedirects(response, reverse("groups"))
        self.assertEqual(
            self.client.session[SELECTED_GROUP_SECRET_SESSION_KEY], "secret"
        )

        response = self.client.post(
            reverse("groups"),
            {
                "action": "select_group",
                "group_id": private_group.group_id,
                "secret": "wrong",
            },
            follow=True,
        )
        self.assertContains(response, "Ce groupe n&#x27;est pas accessible", html=False)

    def test_join_request_and_cancellation_paths(self):
        open_group = Group.objects.create(name="Open", status=GroupStatus.OPEN)
        private_group = Group.objects.create(name="Private", status=GroupStatus.PRIVATE)

        guest = self.client.post(
            reverse("groups"),
            {"action": "request_join", "group_id": private_group.group_id},
            follow=True,
        )
        self.assertContains(guest, "Vous devez être connecté")

        self._login()
        wrong_status = self.client.post(
            reverse("groups"),
            {"action": "request_join", "group_id": open_group.group_id},
            follow=True,
        )
        self.assertContains(wrong_status, "réservées aux groupes fermés")

        created = self.client.post(
            reverse("groups"),
            {"action": "request_join", "group_id": private_group.group_id},
        )
        self.assertRedirects(created, reverse("groups"))
        self.assertTrue(
            GroupJoinRequest.objects.filter(
                group=private_group, member_id=MEMBER_ID
            ).exists()
        )

        already_pending = self.client.post(
            reverse("groups"),
            {"action": "request_join", "group_id": private_group.group_id},
        )
        self.assertRedirects(already_pending, reverse("groups"))
        self.assertEqual(
            GroupJoinRequest.objects.filter(
                group=private_group, member_id=MEMBER_ID
            ).count(),
            1,
        )

        cancelled = self.client.post(
            reverse("groups"),
            {"action": "cancel_request", "group_id": private_group.group_id},
        )
        self.assertRedirects(cancelled, reverse("groups"))
        self.assertFalse(
            GroupJoinRequest.objects.filter(
                group=private_group, member_id=MEMBER_ID
            ).exists()
        )

        GroupMembership.objects.create(group=private_group, member_id=MEMBER_ID)
        already_member = self.client.post(
            reverse("groups"),
            {"action": "request_join", "group_id": private_group.group_id},
            follow=True,
        )
        self.assertContains(already_member, "déjà membre")

    def test_leave_group_clears_selection_and_refuses_last_admin(self):
        group = Group.objects.create(name="Private", status=GroupStatus.PRIVATE)
        self._login()
        not_member = self.client.post(
            reverse("groups"),
            {"action": "leave_group", "group_id": group.group_id},
            follow=True,
        )
        self.assertContains(not_member, "Vous n&#x27;êtes pas membre", html=False)

        membership = GroupMembership.objects.create(
            group=group, member_id=MEMBER_ID, is_group_admin=False
        )
        self._select(group)
        response = self.client.post(
            reverse("groups"),
            {"action": "leave_group", "group_id": group.group_id},
        )
        self.assertRedirects(response, reverse("groups"))
        self.assertFalse(GroupMembership.objects.filter(pk=membership.pk).exists())
        self.assertNotIn(SELECTED_GROUP_ID_SESSION_KEY, self.client.session)

        GroupMembership.objects.create(
            group=group, member_id=MEMBER_ID, is_group_admin=True
        )
        refused = self.client.post(
            reverse("groups"),
            {"action": "leave_group", "group_id": group.group_id},
            follow=True,
        )
        self.assertContains(refused, "dernier responsable")

    def test_modify_group_requires_manager_and_builds_full_context(self):
        group = Group.objects.create(
            name="Managed",
            status=GroupStatus.PRIVATE,
            secret_ciphertext="secret",
        )
        GroupMembership.objects.create(
            group=group, member_id=ADMIN_ID, is_group_admin=True
        )
        GroupMembership.objects.create(group=group, member_id=MEMBER_ID)
        GroupJoinRequest.objects.create(group=group, member_id=OTHER_ID)
        Animation.objects.create(
            group=group,
            title="Future",
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
        )
        Animation.objects.create(
            group=group,
            title="Past",
            scheduled_at=timezone.now() - timezone.timedelta(days=1),
        )

        denied = self.client.get(reverse("modify_group", args=[group.group_id]))
        self.assertEqual(denied.status_code, 404)

        self._login(ADMIN_ID)
        response = self.client.get(reverse("modify_group", args=[group.group_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-group-settings-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertEqual(len(response.context["member_cards"]), 2)
        self.assertEqual(len(response.context["join_request_cards"]), 1)
        self.assertEqual(
            [item.title for item in response.context["upcoming_animations"]],
            ["Future"],
        )
        self.assertIn("secret=secret", response.context["share_link"])
        self.assertEqual(response.context["delete_confirmation_word"], "SUPPRIMER")

    @patch("app_group.views._duplicate_name_exists")
    def test_modify_group_saves_settings_and_reports_duplicate(self, duplicate_mock):
        group = Group.objects.create(name="Managed", status=GroupStatus.OPEN)
        GroupMembership.objects.create(
            group=group, member_id=ADMIN_ID, is_group_admin=True
        )
        self._login(ADMIN_ID)

        duplicate_mock.return_value = True
        duplicate = self.client.post(
            reverse("modify_group", args=[group.group_id]),
            {
                "action": "save_group_settings",
                "name": "Duplicate",
                "info": "",
                "is_open": GroupStatus.PRIVATE,
            },
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn("name", duplicate.context["settings_form"].errors)

        duplicate_mock.return_value = False
        saved = self.client.post(
            reverse("modify_group", args=[group.group_id]),
            {
                "action": "save_group_settings",
                "name": "Renamed",
                "info": "<b>Clean  info</b>",
                "is_open": GroupStatus.PRIVATE,
            },
        )
        self.assertRedirects(saved, reverse("modify_group", args=[group.group_id]))
        group.refresh_from_db()
        self.assertEqual(group.name, "Renamed")
        self.assertEqual(group.info, "Clean info")
        self.assertEqual(group.status, GroupStatus.PRIVATE)

    @patch("app_group.views.generate_group_secret", return_value="new-secret")
    def test_modify_group_generates_and_removes_secret(self, _generate_secret):
        group = Group.objects.create(name="Managed", status=GroupStatus.PRIVATE)
        self._login(ADMIN_ID, moderator=True)
        self._select(group, secret="old-secret")

        generated = self.client.post(
            reverse("modify_group", args=[group.group_id]),
            {"action": "generate_secret"},
        )
        self.assertRedirects(generated, reverse("modify_group", args=[group.group_id]))
        group.refresh_from_db()
        self.assertEqual(group.secret_ciphertext, "new-secret")
        self.assertNotIn(SELECTED_GROUP_ID_SESSION_KEY, self.client.session)

        self._select(group, secret="new-secret")
        removed = self.client.post(
            reverse("modify_group", args=[group.group_id]),
            {"action": "remove_secret"},
        )
        self.assertRedirects(removed, reverse("modify_group", args=[group.group_id]))
        group.refresh_from_db()
        self.assertIsNone(group.secret_ciphertext)
        self.assertNotIn(SELECTED_GROUP_ID_SESSION_KEY, self.client.session)

    def test_modify_group_membership_actions_cover_success_and_errors(self):
        group = Group.objects.create(name="Managed", status=GroupStatus.PRIVATE)
        GroupMembership.objects.create(
            group=group, member_id=ADMIN_ID, is_group_admin=True
        )
        GroupMembership.objects.create(group=group, member_id=MEMBER_ID)
        GroupJoinRequest.objects.create(group=group, member_id=OTHER_ID)
        self._login(ADMIN_ID)
        url = reverse("modify_group", args=[group.group_id])

        accepted = self.client.post(
            url, {"action": "accept_join_request", "member_id": OTHER_ID}
        )
        self.assertRedirects(accepted, url)
        self.assertTrue(
            GroupMembership.objects.filter(group=group, member_id=OTHER_ID).exists()
        )

        promoted = self.client.post(
            url, {"action": "promote_member", "member_id": MEMBER_ID}
        )
        self.assertRedirects(promoted, url)
        self.assertTrue(
            GroupMembership.objects.get(group=group, member_id=MEMBER_ID).is_group_admin
        )

        demoted = self.client.post(
            url, {"action": "demote_member", "member_id": MEMBER_ID}
        )
        self.assertRedirects(demoted, url)
        self.assertFalse(
            GroupMembership.objects.get(group=group, member_id=MEMBER_ID).is_group_admin
        )

        removed = self.client.post(
            url, {"action": "remove_member", "member_id": MEMBER_ID}
        )
        self.assertRedirects(removed, url)
        self.assertFalse(
            GroupMembership.objects.filter(group=group, member_id=MEMBER_ID).exists()
        )

        for action in ("promote_member", "demote_member", "remove_member"):
            with self.subTest(action=action):
                response = self.client.post(
                    url, {"action": action, "member_id": MEMBER_ID}, follow=True
                )
                self.assertEqual(response.status_code, 200)

        GroupJoinRequest.objects.create(group=group, member_id=MEMBER_ID)
        rejected = self.client.post(
            url, {"action": "reject_join_request", "member_id": MEMBER_ID}
        )
        self.assertRedirects(rejected, url)
        self.assertFalse(
            GroupJoinRequest.objects.filter(group=group, member_id=MEMBER_ID).exists()
        )

        failed_accept = self.client.post(
            url, {"action": "accept_join_request", "member_id": "invalid"}
        )
        self.assertRedirects(failed_accept, url)

    def test_modify_group_deletion_requires_exact_word_and_clears_selection(self):
        group = Group.objects.create(name="Managed", status=GroupStatus.OPEN)
        GroupMembership.objects.create(
            group=group, member_id=ADMIN_ID, is_group_admin=True
        )
        self._login(ADMIN_ID)
        self._select(group)
        url = reverse("modify_group", args=[group.group_id])

        refused = self.client.post(
            url, {"action": "delete_group", "confirmation_word": "DELETE"}
        )
        self.assertEqual(refused.status_code, 200)
        self.assertTrue(Group.objects.filter(pk=group.pk).exists())

        deleted = self.client.post(
            url, {"action": "delete_group", "confirmation_word": "SUPPRIMER"}
        )
        self.assertRedirects(deleted, reverse("groups"))
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())
        self.assertNotIn(SELECTED_GROUP_ID_SESSION_KEY, self.client.session)

    def test_share_link_is_absent_without_secret(self):
        request = RequestFactory().get("/groups/")
        self.assertIsNone(_build_group_share_link(request, Group(name="G")))
