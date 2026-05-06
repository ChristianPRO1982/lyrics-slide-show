from __future__ import annotations

import re

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user
from app_song.models import Song
from app_song.search import (
    SONG_SEARCH_VALIDATION_VALUES,
    SongReferenceOptions,
    SongSearchParams,
    get_reference_options,
    search_songs,
)

from .forms import AnimationForm
from .models import Animation, AnimationSong, AnimationVerseOverride
from .services.access import ensure_animation_in_selected_group, get_selected_group_or_404
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.render_bundle import build_animation_render_bundle


SONG_OVERRIDE_PATTERN = re.compile(r"^song_overrides\[(?P<animation_song_id>\d+)\]\[(?P<field>[a-z_]+)\]$")
VERSE_OVERRIDE_PATTERN = re.compile(r"^rows\[(?P<verse_id>\d+)\]\[(?P<field>[a-z_]+)\]$")


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _bool_from_query(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "and"}


def _normalize_ids(values: list[str]) -> tuple[int, ...]:
    normalized: list[int] = []
    for value in values:
        try:
            item_id = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if item_id > 0 and item_id not in normalized:
            normalized.append(item_id)
    return tuple(normalized)


def _ids_from_query(request: HttpRequest, name: str) -> tuple[int, ...]:
    values: list[str] = []
    for value in request.GET.getlist(name):
        values.extend(value.split(","))
    return _normalize_ids(values)


def _build_song_search_params(request: HttpRequest, mode: str) -> SongSearchParams:
    search_text = str(request.GET.get("song_q") or "").strip()

    if mode == "advanced":
        validation = str(request.GET.get("validation") or "all").strip().lower()
        if validation not in SONG_SEARCH_VALIDATION_VALUES:
            validation = "all"
        search_logic = str(request.GET.get("search_logic") or "or").strip().lower()
        return SongSearchParams(
            text=search_text,
            everywhere=_bool_from_query(request.GET.get("everywhere")),
            match_all_selected_refs=search_logic == "and",
            genre_ids=_ids_from_query(request, "genre_ids"),
            band_ids=_ids_from_query(request, "band_ids"),
            artist_ids=_ids_from_query(request, "artist_ids"),
            validation=validation,
            favorites_only=False,
        )

    if mode == "favorites":
        return SongSearchParams(text=search_text, favorites_only=True)

    return SongSearchParams(text=search_text)


def _empty_reference_options() -> SongReferenceOptions:
    return SongReferenceOptions(genres=(), bands=(), artists=())


def _build_song_selector_context(request: HttpRequest) -> dict[str, object]:
    member_id = get_member_id_from_user(request.user)
    song_mode = str(request.GET.get("song_mode") or "all").strip().lower()
    if song_mode not in {"all", "favorites", "advanced"}:
        song_mode = "all"

    if song_mode == "favorites" and not member_id:
        song_mode = "all"

    params = _build_song_search_params(request, song_mode)
    search_results = search_songs(params, request.user, member_id)

    reference_options = _empty_reference_options()
    if _is_authenticated(request.user):
        reference_options = get_reference_options()

    return {
        "song_mode": song_mode,
        "song_search": search_results,
        "song_reference_options": reference_options,
        "song_search_text": params.text,
        "can_use_favorites": bool(member_id),
        "can_use_advanced": _is_authenticated(request.user),
    }


def _normalize_nullable_string(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_nullable_int(value: str | None) -> int | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        parsed = int(normalized)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _save_song_overrides(request: HttpRequest, animation: Animation) -> None:
    editable_fields = {
        "text_color_override",
        "bg_color_override",
        "font_family_override",
        "font_size_override",
        "horizontal_padding_override",
        "background_asset_code_override",
    }

    updates_by_song_id: dict[int, dict[str, object]] = {}
    for key, value in request.POST.items():
        match = SONG_OVERRIDE_PATTERN.match(key)
        if not match:
            continue
        animation_song_id = int(match.group("animation_song_id"))
        field = match.group("field")
        if field not in editable_fields:
            continue
        updates_by_song_id.setdefault(animation_song_id, {})[field] = value

    if not updates_by_song_id:
        return

    with transaction.atomic():
        for animation_song in AnimationSong.objects.filter(
            animation_id=animation.animation_id,
            animation_song_id__in=tuple(updates_by_song_id.keys()),
        ):
            field_values = updates_by_song_id.get(animation_song.animation_song_id, {})
            update_fields: list[str] = []
            for field_name in editable_fields:
                if field_name not in field_values:
                    continue
                if field_name in {"font_size_override", "horizontal_padding_override"}:
                    normalized_value = _normalize_nullable_int(field_values[field_name])
                else:
                    normalized_value = _normalize_nullable_string(field_values[field_name])
                if getattr(animation_song, field_name) != normalized_value:
                    setattr(animation_song, field_name, normalized_value)
                    update_fields.append(field_name)

            if update_fields:
                animation_song.save(update_fields=update_fields)


def _build_accessible_song_ids(user) -> set[int]:
    queryset = Song.objects.all()
    if not _is_authenticated(user):
        queryset = queryset.filter(licensed=False)
    return set(queryset.values_list("song_id", flat=True))


def animations(request: HttpRequest) -> HttpResponse:
    selected_group = get_selected_group_or_404(request)
    now = timezone.now()
    upcoming_animations = Animation.objects.filter(
        group_id=selected_group.group_id,
        scheduled_at__gte=now,
    ).order_by("scheduled_at", "animation_id")

    return render(
        request,
        "animation/animations.html",
        {
            "selected_group": selected_group,
            "upcoming_animations": upcoming_animations,
        },
    )


def animation_history(request: HttpRequest) -> HttpResponse:
    selected_group = get_selected_group_or_404(request)
    now = timezone.now()
    past_animations = Animation.objects.filter(
        group_id=selected_group.group_id,
        scheduled_at__lt=now,
    ).order_by("-scheduled_at", "-animation_id")

    return render(
        request,
        "animation/animation_history.html",
        {
            "selected_group": selected_group,
            "past_animations": past_animations,
        },
    )


def new_animation(request: HttpRequest) -> HttpResponse:
    selected_group = get_selected_group_or_404(request)

    if request.method == "POST":
        form = AnimationForm(request.POST)
        if form.is_valid():
            animation = form.save(commit=False)
            animation.group = selected_group
            animation.save()
            messages.success(request, _("L'animation a été créée."))
            return redirect("edit_animation", animation_id=animation.animation_id)
    else:
        form = AnimationForm(initial={"scheduled_at": timezone.localtime(timezone.now())})

    return render(
        request,
        "animation/animation_form.html",
        {
            "selected_group": selected_group,
            "form": form,
            "is_creation": True,
            "animation": None,
        },
    )


def edit_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    animation = get_object_or_404(Animation, animation_id=animation_id)
    selected_group = ensure_animation_in_selected_group(request, animation)

    if request.method == "POST":
        action = str(request.POST.get("action") or "save_animation").strip()

        if action == "save_animation":
            form = AnimationForm(request.POST, instance=animation)
            if form.is_valid():
                form.save()
                messages.success(request, _("Les paramètres de l'animation ont été enregistrés."))
                return redirect("edit_animation", animation_id=animation.animation_id)
        elif action == "save_playlist":
            ordered_tokens = parse_ordered_mix(request.POST.get("ordered_mix"))
            allowed_song_ids = _build_accessible_song_ids(request.user)
            sync_result = sync_animation_playlist(animation, ordered_tokens, allowed_song_ids)
            messages.success(
                request,
                _("Playlist enregistrée (%(created)s ajoutés, %(deleted)s supprimés).")
                % {"created": sync_result.created_count, "deleted": sync_result.deleted_count},
            )
            return redirect("edit_animation", animation_id=animation.animation_id)
        elif action == "save_song_overrides":
            _save_song_overrides(request, animation)
            messages.success(request, _("Les overrides de chants ont été enregistrés."))
            return redirect("edit_animation", animation_id=animation.animation_id)
        else:
            raise Http404
    else:
        form = AnimationForm(instance=animation)

    selector_context = _build_song_selector_context(request)
    playlist = list(animation.animation_songs.select_related("song").order_by("position", "animation_song_id"))
    bundle = build_animation_render_bundle(animation)

    return render(
        request,
        "animation/animation_form.html",
        {
            "selected_group": selected_group,
            "form": form,
            "is_creation": False,
            "animation": animation,
            "playlist": playlist,
            "rendered_bundle_count": len(bundle),
            **selector_context,
        },
    )


def delete_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    if request.method != "POST":
        raise Http404

    animation = get_object_or_404(Animation, animation_id=animation_id)
    ensure_animation_in_selected_group(request, animation)
    animation.delete()
    messages.success(request, _("L'animation a été supprimée."))
    return redirect("animations")


def _build_verse_override_rows(animation_song: AnimationSong) -> list[dict[str, object]]:
    overrides_by_verse_id = {
        override.source_verse_id: override
        for override in animation_song.verse_overrides.all()
    }

    rows_by_verse_id: dict[int, dict[str, object]] = {}
    for verse in animation_song.song.verses.all().order_by("num", "verse_id"):
        if verse.verse_id in rows_by_verse_id:
            continue
        override = overrides_by_verse_id.get(verse.verse_id)
        rows_by_verse_id[verse.verse_id] = {
            "verse_id": verse.verse_id,
            "label": (verse.prefix or "").strip() or (_("Refrain") if verse.chorus else _("Couplet %(num)s") % {"num": verse.num_verse}),
            "text": verse.text or "",
            "is_visible": override.is_visible if override is not None else True,
            "text_color_override": override.text_color_override if override is not None else "",
            "bg_color_override": override.bg_color_override if override is not None else "",
            "font_family_override": override.font_family_override if override is not None else "",
            "font_size_override": override.font_size_override if override is not None else "",
            "horizontal_padding_override": override.horizontal_padding_override if override is not None else "",
            "background_asset_code_override": override.background_asset_code_override if override is not None else "",
        }
    return list(rows_by_verse_id.values())


def _save_verse_overrides(request: HttpRequest, animation_song: AnimationSong) -> None:
    rows_by_verse_id: dict[int, dict[str, str]] = {}
    for key, value in request.POST.items():
        match = VERSE_OVERRIDE_PATTERN.match(key)
        if not match:
            continue
        verse_id = int(match.group("verse_id"))
        field = match.group("field")
        rows_by_verse_id.setdefault(verse_id, {})[field] = value

    editable_verse_ids = {
        verse.verse_id
        for verse in animation_song.song.verses.all()
    }

    with transaction.atomic():
        for verse_id, row in rows_by_verse_id.items():
            if verse_id not in editable_verse_ids:
                continue

            is_visible = _bool_from_query(row.get("visible", "1"))
            text_color = _normalize_nullable_string(row.get("text_color"))
            bg_color = _normalize_nullable_string(row.get("bg_color"))
            font_family = _normalize_nullable_string(row.get("font_family"))
            font_size = _normalize_nullable_int(row.get("font_size"))
            horizontal_padding = _normalize_nullable_int(row.get("horizontal_padding"))
            background_asset_code = _normalize_nullable_string(row.get("background_asset_code"))

            has_effective_override = (
                not is_visible
                or text_color is not None
                or bg_color is not None
                or font_family is not None
                or font_size is not None
                or horizontal_padding is not None
                or background_asset_code is not None
            )

            if not has_effective_override:
                AnimationVerseOverride.objects.filter(
                    animation_song_id=animation_song.animation_song_id,
                    source_verse_id=verse_id,
                ).delete()
                continue

            AnimationVerseOverride.objects.update_or_create(
                animation_song_id=animation_song.animation_song_id,
                source_verse_id=verse_id,
                defaults={
                    "is_visible": is_visible,
                    "text_color_override": text_color,
                    "bg_color_override": bg_color,
                    "font_family_override": font_family,
                    "font_size_override": font_size,
                    "horizontal_padding_override": horizontal_padding,
                    "background_asset_code_override": background_asset_code,
                },
            )


def edit_animation_song_verses(request: HttpRequest, animation_id: int, animation_song_id: int) -> HttpResponse:
    animation = get_object_or_404(Animation, animation_id=animation_id)
    selected_group = ensure_animation_in_selected_group(request, animation)

    animation_song = get_object_or_404(
        AnimationSong.objects.select_related("song", "animation").prefetch_related("song__verses", "verse_overrides"),
        animation_song_id=animation_song_id,
        animation_id=animation.animation_id,
    )

    if request.method == "POST":
        _save_verse_overrides(request, animation_song)
        messages.success(request, _("Les overrides de couplets ont été enregistrés."))
        return redirect(
            "edit_animation_song_verses",
            animation_id=animation.animation_id,
            animation_song_id=animation_song.animation_song_id,
        )

    return render(
        request,
        "animation/animation_song_verses.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "animation_song": animation_song,
            "rows": _build_verse_override_rows(animation_song),
        },
    )
