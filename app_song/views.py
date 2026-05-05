import re
from dataclasses import dataclass

from django.db import connection, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.translation import gettext as _

from app_group.services import get_member_id_from_user, get_selected_group_state
from app_member.services import get_site_params_for_language

from .models import (
    Song,
    SongArtist,
    SongBand,
    SongFavorite,
    SongGenre,
    SongMessage,
    SongMessageStatus,
    SongStatus,
    Verse,
)
from .rendering import (
    ChorusRenderMode,
    SongRenderSettings,
    build_song_full_title_with_tags,
    build_song_text_artifacts,
    render_song_blocks,
    normalize_lyrics_linebreaks,
)
from .search import (
    TEXT_MODE_FULL_CHORUS,
    TEXT_MODE_SINGLE_CHORUS,
    SongReferenceOptions,
    build_song_search_query,
    get_active_song_search,
    get_reference_options,
    search_songs,
)
from .tag_emojis import with_artist_emoji, with_band_emoji, with_music_emoji


SONG_DESCRIPTION_SUMMARY_LENGTH = 180
SONG_PAGE_SUMMARY_MAX_LENGTH = 100
DEFAULT_VERSE_MAX_LINES = 10
DEFAULT_VERSE_MAX_CHARS = 50
BLOCK_FIELD_PATTERN = re.compile(r"^blocks\[(?P<row>[^\]]+)\]\[(?P<field>[a-z_]+)\]$")
MULTISPACE_PATTERN = re.compile(r"[ \t]+")
FRENCH_PUNCTUATION_PATTERN = re.compile(r"(?<=\S)[ \u00A0\u202F]*([!?;:])")


@dataclass
class ParsedSongBlock:
    row_key: str
    block_id: int | None
    position: int
    block_type: str
    text: str
    prefix: str
    followed: bool
    not_c_num: bool
    delete: bool
    chorus: bool = False
    chorus_like: bool = False
    num: int = 0
    display_num: int = 0


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _is_moderator(user) -> bool:
    return bool(_is_authenticated(user) and getattr(user, "is_moderator", False))


def _can_edit_song(user, song: Song) -> bool:
    if not _is_authenticated(user):
        return False
    return (not song.is_validated) or _is_moderator(user)


def _can_read_song(user, song: Song) -> bool:
    return _is_authenticated(user) or not song.licensed


def _can_report_message(user, song: Song) -> bool:
    return _can_read_song(user, song) and not _can_edit_song(user, song)


def _is_truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _safe_int(value: str | None, fallback: int) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return fallback


def _apply_french_spacing(value: str) -> str:
    return FRENCH_PUNCTUATION_PATTERN.sub("\u00A0\\1", value)


def _normalize_inline_text(value: str | None) -> str:
    normalized = normalize_lyrics_linebreaks(value).replace("\n", " ")
    normalized = MULTISPACE_PATTERN.sub(" ", normalized).strip()
    if not normalized:
        return ""
    return _apply_french_spacing(normalized)


def _normalize_multiline_text(value: str | None) -> str:
    normalized = normalize_lyrics_linebreaks(value)
    raw_lines = normalized.split("\n")
    clean_lines: list[str] = []

    for line in raw_lines:
        stripped = str(line).strip()
        if not stripped:
            clean_lines.append("")
            continue
        collapsed = MULTISPACE_PATTERN.sub(" ", stripped)
        clean_lines.append(_apply_french_spacing(collapsed))

    while clean_lines and clean_lines[0] == "":
        clean_lines.pop(0)
    while clean_lines and clean_lines[-1] == "":
        clean_lines.pop()

    return "\n".join(clean_lines)


def _extract_block_rows(data) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for key, value in data.items():
        match = BLOCK_FIELD_PATTERN.match(key)
        if not match:
            continue
        row_key = match.group("row")
        field_name = match.group("field")
        rows.setdefault(row_key, {})[field_name] = value
    return rows


def _map_block_type(block_type: str) -> tuple[bool, bool]:
    if block_type == "chorus":
        return True, False
    if block_type == "special":
        return False, True
    return False, False


def _parse_song_blocks(post_data) -> list[ParsedSongBlock]:
    rows = _extract_block_rows(post_data)
    blocks: list[ParsedSongBlock] = []

    for row_key, row_data in rows.items():
        block_type = (row_data.get("type") or "verse").strip().lower()
        if block_type not in {"verse", "chorus", "special"}:
            block_type = "verse"
        block_id_raw = (row_data.get("id") or "").strip()
        block_id = _safe_int(block_id_raw, fallback=-1) if block_id_raw else None
        if block_id is not None and block_id <= 0:
            block_id = None

        parsed = ParsedSongBlock(
            row_key=row_key,
            block_id=block_id,
            position=_safe_int(row_data.get("position"), fallback=999999),
            block_type=block_type,
            text=_normalize_multiline_text(row_data.get("text")),
            prefix=_normalize_inline_text(row_data.get("prefix")),
            followed=_is_truthy(row_data.get("followed")),
            not_c_num=_is_truthy(row_data.get("not_c_num")),
            delete=_is_truthy(row_data.get("delete")),
        )

        if parsed.block_id is None and not parsed.text and not parsed.prefix and not parsed.delete:
            continue

        parsed.chorus, parsed.chorus_like = _map_block_type(parsed.block_type)
        if parsed.chorus:
            parsed.followed = False
            parsed.not_c_num = False
            parsed.prefix = ""
        blocks.append(parsed)

    blocks.sort(key=lambda item: (item.position, item.row_key))
    return blocks


def _recalculate_song_blocks(blocks: list[ParsedSongBlock]) -> list[ParsedSongBlock]:
    display_number = 0
    for index, block in enumerate(blocks):
        block.num = (index + 1) * 2
        if not block.chorus and not block.chorus_like and not block.not_c_num:
            display_number += 1
        block.display_num = display_number
    return blocks


def _build_blocks_from_song(song: Song) -> list[ParsedSongBlock]:
    blocks: list[ParsedSongBlock] = []
    for verse in song.verses.all().order_by("num", "verse_id"):
        if verse.chorus:
            block_type = "chorus"
        elif verse.chorus_like:
            block_type = "special"
        else:
            block_type = "verse"
        blocks.append(
            ParsedSongBlock(
                row_key=f"existing-{verse.verse_id}",
                block_id=verse.verse_id,
                position=verse.num,
                block_type=block_type,
                text=_normalize_display_linebreaks(verse.text).strip(),
                prefix=(verse.prefix or "").strip(),
                followed=bool(verse.followed),
                not_c_num=bool(verse.notcontinuenumbering),
                delete=False,
                chorus=bool(verse.chorus),
                chorus_like=bool(verse.chorus_like),
                num=verse.num,
                display_num=verse.num_verse,
            )
        )
    return _recalculate_song_blocks(blocks)


def _build_preview_markdown(song: Song, blocks: list[ParsedSongBlock], settings: SongRenderSettings) -> str:
    preview_verses = []
    for block in blocks:
        preview_verses.append(
            Verse(
                verse_id=block.block_id or 0,
                song=song,
                num=block.num,
                num_verse=block.display_num,
                chorus=block.chorus,
                chorus_like=block.chorus_like,
                followed=block.followed,
                notcontinuenumbering=block.not_c_num,
                text=block.text,
                prefix=block.prefix,
            )
        )

    rendered_blocks = render_song_blocks(song, ChorusRenderMode.FULL, settings=settings, verses=preview_verses)
    lines: list[str] = []
    for rendered_block in rendered_blocks:
        label = str(rendered_block.label or "").strip()
        if label:
            lines.append(f"**{label}**")
        lines.extend(str(rendered_block.text or "").split("\n"))
        lines.append("")

    return "\n".join(lines).strip()


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


def _build_page_summary(value: str | None) -> tuple[str, bool]:
    normalized = _normalize_display_linebreaks(value).strip()
    if not normalized:
        return "", False

    if len(normalized) <= SONG_PAGE_SUMMARY_MAX_LENGTH:
        return normalized, False

    end = SONG_PAGE_SUMMARY_MAX_LENGTH
    while end < len(normalized) and not normalized[end].isspace():
        end += 1

    return normalized[:end].rstrip(), True


def _build_song_cards(search_results, user) -> list[dict[str, object]]:
    cards = []
    for result in search_results:
        song = result.song
        description_summary, description_rest = _split_description_for_display(song.description)
        cards.append(
            {
                "song": song,
                "is_favorite": result.is_favorite,
                "is_validated": song.is_validated,
                "description_summary": description_summary,
                "description_rest": description_rest,
                "can_edit": _can_edit_song(user, song),
                "title_complete_with_tags": build_song_full_title_with_tags(song),
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


def _fetch_genre_labels(ids: set[int]) -> dict[int, tuple[str, str]]:
    if not ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT genre_id, "group", "name"
            FROM "common"."genres"
            WHERE genre_id = ANY(%s)
            ORDER BY "group", "name"
            """,
            [list(ids)],
        )
        return {row[0]: (row[1] or "#", row[2]) for row in cursor.fetchall()}


def _fetch_name_labels(table: str, id_column: str, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {id_column}, "name"
            FROM "common"."{table}"
            WHERE {id_column} = ANY(%s)
            ORDER BY "name"
            """,
            [list(ids)],
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def _get_song_metadata_labels(
    song: Song,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    genre_ids = tuple(
        SongGenre.objects.filter(song_id=song.song_id)
        .values_list("genre_id", flat=True)
    )
    band_ids = tuple(
        SongBand.objects.filter(song_id=song.song_id)
        .values_list("band_id", flat=True)
    )
    artist_ids = tuple(
        SongArtist.objects.filter(song_id=song.song_id)
        .values_list("artist_id", flat=True)
    )

    genre_labels = _fetch_genre_labels(set(genre_ids))
    band_labels = _fetch_name_labels("bands", "band_id", set(band_ids))
    artist_labels = _fetch_name_labels("artists", "artist_id", set(artist_ids))

    grouped_genres: dict[str, list[str]] = {}
    for item in genre_ids:
        label = genre_labels.get(item)
        if not label:
            continue
        group_name, genre_name = label
        grouped_genres.setdefault(group_name, []).append(genre_name)

    return (
        tuple(with_band_emoji(label) for label in (band_labels.get(item) for item in band_ids) if label),
        tuple(with_artist_emoji(label) for label in (artist_labels.get(item) for item in artist_ids) if label),
        tuple((group_name, tuple(with_music_emoji(name) for name in names)) for group_name, names in grouped_genres.items()),
    )


def _get_song_message_status_label(status: int) -> str:
    if status == SongMessageStatus.NEW:
        return _("Nouveau")
    if status == SongMessageStatus.HANDLED:
        return _("Traité")
    if status == SongMessageStatus.REJECTED:
        return _("Rejeté")
    return _("Inconnu")


def _get_song_validation_label(song: Song) -> str:
    if song.status == SongStatus.VALIDATED:
        return _("Chant validé")
    if song.status == SongStatus.VALIDATED_WITH_CONCERN:
        return _("Chant validé avec des messages")
    return _("Chant non validé")


def _build_block_display_label(block: ParsedSongBlock, settings: SongRenderSettings) -> str:
    if block.chorus:
        return settings.chorus_prefix
    if block.chorus_like:
        return block.prefix or _("Section spéciale")
    if block.not_c_num:
        return _("Couplet (sans numérotation)")
    return settings.verse_label(block.display_num)


def _build_block_display_text(block: ParsedSongBlock) -> str:
    return _normalize_display_linebreaks(block.text).strip()


def _build_block_drag_label(block: ParsedSongBlock, settings: SongRenderSettings) -> str:
    prefix = str(block.prefix or "").strip()
    if prefix:
        return prefix
    if block.chorus:
        return settings.chorus_prefix
    return settings.verse_label(block.display_num)


def _build_block_drag_text(block: ParsedSongBlock) -> str:
    normalized = _build_block_display_text(block)
    if not normalized:
        return _("Bloc vide")

    for line in normalized.split("\n"):
        excerpt = line.strip()
        if excerpt:
            return excerpt
    return _("Bloc vide")


def _as_template_block(
    block: ParsedSongBlock,
    settings: SongRenderSettings,
    verse_max_lines: int,
    verse_max_characters_for_line: int,
) -> dict[str, object]:
    lines = _build_block_display_text(block).split("\n") if block.text else []
    max_line_length = max((len(line) for line in lines), default=0)
    return {
        "row_key": block.row_key,
        "id": block.block_id or "",
        "position": block.num or block.position,
        "type": block.block_type,
        "text": block.text,
        "prefix": block.prefix,
        "followed": block.followed,
        "not_c_num": block.not_c_num,
        "delete": block.delete,
        "display_label": _build_block_display_label(block, settings),
        "display_text": _build_block_display_text(block),
        "drag_label": _build_block_drag_label(block, settings),
        "drag_text": _build_block_drag_text(block),
        "line_count": len(lines),
        "max_line_length": max_line_length,
        "has_too_many_lines": len(lines) > verse_max_lines if verse_max_lines > 0 else False,
        "has_line_too_long": max_line_length > verse_max_characters_for_line if verse_max_characters_for_line > 0 else False,
    }


def _build_modify_song_context(
    request: HttpRequest,
    selected_group,
    song: Song,
    parsed_blocks: list[ParsedSongBlock] | None = None,
) -> dict[str, object]:
    render_settings = SongRenderSettings.from_language(getattr(request, "LANGUAGE_CODE", None))
    site_params = get_site_params_for_language(getattr(request, "LANGUAGE_CODE", None))
    verse_max_lines = site_params.verse_max_lines if site_params else DEFAULT_VERSE_MAX_LINES
    verse_max_characters_for_line = (
        site_params.verse_max_characters_for_a_line if site_params else DEFAULT_VERSE_MAX_CHARS
    )

    blocks = _recalculate_song_blocks(parsed_blocks or _build_blocks_from_song(song))
    bands, artists, genre_groups = _get_song_metadata_labels(song)
    page_summary_text, page_summary_truncated = _build_page_summary(song.description)

    return {
        "selected_group": selected_group,
        "song": song,
        "title_complete_with_tags": build_song_full_title_with_tags(song),
        "description_display": _normalize_display_linebreaks(song.description).strip(),
        "page_summary_text": page_summary_text,
        "page_summary_truncated": page_summary_truncated,
        "validation_label": _get_song_validation_label(song),
        "licensed_label": _("Chant sous licence") if song.licensed else _("Chant hors licence"),
        "links": song.links.all().order_by("link"),
        "bands": bands,
        "artists": artists,
        "genre_groups": genre_groups,
        "can_edit": _can_edit_song(request.user, song),
        "can_devalidate": bool(song.is_validated and _is_moderator(request.user)),
        "display_url": reverse("song", args=[song.song_id]),
        "preview_url": reverse("modify_song_preview", args=[song.song_id]),
        "verse_max_lines": verse_max_lines,
        "verse_max_characters_for_line": verse_max_characters_for_line,
        "song_blocks": [
            _as_template_block(
                block,
                settings=render_settings,
                verse_max_lines=verse_max_lines,
                verse_max_characters_for_line=verse_max_characters_for_line,
            )
            for block in blocks
            if not block.delete
        ],
    }


def _update_song_from_form(song: Song, request: HttpRequest) -> None:
    song.title = _normalize_inline_text(request.POST.get("title"))
    song.subtitle = _normalize_inline_text(request.POST.get("subtitle"))
    song.description = _normalize_multiline_text(request.POST.get("description"))
    validated_checked = _is_truthy(request.POST.get("status_validated"))

    parsed_blocks = _parse_song_blocks(request.POST)
    active_blocks = _recalculate_song_blocks([block for block in parsed_blocks if not block.delete])
    existing_by_id = {verse.verse_id: verse for verse in song.verses.all()}
    song_update_fields = ["title", "subtitle", "description"]
    if _is_moderator(request.user):
        next_status = SongStatus.NOT_VALIDATED
        if validated_checked:
            if song.status == SongStatus.VALIDATED_WITH_CONCERN:
                next_status = SongStatus.VALIDATED_WITH_CONCERN
            else:
                next_status = SongStatus.VALIDATED
        if song.status != next_status:
            song.status = next_status
            song_update_fields.append("status")

    with transaction.atomic():
        song.save(update_fields=song_update_fields)
        for block in active_blocks:
            verse = existing_by_id.pop(block.block_id, None) if block.block_id else None
            if verse is None:
                verse = Verse(song=song)
            verse.num = block.num
            verse.num_verse = block.display_num
            verse.chorus = block.chorus
            verse.chorus_like = block.chorus_like
            verse.followed = block.followed
            verse.notcontinuenumbering = block.not_c_num
            verse.text = block.text
            verse.prefix = block.prefix
            verse.save()

        if existing_by_id:
            Verse.objects.filter(verse_id__in=tuple(existing_by_id.keys())).delete()


def _handle_song_post(request: HttpRequest, redirect_url: str) -> HttpResponse:
    action = request.POST.get("action")
    song = get_object_or_404(Song, song_id=request.POST.get("song_id"))
    if action == "delete_song":
        if not _can_edit_song(request.user, song):
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
    search_results = search_songs(search_params, request.user, member_id)
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
        action = request.POST.get("action")
        if action == "delete_song":
            return _handle_song_post(request, "songs")
        if action == "add_message":
            if not _can_report_message(request.user, song_object):
                raise Http404
            message = (request.POST.get("message") or "").strip()
            if message:
                SongMessage.objects.create(
                    song=song_object,
                    message=message,
                    status=SongMessageStatus.NEW,
                    date=timezone.now(),
                )
                return redirect("song", song_id=song_object.song_id)

    description_summary, description_rest = _split_description_for_display(song_object.description)
    page_summary_text, page_summary_truncated = _build_page_summary(song_object.description)
    validation_label = ""
    if song_object.status == SongStatus.VALIDATED:
        validation_label = _("Chant validé")
    elif song_object.status == SongStatus.VALIDATED_WITH_CONCERN:
        validation_label = _("Chant validé avec des messages")
    else:
        validation_label = _("Chant non validé")

    member_id = get_member_id_from_user(request.user)
    bands, artists, genre_groups = _get_song_metadata_labels(song_object)
    is_favorite = bool(
        member_id
        and SongFavorite.objects.filter(song_id=song_object.song_id, member_id=member_id).exists()
    )
    can_report = _can_report_message(request.user, song_object)
    render_settings = SongRenderSettings.from_language(getattr(request, "LANGUAGE_CODE", None))
    text_artifacts = build_song_text_artifacts(song_object, settings=render_settings)
    messages_history = song_object.messages.all().order_by("-date", "-message_id")

    return render(
        request,
        "song/song.html",
        {
            "selected_group": selected_group,
            "song": song_object,
            "description_display": _normalize_display_linebreaks(song_object.description).strip(),
            "page_summary_text": page_summary_text,
            "page_summary_truncated": page_summary_truncated,
            "description_summary": description_summary,
            "description_rest": description_rest,
            "validation_label": validation_label,
            "licensed_label": _("Chant sous licence") if song_object.licensed else _("Chant hors licence"),
            "is_favorite": is_favorite,
            "can_edit": _can_edit_song(request.user, song_object),
            "can_view_messages": bool(member_id),
            "can_report_message": can_report,
            "message_error": request.method == "POST" and request.POST.get("action") == "add_message" and not bool((request.POST.get("message") or "").strip()),
            "messages_history": messages_history,
            "messages_with_status": [
                {
                    "item": item,
                    "status_label": _get_song_message_status_label(item.status),
                }
                for item in messages_history
            ],
            "links": song_object.links.all().order_by("link"),
            "bands": bands,
            "artists": artists,
            "genre_groups": genre_groups,
            "title_complete": text_artifacts.full_title,
            "title_complete_with_tags": text_artifacts.full_title_with_tags,
            "text_short_html": text_artifacts.short_text_html,
            "text_long_html": text_artifacts.long_text_html,
            "display_url": reverse("song", args=[song_object.song_id]),
            "print_single_url": reverse("song_text", args=[song_object.song_id, TEXT_MODE_SINGLE_CHORUS]),
            "print_full_url": reverse("song_text", args=[song_object.song_id, TEXT_MODE_FULL_CHORUS]),
            "print_single_plain_url": f"{reverse('song_text', args=[song_object.song_id, TEXT_MODE_SINGLE_CHORUS])}?format=plain",
            "print_full_plain_url": f"{reverse('song_text', args=[song_object.song_id, TEXT_MODE_FULL_CHORUS])}?format=plain",
        },
    )


def modify_song(request: HttpRequest, song_id: int) -> HttpResponse:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    song_object = get_object_or_404(Song.objects.prefetch_related("verses", "links"), song_id=song_id)
    if not _is_authenticated(request.user):
        raise Http404

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "devalidate_song":
            if not (_is_moderator(request.user) and song_object.is_validated):
                raise Http404
            song_object.status = SongStatus.NOT_VALIDATED
            song_object.save(update_fields=["status"])
            return redirect("modify_song", song_id=song_object.song_id)

        if not _can_edit_song(request.user, song_object):
            raise Http404
        _update_song_from_form(song_object, request)
        submit_intent = (request.POST.get("submit_intent") or "save").strip()
        next_url = (request.POST.get("next_url") or "").strip()
        if submit_intent == "save_and_exit":
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("song", song_id=song_object.song_id)
        return redirect("modify_song", song_id=song_object.song_id)

    return render(
        request,
        "song/modify_song.html",
        _build_modify_song_context(request, selected_group, song_object),
    )


def modify_song_preview(request: HttpRequest, song_id: int) -> JsonResponse:
    if request.method != "POST":
        raise Http404

    song_object = get_object_or_404(Song, song_id=song_id)
    if not _can_edit_song(request.user, song_object):
        raise Http404

    preview_song = Song(
        song_id=song_object.song_id,
        title=_normalize_inline_text(request.POST.get("title")) or song_object.title,
        subtitle=_normalize_inline_text(request.POST.get("subtitle")) or "",
        description=_normalize_multiline_text(request.POST.get("description")),
        status=song_object.status,
        licensed=song_object.licensed,
    )
    parsed_blocks = _recalculate_song_blocks([block for block in _parse_song_blocks(request.POST) if not block.delete])
    render_settings = SongRenderSettings.from_language(getattr(request, "LANGUAGE_CODE", None))
    artifacts = build_song_text_artifacts(preview_song, settings=render_settings, verses=[
        Verse(
            verse_id=block.block_id or 0,
            song=preview_song,
            num=block.num,
            num_verse=block.display_num,
            chorus=block.chorus,
            chorus_like=block.chorus_like,
            followed=block.followed,
            notcontinuenumbering=block.not_c_num,
            text=block.text,
            prefix=block.prefix,
        )
        for block in parsed_blocks
    ])

    return JsonResponse(
        {
            "title": artifacts.full_title_with_tags,
            "markdown": _build_preview_markdown(preview_song, parsed_blocks, settings=render_settings),
            "html": artifacts.long_text_html,
        }
    )


def song_metadata(request: HttpRequest, song_id: int) -> HttpResponse:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    song_object = get_object_or_404(Song, song_id=song_id)
    if not _can_read_song(request.user, song_object):
        raise Http404
    return render(
        request,
        "song/metadata.html",
        {
            "selected_group": selected_group,
            "song": song_object,
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
    text_artifacts = build_song_text_artifacts(song, settings=render_settings)
    text_html = text_artifacts.short_text_html if render_mode == ChorusRenderMode.SINGLE else text_artifacts.long_text_html
    if request.GET.get("format") == "plain":
        return HttpResponse(text_html, content_type="text/plain; charset=utf-8")

    return render(
        request,
        "song/song_text.html",
        {
            "song": song,
            "mode": mode,
            "title_complete": text_artifacts.full_title,
            "text_html": text_html,
        },
    )
