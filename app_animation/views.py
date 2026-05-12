from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user
from app_song.search import SongSearchParams, load_member_song_search, search_songs

from .font_catalog import list_font_choices, list_font_previews
from .forms import AnimationForm
from .models import Animation
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
    ordered_mix_initial = "|".join([f"asid:{row.animation_song_id}" for row in animation_songs])

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
        advanced_song_results = search_songs(load_member_song_search(member_id), request.user, member_id)
        favorite_song_results = search_songs(SongSearchParams(favorites_only=True), request.user, member_id)
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
                    sync_animation_playlist(animation, ordered_tokens, allowed_song_ids=accessible_song_ids)
                apply_songs_payload(form.instance, songs_payload)
                form.instance.save()
            messages.success(request, _("L'animation a été enregistrée."))
            return redirect("modify_animation", animation_id=animation.animation_id)
        songs_payload_initial_json = str(request.POST.get("songs_payload") or songs_payload_initial_json)
        ordered_mix_initial = str(request.POST.get("ordered_mix") or ordered_mix_initial)
    else:
        form = AnimationForm(instance=animation)

    font_choices = [{"value": value, "label": label} for value, label in list_font_choices()]
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
