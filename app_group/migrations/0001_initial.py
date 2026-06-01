# Generated manually for app_group initial schema.

from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Group",
            fields=[
                ("group_id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("info", models.TextField(blank=True, null=True)),
                ("secret_ciphertext", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("private", "Private")],
                        default="open",
                        max_length=32,
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."g_groups',
                "indexes": [
                    models.Index(fields=["status"], name="g_groups_status_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(("status__in", ["open", "private"])),
                        name="g_groups_status_check",
                    ),
                    models.UniqueConstraint(Lower("name"), name="g_groups_name_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GroupMembership",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey("group", "member_id", blank=True, editable=False, primary_key=True, serialize=False),
                ),
                ("member_id", models.UUIDField()),
                ("is_group_admin", models.BooleanField(default=False)),
                (
                    "group",
                    models.ForeignKey(
                        db_column="group_id",
                        on_delete=models.deletion.CASCADE,
                        related_name="memberships",
                        to="app_group.group",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."g_group_user',
                "indexes": [
                    models.Index(fields=["is_group_admin"], name="g_grp_usr_is_admin_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="GroupJoinRequest",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey("group", "member_id", blank=True, editable=False, primary_key=True, serialize=False),
                ),
                ("member_id", models.UUIDField()),
                (
                    "group",
                    models.ForeignKey(
                        db_column="group_id",
                        on_delete=models.deletion.CASCADE,
                        related_name="join_requests",
                        to="app_group.group",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."g_group_user_ask_to_join',
            },
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."g_group_user" '
                'ADD CONSTRAINT g_group_user_member_fk '
                'FOREIGN KEY ("member_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."g_group_user" '
                'DROP CONSTRAINT IF EXISTS g_group_user_member_fk'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."g_group_user_ask_to_join" '
                'ADD CONSTRAINT g_group_user_ask_to_join_member_fk '
                'FOREIGN KEY ("member_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."g_group_user_ask_to_join" '
                'DROP CONSTRAINT IF EXISTS g_group_user_ask_to_join_member_fk'
            ),
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION lss.delete_group_join_request_on_membership_delete()
                RETURNS TRIGGER AS $$
                BEGIN
                    DELETE FROM "lss"."g_group_user_ask_to_join"
                    WHERE "group_id" = OLD."group_id" AND "member_id" = OLD."member_id";
                    RETURN OLD;
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER g_group_user_delete_join_request_cleanup
                AFTER DELETE ON "lss"."g_group_user"
                FOR EACH ROW
                EXECUTE FUNCTION lss.delete_group_join_request_on_membership_delete();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS g_group_user_delete_join_request_cleanup
                ON "lss"."g_group_user";
                DROP FUNCTION IF EXISTS lss.delete_group_join_request_on_membership_delete();
            """,
        ),
    ]
