from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user, get_selected_group_state

from .models import (
    Song,
    SongFavorite,
    SongStatus,
)
from .rendering import ChorusRenderMode, SongRenderSettings, normalize_lyrics_linebreaks, render_song_text
from .search import (
    TEXT_MODE_FULL_CHORUS,
    TEXT_MODE_SINGLE_CHORUS,
    SongReferenceOptions,
    build_song_search_query,
    get_active_song_search,
    get_reference_options,
    search_songs,
)


SONG_RESULT_LIMIT = 200
SONG_DESCRIPTION_SUMMARY_LENGTH = 180


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _can_edit_unvalidated_song(user, song: Song) -> bool:
    return _is_authenticated(user) and not song.is_validated


def _can_read_song(user, song: Song) -> bool:
    return _is_authenticated(user) or not song.licensed


def _normalize_display_linebreaks(value: str | None) -> str:
    return normalize_lyrics_linebreaks(value)


def _split_description_for_display(value: str | None) -> tuple[str, str]:
    normalized = _normalize_display_linebreaks(value).strip()
    if not normalized:
        return "", ""

    lines = normalized.split("\n")
    first_line = lines[0].strip()
    remaining_lines = lines[1:]

    if len(first_line) > SONG_DESCRIPTION_SUMMARY_LENGTH:
        summary = f"{first_line[:SONG_DESCRIPTION_SUMMARY_LENGTH].rstrip()}…"
        rest_parts = [first_line[SONG_DESCRIPTION_SUMMARY_LENGTH:].lstrip(), *remaining_lines]
        return summary, "\n".join(rest_parts).strip()

    return first_line, "\n".join(remaining_lines).strip()


def _build_song_cards(search_results, user) -> list[dict[str, object]]:
    cards = []
    for result in search_results:
        song = result.song
        description_summary, description_rest = _split_description_for_display(song.description)
        cards.append(
            {
                "song": song,
                "is_favorite": result.is_favorite,
                "validation_label": result.validation_label,
                "is_validated": song.is_validated,
                "description_summary": description_summary,
                "description_rest": description_rest,
                "can_edit": _can_edit_unvalidated_song(user, song),
                "genres": result.genres,
                "bands": result.bands,
                "artists": result.artists,
                "display_url": result.display_url,
                "print_single_url": result.print_single_url,
                "print_full_url": result.print_full_url,
                "print_single_plain_url": result.print_single_plain_url,
                "print_full_plain_url": result.print_full_plain_url,
            }
        )
    return cards


def _empty_reference_options() -> SongReferenceOptions:
    return SongReferenceOptions(genres=(), bands=(), artists=())


def _handle_song_post(request: HttpRequest, redirect_url: str) -> HttpResponse:
    action = request.POST.get("action")
    song = get_object_or_404(Song, song_id=request.POST.get("song_id"))
    if action == "delete_song":
        if not _can_edit_unvalidated_song(request.user, song):
            raise Http404
        song.delete()
        return redirect(redirect_url)
    raise Http404


def songs(request: HttpRequest) -> HttpResponse:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    member_id = get_member_id_from_user(request.user)

    if request.method == "POST":
        return _handle_song_post(request, "songs")

    search_params = get_active_song_search(request, member_id)
    search_results = search_songs(search_params, request.user, member_id, limit=SONG_RESULT_LIMIT)
    song_cards = _build_song_cards(search_results.results, request.user)
    reference_options = get_reference_options() if _is_authenticated(request.user) else _empty_reference_options()

    return render(
        request,
        "song/songs.html",
        {
            "selected_group": selected_group,
            "search_params": search_results.params,
            "reference_options": reference_options,
            "song_cards": song_cards,
            "displayed_count": search_results.displayed_count,
            "search_count": search_results.search_count,
            "catalog_count": search_results.catalog_count,
            "result_limit": search_results.result_limit,
            "is_limited": search_results.is_limited,
            "can_use_favorites": bool(member_id),
            "can_use_advanced_search": _is_authenticated(request.user),
            "can_create_song": _is_authenticated(request.user),
            "favorites_toggle_query": build_song_search_query(
                search_results.params,
                favorites_only=not search_results.params.favorites_only,
            ),
        },
    )


def song(request: HttpRequest, song_id: int) -> HttpResponse:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    song_object = get_object_or_404(
        Song.objects.prefetch_related("verses", "messages", "links"),
        song_id=song_id,
    )
    if not _can_read_song(request.user, song_object):
        raise Http404

    if request.method == "POST":
        return _handle_song_post(request, "songs")

    description_summary, description_rest = _split_description_for_display(song_object.description)
    validation_label = ""
    if song_object.status == SongStatus.VALIDATED:
        validation_label = _("Chant validé")
    elif song_object.status == SongStatus.VALIDATED_WITH_CONCERN:
        validation_label = _("Chant validé avec des messages")
    else:
        validation_label = _("Chant non validé")

    member_id = get_member_id_from_user(request.user)
    is_favorite = bool(
        member_id
        and SongFavorite.objects.filter(song_id=song_object.song_id, member_id=member_id).exists()
    )
    render_settings = SongRenderSettings.from_language(getattr(request, "LANGUAGE_CODE", None))
    rendered_text = render_song_text(song_object, ChorusRenderMode.FULL, settings=render_settings)

    return render(
        request,
        "song/song.html",
        {
            "selected_group": selected_group,
            "song": song_object,
            "description_display": _normalize_display_linebreaks(song_object.description).strip(),
            "description_summary": description_summary,
            "description_rest": description_rest,
            "validation_label": validation_label,
            "is_favorite": is_favorite,
            "can_edit": _can_edit_unvalidated_song(request.user, song_object),
            "can_view_messages": bool(member_id),
            "can_report_message": not _can_edit_unvalidated_song(request.user, song_object),
            "messages_history": song_object.messages.all().order_by("-date", "-message_id"),
            "links": song_object.links.all().order_by("link"),
            "rendered_text": rendered_text,
            "display_url": reverse("song", args=[song_object.song_id]),
            "print_single_url": reverse("song_text", args=[song_object.song_id, TEXT_MODE_SINGLE_CHORUS]),
            "print_full_url": reverse("song_text", args=[song_object.song_id, TEXT_MODE_FULL_CHORUS]),
            "print_single_plain_url": f"{reverse('song_text', args=[song_object.song_id, TEXT_MODE_SINGLE_CHORUS])}?format=plain",
            "print_full_plain_url": f"{reverse('song_text', args=[song_object.song_id, TEXT_MODE_FULL_CHORUS])}?format=plain",
        },
    )


def song_text(request: HttpRequest, song_id: int, mode: str) -> HttpResponse:
    try:
        render_mode = ChorusRenderMode(mode)
    except ValueError:
        raise Http404

    song = get_object_or_404(Song, song_id=song_id)
    if not _can_read_song(request.user, song):
        raise Http404

    render_settings = SongRenderSettings.from_language(getattr(request, "LANGUAGE_CODE", None))
    rendered_text = render_song_text(song, render_mode, settings=render_settings)
    if request.GET.get("format") == "plain":
        return HttpResponse(rendered_text, content_type="text/plain; charset=utf-8")

    return render(
        request,
        "song/song_text.html",
        {
            "song": song,
            "mode": mode,
            "rendered_text": rendered_text,
        },
    )
