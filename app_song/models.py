from django.db import models
from django.utils.translation import gettext_lazy as _


SONG_STATUS_NOT_VALIDATED = 0
SONG_STATUS_VALIDATED = 1
SONG_STATUS_VALIDATED_WITH_CONCERN = 2

LINK_TYPE_INTERNAL = "internal"
LINK_TYPE_WEB = "web"
LINK_TYPE_SCORE = "score"
LINK_TYPE_AUDIO = "audio"
LINK_TYPE_YOUTUBE = "youtube"


class SongStatus(models.IntegerChoices):
    NOT_VALIDATED = SONG_STATUS_NOT_VALIDATED, _("Not validated")
    VALIDATED = SONG_STATUS_VALIDATED, _("Validated")
    VALIDATED_WITH_CONCERN = (
        SONG_STATUS_VALIDATED_WITH_CONCERN,
        _("Validated with concern"),
    )


class SongLinkType(models.TextChoices):
    SCORE = LINK_TYPE_SCORE, _("partition")
    AUDIO = LINK_TYPE_AUDIO, _("audio")
    YOUTUBE = LINK_TYPE_YOUTUBE, _("YouTube")
    WEB = LINK_TYPE_WEB, _("page Web")
    INTERNAL = LINK_TYPE_INTERNAL, _("lien interne - Lyrics Slide Show")


class Song(models.Model):
    song_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, db_column="sub_title")
    description = models.TextField(blank=True, null=True)
    status = models.IntegerField(
        choices=SongStatus.choices,
        default=SongStatus.NOT_VALIDATED,
    )
    licensed = models.BooleanField(default=False)

    class Meta:
        db_table = 'lss"."s_songs'
        constraints = [
            models.UniqueConstraint(
                fields=["title", "subtitle"],
                name="s_songs_unique",
            ),
        ]
        ordering = ["title", "subtitle"]

    def __str__(self) -> str:
        return self.display_title

    @property
    def is_validated(self) -> bool:
        return self.status in {
            SongStatus.VALIDATED,
            SongStatus.VALIDATED_WITH_CONCERN,
        }

    @property
    def validation_marker(self) -> str:
        if self.status == SongStatus.VALIDATED:
            return "✔️"
        if self.status == SongStatus.VALIDATED_WITH_CONCERN:
            return "✔️⁉️"
        return ""

    @property
    def display_title(self) -> str:
        title = self.title
        if self.subtitle:
            title = f"{title} - {self.subtitle}"
        marker = self.validation_marker
        if marker:
            title = f"{title} {marker}"
        if self.licensed:
            title = f"{title} ©"
        return title


class SongMessage(models.Model):
    message_id = models.AutoField(primary_key=True)
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="messages",
        db_index=False,
    )
    message = models.TextField()
    is_read = models.BooleanField(db_column="vu", default=False)
    date = models.DateTimeField()

    class Meta:
        db_table = 'lss"."s_song_messages'
        ordering = ["-date", "-message_id"]


class SongLink(models.Model):
    pk = models.CompositePrimaryKey("song", "link")
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="links",
        db_index=False,
    )
    link = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20,
        choices=SongLinkType.choices,
        default=SongLinkType.SCORE,
    )

    class Meta:
        db_table = 'lss"."s_song_links'
        ordering = ["link"]


class Verse(models.Model):
    verse_id = models.AutoField(primary_key=True)
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="verses",
        db_index=False,
    )
    num = models.IntegerField(default=1000)
    num_verse = models.IntegerField(default=1000)
    chorus = models.BooleanField(default=False)
    chorus_like = models.BooleanField(default=False)
    followed = models.BooleanField(default=False)
    notcontinuenumbering = models.BooleanField(default=False)
    text = models.TextField(blank=True, null=True)
    prefix = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'lss"."s_verses'
        indexes = [
            models.Index(fields=["song"], name="s_verses_song_id_idx"),
            models.Index(fields=["num"], name="s_verses_num_idx"),
            models.Index(fields=["chorus"], name="s_verses_chorus_idx"),
        ]
        ordering = ["num", "verse_id"]


class VersePrefix(models.Model):
    prefix_id = models.AutoField(primary_key=True)
    prefix = models.CharField(max_length=15)
    comment = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'lss"."s_verse_prefixes'
        constraints = [
            models.UniqueConstraint(
                fields=["prefix"],
                name="s_verse_prefixes_unique",
            ),
        ]
        ordering = ["prefix"]

    def __str__(self) -> str:
        return self.prefix


class SongGenre(models.Model):
    pk = models.CompositePrimaryKey("song", "genre_id")
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="genre_relations",
        db_index=False,
    )
    genre_id = models.IntegerField()

    class Meta:
        db_table = 'lss"."s_song_genres'


class SongArtist(models.Model):
    pk = models.CompositePrimaryKey("song", "artist_id")
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="artist_relations",
        db_index=False,
    )
    artist_id = models.IntegerField()

    class Meta:
        db_table = 'lss"."s_song_artists'


class SongBand(models.Model):
    pk = models.CompositePrimaryKey("song", "band_id")
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="band_relations",
        db_index=False,
    )
    band_id = models.IntegerField()

    class Meta:
        db_table = 'lss"."s_song_bands'


class SongFavorite(models.Model):
    pk = models.CompositePrimaryKey("song", "member_id")
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        db_column="song_id",
        db_constraint=False,
        related_name="favorites",
        db_index=False,
    )
    member_id = models.UUIDField(db_column="user_id")

    class Meta:
        db_table = 'lss"."m_songs_users'
