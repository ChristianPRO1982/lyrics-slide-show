from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def get_animation_archive_delay() -> timedelta:
    hours = max(0, int(getattr(settings, "ANIMATION_ARCHIVE_DELAY_HOURS", 48)))
    return timedelta(hours=hours)


def get_animation_archive_threshold():
    return timezone.now() - get_animation_archive_delay()
