# Generated manually for app_animation initial schema.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("app_group", "0001_initial"),
        ("app_song", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Animation",
            fields=[
                ("animation_id", models.AutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("scheduled_at", models.DateTimeField()),
                ("text_color", models.CharField(default="#FFFFFF", max_length=32)),
                ("bg_color", models.CharField(default="#000000", max_length=32)),
                ("font_family", models.CharField(default="Source Sans Pro", max_length=120)),
                ("font_size", models.PositiveIntegerField(default=72)),
                ("horizontal_padding", models.PositiveIntegerField(default=80)),
                ("background_asset_code", models.CharField(blank=True, max_length=128, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        db_column="group_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="animations",
                        to="app_group.group",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."a_animations',
                "ordering": ["scheduled_at", "animation_id"],
                "indexes": [
                    models.Index(fields=["group"], name="a_animations_group_idx"),
                    models.Index(fields=["scheduled_at"], name="a_animations_sched_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AnimationSong",
            fields=[
                ("animation_song_id", models.AutoField(primary_key=True, serialize=False)),
                ("position", models.IntegerField(default=1000)),
                ("text_color_override", models.CharField(blank=True, max_length=32, null=True)),
                ("bg_color_override", models.CharField(blank=True, max_length=32, null=True)),
                ("font_family_override", models.CharField(blank=True, max_length=120, null=True)),
                ("font_size_override", models.PositiveIntegerField(blank=True, null=True)),
                ("horizontal_padding_override", models.PositiveIntegerField(blank=True, null=True)),
                ("background_asset_code_override", models.CharField(blank=True, max_length=128, null=True)),
                (
                    "animation",
                    models.ForeignKey(
                        db_column="animation_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="animation_songs",
                        to="app_animation.animation",
                    ),
                ),
                (
                    "song",
                    models.ForeignKey(
                        db_column="song_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="animation_usages",
                        to="app_song.song",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."a_animation_songs',
                "ordering": ["position", "animation_song_id"],
                "indexes": [
                    models.Index(fields=["animation"], name="a_anim_songs_anim_idx"),
                    models.Index(fields=["position"], name="a_anim_songs_pos_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("animation", "position"), name="a_anim_songs_anim_pos_uniq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AnimationVerseOverride",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "animation_song",
                        "source_verse_id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("source_verse_id", models.IntegerField()),
                ("is_visible", models.BooleanField(default=True)),
                ("text_color_override", models.CharField(blank=True, max_length=32, null=True)),
                ("bg_color_override", models.CharField(blank=True, max_length=32, null=True)),
                ("font_family_override", models.CharField(blank=True, max_length=120, null=True)),
                ("font_size_override", models.PositiveIntegerField(blank=True, null=True)),
                ("horizontal_padding_override", models.PositiveIntegerField(blank=True, null=True)),
                ("background_asset_code_override", models.CharField(blank=True, max_length=128, null=True)),
                (
                    "animation_song",
                    models.ForeignKey(
                        db_column="animation_song_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verse_overrides",
                        to="app_animation.animationsong",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."a_animation_verse_overrides',
                "indexes": [
                    models.Index(fields=["animation_song"], name="a_anim_vo_anim_song_idx"),
                    models.Index(fields=["source_verse_id"], name="a_anim_vo_source_idx"),
                ],
            },
        ),
    ]
