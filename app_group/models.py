import re

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _


_GROUP_NAME_SPACES_RE = re.compile(r"\s+")
_GROUP_INFO_SPACES_RE = re.compile(r"[^\S\n]+")


def normalize_group_name(value: str) -> str:
    return _GROUP_NAME_SPACES_RE.sub(" ", value.strip())


def normalize_group_info(value: str) -> str:
    normalized_newlines = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized_lines = [
        _GROUP_INFO_SPACES_RE.sub(" ", line).strip()
        for line in strip_tags(normalized_newlines).split("\n")
    ]
    return "\n".join(normalized_lines).strip()


class GroupStatus(models.TextChoices):
    OPEN = "open", _("Open")
    PRIVATE = "private", _("Private")


class Group(models.Model):
    group_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    info = models.TextField(blank=True, null=True)
    secret_ciphertext = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=32,
        choices=GroupStatus.choices,
        default=GroupStatus.OPEN,
    )

    class Meta:
        db_table = 'lss"."g_groups'
        indexes = [
            models.Index(fields=["status"], name="g_groups_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=[GroupStatus.OPEN, GroupStatus.PRIVATE]),
                name="g_groups_status_check",
            ),
            models.UniqueConstraint(
                Lower("name"),
                name="g_groups_name_unique",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.name = normalize_group_name(self.name)
        self.info = normalize_group_info(self.info) if self.info else None

    def save(self, *args, **kwargs):
        self.name = normalize_group_name(self.name)
        self.info = normalize_group_info(self.info) if self.info else None
        return super().save(*args, **kwargs)

    @property
    def business_status(self) -> str:
        if self.status == GroupStatus.PRIVATE and self.secret_ciphertext:
            return "private_with_secret"
        return self.status

    def __str__(self) -> str:
        return self.name


class GroupMembership(models.Model):
    pk = models.CompositePrimaryKey("group", "member_id")
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column="group_id",
        related_name="memberships",
    )
    member_id = models.UUIDField()
    is_group_admin = models.BooleanField(default=False)

    class Meta:
        db_table = 'lss"."g_group_user'
        indexes = [
            models.Index(fields=["is_group_admin"], name="g_grp_usr_is_admin_idx"),
        ]


class GroupJoinRequest(models.Model):
    pk = models.CompositePrimaryKey("group", "member_id")
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column="group_id",
        related_name="join_requests",
    )
    member_id = models.UUIDField()

    class Meta:
        db_table = 'lss"."g_group_user_ask_to_join'
