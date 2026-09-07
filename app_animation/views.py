from __future__ import annotations

import random
import re
import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user, get_selected_group_state
from app_main import lyrics as lyrics_helpers
from app_main.lyrics import (
    build_lyrics_page_context,
    build_lyrics_song_entry,
    build_qr_png_base64,
    build_request_share_url,
)
from app_member.services import can_manage_moderator_popup
from app_song.models import SongSlideDisplayMode, Verse
from app_song.rendering import ChorusRenderMode, SongRenderSettings
from app_song.search import SongSearchParams, load_member_song_search, search_songs

from .font_catalog import (
    GOOGLE_FONTS_STYLESHEET_HREF,
    list_font_choices,
    list_font_previews,
)
from .forms import (
    AnimationForm,
    BackgroundImageInactiveEditForm,
    BackgroundImageUploadForm,
)
from .models import (
    Animation,
    AnimationSong,
    AnimationVerseOverride,
    BackgroundImage,
    BackgroundImageStatus,
)
from .transitions import (
    list_enabled_transition_options,
    list_enabled_transition_runtime_options,
    resolve_enabled_transition_id,
)
from .services.background_images import (
    active_background_image_options,
    build_background_context_slug,
    build_image_validation_config,
    clear_background_image_references,
    count_background_image_references,
    delete_image_file,
    ensure_background_image_dirs,
    fetch_active_background_genre_options,
    fetch_genre_options,
    fetch_target_options,
    generate_asset_code,
    list_background_images_for_view,
    move_image_to_status,
    normalize_genre_ids,
    normalize_member_id,
    relative_stored_path,
    replace_image_genres,
    resolve_background_asset_url,
    store_uploaded_image_file,
)
from .services.render_bundle import build_animation_render_bundle
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.song_edits import (
    apply_songs_payload,
    build_main_song_cards,
    build_songs_payload_initial,
    normalize_animation_song_slide_display_mode,
    parse_songs_payload,
    serialize_songs_payload,
)
from .utils import _open_image, validate_image
from .services.access import (
    get_selected_group_or_404,
    redirect_to_groups_when_no_selection,
)
from .services.shortcuts import (
    SHORTCUT_ACTION_ORDER,
    SHORTCUT_ACTION_TO_REMOTE_ACTION,
    build_effective_shortcut_bindings,
    build_form_shortcut_bindings,
    build_site_shortcut_bindings,
    format_shortcut_token,
    load_member_shortcut_bindings,
    save_member_shortcut_bindings,
    validate_shortcut_submission,
)

qrcode = lyrics_helpers.qrcode

TARGET_ROW_FIELD_PATTERN = re.compile(
    r"^rows\[(?P<target_id>\d+)\]\[(?P<field>name|sort_order|delete)\]$"
)


def _safe_int(value: str | None, fallback: int) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return fallback


def _shortcut_action_labels() -> dict[str, str]:
    return {
        "black": _("BLACK MODE"),
        "prev_slide": _("Diapo précédente"),
        "next_slide": _("Diapo suivante"),
        "chorus": _("Refrain"),
        "open_display": _("Afficher la fenêtre de la diapo en cours"),
        "prev_song": _("Chant précédent"),
        "next_song": _("Chant suivant"),
        "toggle_chorus": _("Afficher / masquer les refrains"),
        "toggle_scroll": _("Scroll on ↕️ or not 🧱"),
        "toggle_qr": _("📱 QR code pour les paroles"),
        "next_transition": _("Transition suivante"),
        "force_direct": _("Forcer Direct"),
    }


def _serialize_shortcut_bindings(
    bindings: dict[str, list[str]],
) -> dict[str, list[str]]:
    return {
        action: [str(token) for token in bindings.get(action, [])]
        for action in SHORTCUT_ACTION_ORDER
    }


def _build_shortcuts_config(
    request: HttpRequest,
    animation: Animation,
) -> dict[str, object]:
    member_id = get_member_id_from_user(request.user)
    saved_bindings = load_member_shortcut_bindings(member_id)
    can_customize = bool(member_id)
    action_labels = _shortcut_action_labels()
    return {
        "siteBindings": _serialize_shortcut_bindings(build_site_shortcut_bindings()),
        "effectiveBindings": _serialize_shortcut_bindings(
            build_effective_shortcut_bindings(saved_bindings)
        ),
        "formBindings": _serialize_shortcut_bindings(
            build_form_shortcut_bindings(saved_bindings)
        ),
        "actionOrder": list(SHORTCUT_ACTION_ORDER),
        "actionToRemoteAction": dict(SHORTCUT_ACTION_TO_REMOTE_ACTION),
        "actionLabels": action_labels,
        "canCustomizeShortcuts": can_customize,
        "customizeUrl": reverse(
            "lyrics_slide_show_shortcuts", args=[animation.animation_id]
        ),
    }


def animations(request: HttpRequest) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)
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


def _translate_image_validation_error(error_code: str, cfg: dict[str, object]) -> str:
    if error_code == "too_large":
        max_bytes = int(cfg.get("max_bytes", 0))
        max_mb = max_bytes / (1024 * 1024) if max_bytes else 0
        return _("L'image dépasse la taille autorisée (%(size).1f Mo maximum).") % {
            "size": max_mb
        }
    if error_code == "invalid_extension":
        return _("L'extension de cette image n'est pas autorisée.")
    if error_code == "invalid_mime":
        return _("Le type MIME de cette image n'est pas autorisé.")
    if error_code == "invalid_image":
        return _("Le fichier envoyé n'est pas une image valide.")
    if error_code == "too_small":
        return _("L'image est trop petite pour être utilisée en fond.")
    if error_code == "too_large_dimensions":
        return _("L'image dépasse les dimensions autorisées.")
    if error_code == "invalid_ratio":
        return _("Le ratio de l'image n'est pas autorisé.")
    return _("Cette image n'est pas conforme.")


def _background_image_popup_options() -> list[dict[str, object]]:
    return [
        {
            "value": item["asset_code"],
            "label": " | ".join(
                part
                for part in [
                    str(item["title"]),
                    str(item["target"]),
                    ", ".join(item["genres"]) if item["genres"] else "",
                ]
                if part
            ),
            "imageUrl": item["url"],
            "title": item["title"],
            "target": item["target"],
            "genres": list(item["genres"]),
        }
        for item in active_background_image_options()
    ]


def _normalize_background_picker_level(value: str | None) -> str:
    level = str(value or "").strip().lower()
    if level in {"animation", "song", "verse"}:
        return level
    return "animation"


def _build_background_picker_url(
    animation: Animation,
    *,
    level: str,
    animation_song_id: int | None = None,
    verse_id: int | None = None,
    selected_asset_code: str | None = None,
    genre_ids: list[int] | None = None,
    query: str | None = None,
) -> str:
    query_parts: list[tuple[str, str | int]] = [
        ("level", _normalize_background_picker_level(level))
    ]
    if animation_song_id:
        query_parts.append(("animation_song_id", int(animation_song_id)))
    if verse_id:
        query_parts.append(("verse_id", int(verse_id)))
    if selected_asset_code:
        query_parts.append(("selected_asset_code", selected_asset_code))
    if query:
        query_parts.append(("q", query))
    for genre_id in genre_ids or []:
        if int(genre_id) > 0:
            query_parts.append(("genre_ids", int(genre_id)))
    return (
        reverse("animation_background_picker", args=[animation.animation_id])
        + "?"
        + urlencode(query_parts, doseq=True)
    )


def _build_style_picker_url(
    animation: Animation,
    *,
    level: str,
    animation_song_id: int | None = None,
    verse_id: int | None = None,
    selected_occurrence_token: str | None = None,
) -> str:
    query_parts: list[tuple[str, str | int]] = [
        ("level", _normalize_background_picker_level(level))
    ]
    if animation_song_id:
        query_parts.append(("animation_song_id", int(animation_song_id)))
    if verse_id:
        query_parts.append(("verse_id", int(verse_id)))
    if selected_occurrence_token:
        query_parts.append(("selected_occurrence_token", selected_occurrence_token))
    return (
        reverse("animation_style_picker", args=[animation.animation_id])
        + "?"
        + urlencode(query_parts, doseq=True)
    )


def _build_modify_animation_return_url(
    animation: Animation,
    *,
    animation_song_id: int | None = None,
) -> str:
    url = reverse("modify_animation", args=[animation.animation_id])
    if not animation_song_id:
        return url
    return f"{url}#animation-song-{int(animation_song_id)}"


def _resolve_background_picker_target(
    animation: Animation,
    *,
    level: str,
    animation_song_id: int | None = None,
    verse_id: int | None = None,
) -> tuple[str, AnimationSong | None, Verse | None]:
    normalized_level = _normalize_background_picker_level(level)
    if normalized_level == "animation":
        return normalized_level, None, None

    parsed_animation_song_id = _safe_int(
        str(animation_song_id or "").strip() or None,
        fallback=0,
    )
    if parsed_animation_song_id <= 0:
        raise Http404

    animation_song = get_object_or_404(
        AnimationSong.objects.select_related("song"),
        animation=animation,
        animation_song_id=parsed_animation_song_id,
    )
    if normalized_level == "song":
        return normalized_level, animation_song, None

    parsed_verse_id = _safe_int(str(verse_id or "").strip() or None, fallback=0)
    if parsed_verse_id <= 0:
        raise Http404
    verse = get_object_or_404(
        Verse.objects.filter(song_id=animation_song.song_id),
        verse_id=parsed_verse_id,
    )
    return normalized_level, animation_song, verse


def _resolve_picker_scope_style(
    animation: Animation,
    *,
    level: str,
    animation_song: AnimationSong | None = None,
    verse: Verse | None = None,
) -> dict[str, object]:
    animation_bg_color = str(animation.bg_color or "").strip() or "#000000"
    animation_bg_asset = str(animation.background_asset_code or "").strip()
    animation_text_color = str(animation.text_color or "").strip() or "#FFFFFF"
    animation_font_family = (
        str(animation.font_family or "").strip() or "Source Sans Pro"
    )
    animation_font_size = int(animation.font_size or 72)

    if level == "animation":
        return {
            "text_color": animation_text_color,
            "font_family": animation_font_family,
            "font_size": animation_font_size,
            "bg_color": animation_bg_color,
            "effective_background_asset_code": animation_bg_asset,
            "local_background_asset_code": animation_bg_asset,
            "scope_title": _("Image de fond de l'animation"),
            "scope_label": animation.title,
        }

    if animation_song is None:
        raise Http404

    song_text_color = (
        str(animation_song.text_color_override or "").strip() or animation_text_color
    )
    song_font_family = (
        str(animation_song.font_family_override or "").strip() or animation_font_family
    )
    song_font_size = (
        int(animation_song.font_size_override)
        if animation_song.font_size_override is not None
        else animation_font_size
    )
    song_bg_color_override = str(animation_song.bg_color_override or "").strip()
    song_bg_asset_override = str(
        animation_song.background_asset_code_override or ""
    ).strip()
    song_bg_color = song_bg_color_override or animation_bg_color

    if song_bg_asset_override:
        song_effective_bg_asset = song_bg_asset_override
    elif song_bg_color_override:
        song_effective_bg_asset = ""
    else:
        song_effective_bg_asset = animation_bg_asset

    if level == "song":
        return {
            "text_color": song_text_color,
            "font_family": song_font_family,
            "font_size": song_font_size,
            "bg_color": song_bg_color,
            "effective_background_asset_code": song_effective_bg_asset,
            "local_background_asset_code": song_bg_asset_override,
            "scope_title": _("Image de fond du chant"),
            "scope_label": animation_song.song.display_title,
        }

    if verse is None:
        raise Http404

    verse_override = AnimationVerseOverride.objects.filter(
        animation_song=animation_song,
        source_verse_id=verse.verse_id,
    ).first()
    verse_text_color = (
        str(verse_override.text_color_override or "").strip()
        if verse_override and verse_override.text_color_override
        else song_text_color
    )
    verse_font_family = (
        str(verse_override.font_family_override or "").strip()
        if verse_override and verse_override.font_family_override
        else song_font_family
    )
    verse_font_size = (
        int(verse_override.font_size_override)
        if verse_override and verse_override.font_size_override is not None
        else song_font_size
    )
    verse_bg_color_override = (
        str(verse_override.bg_color_override or "").strip() if verse_override else ""
    )
    verse_bg_asset_override = (
        str(verse_override.background_asset_code_override or "").strip()
        if verse_override
        else ""
    )
    verse_bg_color = verse_bg_color_override or song_bg_color

    if verse_bg_asset_override:
        verse_effective_bg_asset = verse_bg_asset_override
    elif verse_bg_color_override:
        verse_effective_bg_asset = ""
    else:
        verse_effective_bg_asset = song_effective_bg_asset

    verse_label = _("Couplet %(number)s") % {"number": int(verse.num_verse or 0)}
    if verse.chorus:
        verse_label = _("Refrain")
    elif verse.chorus_like:
        verse_label = str(verse.prefix or "").strip() or _("Section spéciale")

    return {
        "text_color": verse_text_color,
        "font_family": verse_font_family,
        "font_size": verse_font_size,
        "bg_color": verse_bg_color,
        "effective_background_asset_code": verse_effective_bg_asset,
        "local_background_asset_code": verse_bg_asset_override,
        "scope_title": _("Image de fond du couplet"),
        "scope_label": f"{animation_song.song.display_title} - {verse_label}",
    }


def _build_picker_scope_heading(level: str, *, picker_kind: str) -> str:
    normalized_level = _normalize_background_picker_level(level)
    if picker_kind == "style":
        if normalized_level == "animation":
            return _("Style de l'animation")
        if normalized_level == "song":
            return _("Style du chant")
        return _("Style du couplet")
    if normalized_level == "animation":
        return _("Image de fond de l'animation")
    if normalized_level == "song":
        return _("Image de fond du chant")
    return _("Image de fond du couplet")


def _resolve_style_source_scope(
    animation: Animation,
    animation_song: AnimationSong,
    verse_override: AnimationVerseOverride | None,
) -> str:
    if verse_override and verse_override.font_size_override is not None:
        return "verse"
    if animation_song.font_size_override is not None:
        return "song"
    return "animation"


def _build_style_occurrence_label(
    slide,
    *,
    source_scope: str,
) -> str:
    if source_scope == "song":
        return _("Chant : %(title)s") % {"title": slide.song_title}
    if source_scope == "verse":
        return _("%(title)s - %(label)s") % {
            "title": slide.song_title,
            "label": slide.label,
        }
    return _("Animation - %(title)s - %(label)s") % {
        "title": slide.song_title,
        "label": slide.label,
    }


def _build_style_picker_options(animation: Animation) -> list[dict[str, object]]:
    animation_songs = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses", "verse_overrides")
        .order_by("position", "animation_song_id")
    )
    animation_songs_by_id = {
        int(item.animation_song_id): item for item in animation_songs
    }
    verse_overrides_by_key = {
        (int(item.animation_song_id), int(override.source_verse_id)): override
        for item in animation_songs
        for override in item.verse_overrides.all()
    }

    options_by_key: dict[
        tuple[str, int, str, str, str],
        dict[str, object],
    ] = {}
    for slide in build_animation_render_bundle(animation):
        background_asset_code = str(slide.style.background_asset_code or "").strip()
        style_key = (
            str(slide.style.font_family),
            int(slide.style.font_size),
            str(slide.style.text_color),
            str(slide.style.bg_color),
            background_asset_code,
        )
        animation_song = animation_songs_by_id.get(int(slide.animation_song_id))
        if animation_song is None:
            continue
        verse_override = None
        if slide.source_verse_id is not None:
            verse_override = verse_overrides_by_key.get(
                (int(slide.animation_song_id), int(slide.source_verse_id))
            )
        source_scope = _resolve_style_source_scope(
            animation,
            animation_song,
            verse_override,
        )
        occurrence_token = (
            f"{source_scope}:{int(slide.animation_song_id)}:"
            f"{int(slide.source_verse_id or 0)}"
        )
        option = options_by_key.setdefault(
            style_key,
            {
                "style_key": "|".join(
                    [
                        str(slide.style.font_family),
                        str(int(slide.style.font_size)),
                        str(slide.style.text_color),
                        str(slide.style.bg_color),
                        background_asset_code,
                    ]
                ),
                "font_family": str(slide.style.font_family),
                "font_size": int(slide.style.font_size),
                "text_color": str(slide.style.text_color),
                "bg_color": str(slide.style.bg_color),
                "background_asset_code": background_asset_code,
                "background_url": resolve_background_asset_url(background_asset_code),
                "occurrences": [],
                "preview_occurrences": [],
                "occurrence_tokens": set(),
            },
        )
        if occurrence_token in option["occurrence_tokens"]:
            continue
        occurrence = {
            "token": occurrence_token,
            "source_scope": source_scope,
            "label": _build_style_occurrence_label(slide, source_scope=source_scope),
        }
        option["occurrences"].append(occurrence)
        option["occurrence_tokens"].add(occurrence_token)
        if len(option["preview_occurrences"]) < 3:
            option["preview_occurrences"].append(occurrence)

    options = []
    for option in options_by_key.values():
        option["preview_has_more"] = len(option["occurrences"]) > len(
            option["preview_occurrences"]
        )
        option.pop("occurrence_tokens", None)
        options.append(option)
    options.sort(
        key=lambda item: (
            str(item["font_family"]).casefold(),
            int(item["font_size"]),
            str(item["text_color"]).casefold(),
            str(item["bg_color"]).casefold(),
            str(item["background_asset_code"]).casefold(),
        )
    )
    return options


def _find_style_picker_default_token(
    picker_scope_style: dict[str, object],
    style_options: list[dict[str, object]],
) -> str:
    target_font_family = str(picker_scope_style.get("font_family") or "").strip()
    target_font_size = int(picker_scope_style.get("font_size") or 0)
    target_text_color = str(picker_scope_style.get("text_color") or "").strip()
    target_bg_color = str(picker_scope_style.get("bg_color") or "").strip()
    target_bg_asset = str(
        picker_scope_style.get("effective_background_asset_code") or ""
    ).strip()
    for option in style_options:
        if (
            str(option.get("font_family") or "").strip() == target_font_family
            and int(option.get("font_size") or 0) == target_font_size
            and str(option.get("text_color") or "").strip() == target_text_color
            and str(option.get("bg_color") or "").strip() == target_bg_color
            and str(option.get("background_asset_code") or "").strip()
            == target_bg_asset
        ):
            occurrences = option.get("occurrences") or []
            if occurrences:
                return str(occurrences[0].get("token") or "").strip()
    return ""


def _apply_copied_style_to_target(
    *,
    animation: Animation,
    level: str,
    source_scope: str,
    copied_style: dict[str, object],
    animation_song: AnimationSong | None = None,
    verse: Verse | None = None,
) -> None:
    font_family = (
        str(copied_style.get("font_family") or "").strip() or animation.font_family
    )
    text_color = (
        str(copied_style.get("text_color") or "").strip() or animation.text_color
    )
    bg_color = str(copied_style.get("bg_color") or "").strip() or "#000000"
    background_asset_code = str(copied_style.get("background_asset_code") or "").strip()
    font_size = int(copied_style.get("font_size") or animation.font_size)

    if level == "animation":
        animation.font_family = font_family
        animation.text_color = text_color
        if background_asset_code:
            animation.background_asset_code = background_asset_code
            animation.bg_color = None
        else:
            animation.background_asset_code = None
            animation.bg_color = bg_color
        animation.save(
            update_fields=[
                "font_family",
                "text_color",
                "background_asset_code",
                "bg_color",
            ]
        )
        return

    if animation_song is None:
        raise Http404

    if level == "song":
        animation_song.font_family_override = font_family
        animation_song.text_color_override = text_color
        if background_asset_code:
            animation_song.background_asset_code_override = background_asset_code
            animation_song.bg_color_override = None
        else:
            animation_song.background_asset_code_override = None
            animation_song.bg_color_override = bg_color
        update_fields = [
            "font_family_override",
            "text_color_override",
            "background_asset_code_override",
            "bg_color_override",
        ]
        if source_scope == "song":
            animation_song.font_size_override = font_size
            update_fields.append("font_size_override")
        animation_song.save(update_fields=update_fields)
        return

    if verse is None:
        raise Http404
    verse_override, _created = AnimationVerseOverride.objects.get_or_create(
        animation_song=animation_song,
        source_verse_id=verse.verse_id,
        defaults={"is_visible": True},
    )
    verse_override.font_family_override = font_family
    verse_override.text_color_override = text_color
    if background_asset_code:
        verse_override.background_asset_code_override = background_asset_code
        verse_override.bg_color_override = None
    else:
        verse_override.background_asset_code_override = None
        verse_override.bg_color_override = bg_color
    update_fields = [
        "font_family_override",
        "text_color_override",
        "background_asset_code_override",
        "bg_color_override",
    ]
    if source_scope == "verse":
        verse_override.font_size_override = font_size
        update_fields.append("font_size_override")
    verse_override.save(update_fields=update_fields)


def _fetch_target_rows() -> list[dict[str, object]]:
    return fetch_target_options()


def _parse_target_rows(post_data) -> tuple[str, str, dict[int, dict[str, object]]]:
    new_name = str(post_data.get("new_name") or "").strip()
    new_sort_order = str(post_data.get("new_sort_order") or "").strip()
    rows_by_id: dict[int, dict[str, object]] = {}

    for key, value in post_data.items():
        match = TARGET_ROW_FIELD_PATTERN.match(key)
        if not match:
            continue
        target_id = int(match.group("target_id"))
        field = match.group("field")
        row = rows_by_id.setdefault(
            target_id,
            {"name": "", "sort_order": "", "delete": False},
        )
        if field == "delete":
            row["delete"] = str(value or "").strip().lower() in {"1", "true", "on"}
        else:
            row[field] = str(value or "").strip()

    return new_name, new_sort_order, rows_by_id


def _save_target_rows(request: HttpRequest) -> None:
    new_name, new_sort_order, parsed_rows = _parse_target_rows(request.POST)
    success_parts: list[str] = []
    error_parts: list[str] = []

    created_count = 0
    updated_count = 0
    deleted_count = 0

    existing_rows = _fetch_target_rows()
    existing_by_id = {int(item["id"]): item for item in existing_rows}

    if new_name or new_sort_order:
        if new_name and new_sort_order:
            sort_order_value = _safe_int(new_sort_order, fallback=0)
            if str(sort_order_value) != new_sort_order:
                error_parts.append(
                    _("Pour créer une cible, l'ordre doit être un entier valide.")
                )
            else:
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                'INSERT INTO "common"."targets" ("name", "sort_order") VALUES (%s, %s)',
                                [new_name, sort_order_value],
                            )
                    created_count += 1
                except IntegrityError:
                    error_parts.append(
                        _('Création impossible pour la cible "%(name)s".')
                        % {"name": new_name}
                    )
        else:
            error_parts.append(
                _("Pour créer une cible, renseignez à la fois le nom et l'ordre.")
            )

    for target_id, values in parsed_rows.items():
        existing = existing_by_id.get(target_id)
        if not existing:
            continue

        if bool(values.get("delete")):
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            'DELETE FROM "common"."targets" WHERE target_id = %s',
                            [target_id],
                        )
                deleted_count += 1
            except Exception:
                error_parts.append(
                    _("Suppression impossible pour la cible #%(target_id)s.")
                    % {"target_id": target_id}
                )
            continue

        new_name_value = str(values.get("name") or "").strip()
        new_sort_order_value = str(values.get("sort_order") or "").strip()
        if not new_name_value or not new_sort_order_value:
            error_parts.append(
                _(
                    "Mise à jour ignorée pour la cible #%(target_id)s (nom et ordre obligatoires)."
                )
                % {"target_id": target_id}
            )
            continue

        parsed_sort_order = _safe_int(new_sort_order_value, fallback=0)
        if str(parsed_sort_order) != new_sort_order_value:
            error_parts.append(
                _("Mise à jour ignorée pour la cible #%(target_id)s (ordre invalide).")
                % {"target_id": target_id}
            )
            continue

        old_name = str(existing.get("name") or "").strip()
        old_sort_order = int(existing.get("sort_order") or 0)
        if old_name == new_name_value and old_sort_order == parsed_sort_order:
            continue

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        'UPDATE "common"."targets" SET "name" = %s, "sort_order" = %s WHERE target_id = %s',
                        [new_name_value, parsed_sort_order, target_id],
                    )
            updated_count += 1
        except IntegrityError:
            error_parts.append(
                _("Mise à jour impossible pour la cible #%(target_id)s.")
                % {"target_id": target_id}
            )

    if created_count:
        success_parts.append(_("%(count)s création(s)") % {"count": created_count})
    if updated_count:
        success_parts.append(_("%(count)s mise(s) à jour") % {"count": updated_count})
    if deleted_count:
        success_parts.append(_("%(count)s suppression(s)") % {"count": deleted_count})

    if success_parts:
        messages.success(
            request,
            _("Cibles enregistrées : %(summary)s.")
            % {"summary": ", ".join(success_parts)},
        )
    if error_parts:
        messages.error(request, " ".join(error_parts))


def background_images(request: HttpRequest) -> HttpResponse:
    is_moderator = bool(can_manage_moderator_popup(request.user))
    if not is_moderator:
        raise Http404

    query = str(request.GET.get("q") or "").strip()
    genre_ids = normalize_genre_ids(request.GET.getlist("genre_ids"))
    moderation_quick = bool(
        str(request.GET.get("moderation_quick") or "").strip() == "1"
    )
    inactive_quick = bool(str(request.GET.get("inactive_quick") or "").strip() == "1")

    if request.method == "POST":
        image = get_object_or_404(
            BackgroundImage, image_id=int(request.POST.get("image_id") or 0)
        )
        action = str(request.POST.get("action") or "").strip()
        if action == "edit_inactive_metadata":
            if image.status != BackgroundImageStatus.INACTIVE:
                return JsonResponse(
                    {
                        "message": _(
                            "Seules les images inactives peuvent être modifiées."
                        )
                    },
                    status=400,
                )
            edit_form = BackgroundImageInactiveEditForm(
                request.POST,
                current_target=image.target,
            )
            if not edit_form.is_valid():
                return JsonResponse(
                    {
                        "fieldErrors": {
                            field: [
                                str(error) for error in errors if str(error).strip()
                            ]
                            for field, errors in edit_form.errors.items()
                        },
                        "message": _("Impossible d'enregistrer les modifications."),
                        "currentTargetMissing": (
                            not edit_form.current_target_exists
                            and bool(edit_form.current_target)
                        ),
                    },
                    status=400,
                )
            image.title = edit_form.cleaned_data["title"]
            image.description = edit_form.cleaned_data["description"]
            image.target = edit_form.cleaned_data["target"]
            with transaction.atomic():
                image.save(update_fields=["title", "description", "target"])
                replace_image_genres(
                    image,
                    normalize_genre_ids(edit_form.cleaned_data.get("genre_ids", [])),
                )
            return JsonResponse({"message": _("L'image inactive a été mise à jour.")})
        redirect_url = reverse("background_images")
        query_parts: list[str] = []
        if moderation_quick:
            query_parts.append("moderation_quick=1")
        if inactive_quick:
            query_parts.append("inactive_quick=1")
        if query:
            query_parts.append(f"q={query}")
        for genre_id in genre_ids:
            query_parts.append(f"genre_ids={genre_id}")
        if query_parts:
            redirect_url = f"{redirect_url}?{'&'.join(query_parts)}"

        with transaction.atomic():
            if action == "validate" and image.status == BackgroundImageStatus.PENDING:
                move_image_to_status(image, BackgroundImageStatus.INACTIVE)
                messages.success(
                    request, _("L'image a été validée puis placée en inactif.")
                )
            elif (
                action == "invalidate" and image.status == BackgroundImageStatus.PENDING
            ):
                delete_image_file(image)
                image.delete()
                messages.success(request, _("L'image en attente a été supprimée."))
            elif (
                action == "activate" and image.status == BackgroundImageStatus.INACTIVE
            ):
                move_image_to_status(image, BackgroundImageStatus.ACTIVE)
                messages.success(request, _("L'image a été activée."))
            elif (
                action == "deactivate" and image.status == BackgroundImageStatus.ACTIVE
            ):
                reference_counts = count_background_image_references(image.asset_code)
                if any(reference_counts.values()):
                    messages.warning(
                        request,
                        _(
                            "L'image était utilisée dans %(animations)s animation(s), %(songs)s chant(s) d'animation et %(verses)s couplet(s). Les références ont été supprimées."
                        )
                        % reference_counts,
                    )
                clear_background_image_references(image.asset_code)
                move_image_to_status(image, BackgroundImageStatus.INACTIVE)
                messages.success(request, _("L'image a été désactivée."))
            elif action == "delete" and image.status == BackgroundImageStatus.INACTIVE:
                delete_image_file(image)
                image.delete()
                messages.success(
                    request, _("L'image inactive a été supprimée définitivement.")
                )
            elif action:
                messages.error(
                    request, _("Action impossible pour l'état courant de l'image.")
                )
        return redirect(redirect_url)

    background_images_list = list_background_images_for_view(
        include_all_statuses=True,
        query=query,
        genre_ids=genre_ids,
        moderation_quick=moderation_quick,
        inactive_quick=inactive_quick,
    )
    summary_candidates = list_background_images_for_view(
        include_all_statuses=False,
        query="",
        genre_ids=[],
        moderation_quick=False,
        inactive_quick=False,
    )
    summary_background_images = random.sample(
        summary_candidates,
        min(15, len(summary_candidates)),
    )

    return render(
        request,
        "animation/background_images.html",
        {
            "background_images": background_images_list,
            "summary_background_images": summary_background_images,
            "genre_options": fetch_genre_options(),
            "selected_genre_ids": set(genre_ids),
            "query": query,
            "is_moderator": is_moderator,
            "moderation_quick_active": moderation_quick,
            "inactive_quick_active": inactive_quick,
            "background_image_target_options": fetch_target_options(),
            "background_image_genre_options": fetch_genre_options(),
            "background_images_i18n": {
                "editTitle": _("Modifier l'image inactive"),
                "saveLabel": _("Enregistrer"),
                "cancelLabel": _("Annuler"),
                "titleLabel": _("Titre"),
                "descriptionLabel": _("Description"),
                "targetLabel": _("Cible"),
                "genresLabel": _("Genres"),
                "genresFilterPlaceholder": _("Trouver un genre"),
                "currentTargetMissing": _(
                    "Cette image utilise une ancienne cible. Choisissez une cible actuelle."
                ),
                "saveFailedMessage": _("Impossible d'enregistrer les modifications."),
                "targetRequiredMessage": _("Sélectionnez une cible."),
                "titleRequiredMessage": _("Le titre est obligatoire."),
            },
        },
    )


def modify_background_targets(request: HttpRequest) -> HttpResponse:
    if not can_manage_moderator_popup(request.user):
        raise Http404

    selected_group, _selected_via_secret = get_selected_group_state(request)
    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip()
        if action != "save":
            messages.error(request, _("Action inconnue."))
            return redirect("modify_background_targets")
        _save_target_rows(request)
        return redirect("modify_background_targets")

    return render(
        request,
        "animation/modify_background_targets.html",
        {
            "selected_group": selected_group,
            "item_rows": _fetch_target_rows(),
        },
    )


def upload_background_image(request: HttpRequest) -> HttpResponse:
    if not getattr(request.user, "is_authenticated", False):
        return redirect("login")

    ensure_background_image_dirs()
    if request.method == "POST":
        form = BackgroundImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data["image_file"]
            validation_cfg = build_image_validation_config(
                getattr(request, "LANGUAGE_CODE", None)
            )
            validation_error = validate_image(image_file, validation_cfg)
            if validation_error:
                form.add_error(
                    "image_file",
                    _translate_image_validation_error(validation_error, validation_cfg),
                )
            else:
                genre_ids = normalize_genre_ids(form.cleaned_data.get("genre_ids", []))
                context_slug = build_background_context_slug(genre_ids)
                width, height, _fmt = _open_image(image_file)

                def create_background_image(
                    filename: str, destination
                ) -> BackgroundImage:
                    return BackgroundImage.objects.create(
                        asset_code=generate_asset_code(),
                        storage_filename=filename,
                        title=form.cleaned_data["title"].strip(),
                        target=form.cleaned_data["target"].strip(),
                        description=str(
                            form.cleaned_data.get("description") or ""
                        ).strip()
                        or None,
                        status=BackgroundImageStatus.PENDING,
                        stored_path=relative_stored_path(
                            BackgroundImageStatus.PENDING, filename
                        ),
                        original_name=str(image_file.name or "")[:255],
                        extension=destination.suffix.lower(),
                        mime=str(image_file.content_type or "")[:100],
                        size_bytes=int(getattr(image_file, "size", 0)),
                        width=int(width or 0),
                        height=int(height or 0),
                        member_id=normalize_member_id(
                            get_member_id_from_user(request.user)
                        ),
                    )

                try:
                    _filename, _destination, background_image = (
                        store_uploaded_image_file(
                            image_file,
                            status=BackgroundImageStatus.PENDING,
                            context_slug=context_slug,
                            on_after_write=create_background_image,
                        )
                    )
                except RuntimeError:
                    form.add_error(
                        "image_file",
                        _("Impossible d'enregistrer l'image pour le moment."),
                    )
                    return render(
                        request,
                        "animation/upload_background_image.html",
                        {
                            "form": form,
                            "upload_targets_missing": not form.has_target_options,
                            "upload_targets_missing_message": BackgroundImageUploadForm.no_targets_message,
                        },
                    )
                replace_image_genres(
                    background_image,
                    genre_ids,
                )
                messages.success(
                    request,
                    _("L'image a été envoyée pour modération."),
                )
                return redirect("background_images")
    else:
        form = BackgroundImageUploadForm()

    return render(
        request,
        "animation/upload_background_image.html",
        {
            "form": form,
            "upload_targets_missing": not form.has_target_options,
            "upload_targets_missing_message": BackgroundImageUploadForm.no_targets_message,
        },
    )


def animation_history(request: HttpRequest) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)
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


def add_animation(request: HttpRequest) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    if request.method == "POST":
        form = AnimationForm(request.POST)
        if form.is_valid():
            animation = form.save(commit=False)
            animation.group = selected_group
            animation.save()
            messages.success(request, _("L'animation a été créée."))
            return redirect("modify_animation", animation_id=animation.animation_id)
    else:
        form = AnimationForm()

    return render(
        request,
        "animation/add_animation.html",
        {
            "selected_group": selected_group,
            "form": form,
            "background_image_options": _background_image_popup_options(),
        },
    )


def modify_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    animation_songs = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses", "verse_overrides")
        .order_by("position", "animation_song_id")
    )
    main_song_cards = build_main_song_cards(animation, animation_songs)
    songs_payload_initial = build_songs_payload_initial(main_song_cards)
    songs_payload_initial_json = serialize_songs_payload(songs_payload_initial)
    ordered_mix_initial = "|".join(
        [f"asid:{row.animation_song_id}" for row in animation_songs]
    )

    member_id = get_member_id_from_user(request.user)

    all_song_results = search_songs(SongSearchParams.empty(), request.user, member_id)
    all_song_catalog = [
        {
            "id": item.song.song_id,
            "title": item.song.display_title,
        }
        for item in all_song_results.results
    ]
    accessible_song_ids = {item["id"] for item in all_song_catalog}

    advanced_song_catalog: list[dict[str, object]] = []
    favorite_song_catalog: list[dict[str, object]] = []
    if member_id:
        advanced_song_results = search_songs(
            load_member_song_search(member_id), request.user, member_id
        )
        favorite_song_results = search_songs(
            SongSearchParams(favorites_only=True), request.user, member_id
        )
        advanced_song_catalog = [
            {
                "id": item.song.song_id,
                "title": item.song.display_title,
            }
            for item in advanced_song_results.results
        ]
        favorite_song_catalog = [
            {
                "id": item.song.song_id,
                "title": item.song.display_title,
            }
            for item in favorite_song_results.results
        ]

    if request.method == "POST":
        form = AnimationForm(request.POST, instance=animation)
        if form.is_valid():
            form.instance = form.save(commit=False)
            songs_payload = parse_songs_payload(request.POST.get("songs_payload"))
            with transaction.atomic():
                ordered_mix_raw = request.POST.get("ordered_mix")
                if ordered_mix_raw is not None:
                    ordered_tokens = parse_ordered_mix(ordered_mix_raw)
                    sync_animation_playlist(
                        animation, ordered_tokens, allowed_song_ids=accessible_song_ids
                    )
                apply_songs_payload(form.instance, songs_payload)
                form.instance.save()
            if (
                str(request.POST.get("background_picker_after_save") or "").strip()
                == "1"
            ):
                picker_kind = str(request.POST.get("picker_kind") or "").strip()
                picker_level = request.POST.get("background_picker_level")
                picker_animation_song_id = (
                    _safe_int(
                        request.POST.get("background_picker_animation_song_id"),
                        fallback=0,
                    )
                    or None
                )
                picker_verse_id = (
                    _safe_int(
                        request.POST.get("background_picker_source_verse_id"),
                        fallback=0,
                    )
                    or None
                )
                if picker_kind == "style":
                    return redirect(
                        _build_style_picker_url(
                            animation,
                            level=picker_level,
                            animation_song_id=picker_animation_song_id,
                            verse_id=picker_verse_id,
                        )
                    )
                return redirect(
                    _build_background_picker_url(
                        animation,
                        level=picker_level,
                        animation_song_id=picker_animation_song_id,
                        verse_id=picker_verse_id,
                    )
                )
            messages.success(request, _("L'animation a été enregistrée."))
            return redirect("modify_animation", animation_id=animation.animation_id)
        songs_payload_initial_json = str(
            request.POST.get("songs_payload") or songs_payload_initial_json
        )
        ordered_mix_initial = str(
            request.POST.get("ordered_mix") or ordered_mix_initial
        )
    else:
        form = AnimationForm(instance=animation)

    font_choices = [
        {"value": value, "label": label} for value, label in list_font_choices()
    ]
    font_size_delta_choices = list(range(-30, 35, 5))
    font_previews = [
        {
            "fontFamily": item.family,
            "sample": item.sample,
            "label": item.label,
        }
        for item in list_font_previews()
    ]

    return render(
        request,
        "animation/modify_animation.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "animation_songs": animation_songs,
            "main_song_cards": main_song_cards,
            "ordered_mix_initial": ordered_mix_initial,
            "songs_payload_initial_json": songs_payload_initial_json,
            "font_choices": font_choices,
            "font_size_delta_choices": font_size_delta_choices,
            "form": form,
            "popup_data": {
                "fontChoices": font_choices,
                "fontPreviews": font_previews,
                "transitionChoices": list_enabled_transition_options(),
                "backgroundImageOptions": _background_image_popup_options(),
                "backgroundPickerUrl": reverse(
                    "animation_background_picker", args=[animation.animation_id]
                ),
                "stylePickerUrl": reverse(
                    "animation_style_picker", args=[animation.animation_id]
                ),
                "backgroundImageGenres": fetch_genre_options(),
                # Backward compatibility key kept while consumers migrate.
                "songCatalog": all_song_catalog,
                "advancedSongCatalog": advanced_song_catalog,
                "favoriteSongCatalog": favorite_song_catalog,
                "allSongCatalog": all_song_catalog,
                "canUseMemberSongTabs": bool(member_id),
            },
        },
    )


def animation_background_picker(
    request: HttpRequest, animation_id: int
) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    raw_level = request.GET.get("level") or request.POST.get("level")
    raw_animation_song_id = request.GET.get("animation_song_id") or request.POST.get(
        "animation_song_id"
    )
    raw_verse_id = request.GET.get("verse_id") or request.POST.get("verse_id")
    level, animation_song, verse = _resolve_background_picker_target(
        animation,
        level=raw_level,
        animation_song_id=_safe_int(raw_animation_song_id, fallback=0) or None,
        verse_id=_safe_int(raw_verse_id, fallback=0) or None,
    )
    raw_query = str(request.GET.get("q") or "").strip()
    query = raw_query if len(raw_query) >= 3 else ""
    selected_genre_ids = normalize_genre_ids(request.GET.getlist("genre_ids"))
    scope_style = _resolve_picker_scope_style(
        animation,
        level=level,
        animation_song=animation_song,
        verse=verse,
    )

    background_images_list = list_background_images_for_view(
        include_all_statuses=False,
        query=query,
        genre_ids=selected_genre_ids,
        moderation_quick=False,
        inactive_quick=False,
    )
    background_images_list = sorted(
        background_images_list,
        key=lambda item: (
            str(item.get("title") or "").casefold(),
            int(item.get("image_id") or 0),
        ),
    )
    active_asset_codes = {
        str(item["asset_code"] or "").strip() for item in background_images_list
    }
    selected_asset_code = str(
        request.GET.get("selected_asset_code")
        or scope_style["local_background_asset_code"]
        or ""
    ).strip()
    if selected_asset_code and selected_asset_code not in active_asset_codes:
        selected_asset_code = ""

    picker_error = ""
    if request.method == "POST":
        selected_asset_code = str(request.POST.get("selected_asset_code") or "").strip()
        if not selected_asset_code:
            picker_error = _("Choisissez une image de fond.")
        else:
            image = get_object_or_404(
                BackgroundImage,
                asset_code=selected_asset_code,
                status=BackgroundImageStatus.ACTIVE,
            )
            if level == "animation":
                animation.background_asset_code = image.asset_code
                animation.bg_color = None
                animation.save(update_fields=["background_asset_code", "bg_color"])
            elif level == "song":
                if animation_song is None:
                    raise Http404
                animation_song.background_asset_code_override = image.asset_code
                animation_song.bg_color_override = None
                animation_song.save(
                    update_fields=[
                        "background_asset_code_override",
                        "bg_color_override",
                    ]
                )
            else:
                if animation_song is None or verse is None:
                    raise Http404
                verse_override, _created = AnimationVerseOverride.objects.get_or_create(
                    animation_song=animation_song,
                    source_verse_id=verse.verse_id,
                    defaults={"is_visible": True},
                )
                verse_override.background_asset_code_override = image.asset_code
                verse_override.bg_color_override = None
                verse_override.save(
                    update_fields=[
                        "background_asset_code_override",
                        "bg_color_override",
                    ]
                )
            messages.success(request, _("L'image de fond a été enregistrée."))
            return redirect(
                _build_modify_animation_return_url(
                    animation,
                    animation_song_id=(
                        int(animation_song.animation_song_id)
                        if animation_song is not None
                        else None
                    ),
                )
            )

    return render(
        request,
        "animation/background_picker.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "picker_level": level,
            "picker_scope_style": scope_style,
            "picker_scope_label": str(scope_style["scope_label"]),
            "picker_scope_title": str(scope_style["scope_title"]),
            "picker_selected_asset_code": selected_asset_code,
            "picker_query": raw_query,
            "picker_focus_query": str(request.GET.get("focus_query") or "").strip()
            == "1",
            "picker_error": picker_error,
            "picker_base_url": reverse(
                "animation_background_picker", args=[animation.animation_id]
            ),
            "picker_animation_song_id": (
                int(animation_song.animation_song_id) if animation_song else None
            ),
            "picker_verse_id": (int(verse.verse_id) if verse else None),
            "background_images": background_images_list,
            "genre_options": fetch_active_background_genre_options(),
            "selected_genre_ids": set(selected_genre_ids),
            "picker_back_url": _build_modify_animation_return_url(
                animation,
                animation_song_id=(
                    int(animation_song.animation_song_id)
                    if animation_song is not None
                    else None
                ),
            ),
            "picker_filter_action": _build_background_picker_url(
                animation,
                level=level,
                animation_song_id=(
                    int(animation_song.animation_song_id) if animation_song else None
                ),
                verse_id=(int(verse.verse_id) if verse else None),
            ),
        },
    )


def animation_style_picker(request: HttpRequest, animation_id: int) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    raw_level = request.GET.get("level") or request.POST.get("level")
    raw_animation_song_id = request.GET.get("animation_song_id") or request.POST.get(
        "animation_song_id"
    )
    raw_verse_id = request.GET.get("verse_id") or request.POST.get("verse_id")
    level, animation_song, verse = _resolve_background_picker_target(
        animation,
        level=raw_level,
        animation_song_id=_safe_int(raw_animation_song_id, fallback=0) or None,
        verse_id=_safe_int(raw_verse_id, fallback=0) or None,
    )
    scope_style = _resolve_picker_scope_style(
        animation,
        level=level,
        animation_song=animation_song,
        verse=verse,
    )
    style_options = _build_style_picker_options(animation)
    valid_occurrence_tokens = {
        str(occurrence["token"]).strip()
        for option in style_options
        for occurrence in option["occurrences"]
    }
    selected_occurrence_token = str(
        request.GET.get("selected_occurrence_token") or ""
    ).strip()
    if not selected_occurrence_token:
        selected_occurrence_token = _find_style_picker_default_token(
            scope_style,
            style_options,
        )
    if selected_occurrence_token not in valid_occurrence_tokens:
        selected_occurrence_token = ""

    picker_error = ""
    if request.method == "POST":
        selected_occurrence_token = str(
            request.POST.get("selected_occurrence_token") or ""
        ).strip()
        selected_option = next(
            (
                (option, occurrence)
                for option in style_options
                for occurrence in option["occurrences"]
                if str(occurrence["token"]).strip() == selected_occurrence_token
            ),
            None,
        )
        if selected_option is None:
            picker_error = _("Choisissez un style.")
        else:
            option, occurrence = selected_option
            _apply_copied_style_to_target(
                animation=animation,
                level=level,
                source_scope=str(occurrence["source_scope"]),
                copied_style=option,
                animation_song=animation_song,
                verse=verse,
            )
            messages.success(request, _("Le style a été copié."))
            return redirect(
                _build_modify_animation_return_url(
                    animation,
                    animation_song_id=(
                        int(animation_song.animation_song_id)
                        if animation_song is not None
                        else None
                    ),
                )
            )

    return render(
        request,
        "animation/style_picker.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "picker_level": level,
            "picker_scope_style": scope_style,
            "picker_scope_label": str(scope_style["scope_label"]),
            "picker_scope_title": _build_picker_scope_heading(
                level, picker_kind="style"
            ),
            "picker_selected_occurrence_token": selected_occurrence_token,
            "picker_error": picker_error,
            "picker_base_url": reverse(
                "animation_style_picker", args=[animation.animation_id]
            ),
            "picker_animation_song_id": (
                int(animation_song.animation_song_id) if animation_song else None
            ),
            "picker_verse_id": (int(verse.verse_id) if verse else None),
            "style_options": style_options,
            "picker_back_url": _build_modify_animation_return_url(
                animation,
                animation_song_id=(
                    int(animation_song.animation_song_id)
                    if animation_song is not None
                    else None
                ),
            ),
        },
    )


DISPLAY_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


def _truncate_excerpt(text: str, max_chars: int = 50) -> str:
    flat = " ".join(str(text or "").split())
    if len(flat) <= max_chars:
        return flat
    return f"{flat[:max_chars].rstrip()}[...]"


def _should_include_remote_card(
    *,
    slide_kind: str,
    source_verse: Verse | None,
    slide_display_mode: SongSlideDisplayMode,
) -> bool:
    if slide_display_mode in {
        SongSlideDisplayMode.SINGLE,
        SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
    }:
        return True

    if slide_display_mode == SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL:
        return slide_kind != "chorus"

    if slide_display_mode == SongSlideDisplayMode.VERSES_BY_PAIRS:
        if slide_kind != "verse" or source_verse is None:
            return True
        return int(source_verse.num_verse or 0) % 2 == 1

    return True


def _clone_slide_payload(slide_payload: dict[str, object]) -> dict[str, object]:
    cloned = dict(slide_payload)
    style = slide_payload.get("style")
    cloned["style"] = dict(style) if isinstance(style, dict) else {}
    return cloned


def _build_projection_step(
    *,
    animation_song_id: int,
    song_id: int,
    song_title: str,
    mode: str,
    left_slide: dict[str, object],
    right_slide: dict[str, object] | None = None,
    primary_source_global_index: int,
    source_global_indexes: list[int],
    card_source_global_indexes: list[int],
) -> dict[str, object]:
    return {
        "animationSongId": int(animation_song_id),
        "songId": int(song_id),
        "songTitle": str(song_title or ""),
        "mode": str(mode),
        "left": _clone_slide_payload(left_slide),
        "right": _clone_slide_payload(right_slide) if right_slide is not None else None,
        "primarySourceGlobalIndex": int(primary_source_global_index),
        "sourceGlobalIndexes": [int(index) for index in source_global_indexes],
        "_cardSourceGlobalIndexes": [
            int(index) for index in card_source_global_indexes
        ],
    }


def _append_simple_projection_steps(
    *,
    target: list[dict[str, object]],
    slides: list[dict[str, object]],
) -> None:
    for slide in slides:
        source_global_index = int(slide["globalIndex"])
        target.append(
            _build_projection_step(
                animation_song_id=int(slide["animationSongId"]),
                song_id=int(slide["songId"]),
                song_title=str(slide["songTitle"] or ""),
                mode="simple",
                left_slide=slide,
                primary_source_global_index=source_global_index,
                source_global_indexes=[source_global_index],
                card_source_global_indexes=[source_global_index],
            )
        )


def _append_double_projection_steps(
    *,
    target: list[dict[str, object]],
    left_slides: list[dict[str, object]],
    right_slides: list[dict[str, object]],
    primary_side: str,
    card_side: str,
) -> None:
    if not left_slides or not right_slides:
        return

    steps_count = max(len(left_slides), len(right_slides))
    for offset in range(steps_count):
        left_slide = (
            left_slides[offset] if offset < len(left_slides) else left_slides[-1]
        )
        right_slide = (
            right_slides[offset] if offset < len(right_slides) else right_slides[-1]
        )
        primary_slide = left_slide if primary_side == "left" else right_slide
        card_source_global_indexes = [
            int((left_slide if card_side == "left" else right_slide)["globalIndex"])
        ]
        target.append(
            _build_projection_step(
                animation_song_id=int(primary_slide["animationSongId"]),
                song_id=int(primary_slide["songId"]),
                song_title=str(primary_slide["songTitle"] or ""),
                mode="double",
                left_slide=left_slide,
                right_slide=right_slide,
                primary_source_global_index=int(primary_slide["globalIndex"]),
                source_global_indexes=[
                    int(left_slide["globalIndex"]),
                    int(right_slide["globalIndex"]),
                ],
                card_source_global_indexes=card_source_global_indexes,
            )
        )


def _source_verse_for_slide(
    slide_payload: dict[str, object],
    *,
    verses_by_id: dict[int, Verse],
) -> Verse | None:
    source_verse_id = slide_payload.get("sourceVerseId")
    if source_verse_id is None:
        return None
    try:
        return verses_by_id.get(int(source_verse_id))
    except (TypeError, ValueError):
        return None


def _consume_chorus_group(
    slides: list[dict[str, object]], start_index: int
) -> tuple[list[dict[str, object]], int]:
    group: list[dict[str, object]] = []
    index = start_index
    while index < len(slides) and str(slides[index].get("kind") or "") == "chorus":
        group.append(slides[index])
        index += 1
    return group, index


def _consume_verse_group(
    slides: list[dict[str, object]],
    start_index: int,
    *,
    verses_by_id: dict[int, Verse],
) -> tuple[list[dict[str, object]], int]:
    if start_index >= len(slides):
        return [], start_index

    first_slide = slides[start_index]
    first_verse = _source_verse_for_slide(first_slide, verses_by_id=verses_by_id)
    if first_verse is None or str(first_slide.get("kind") or "") != "verse":
        return [], start_index

    target_num_verse = int(first_verse.num_verse or 0)
    group = [first_slide]
    index = start_index + 1
    while index < len(slides):
        slide = slides[index]
        if str(slide.get("kind") or "") != "verse":
            break
        verse = _source_verse_for_slide(slide, verses_by_id=verses_by_id)
        if verse is None or int(verse.num_verse or 0) != target_num_verse:
            break
        group.append(slide)
        index += 1
    return group, index


def _build_song_projection_groups(
    *,
    song_slides: list[dict[str, object]],
    verses_by_id: dict[int, Verse],
    slide_display_mode: SongSlideDisplayMode,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    normal_steps: list[dict[str, object]] = []
    chorus_shortcut_steps: list[dict[str, object]] = []

    index = 0
    while index < len(song_slides):
        slide = song_slides[index]
        kind = str(slide.get("kind") or "")
        if kind == "chorus":
            chorus_group, next_index = _consume_chorus_group(song_slides, index)
            _append_simple_projection_steps(
                target=chorus_shortcut_steps, slides=chorus_group
            )
            if slide_display_mode == SongSlideDisplayMode.SINGLE:
                _append_simple_projection_steps(
                    target=normal_steps, slides=chorus_group
                )
                index = next_index
                continue

            if slide_display_mode == SongSlideDisplayMode.CHORUS_THEN_PARALLEL:
                _append_simple_projection_steps(
                    target=normal_steps, slides=chorus_group
                )
                if next_index < len(song_slides):
                    next_slide = song_slides[next_index]
                    if str(next_slide.get("kind") or "") == "verse":
                        verse_group, verse_end_index = _consume_verse_group(
                            song_slides,
                            next_index,
                            verses_by_id=verses_by_id,
                        )
                        if verse_group:
                            _append_double_projection_steps(
                                target=normal_steps,
                                left_slides=chorus_group,
                                right_slides=verse_group,
                                primary_side="right",
                                card_side="right",
                            )
                            index = verse_end_index
                            continue
                index = next_index
                continue

            if slide_display_mode == SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL:
                if next_index < len(song_slides):
                    next_slide = song_slides[next_index]
                    if str(next_slide.get("kind") or "") == "verse":
                        verse_group, verse_end_index = _consume_verse_group(
                            song_slides,
                            next_index,
                            verses_by_id=verses_by_id,
                        )
                        if verse_group:
                            _append_double_projection_steps(
                                target=normal_steps,
                                left_slides=chorus_group,
                                right_slides=verse_group,
                                primary_side="right",
                                card_side="right",
                            )
                            index = verse_end_index
                            continue

                has_any_verse = any(
                    str(item.get("kind") or "") == "verse" for item in song_slides
                )
                if not has_any_verse:
                    _append_simple_projection_steps(
                        target=normal_steps, slides=chorus_group
                    )
                index = next_index
                continue

            _append_simple_projection_steps(target=normal_steps, slides=chorus_group)
            index = next_index
            continue

        if kind == "verse":
            verse_group, next_index = _consume_verse_group(
                song_slides,
                index,
                verses_by_id=verses_by_id,
            )
            if not verse_group:
                _append_simple_projection_steps(target=normal_steps, slides=[slide])
                index += 1
                continue

            if slide_display_mode == SongSlideDisplayMode.VERSES_BY_PAIRS:
                left_verse = _source_verse_for_slide(
                    verse_group[0], verses_by_id=verses_by_id
                )
                left_num_verse = int(left_verse.num_verse or 0) if left_verse else 0
                if left_num_verse > 0 and left_num_verse % 2 == 1:
                    right_group: list[dict[str, object]] = []
                    after_right_index = next_index
                    if next_index < len(song_slides):
                        next_slide = song_slides[next_index]
                        if str(next_slide.get("kind") or "") == "verse":
                            candidate_group, candidate_end_index = _consume_verse_group(
                                song_slides,
                                next_index,
                                verses_by_id=verses_by_id,
                            )
                            right_verse = (
                                _source_verse_for_slide(
                                    candidate_group[0], verses_by_id=verses_by_id
                                )
                                if candidate_group
                                else None
                            )
                            right_num_verse = (
                                int(right_verse.num_verse or 0) if right_verse else 0
                            )
                            if right_num_verse == left_num_verse + 1:
                                right_group = candidate_group
                                after_right_index = candidate_end_index
                    if right_group:
                        _append_double_projection_steps(
                            target=normal_steps,
                            left_slides=verse_group,
                            right_slides=right_group,
                            primary_side="left",
                            card_side="left",
                        )
                        index = after_right_index
                        continue

            _append_simple_projection_steps(target=normal_steps, slides=verse_group)
            index = next_index
            continue

        _append_simple_projection_steps(target=normal_steps, slides=[slide])
        index += 1

    return normal_steps, chorus_shortcut_steps


def _build_runtime_payload(animation: Animation, public_url: str) -> dict[str, object]:
    rendered_slides = build_animation_render_bundle(animation)
    animation_songs = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses")
        .order_by("position", "animation_song_id")
    )
    animation_song_meta: dict[int, dict[str, object]] = {}
    for animation_song in animation_songs:
        verses = list(animation_song.song.verses.all())
        verses_by_id = {int(verse.verse_id): verse for verse in verses}
        has_chorus = any(bool(verse.chorus) for verse in verses)
        animation_song_meta[int(animation_song.animation_song_id)] = {
            "verses_by_id": verses_by_id,
            "slide_display_mode": normalize_animation_song_slide_display_mode(
                animation_song.slide_display_mode,
                has_chorus=has_chorus,
            ),
        }

    slides_payload: list[dict[str, object]] = []
    songs_payload: list[dict[str, object]] = []
    songs_by_animation_song_id: dict[int, dict[str, object]] = {}
    raw_song_slides_by_animation_song_id: dict[int, list[dict[str, object]]] = {}
    background_urls: set[str] = set()

    for index, slide in enumerate(rendered_slides):
        background_url = resolve_background_asset_url(slide.style.background_asset_code)
        if background_url:
            background_urls.add(background_url)
        slide_payload = {
            "globalIndex": index,
            "slideId": f"slide-{index + 1}",
            "animationSongId": int(slide.animation_song_id),
            "songId": int(slide.song_id),
            "songTitle": slide.song_title,
            "sourceVerseId": int(slide.source_verse_id)
            if slide.source_verse_id is not None
            else None,
            "kind": str(slide.kind),
            "label": str(slide.label or ""),
            "text": str(slide.text or ""),
            "excerpt": _truncate_excerpt(str(slide.text or "")),
            "style": {
                "textColor": str(slide.style.text_color or "#FFFFFF"),
                "bgColor": str(slide.style.bg_color or "#000000"),
                "fontFamily": str(slide.style.font_family or "Source Sans Pro"),
                "fontWeight": str(slide.style.font_weight or "normal"),
                "fontSize": int(slide.style.font_size)
                if slide.style.font_size is not None
                else 72,
                "horizontalPadding": int(slide.style.horizontal_padding)
                if slide.style.horizontal_padding is not None
                else 80,
                "backgroundAssetCode": str(slide.style.background_asset_code or ""),
                "backgroundUrl": background_url,
            },
        }
        slides_payload.append(slide_payload)
        raw_song_slides_by_animation_song_id.setdefault(
            int(slide.animation_song_id), []
        ).append(slide_payload)

        song_entry = songs_by_animation_song_id.get(slide.animation_song_id)
        if song_entry is None:
            song_entry = {
                "animationSongId": int(slide.animation_song_id),
                "songId": int(slide.song_id),
                "songTitle": slide.song_title,
                "slideIndexes": [],
                "chorusIndexes": [],
                "projectionIndexes": [],
                "chorusProjectionIndexes": [],
            }
            songs_by_animation_song_id[slide.animation_song_id] = song_entry
            songs_payload.append(song_entry)

        song_entry["slideIndexes"].append(index)
        if str(slide.kind) == "chorus":
            song_entry["chorusIndexes"].append(index)

    projection_steps: list[dict[str, object]] = []
    card_projection_index_by_source_global_index: dict[int, int] = {}
    chorus_shortcut_groups_by_animation_song_id: dict[int, list[dict[str, object]]] = {}

    for song_entry in songs_payload:
        animation_song_id = int(song_entry["animationSongId"])
        meta = animation_song_meta.get(animation_song_id, {})
        verses_by_id = meta.get("verses_by_id", {})
        slide_display_mode = meta.get("slide_display_mode", SongSlideDisplayMode.SINGLE)
        normal_steps, chorus_shortcut_steps = _build_song_projection_groups(
            song_slides=raw_song_slides_by_animation_song_id.get(animation_song_id, []),
            verses_by_id=verses_by_id if isinstance(verses_by_id, dict) else {},
            slide_display_mode=slide_display_mode,
        )
        for step in normal_steps:
            step["projectionIndex"] = len(projection_steps)
            projection_steps.append(step)
            song_entry["projectionIndexes"].append(int(step["projectionIndex"]))
            for source_index in step.get("_cardSourceGlobalIndexes", []):
                card_projection_index_by_source_global_index[int(source_index)] = int(
                    step["projectionIndex"]
                )
        chorus_shortcut_groups_by_animation_song_id[animation_song_id] = (
            chorus_shortcut_steps
        )

    for song_entry in songs_payload:
        animation_song_id = int(song_entry["animationSongId"])
        chorus_projection_indexes = [
            int(step["projectionIndex"])
            for step in projection_steps
            if int(step["animationSongId"]) == animation_song_id
            and str(step["mode"]) == "simple"
            and str(step["left"].get("kind") or "") == "chorus"
            and step.get("right") is None
        ]
        if not chorus_projection_indexes:
            for step in chorus_shortcut_groups_by_animation_song_id.get(
                animation_song_id, []
            ):
                step["projectionIndex"] = len(projection_steps)
                projection_steps.append(step)
                chorus_projection_indexes.append(int(step["projectionIndex"]))
        song_entry["chorusProjectionIndexes"] = chorus_projection_indexes

    serialized_projection_steps: list[dict[str, object]] = []
    for step in projection_steps:
        serialized_projection_steps.append(
            {
                "projectionIndex": int(step["projectionIndex"]),
                "animationSongId": int(step["animationSongId"]),
                "songId": int(step["songId"]),
                "songTitle": str(step["songTitle"] or ""),
                "mode": str(step["mode"]),
                "left": step["left"],
                "right": step["right"],
                "primarySourceGlobalIndex": int(step["primarySourceGlobalIndex"]),
                "sourceGlobalIndexes": [
                    int(index) for index in step["sourceGlobalIndexes"]
                ],
            }
        )

    card_groups: list[dict[str, object]] = []
    for song_entry in songs_payload:
        animation_song_id = int(song_entry["animationSongId"])
        song_title = str(song_entry["songTitle"] or "")
        meta = animation_song_meta.get(animation_song_id, {})
        verses_by_id = meta.get("verses_by_id", {})
        slide_display_mode = meta.get("slide_display_mode", SongSlideDisplayMode.SINGLE)
        cards: list[dict[str, object]] = []
        for slide_payload in raw_song_slides_by_animation_song_id.get(
            animation_song_id, []
        ):
            source_verse = _source_verse_for_slide(
                slide_payload,
                verses_by_id=verses_by_id if isinstance(verses_by_id, dict) else {},
            )
            if not _should_include_remote_card(
                slide_kind=str(slide_payload.get("kind") or ""),
                source_verse=source_verse,
                slide_display_mode=slide_display_mode,
            ):
                continue
            global_index = int(slide_payload["globalIndex"])
            projection_index = card_projection_index_by_source_global_index.get(
                global_index
            )
            if projection_index is None:
                projection_index = int(
                    next(
                        (
                            step["projectionIndex"]
                            for step in serialized_projection_steps
                            if global_index in step["sourceGlobalIndexes"]
                        ),
                        -1,
                    )
                )
            cards.append(
                {
                    "globalIndex": global_index,
                    "projectionIndex": projection_index,
                    "excerpt": slide_payload["excerpt"],
                    "label": str(slide_payload.get("label") or ""),
                    "kind": str(slide_payload.get("kind") or ""),
                }
            )
        card_groups.append(
            {
                "animationSongId": animation_song_id,
                "songTitle": song_title,
                "cards": cards,
            }
        )

    return {
        "animationId": int(animation.animation_id),
        "animationTitle": animation.title,
        "scheduledAt": animation.scheduled_at.isoformat(),
        "slides": slides_payload,
        "projectionSteps": serialized_projection_steps,
        "songs": songs_payload,
        "backgroundUrls": sorted(background_urls),
        "publicUrl": public_url,
        "qrCodePngBase64": build_qr_png_base64(public_url),
        "cardGroups": card_groups,
        "transitions": list_enabled_transition_runtime_options(),
        "defaultTransitionId": resolve_enabled_transition_id(
            animation.default_transition
        ),
    }


def lyrics_slide_show(request: HttpRequest, animation_id: int) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    public_url = request.build_absolute_uri(
        reverse(
            "lyrics_slide_show_public", kwargs={"animation_id": animation.animation_id}
        )
    )
    runtime_payload = _build_runtime_payload(animation, public_url)
    display_session_id = f"{uuid.uuid4().hex[:16]}-{animation.animation_id}"
    shortcuts_config = _build_shortcuts_config(request, animation)

    return render(
        request,
        "animation/lyrics_slide_show.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "display_session_id": display_session_id,
            "google_fonts_stylesheet_href": GOOGLE_FONTS_STYLESHEET_HREF,
            "runtime_payload": runtime_payload,
            "shortcuts_config": shortcuts_config,
            "lyrics_i18n": {
                "openSecondScreenLabel": _("Ouvrir le second écran"),
                "reopenSecondScreenLabel": _("Rouvrir le second écran"),
                "popupBlockedTitle": _("Fenêtre bloquée"),
                "popupBlockedMessage": _(
                    "Le navigateur a bloqué l'ouverture du second écran."
                ),
                "preloadWarningTitle": _("Préchargement incomplet"),
                "preloadWarningMessage": _(
                    "Certaines images de fond n'ont pas pu être préchargées."
                ),
                "okLabel": _("OK"),
                "noneLabel": _("Aucun"),
                "currentSlidePlaceholder": _("Aucune diapo projetée."),
                "nextSlidePlaceholder": _("Aucune diapo suivante."),
                "blackModeLabel": _("BLACK MODE"),
                "chorusLabel": _("Refrain"),
                "previewCurrentLabel": _("Diapo en cours"),
                "previewNextLabel": _("Diapo suivante"),
                "qrInfoLabel": _("QR code pour les paroles"),
                "hiddenChorusLabel": _("Refrains masqués dans la grille."),
                "scrollLockedLabel": _("Scroll bloqué"),
                "scrollUnlockedLabel": _("Scroll autorisé"),
                "scrollAllowEmoji": "↕️",
                "scrollAllowText": _("Scroll"),
                "scrollStopEmoji": "🧱",
                "scrollStopText": _("Stop scroll"),
                "chorusShowEmoji": "🎼🔼",
                "chorusShowText": _("Refrain"),
                "chorusHideEmoji": "🎼🔽",
                "chorusHideText": _("Pas de refrain"),
                "shortcutsPopupTitle": _("Raccourcis clavier"),
                "shortcutsCustomizeButtonLabel": _("Personnaliser les raccourcis"),
                "shortcutsPopupFooter": _("⌨️👈 en majuscules ou en minuscules"),
                "shortcutsCustomizeTitle": _("Personnaliser les raccourcis"),
                "shortcutsCustomizeHelp": _(
                    "Clique sur un slot puis appuie sur une touche simple.\n"
                    "Jusqu'à 3 touches par action.\n"
                    "La petite croix efface un slot.\n"
                    "Aucune combinaison n'est autorisée.\n"
                    "Escape n'est pas autorisé.\n"
                    "Laisser vide désactive l'action personnalisable."
                ),
                "shortcutsCaptureLabel": _("Appuyer sur une touche"),
                "shortcutsClearSlotLabel": _("Effacer ce raccourci"),
                "shortcutsSaveLabel": _("Enregistrer"),
                "shortcutsCancelLabel": _("Annuler"),
                "shortcutsResetLabel": _("Revenir aux raccourcis du site"),
                "shortcutsGuestCustomizeMessage": _(
                    "La personnalisation des raccourcis nécessite une connexion."
                ),
                "shortcutsGuestCustomizeTitle": _("Connexion requise"),
                "shortcutsSaveFailedTitle": _("Enregistrement impossible"),
                "shortcutsSaveFailedMessage": _(
                    "Les raccourcis n'ont pas pu être enregistrés."
                ),
            },
        },
    )


def lyrics_slide_show_shortcuts(
    request: HttpRequest, animation_id: int
) -> JsonResponse:
    if request.method != "POST":
        raise Http404

    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return JsonResponse({"message": _("Aucun groupe sélectionné.")}, status=404)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    member_id = get_member_id_from_user(request.user)
    if not member_id:
        return JsonResponse(
            {"message": _("La personnalisation nécessite une connexion.")}, status=403
        )

    if str(request.POST.get("use_site_defaults", "") or "").strip() == "1":
        save_member_shortcut_bindings(
            member_id,
            build_form_shortcut_bindings(None),
            use_site_defaults=True,
        )
        effective_bindings = build_effective_shortcut_bindings(None)
        return JsonResponse(
            {
                "savedBindings": _serialize_shortcut_bindings(
                    build_form_shortcut_bindings(None)
                ),
                "effectiveBindings": _serialize_shortcut_bindings(effective_bindings),
                "fieldErrors": {},
                "globalMessage": "",
                "usedSiteDefaults": True,
                "formattedBindings": {
                    action: [
                        format_shortcut_token(token)
                        for token in effective_bindings.get(action, [])
                    ]
                    for action in SHORTCUT_ACTION_ORDER
                },
            }
        )

    action_labels = _shortcut_action_labels()
    submitted_values = {
        action: str(request.POST.get(action, "") or "")
        for action in SHORTCUT_ACTION_ORDER
    }
    validation = validate_shortcut_submission(
        submitted_values,
        action_labels=action_labels,
    )
    used_site_defaults = save_member_shortcut_bindings(
        member_id,
        validation.saved_bindings,
        use_site_defaults=validation.used_site_defaults,
    )
    effective_bindings = build_effective_shortcut_bindings(
        None if used_site_defaults else validation.saved_bindings
    )

    return JsonResponse(
        {
            "savedBindings": _serialize_shortcut_bindings(
                build_form_shortcut_bindings(
                    None if used_site_defaults else validation.saved_bindings
                )
            ),
            "effectiveBindings": _serialize_shortcut_bindings(effective_bindings),
            "fieldErrors": validation.field_errors,
            "globalMessage": validation.global_message,
            "usedSiteDefaults": used_site_defaults,
            "formattedBindings": {
                action: [
                    format_shortcut_token(token)
                    for token in effective_bindings.get(action, [])
                ]
                for action in SHORTCUT_ACTION_ORDER
            },
        }
    )


def lyrics_slide_show_display(request: HttpRequest, animation_id: int) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    session_id = str(request.GET.get("session") or "").strip()
    if not DISPLAY_SESSION_PATTERN.match(session_id):
        raise Http404

    return render(
        request,
        "animation/lyrics_slide_show_display.html",
        {
            "animation": animation,
            "display_session_id": session_id,
            "google_fonts_stylesheet_href": GOOGLE_FONTS_STYLESHEET_HREF,
            "display_i18n": {
                "waitingLabel": _("En attente du maître"),
                "f11ReminderLabel": _("APPUYEZ SUR F11 SUR CETTE ÉCRAN"),
            },
            "display_debug_enabled": settings.DEBUG,
        },
    )


def lyrics_slide_show_public(request: HttpRequest, animation_id: int) -> HttpResponse:
    animation = get_object_or_404(Animation, animation_id=animation_id)
    render_settings = SongRenderSettings.from_language(
        getattr(request, "LANGUAGE_CODE", None)
    )
    animation_songs = list(
        animation.animation_songs.select_related("song")
        .prefetch_related("song__verses")
        .order_by("position", "animation_song_id")
    )
    songs_payload = [
        build_lyrics_song_entry(
            animation_song.song,
            anchor_id=f"lyrics-song-{index + 1}",
            mode=ChorusRenderMode.FULL,
            settings=render_settings,
            verses=animation_song.song.verses.all(),
        )
        for index, animation_song in enumerate(animation_songs)
    ]

    context = build_lyrics_page_context(
        page_title=str(animation.title or ""),
        share_url=build_request_share_url(request),
        songs=songs_payload,
        animation_title=str(animation.title or ""),
        drawer_title=str(animation.title or ""),
        drawer_link_url=reverse("songs"),
        drawer_link_label=_("Liste des chants"),
        is_animation_view=True,
    )
    context["animation"] = animation

    return render(
        request,
        "lyrics/lyrics.html",
        context,
    )


def delete_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    if request.method != "POST":
        raise Http404

    animation = get_object_or_404(Animation, animation_id=animation_id)
    selected_group = get_selected_group_or_404(request)
    if animation.group_id != selected_group.group_id:
        raise Http404
    animation.delete()
    messages.success(request, _("L'animation a été supprimée."))
    return redirect("animations")
