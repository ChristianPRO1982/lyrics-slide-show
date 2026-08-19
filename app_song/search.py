from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from urllib.parse import urlencode

from django.db import connection
from django.db.models import (
    Exists,
    Max,
    OuterRef,
    Q,
    QuerySet,
)
from django.http import HttpRequest, QueryDict
from django.urls import reverse
from django.utils.translation import gettext as _

from app_member.models import MemberPreferences, default_song_search

from .genre_labels import build_genre_display_label
from .models import (
    SONG_STATUS_VALIDATED_WITH_CONCERN,
    Song,
    SongArtist,
    SongBand,
    SongFavorite,
    SongGenre,
    SongStatus,
)
from .tag_emojis import with_artist_emoji, with_band_emoji, with_music_emoji


SONG_SEARCH_VALIDATION_VALUES = {
    "all",
    "validated_only",
    "non_validated_only",
}
TEXT_MODE_SINGLE_CHORUS = "single-chorus"
TEXT_MODE_FULL_CHORUS = "full-chorus"
SEARCH_SONG_CATALOG_SQL = """
SELECT
    song_id,
    title,
    subtitle,
    description,
    status,
    licensed,
    is_favorite,
    search_count,
    catalog_count
FROM lss.search_song_catalog(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


@dataclass(frozen=True)
class SongSearchParams:
    text: str = ""
    everywhere: bool = False
    match_all_selected_refs: bool = False
    genre_ids: tuple[int, ...] = ()
    band_ids: tuple[int, ...] = ()
    artist_ids: tuple[int, ...] = ()
    validation: str = "all"
    favorites_only: bool = False

    @classmethod
    def empty(cls) -> "SongSearchParams":
        return cls.from_mapping(default_song_search())

    @classmethod
    def from_mapping(cls, value: dict[str, object]) -> "SongSearchParams":
        validation = str(value.get("validation") or "all")
        if validation not in SONG_SEARCH_VALIDATION_VALUES:
            validation = "all"
        return cls(
            text=str(value.get("text") or "").strip(),
            everywhere=bool(value.get("everywhere")),
            match_all_selected_refs=bool(value.get("match_all_selected_refs")),
            genre_ids=_normalize_ids(value.get("genre_ids")),
            band_ids=_normalize_ids(value.get("band_ids")),
            artist_ids=_normalize_ids(value.get("artist_ids")),
            validation=validation,
            favorites_only=bool(value.get("favorites_only")),
        )

    def for_guest(self) -> "SongSearchParams":
        return SongSearchParams(text=self.text)

    def to_preferences(self) -> dict[str, object]:
        return {
            "text": self.text,
            "everywhere": self.everywhere,
            "match_all_selected_refs": self.match_all_selected_refs,
            "genre_ids": list(self.genre_ids),
            "band_ids": list(self.band_ids),
            "artist_ids": list(self.artist_ids),
            "validation": self.validation,
            "favorites_only": self.favorites_only,
        }


@dataclass(frozen=True)
class SongReferenceOption:
    id: int
    label: str
    group: str = ""


@dataclass(frozen=True)
class SongReferenceTag:
    kind: str
    id: int
    label: str


@dataclass(frozen=True)
class SongSearchResult:
    song: Song
    is_favorite: bool
    validation_label: str
    genres: tuple[str, ...]
    bands: tuple[str, ...]
    artists: tuple[str, ...]
    genre_tags: tuple[SongReferenceTag, ...]
    band_tags: tuple[SongReferenceTag, ...]
    artist_tags: tuple[SongReferenceTag, ...]
    display_url: str
    print_single_url: str
    print_full_url: str
    print_single_plain_url: str
    print_full_plain_url: str


@dataclass(frozen=True)
class SongSearchResults:
    params: SongSearchParams
    results: tuple[SongSearchResult, ...]
    displayed_count: int
    search_count: int
    catalog_count: int


@dataclass(frozen=True)
class SongCatalogSearchRow:
    song: Song | None
    is_favorite: bool
    search_count: int
    catalog_count: int


@dataclass(frozen=True)
class SongReferenceOptions:
    genres: tuple[SongReferenceOption, ...]
    bands: tuple[SongReferenceOption, ...]
    artists: tuple[SongReferenceOption, ...]


REFERENCE_KIND_TO_FIELD = {
    "genre": "genre_ids",
    "band": "band_ids",
    "artist": "artist_ids",
}


def _normalize_ids(value: object) -> tuple[int, ...]:
    if value is None:
        return ()
    raw_values: Iterable[object]
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, Iterable):
        raw_values = value
    else:
        raw_values = [value]

    normalized = []
    for raw_value in raw_values:
        try:
            normalized_id = int(str(raw_value).strip())
        except (TypeError, ValueError):
            continue
        if normalized_id > 0 and normalized_id not in normalized:
            normalized.append(normalized_id)
    return tuple(normalized)


def _bool_from_query(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "and"}


def _ids_from_query(query: QueryDict, name: str) -> tuple[int, ...]:
    values: list[str] = []
    for value in query.getlist(name):
        values.extend(value.split(","))
    return _normalize_ids(values)


def _params_from_query(query: QueryDict) -> SongSearchParams:
    validation = query.get("validation", "all")
    if validation not in SONG_SEARCH_VALIDATION_VALUES:
        validation = "all"
    return SongSearchParams(
        text=(query.get("text") or query.get("q") or "").strip(),
        everywhere=_bool_from_query(query.get("everywhere") or query.get("extended")),
        match_all_selected_refs=_bool_from_query(
            query.get("match_all_selected_refs") or query.get("search_logic")
        ),
        genre_ids=_ids_from_query(query, "genre_ids"),
        band_ids=_ids_from_query(query, "band_ids"),
        artist_ids=_ids_from_query(query, "artist_ids"),
        validation=validation,
        favorites_only=_bool_from_query(query.get("favorites_only")),
    )


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _validation_label(song: Song) -> str:
    if song.status == SongStatus.VALIDATED:
        return _("Chant validé")
    if song.status == SongStatus.VALIDATED_WITH_CONCERN:
        return _("Chant validé avec des messages")
    return _("Chant non validé")


def load_member_song_search(member_id: str | None) -> SongSearchParams:
    if not member_id:
        return SongSearchParams.empty()
    try:
        member_uuid = uuid.UUID(str(member_id))
    except (TypeError, ValueError):
        return SongSearchParams.empty()

    try:
        preferences = MemberPreferences.objects.filter(member_id=member_uuid).first()
    except Exception:
        return SongSearchParams.empty()
    if preferences is None:
        return SongSearchParams.empty()
    return SongSearchParams.from_mapping(preferences.song_search)


def save_song_search(member_id: str | None, params: SongSearchParams) -> None:
    if not member_id:
        return
    try:
        member_uuid = uuid.UUID(str(member_id))
    except (TypeError, ValueError):
        return
    MemberPreferences.objects.update_or_create(
        member_id=member_uuid,
        defaults={"song_search": params.to_preferences()},
    )


def get_active_song_search(
    request: HttpRequest, member_id: str | None
) -> SongSearchParams:
    if "reset_search" in request.GET:
        params = SongSearchParams.empty()
        if member_id:
            save_song_search(member_id, params)
        return params

    if not _is_authenticated(request.user):
        return _params_from_query(request.GET).for_guest()

    if request.GET:
        params = _params_from_query(request.GET)
        save_song_search(member_id, params)
        return params

    return load_member_song_search(member_id)


def build_song_search_query(params: SongSearchParams, **overrides: object) -> str:
    values = params.to_preferences()
    values.update(overrides)
    normalized = SongSearchParams.from_mapping(values)
    explicit_favorites_override = "favorites_only" in overrides
    query: dict[str, object] = {}

    if normalized.text:
        query["text"] = normalized.text
    if normalized.everywhere:
        query["everywhere"] = "1"
    if normalized.match_all_selected_refs:
        query["match_all_selected_refs"] = "1"
    if normalized.genre_ids:
        query["genre_ids"] = list(normalized.genre_ids)
    if normalized.band_ids:
        query["band_ids"] = list(normalized.band_ids)
    if normalized.artist_ids:
        query["artist_ids"] = list(normalized.artist_ids)
    if normalized.validation != "all":
        query["validation"] = normalized.validation
    if normalized.favorites_only:
        query["favorites_only"] = "1"
    elif explicit_favorites_override:
        query["favorites_only"] = "0"
    return urlencode(query, doseq=True)


def _get_reference_field_name(kind: str) -> str:
    try:
        return REFERENCE_KIND_TO_FIELD[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported song search reference kind: {kind}") from exc


def _replace_reference_ids(
    params: SongSearchParams,
    *,
    kind: str,
    ids: tuple[int, ...],
) -> SongSearchParams:
    field_name = _get_reference_field_name(kind)
    return replace(params, **{field_name: ids})


def add_song_search_reference(
    params: SongSearchParams,
    *,
    kind: str,
    reference_id: int,
) -> SongSearchParams:
    if reference_id <= 0:
        return params
    field_name = _get_reference_field_name(kind)
    existing_ids = list(getattr(params, field_name))
    if reference_id not in existing_ids:
        existing_ids.append(reference_id)
    return _replace_reference_ids(
        params,
        kind=kind,
        ids=tuple(existing_ids),
    )


def remove_song_search_reference(
    params: SongSearchParams,
    *,
    kind: str,
    reference_id: int,
) -> SongSearchParams:
    field_name = _get_reference_field_name(kind)
    next_ids = tuple(
        current_id
        for current_id in getattr(params, field_name)
        if current_id != reference_id
    )
    return _replace_reference_ids(
        params,
        kind=kind,
        ids=next_ids,
    )


def build_song_search_url(params: SongSearchParams, **overrides: object) -> str:
    query = build_song_search_query(params, **overrides)
    base_url = reverse("songs")
    if not query:
        return base_url
    return f"{base_url}?{query}"


def build_song_search_reference_add_url(
    params: SongSearchParams,
    *,
    kind: str,
    reference_id: int,
) -> str:
    next_params = add_song_search_reference(
        params,
        kind=kind,
        reference_id=reference_id,
    )
    return build_song_search_url(next_params)


def build_song_search_reference_remove_url(
    params: SongSearchParams,
    *,
    kind: str,
    reference_id: int,
) -> str:
    next_params = remove_song_search_reference(
        params,
        kind=kind,
        reference_id=reference_id,
    )
    return build_song_search_url(next_params)


def build_active_song_search_reference_tags(
    params: SongSearchParams,
) -> tuple[dict[str, object], ...]:
    genre_labels = _fetch_genre_labels(set(params.genre_ids))
    band_labels = _fetch_name_labels("bands", "band_id", set(params.band_ids))
    artist_labels = _fetch_name_labels("artists", "artist_id", set(params.artist_ids))
    active_tags: list[dict[str, object]] = []

    for genre_id in params.genre_ids:
        label = genre_labels.get(genre_id)
        if not label:
            continue
        active_tags.append(
            {
                "kind": "genre",
                "id": genre_id,
                "label": with_music_emoji(label),
                "remove_url": build_song_search_reference_remove_url(
                    params,
                    kind="genre",
                    reference_id=genre_id,
                ),
            }
        )
    for band_id in params.band_ids:
        label = band_labels.get(band_id)
        if not label:
            continue
        active_tags.append(
            {
                "kind": "band",
                "id": band_id,
                "label": with_band_emoji(label),
                "remove_url": build_song_search_reference_remove_url(
                    params,
                    kind="band",
                    reference_id=band_id,
                ),
            }
        )
    for artist_id in params.artist_ids:
        label = artist_labels.get(artist_id)
        if not label:
            continue
        active_tags.append(
            {
                "kind": "artist",
                "id": artist_id,
                "label": with_artist_emoji(label),
                "remove_url": build_song_search_reference_remove_url(
                    params,
                    kind="artist",
                    reference_id=artist_id,
                ),
            }
        )

    return tuple(active_tags)


def _base_accessible_songs(user) -> QuerySet[Song]:
    queryset = Song.objects.all()
    if not _is_authenticated(user):
        queryset = queryset.filter(licensed=False)
    return queryset


def _with_favorite_state(
    queryset: QuerySet[Song], member_id: str | None
) -> QuerySet[Song]:
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


def _fetch_genre_labels(ids: set[int]) -> dict[int, str]:
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
        return {
            row[0]: build_genre_display_label(row[1], row[2])
            for row in cursor.fetchall()
        }


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


def _get_relation_maps(song_ids: list[int]):
    genre_map: dict[int, list[int]] = defaultdict(list)
    band_map: dict[int, list[int]] = defaultdict(list)
    artist_map: dict[int, list[int]] = defaultdict(list)

    for song_id, genre_id in SongGenre.objects.filter(song_id__in=song_ids).values_list(
        "song_id", "genre_id"
    ):
        genre_map[song_id].append(genre_id)
    for song_id, band_id in SongBand.objects.filter(song_id__in=song_ids).values_list(
        "song_id", "band_id"
    ):
        band_map[song_id].append(band_id)
    for song_id, artist_id in SongArtist.objects.filter(
        song_id__in=song_ids
    ).values_list("song_id", "artist_id"):
        artist_map[song_id].append(artist_id)

    genre_labels = _fetch_genre_labels(
        {genre_id for ids in genre_map.values() for genre_id in ids}
    )
    band_labels = _fetch_name_labels(
        "bands", "band_id", {band_id for ids in band_map.values() for band_id in ids}
    )
    artist_labels = _fetch_name_labels(
        "artists",
        "artist_id",
        {artist_id for ids in artist_map.values() for artist_id in ids},
    )
    return genre_map, band_map, artist_map, genre_labels, band_labels, artist_labels


def _build_result(song: Song, relation_maps) -> SongSearchResult:
    genre_map, band_map, artist_map, genre_labels, band_labels, artist_labels = (
        relation_maps
    )
    print_single_url = reverse(
        "song_text", args=[song.song_id, TEXT_MODE_SINGLE_CHORUS]
    )
    print_full_url = reverse("song_text", args=[song.song_id, TEXT_MODE_FULL_CHORUS])
    return SongSearchResult(
        song=song,
        is_favorite=bool(getattr(song, "is_favorite", False)),
        validation_label=_validation_label(song),
        genres=tuple(
            with_music_emoji(label)
            for label in (
                genre_labels.get(item) for item in genre_map.get(song.song_id, [])
            )
            if label
        ),
        genre_tags=tuple(
            SongReferenceTag(
                kind="genre",
                id=item,
                label=with_music_emoji(label),
            )
            for item in genre_map.get(song.song_id, [])
            for label in [genre_labels.get(item)]
            if label
        ),
        bands=tuple(
            with_band_emoji(label)
            for label in (
                band_labels.get(item) for item in band_map.get(song.song_id, [])
            )
            if label
        ),
        band_tags=tuple(
            SongReferenceTag(
                kind="band",
                id=item,
                label=with_band_emoji(label),
            )
            for item in band_map.get(song.song_id, [])
            for label in [band_labels.get(item)]
            if label
        ),
        artists=tuple(
            with_artist_emoji(label)
            for label in (
                artist_labels.get(item) for item in artist_map.get(song.song_id, [])
            )
            if label
        ),
        artist_tags=tuple(
            SongReferenceTag(
                kind="artist",
                id=item,
                label=with_artist_emoji(label),
            )
            for item in artist_map.get(song.song_id, [])
            for label in [artist_labels.get(item)]
            if label
        ),
        display_url=reverse("song", args=[song.song_id]),
        print_single_url=print_single_url,
        print_full_url=print_full_url,
        print_single_plain_url=f"{print_single_url}?format=plain",
        print_full_plain_url=f"{print_full_url}?format=plain",
    )


def _build_results_from_songs(
    songs: list[Song],
) -> tuple[SongSearchResult, ...]:
    song_ids = [song.song_id for song in songs]
    relation_maps = (
        _get_relation_maps(song_ids) if song_ids else ({}, {}, {}, {}, {}, {})
    )
    return tuple(_build_result(song, relation_maps) for song in songs)


def _build_song_catalog_search_row(row) -> SongCatalogSearchRow:
    search_count = int(row[7] or 0)
    catalog_count = int(row[8] or 0)
    is_favorite = bool(row[6])

    if row[0] is None:
        return SongCatalogSearchRow(
            song=None,
            is_favorite=is_favorite,
            search_count=search_count,
            catalog_count=catalog_count,
        )

    song = Song(
        song_id=int(row[0]),
        title=str(row[1] or ""),
        subtitle=str(row[2] or ""),
        description=row[3],
        status=int(row[4]),
        licensed=bool(row[5]),
    )
    song.is_favorite = is_favorite
    return SongCatalogSearchRow(
        song=song,
        is_favorite=is_favorite,
        search_count=search_count,
        catalog_count=catalog_count,
    )


def search_song_catalog_rows(
    params: SongSearchParams,
    *,
    is_authenticated: bool,
    member_id: str | None,
) -> tuple[SongCatalogSearchRow, ...]:
    normalized_member_id = None
    if member_id:
        try:
            normalized_member_id = uuid.UUID(str(member_id))
        except (TypeError, ValueError):
            normalized_member_id = None

    with connection.cursor() as cursor:
        cursor.execute(
            SEARCH_SONG_CATALOG_SQL,
            [
                bool(is_authenticated),
                normalized_member_id,
                params.text,
                params.everywhere,
                params.match_all_selected_refs,
                list(params.genre_ids),
                list(params.band_ids),
                list(params.artist_ids),
                params.validation,
                params.favorites_only,
            ],
        )
        return tuple(_build_song_catalog_search_row(row) for row in cursor.fetchall())


def search_songs(
    params: SongSearchParams,
    user,
    member_id: str | None,
) -> SongSearchResults:
    active_params = params if _is_authenticated(user) else params.for_guest()
    if not member_id:
        active_params = replace(active_params, favorites_only=False)

    sql_rows = search_song_catalog_rows(
        active_params,
        is_authenticated=_is_authenticated(user),
        member_id=member_id,
    )
    songs = [row.song for row in sql_rows if row.song is not None]
    results = _build_results_from_songs(songs)
    counts_row = sql_rows[0] if sql_rows else SongCatalogSearchRow(None, False, 0, 0)

    return SongSearchResults(
        params=active_params,
        results=results,
        displayed_count=len(results),
        search_count=counts_row.search_count,
        catalog_count=counts_row.catalog_count,
    )


def search_songs_to_moderate(user, member_id: str | None) -> SongSearchResults:
    accessible_songs = _base_accessible_songs(user)
    catalog_count = accessible_songs.count()
    filtered_songs = (
        accessible_songs.filter(status=SONG_STATUS_VALIDATED_WITH_CONCERN)
        .filter(messages__is_read=False)
        .annotate(
            latest_unread_message_date=Max(
                "messages__date",
                filter=Q(messages__is_read=False),
            )
        )
        .distinct()
    )
    search_count = filtered_songs.count()
    songs = list(
        _with_favorite_state(filtered_songs, member_id).order_by(
            "-latest_unread_message_date",
            "title",
            "subtitle",
        )
    )
    results = _build_results_from_songs(songs)

    return SongSearchResults(
        params=SongSearchParams.empty(),
        results=results,
        displayed_count=len(results),
        search_count=search_count,
        catalog_count=catalog_count,
    )


def get_reference_options() -> SongReferenceOptions:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT genre_id, "group", "name"
            FROM "common"."genres"
            ORDER BY "group", "name"
            """
        )
        genres = tuple(
            SongReferenceOption(
                id=row[0],
                group=row[1] or "",
                label=build_genre_display_label(row[1], row[2]),
            )
            for row in cursor.fetchall()
        )

        cursor.execute('SELECT band_id, "name" FROM "common"."bands" ORDER BY "name"')
        bands = tuple(
            SongReferenceOption(id=row[0], label=row[1]) for row in cursor.fetchall()
        )

        cursor.execute(
            'SELECT artist_id, "name" FROM "common"."artists" ORDER BY "name"'
        )
        artists = tuple(
            SongReferenceOption(id=row[0], label=row[1]) for row in cursor.fetchall()
        )

    return SongReferenceOptions(genres=genres, bands=bands, artists=artists)
