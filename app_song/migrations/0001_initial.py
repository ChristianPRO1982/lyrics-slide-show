# Generated manually for app_song initial lss schema.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql='CREATE SCHEMA IF NOT EXISTS "lss";',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="Song",
            fields=[
                ("song_id", models.AutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("subtitle", models.CharField(db_column="sub_title", max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.IntegerField(
                        choices=[
                            (0, "Not validated"),
                            (1, "Validated"),
                            (2, "Validated with concern"),
                        ],
                        default=0,
                    ),
                ),
                ("licensed", models.BooleanField(default=False)),
            ],
            options={
                "db_table": 'lss"."s_songs',
                "ordering": ["title", "subtitle"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("title", "subtitle"),
                        name="s_songs_unique",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="VersePrefix",
            fields=[
                ("prefix_id", models.AutoField(primary_key=True, serialize=False)),
                ("prefix", models.CharField(max_length=15)),
                ("comment", models.CharField(blank=True, max_length=100, null=True)),
            ],
            options={
                "db_table": 'lss"."s_verse_prefixes',
                "ordering": ["prefix"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("prefix",),
                        name="s_verse_prefixes_unique",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SongMessage",
            fields=[
                ("message_id", models.AutoField(primary_key=True, serialize=False)),
                ("message", models.TextField()),
                (
                    "status",
                    models.IntegerField(
                        choices=[(0, "New"), (1, "Handled"), (2, "Rejected")],
                        default=0,
                    ),
                ),
                ("date", models.DateTimeField()),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_messages',
                "ordering": ["-date", "-message_id"],
            },
        ),
        migrations.CreateModel(
            name="SongLink",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "song",
                        "link",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("link", models.CharField(max_length=255)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("internal", "Internal"),
                            ("web", "Web"),
                            ("score", "Score"),
                            ("audio-video", "Audio/video"),
                        ],
                        default="web",
                        max_length=20,
                    ),
                ),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_links',
                "ordering": ["link"],
            },
        ),
        migrations.CreateModel(
            name="Verse",
            fields=[
                ("verse_id", models.AutoField(primary_key=True, serialize=False)),
                ("num", models.IntegerField(default=1000)),
                ("num_verse", models.IntegerField(default=1000)),
                ("chorus", models.BooleanField(default=False)),
                ("chorus_like", models.BooleanField(default=False)),
                ("followed", models.BooleanField(default=False)),
                ("notcontinuenumbering", models.BooleanField(default=False)),
                ("text", models.TextField(blank=True, null=True)),
                ("prefix", models.CharField(blank=True, max_length=50, null=True)),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verses",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_verses',
                "ordering": ["num", "verse_id"],
                "indexes": [
                    models.Index(fields=["song"], name="s_verses_song_id_idx"),
                    models.Index(fields=["num"], name="s_verses_num_idx"),
                    models.Index(fields=["chorus"], name="s_verses_chorus_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SongGenre",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "song",
                        "genre_id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("genre_id", models.IntegerField()),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="genre_relations",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_genres',
            },
        ),
        migrations.CreateModel(
            name="SongArtist",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "song",
                        "artist_id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("artist_id", models.IntegerField()),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artist_relations",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_artists',
            },
        ),
        migrations.CreateModel(
            name="SongBand",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "song",
                        "band_id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("band_id", models.IntegerField()),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="band_relations",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_bands',
            },
        ),
        migrations.CreateModel(
            name="SongFavorite",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "song",
                        "member_id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("member_id", models.UUIDField(db_column="user_id")),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        db_constraint=False,
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."s_song_favorites',
            },
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_messages" '
                "ADD CONSTRAINT s_song_messages_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_messages" '
                "DROP CONSTRAINT IF EXISTS s_song_messages_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_links" '
                "ADD CONSTRAINT s_song_links_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_links" '
                "DROP CONSTRAINT IF EXISTS s_song_links_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_verses" '
                "ADD CONSTRAINT s_verses_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_verses" '
                "DROP CONSTRAINT IF EXISTS s_verses_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_genres" '
                "ADD CONSTRAINT s_song_genres_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_genres" '
                "DROP CONSTRAINT IF EXISTS s_song_genres_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_genres" '
                "ADD CONSTRAINT s_song_genres_genres_fk "
                'FOREIGN KEY ("genre_id") REFERENCES "common"."genres" ("genre_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_genres" '
                "DROP CONSTRAINT IF EXISTS s_song_genres_genres_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_artists" '
                "ADD CONSTRAINT s_song_artists_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_artists" '
                "DROP CONSTRAINT IF EXISTS s_song_artists_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_artists" '
                "ADD CONSTRAINT s_song_artists_artists_fk "
                'FOREIGN KEY ("artist_id") REFERENCES "common"."artists" ("artist_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_artists" '
                "DROP CONSTRAINT IF EXISTS s_song_artists_artists_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_bands" '
                "ADD CONSTRAINT s_song_bands_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_bands" '
                "DROP CONSTRAINT IF EXISTS s_song_bands_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_bands" '
                "ADD CONSTRAINT s_song_bands_bands_fk "
                'FOREIGN KEY ("band_id") REFERENCES "common"."bands" ("band_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_bands" '
                "DROP CONSTRAINT IF EXISTS s_song_bands_bands_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_favorites" '
                "ADD CONSTRAINT s_song_favorites_songs_fk "
                'FOREIGN KEY ("song_id") REFERENCES "lss"."s_songs" ("song_id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_favorites" '
                "DROP CONSTRAINT IF EXISTS s_song_favorites_songs_fk"
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "lss"."s_song_favorites" '
                "ADD CONSTRAINT s_song_favorites_users_fk "
                'FOREIGN KEY ("user_id") REFERENCES "users"."users" ("id") ON DELETE CASCADE'
            ),
            reverse_sql=(
                'ALTER TABLE "lss"."s_song_favorites" '
                "DROP CONSTRAINT IF EXISTS s_song_favorites_users_fk"
            ),
        ),
    ]
