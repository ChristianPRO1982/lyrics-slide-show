from django.db.models import Exists, OuterRef, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user, get_selected_group_state

from .models import (
    SONG_STATUS_VALIDATED,
    SONG_STATUS_VALIDATED_WITH_CONCERN,
    Song,
    SongFavorite,
    SongStatus,
)


SONG_SEARCH_VALIDATION_VALUES = {
    "all",
    "validated_only",
    "non_validated_only",
}
SONG_RESULT_LIMIT = 200
SONG_DESCRIPTION_SUMMARY_LENGTH = 180
TEXT_MODE_SINGLE_CHORUS = "single-chorus"
TEXT_MODE_FULL_CHORUS = "full-chorus"


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _can_edit_unvalidated_song(user, song: Song) -> bool:
    return _is_authenticated(user) and not song.is_validated


def _can_read_song(user, song: Song) -> bool:
    return _is_authenticated(user) or not song.licensed


def _get_search_params(request: HttpRequest, member_id: str | None) -> dict[str, object]:
    validation = request.GET.get("validation", "all")
    if validation not in SONG_SEARCH_VALIDATION_VALUES:
        validation = "all"

    return {
        "q": request.GET.get("q", "").strip(),
        "extended": request.GET.get("extended") == "1",
        "validation": validation,
        "favorites_only": bool(member_id and request.GET.get("favorites_only") == "1"),
    }


def _get_accessible_songs(request: HttpRequest):
    queryset = Song.objects.all()
    if not _is_authenticated(request.user):
        queryset = queryset.filter(licensed=False)
    return queryset


def _apply_search_filters(queryset, params: dict[str, object], member_id: str | None):
    query = str(params["q"])
    if query:
        search_filter = Q(title__icontains=query) | Q(subtitle__icontains=query)
        if params["extended"]:
            search_filter |= Q(description__icontains=query) | Q(verses__text__icontains=query)
        queryset = queryset.filter(search_filter).distinct()

    if params["validation"] == "validated_only":
        queryset = queryset.filter(status__in=[SONG_STATUS_VALIDATED, SONG_STATUS_VALIDATED_WITH_CONCERN])
    elif params["validation"] == "non_validated_only":
        queryset = queryset.filter(status=SongStatus.NOT_VALIDATED)

    if params["favorites_only"] and member_id:
        queryset = queryset.filter(favorites__member_id=member_id)

    return queryset


def _with_favorite_state(queryset, member_id: str | None):
    if not member_id:
        return queryset

    return queryset.annotate(
        is_favorite=Exists(
            SongFavorite.objects.filter(
                song_id=OuterRef("song_id"),
                member_id=member_id,
            )
        )
    )


def _normalize_display_linebreaks(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


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


def _build_song_cards(songs, user) -> list[dict[str, object]]:
    cards = []
    for song in songs:
        validation_label = ""
        if song.status == SongStatus.VALIDATED:
            validation_label = _("Chant validé")
        elif song.status == SongStatus.VALIDATED_WITH_CONCERN:
            validation_label = _("Chant validé avec des messages")

        description_summary, description_rest = _split_description_for_display(song.description)
        cards.append(
            {
                "song": song,
                "is_favorite": bool(getattr(song, "is_favorite", False)),
                "validation_label": validation_label,
                "is_validated": song.is_validated,
                "description_summary": description_summary,
                "description_rest": description_rest,
                "can_edit": _can_edit_unvalidated_song(user, song),
                "display_url": reverse("song_text", args=[song.song_id, TEXT_MODE_FULL_CHORUS]),
                "print_single_url": reverse("song_text", args=[song.song_id, TEXT_MODE_SINGLE_CHORUS]),
                "print_full_url": reverse("song_text", args=[song.song_id, TEXT_MODE_FULL_CHORUS]),
                "print_single_plain_url": f"{reverse('song_text', args=[song.song_id, TEXT_MODE_SINGLE_CHORUS])}?format=plain",
                "print_full_plain_url": f"{reverse('song_text', args=[song.song_id, TEXT_MODE_FULL_CHORUS])}?format=plain",
            }
        )
    return cards


def _build_song_cards_for_request(songs, request: HttpRequest) -> list[dict[str, object]]:
    return _build_song_cards(list(songs), request.user)


def _render_text_block(label: str, text: str | None) -> list[str]:
    if not text:
        return []
    normalized_text = _normalize_display_linebreaks(text).strip()
    if label:
        return [label, normalized_text]
    return [normalized_text]


def _render_chorus_group(choruses, include_label: bool) -> list[str]:
    output = []
    for index, chorus in enumerate(choruses):
        output.extend(_render_text_block(_("Refrain") if include_label and index == 0 else "", chorus.text))
    return output


def _render_song_plain_text(song: Song, mode: str) -> str:
    verses = list(song.verses.all().order_by("num", "verse_id"))
    choruses = [verse for verse in verses if verse.chorus]
    chorus_already_rendered = False
    output = [song.display_title, ""]
    start_by_chorus = True

    for verse in verses:
        if not verse.chorus:
            if verse.text and verse.chorus_like:
                output.extend(_render_text_block(verse.prefix or _("Refrain"), verse.text))
                output.append("")
            elif verse.text:
                label = ""
                if not verse.notcontinuenumbering:
                    label = _("Couplet %(number)s") % {"number": verse.num_verse}
                output.extend(_render_text_block(label, verse.text))
                output.append("")

            if not verse.followed and choruses and (mode == TEXT_MODE_FULL_CHORUS or not chorus_already_rendered):
                output.extend(_render_chorus_group(choruses, include_label=True))
                output.append("")
                chorus_already_rendered = True

        elif start_by_chorus and choruses and (mode == TEXT_MODE_FULL_CHORUS or not chorus_already_rendered):
            output.extend(_render_chorus_group(choruses, include_label=True))
            output.append("")
            chorus_already_rendered = True

        start_by_chorus = False

    if len([line for line in output if line.strip()]) <= 1 and choruses:
        output.extend(_render_chorus_group(choruses, include_label=True))

    return "\n".join(output).strip() + "\n"


def songs(request: HttpRequest) -> HttpResponse:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    member_id = get_member_id_from_user(request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        song = get_object_or_404(Song, song_id=request.POST.get("song_id"))
        if action == "delete_song":
            if not _can_edit_unvalidated_song(request.user, song):
                raise Http404
            song.delete()
            return redirect("songs")
        raise Http404

    search_params = _get_search_params(request, member_id)

    accessible_songs = _get_accessible_songs(request)
    catalog_count = accessible_songs.count()

    filtered_songs = _apply_search_filters(accessible_songs, search_params, member_id)
    search_count = filtered_songs.count()
    limited_songs = _with_favorite_state(filtered_songs, member_id)[:SONG_RESULT_LIMIT]
    song_cards = _build_song_cards_for_request(limited_songs, request)

    return render(
        request,
        "song/songs.html",
        {
            "selected_group": selected_group,
            "search_params": search_params,
            "song_cards": song_cards,
            "displayed_count": len(song_cards),
            "search_count": search_count,
            "catalog_count": catalog_count,
            "result_limit": SONG_RESULT_LIMIT,
            "is_limited": search_count > SONG_RESULT_LIMIT,
            "can_use_favorites": bool(member_id),
            "can_create_song": _is_authenticated(request.user),
        },
    )


def song_text(request: HttpRequest, song_id: int, mode: str) -> HttpResponse:
    if mode not in {TEXT_MODE_SINGLE_CHORUS, TEXT_MODE_FULL_CHORUS}:
        raise Http404

    song = get_object_or_404(Song, song_id=song_id)
    if not _can_read_song(request.user, song):
        raise Http404

    rendered_text = _render_song_plain_text(song, mode)
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
