# Generated manually for app_member role support.

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("app_member", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "lss"."m_users" RENAME TO "m_preferences"',
                    reverse_sql='ALTER TABLE "lss"."m_preferences" RENAME TO "m_users"',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE "lss"."m_preferences" RENAME COLUMN "id" TO "member_id"',
                    reverse_sql='ALTER TABLE "lss"."m_preferences" RENAME COLUMN "member_id" TO "id"',
                ),
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE "lss"."m_preferences" '
                        'RENAME CONSTRAINT "m_users_user_fk" TO "m_preferences_user_fk"'
                    ),
                    reverse_sql=(
                        'ALTER TABLE "lss"."m_preferences" '
                        'RENAME CONSTRAINT "m_preferences_user_fk" TO "m_users_user_fk"'
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name="memberpreferences",
                    table='lss"."m_preferences',
                ),
                migrations.RenameField(
                    model_name="memberpreferences",
                    old_name="id",
                    new_name="member_id",
                ),
            ],
        ),
        migrations.CreateModel(
            name="MemberRole",
            fields=[
                (
                    "member_id",
                    models.UUIDField(editable=False, primary_key=True, serialize=False),
                ),
                ("is_moderator", models.BooleanField(default=False)),
                ("is_admin", models.BooleanField(default=False)),
            ],
            options={
                "db_table": 'lss"."m_member_roles',
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(is_admin=False) | Q(is_moderator=True),
                        name="m_member_roles_admin_requires_moderator",
                    )
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."m_member_roles" '
                "ADD CONSTRAINT m_member_roles_user_fk "
                'FOREIGN KEY ("member_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."m_member_roles" '
                "DROP CONSTRAINT IF EXISTS m_member_roles_user_fk"
            ),
        ),
    ]
