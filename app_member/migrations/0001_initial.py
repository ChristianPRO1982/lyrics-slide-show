# Generated manually for app_member.

from django.db import migrations, models

import app_member.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE SCHEMA IF NOT EXISTS "lss";
            CREATE SCHEMA IF NOT EXISTS "users";
            CREATE TABLE IF NOT EXISTS "users"."users" (
                "id" uuid PRIMARY KEY,
                "username" varchar(255),
                "first_name" varchar(255),
                "last_name" varchar(255),
                "email" varchar(255),
                "enabled" boolean DEFAULT TRUE,
                "email_verified" boolean DEFAULT FALSE,
                "synced_at" time,
                "last_login_at" time
            );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="MemberPreferences",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("theme_slug", models.CharField(default="normal", max_length=32)),
                (
                    "song_search",
                    models.JSONField(
                        default=app_member.models.default_song_search,
                        validators=[app_member.models.validate_song_search],
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."m_users',
            },
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."m_users" '
                'ADD CONSTRAINT m_users_user_fk '
                'FOREIGN KEY ("id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
            ),
            reverse_sql='ALTER TABLE "lss"."m_users" DROP CONSTRAINT IF EXISTS m_users_user_fk',
        ),
    ]
