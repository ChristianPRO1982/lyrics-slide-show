from __future__ import annotations

from django.core.management.base import BaseCommand

from app_main.mock_accounts import DEV_MOCK_ACCOUNTS
from app_main.models import DirectoryUserRecord
from app_member.models import MemberRole


ACCOUNT_ROLE_BY_USERNAME = {
    "testmock": {"is_moderator": True, "is_admin": True},
    "testmock_moderateur": {"is_moderator": True, "is_admin": False},
    "testmock_simpletuser": {"is_moderator": False, "is_admin": False},
    "disabled.user": {"is_moderator": False, "is_admin": False},
}


class Command(BaseCommand):
    help = (
        "Synchronise les comptes auth_mock de dev dans users.users et les rôles "
        "locaux LSS associés."
    )

    def handle(self, *args, **options):
        created_users = 0
        updated_users = 0
        created_roles = 0
        updated_roles = 0
        deleted_roles = 0

        for account in DEV_MOCK_ACCOUNTS:
            if account["username"] == "unknown.user":
                MemberRole.objects.filter(member_id=account["external_id"]).delete()
                deleted_count, _details = DirectoryUserRecord.objects.filter(
                    id=account["external_id"]
                ).delete()
                if deleted_count:
                    self.stdout.write(
                        f"users.users cleared: {account['username']} "
                        f"({account['external_id']})"
                    )
                continue

            defaults = {
                "username": account["username"],
                "email": account["email"],
                "first_name": account["first_name"],
                "last_name": account["last_name"],
                "enabled": account["username"] != "disabled.user",
            }
            record, created = DirectoryUserRecord.objects.update_or_create(
                id=account["external_id"],
                defaults=defaults,
            )
            if created:
                created_users += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"users.users created: {record.username} ({record.id})"
                    )
                )
            else:
                updated_users += 1
                self.stdout.write(
                    f"users.users updated: {record.username} ({record.id})"
                )

            role_state = ACCOUNT_ROLE_BY_USERNAME.get(
                account["username"], {"is_moderator": False, "is_admin": False}
            )
            if not role_state["is_moderator"] and not role_state["is_admin"]:
                deleted_roles += MemberRole.objects.filter(
                    member_id=record.id
                ).delete()[0]
                self.stdout.write(
                    f"lss.m_member_roles cleared: {record.username} ({record.id})"
                )
                continue

            role, role_created = MemberRole.objects.update_or_create(
                member_id=record.id,
                defaults=role_state,
            )
            if role_created:
                created_roles += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"lss.m_member_roles created: {record.username} "
                        f"(moderator={role.is_moderator}, admin={role.is_admin})"
                    )
                )
            else:
                updated_roles += 1
                self.stdout.write(
                    f"lss.m_member_roles updated: {record.username} "
                    f"(moderator={role.is_moderator}, admin={role.is_admin})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                "sync_auth_mock_accounts completed "
                f"(users created={created_users}, users updated={updated_users}, "
                f"roles created={created_roles}, roles updated={updated_roles}, "
                f"roles cleared={deleted_roles})."
            )
        )
