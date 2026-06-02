from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0002_enable_unaccent"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='DROP TABLE IF EXISTS "lss"."s_song_favorites"',
                    reverse_sql=(
                        'CREATE TABLE "lss"."s_song_favorites" ('
                        '"song_id" integer NOT NULL, '
                        '"user_id" uuid NOT NULL, '
                        'CONSTRAINT s_song_favorites_pkey PRIMARY KEY ("song_id", "user_id"), '
                        "CONSTRAINT s_song_favorites_songs_fk "
                        'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE, '
                        "CONSTRAINT s_song_favorites_users_fk "
                        'FOREIGN KEY ("user_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
                        ")"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE TABLE "lss"."m_songs_users" ('
                        '"song_id" integer NOT NULL, '
                        '"user_id" uuid NOT NULL, '
                        'CONSTRAINT m_songs_users_pkey PRIMARY KEY ("song_id", "user_id"), '
                        "CONSTRAINT m_songs_users_songs_fk "
                        'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE, '
                        "CONSTRAINT m_songs_users_users_fk "
                        'FOREIGN KEY ("user_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
                        ")"
                    ),
                    reverse_sql='DROP TABLE IF EXISTS "lss"."m_songs_users"',
                ),
                migrations.RunSQL(
                    sql='CREATE INDEX m_songs_users_user_id_idx ON "lss"."m_songs_users" ("user_id")',
                    reverse_sql='DROP INDEX IF EXISTS "lss"."m_songs_users_user_id_idx"',
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name="songfavorite",
                    table='lss"."m_songs_users',
                ),
            ],
        ),
    ]
