from __future__ import annotations

import base64
import io
import random
import re
import uuid

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user
from app_member.services import can_manage_moderator_popup
from app_song.rendering import SongRenderSettings, render_song_blocks
from app_song.search import SongSearchParams, load_member_song_search, search_songs

from .font_catalog import (
    GOOGLE_FONTS_STYLESHEET_HREF,
    list_font_choices,
    list_font_previews,
)
from .forms import AnimationForm, BackgroundImageUploadForm
from .models import Animation, BackgroundImage, BackgroundImageStatus
from .services.background_images import (
    active_background_image_options,
    build_background_context_slug,
    build_image_validation_config,
    clear_background_image_references,
    count_background_image_references,
    delete_image_file,
    ensure_background_image_dirs,
    fetch_genre_options,
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

try:
    import qrcode
except Exception:  # pragma: no cover - optional dependency in dev envs
    qrcode = None


def _shortcut_action_labels() -> dict[str, str]:
    return {
        "black": _("BLACK MODE"),
        "prev_slide": _("Previous slide"),
        "next_slide": _("Next slide"),
        "chorus": _("Chorus"),
        "open_display": _("Display current slide window"),
        "prev_song": _("Previous song"),
        "next_song": _("Next song"),
        "toggle_chorus": _("Display/hide choruses"),
        "toggle_scroll": _("Scroll on ↕️ or not 🧱"),
        "toggle_qr": _("📱 QR code for lyrics"),
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
                "backgroundImageOptions": _background_image_popup_options(),
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


DISPLAY_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


def _truncate_excerpt(text: str, max_chars: int = 50) -> str:
    flat = " ".join(str(text or "").split())
    if len(flat) <= max_chars:
        return flat
    return f"{flat[:max_chars].rstrip()}[...]"


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
                "shortcutsPopupFooter": _("⌨️👈 in upper or lower case"),
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
