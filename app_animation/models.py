from django.db import models

from app_group.models import Group
from app_song.models import Song


class Animation(models.Model):
    animation_id = models.AutoField(primary_key=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column="group_id",
        related_name="animations",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    scheduled_at = models.DateTimeField()

    text_color = models.CharField(max_length=32, default="#E8E8E8")
    bg_color = models.CharField(max_length=32, default="#111111")
    font_family = models.CharField(max_length=120, default="Source Sans Pro")
    font_size = models.PositiveIntegerField(default=72)
    horizontal_padding = models.PositiveIntegerField(default=80)
    background_asset_code = models.CharField(max_length=128, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lss"."a_animations'
        ordering = ["scheduled_at", "animation_id"]
        indexes = [
            models.Index(fields=["group"], name="a_animations_group_idx"),
            models.Index(fields=["scheduled_at"], name="a_animations_sched_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class AnimationSong(models.Model):
    animation_song_id = models.AutoField(primary_key=True)
    animation = models.ForeignKey(
        Animation,
        on_delete=models.CASCADE,
        db_column="animation_id",
        related_name="animation_songs",
    )
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        related_name="animation_usages",
    )
    position = models.IntegerField(default=1000)

    text_color_override = models.CharField(max_length=32, blank=True, null=True)
    bg_color_override = models.CharField(max_length=32, blank=True, null=True)
    font_family_override = models.CharField(max_length=120, blank=True, null=True)
    font_size_override = models.PositiveIntegerField(blank=True, null=True)
    horizontal_padding_override = models.PositiveIntegerField(blank=True, null=True)
    background_asset_code_override = models.CharField(max_length=128, blank=True, null=True)

    class Meta:
        db_table = 'lss"."a_animation_songs'
        ordering = ["position", "animation_song_id"]
        indexes = [
            models.Index(fields=["animation"], name="a_anim_songs_anim_idx"),
            models.Index(fields=["position"], name="a_anim_songs_pos_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["animation", "position"], name="a_anim_songs_anim_pos_uniq"),
        ]


class AnimationVerseOverride(models.Model):
    pk = models.CompositePrimaryKey("animation_song", "source_verse_id")
    animation_song = models.ForeignKey(
        AnimationSong,
        on_delete=models.CASCADE,
        db_column="animation_song_id",
        related_name="verse_overrides",
    )
    source_verse_id = models.IntegerField()
    is_visible = models.BooleanField(default=True)

    text_color_override = models.CharField(max_length=32, blank=True, null=True)
    bg_color_override = models.CharField(max_length=32, blank=True, null=True)
    font_family_override = models.CharField(max_length=120, blank=True, null=True)
    font_size_override = models.PositiveIntegerField(blank=True, null=True)
    horizontal_padding_override = models.PositiveIntegerField(blank=True, null=True)
    background_asset_code_override = models.CharField(max_length=128, blank=True, null=True)

    class Meta:
        db_table = 'lss"."a_animation_verse_overrides'
        indexes = [
            models.Index(fields=["animation_song"], name="a_anim_vo_anim_song_idx"),
            models.Index(fields=["source_verse_id"], name="a_anim_vo_source_idx"),
        ]
