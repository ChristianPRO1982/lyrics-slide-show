from __future__ import annotations

import base64
import io
import re
import uuid

from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user
from app_song.rendering import SongRenderSettings, render_song_blocks
from app_song.search import SongSearchParams, load_member_song_search, search_songs

from .font_catalog import list_font_choices, list_font_previews
from .forms import AnimationForm
from .models import Animation
from .services.render_bundle import build_animation_render_bundle
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.song_edits import (
    apply_songs_payload,
    build_main_song_cards,
    build_songs_payload_initial,
    parse_songs_payload,
    serialize_songs_payload,
)
from .services.access import (
    get_selected_group_or_404,
    redirect_to_groups_when_no_selection,
)

try:
    import qrcode
except Exception:  # pragma: no cover - optional dependency in dev envs
    qrcode = None


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
            "label": item.family,
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
                # Backward compatibility key kept while consumers migrate.
                "songCatalog": all_song_catalog,
                "advancedSongCatalog": advanced_song_catalog,
                "favoriteSongCatalog": favorite_song_catalog,
                "allSongCatalog": all_song_catalog,
                "canUseMemberSongTabs": bool(member_id),
            },
        },
    )


DISPLAY_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


def _truncate_excerpt(text: str, max_chars: int = 50) -> str:
    flat = " ".join(str(text or "").split())
    if len(flat) <= max_chars:
        return flat
    return f"{flat[:max_chars].rstrip()}[...]"


def _resolve_background_url(background_asset_code: str | None) -> str:
    value = str(background_asset_code or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return f"{settings.MEDIA_URL}{value}"


def _build_qr_png_base64(value: str) -> str:
    if not value or qrcode is None:
        return ""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _build_runtime_payload(animation: Animation, public_url: str) -> dict[str, object]:
    rendered_slides = build_animation_render_bundle(animation)
    slides_payload: list[dict[str, object]] = []
    songs_payload: list[dict[str, object]] = []
    songs_by_animation_song_id: dict[int, dict[str, object]] = {}
    background_urls: set[str] = set()
    card_groups: list[dict[str, object]] = []

    for index, slide in enumerate(rendered_slides):
        background_url = _resolve_background_url(slide.style.background_asset_code)
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
                "fontSize": int(slide.style.font_size or 72),
                "horizontalPadding": int(slide.style.horizontal_padding or 80),
                "backgroundAssetCode": str(slide.style.background_asset_code or ""),
                "backgroundUrl": background_url,
            },
        }
        slides_payload.append(slide_payload)

        song_entry = songs_by_animation_song_id.get(slide.animation_song_id)
        if song_entry is None:
            song_entry = {
                "animationSongId": int(slide.animation_song_id),
                "songId": int(slide.song_id),
                "songTitle": slide.song_title,
                "slideIndexes": [],
                "chorusIndexes": [],
            }
            songs_by_animation_song_id[slide.animation_song_id] = song_entry
            songs_payload.append(song_entry)
            card_groups.append(
                {
                    "animationSongId": int(slide.animation_song_id),
                    "songTitle": slide.song_title,
                    "cards": [],
                }
            )

        song_entry["slideIndexes"].append(index)
        if str(slide.kind) == "chorus":
            song_entry["chorusIndexes"].append(index)

        card_groups[-1]["cards"].append(
            {
                "globalIndex": index,
                "excerpt": slide_payload["excerpt"],
                "label": str(slide.label or ""),
                "kind": str(slide.kind),
            }
        )

    return {
        "animationId": int(animation.animation_id),
        "animationTitle": animation.title,
        "scheduledAt": animation.scheduled_at.isoformat(),
        "slides": slides_payload,
        "songs": songs_payload,
        "backgroundUrls": sorted(background_urls),
        "publicUrl": public_url,
        "qrCodePngBase64": _build_qr_png_base64(public_url),
        "cardGroups": card_groups,
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

    return render(
        request,
        "animation/lyrics_slide_show.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "display_session_id": display_session_id,
            "runtime_payload": runtime_payload,
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
                "shortcutsPopupMessage": _(
                    "- `O` : Ouvrir un second écran\n"
                    "- `Esc` ou `M` : Activer/désactiver BLACK MODE\n"
                    "- `B` ou `↑` : Diapo précédente\n"
                    "- `S`, `V`, `Espace` ou `↓` : Diapo suivante\n"
                    "- `R` ou `C` : Refrain\n"
                    "- `F` ou `←` : Chant précédent\n"
                    "- `N`, `Entrée` ou `→` : Chant suivant\n"
                    "- `A` ou `D` : Afficher/masquer les refrains\n"
                    "- `L` : Activer/bloquer le scroll\n"
                    "- `Q` : Afficher/masquer le QR code"
                ),
            },
        },
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
            "display_i18n": {
                "waitingLabel": _("En attente du maître"),
                "f11ReminderLabel": _("APPUYEZ SUR F11 SUR CETTE ÉCRAN"),
            },
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
    songs_payload: list[dict[str, object]] = []
    for index, animation_song in enumerate(animation_songs):
        blocks = render_song_blocks(
            animation_song.song,
            mode="full-chorus",
            settings=render_settings,
            verses=animation_song.song.verses.all(),
        )
        songs_payload.append(
            {
                "songIndex": index,
                "songTitle": animation_song.song.display_title,
                "blocks": [
                    {
                        "label": str(block.label or ""),
                        "text": str(block.text or ""),
                        "kind": str(block.kind),
                    }
                    for block in blocks
                ],
            }
        )

    return render(
        request,
        "animation/lyrics_slide_show_public.html",
        {
            "animation": animation,
            "public_songs": songs_payload,
        },
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
