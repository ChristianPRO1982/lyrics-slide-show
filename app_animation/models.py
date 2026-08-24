from django.db import models
from django.utils.translation import gettext_lazy as _

from app_group.models import Group
from app_song.models import Song, SongSlideDisplayMode


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

    text_color = models.CharField(max_length=32, default="#FFFFFF")
    bg_color = models.CharField(max_length=32, default="#000000", blank=True, null=True)
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
    slide_display_mode = models.CharField(
        max_length=32,
        choices=SongSlideDisplayMode.choices,
        default=SongSlideDisplayMode.SINGLE,
    )

    text_color_override = models.CharField(max_length=32, blank=True, null=True)
    bg_color_override = models.CharField(max_length=32, blank=True, null=True)
    font_family_override = models.CharField(max_length=120, blank=True, null=True)
    font_size_override = models.PositiveIntegerField(blank=True, null=True)
    horizontal_padding_override = models.PositiveIntegerField(blank=True, null=True)
    background_asset_code_override = models.CharField(
        max_length=128, blank=True, null=True
    )

    class Meta:
        db_table = 'lss"."a_animation_songs'
        ordering = ["position", "animation_song_id"]
        indexes = [
            models.Index(fields=["animation"], name="a_anim_songs_anim_idx"),
            models.Index(fields=["position"], name="a_anim_songs_pos_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["animation", "position"], name="a_anim_songs_anim_pos_uniq"
            ),
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
    background_asset_code_override = models.CharField(
        max_length=128, blank=True, null=True
    )

    class Meta:
        db_table = 'lss"."a_animation_verse_overrides'
        indexes = [
            models.Index(fields=["animation_song"], name="a_anim_vo_anim_song_idx"),
            models.Index(fields=["source_verse_id"], name="a_anim_vo_source_idx"),
        ]


class AnimationRemoteShortcut(models.Model):
    member_id = models.UUIDField(primary_key=True, editable=False)
    lyrics_slide_show_bindings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lss"."m_animation_remote_shortcuts'


class BackgroundImageStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    INACTIVE = "inactive", _("Inactive")
    ACTIVE = "active", _("Active")


class BackgroundImage(models.Model):
    image_id = models.AutoField(primary_key=True)
    asset_code = models.CharField(max_length=128, unique=True)
    storage_filename = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    target = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=16,
        choices=BackgroundImageStatus.choices,
        default=BackgroundImageStatus.PENDING,
    )
    stored_path = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=16)
    mime = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    member_id = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    moderated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'lss"."a_background_images'
        ordering = ["title", "image_id"]
        indexes = [
            models.Index(fields=["status"], name="a_bg_images_status_idx"),
            models.Index(fields=["asset_code"], name="a_bg_images_asset_idx"),
        ]


class BackgroundImageGenre(models.Model):
    image = models.ForeignKey(
        BackgroundImage,
        on_delete=models.CASCADE,
        db_column="image_id",
        related_name="genre_relations",
    )
    genre_id = models.IntegerField()

    class Meta:
        db_table = 'lss"."a_background_image_genres'
        constraints = [
            models.UniqueConstraint(
                fields=["image", "genre_id"],
                name="a_bg_image_genres_unique",
            ),
        ]
