from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from app_animation.models import Animation


def get_animation_archive_delay() -> timedelta:
    hours = max(0, int(getattr(settings, "ANIMATION_ARCHIVE_DELAY_HOURS", 48)))
    return timedelta(hours=hours)


def get_animation_archive_threshold():
    return timezone.now() - get_animation_archive_delay()


def get_animation_upcoming_lookahead_days() -> int:
    return max(0, int(getattr(settings, "ANIMATION_UPCOMING_LOOKAHEAD_DAYS", 63)))


def get_animation_upcoming_lookahead_delay() -> timedelta:
    return timedelta(days=get_animation_upcoming_lookahead_days())


def build_animation_group_stats(group_id: int) -> dict[str, int]:
    now = timezone.now()
    archive_threshold = now - get_animation_archive_delay()
    upcoming_limit = now + get_animation_upcoming_lookahead_delay()
    group_animations = Animation.objects.filter(group_id=group_id)

    return {
        "upcoming": group_animations.filter(
            scheduled_at__gte=archive_threshold,
            scheduled_at__lte=upcoming_limit,
        ).count(),
        "future": group_animations.filter(scheduled_at__gte=archive_threshold).count(),
        "past": group_animations.filter(scheduled_at__lt=archive_threshold).count(),
    }
