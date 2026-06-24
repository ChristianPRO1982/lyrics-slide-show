from types import SimpleNamespace

from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import MagicMock, patch
from django.db import IntegrityError, connection

from app_main.models import DirectoryUserRecord
from app_member.models import MemberPreferences, MemberRole

from .models import (
    Song,
    SongArtist,
    SongBand,
    SongFavorite,
    SongGenre,
    SongLink,
    SongStatus,
    Verse,
)
from . import views as song_views
from .genre_labels import (
    build_genre_display_label,
    normalize_genre_group_display_name,
)
from .rendering import (
    ChorusRenderMode,
    RenderedSongBlockKind,
    SongRenderSettings,
    build_song_full_title,
    build_song_full_title_with_tags,
    build_song_text_artifacts,
    render_song_popup_plain_text,
    render_song_blocks,
    render_song_text,
    _table_html_to_plain_text,
)
from .search import (
    SongSearchParams,
    _apply_filters,
    _apply_reference_filter,
    _fetch_name_labels,
    _get_relation_maps,
    _normalize_ids,
    _params_from_query,
    _validation_label,
    build_song_search_query,
    get_active_song_search,
    load_member_song_search,
    save_song_search,
    search_songs,
)


class AnonymousUser:
    is_authenticated = False


def make_song() -> Song:
    return Song(song_id=1, title="Gloire", subtitle="", status=0, licensed=False)


def make_verse(
    verse_id: int,
    num: int,
    text: str,
    *,
    num_verse: int = 1,
    chorus: bool = False,
    chorus_like: bool = False,
    followed: bool = False,
    notcontinuenumbering: bool = False,
    prefix: str = "",
) -> Verse:
    return Verse(
        verse_id=verse_id,
        num=num,
        num_verse=num_verse,
        chorus=chorus,
        chorus_like=chorus_like,
        followed=followed,
        notcontinuenumbering=notcontinuenumbering,
        text=text,
        prefix=prefix,
    )


class SongRenderingServiceTests(SimpleTestCase):
    settings = SongRenderSettings(
        chorus_prefix="Refrain",
        verse_prefix1="Couplet ",
        verse_prefix2="",
        chorus_like_default_prefix="Refrain",
    )

    def test_song_starting_with_chorus_renders_chorus_group_first(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Chante alleluia", chorus=True, num_verse=0),
                make_verse(2, 4, "Premier couplet", num_verse=1),
            ],
        )

        self.assertEqual(
            [block.kind for block in blocks],
            [
                RenderedSongBlockKind.CHORUS,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.CHORUS,
            ],
        )
        self.assertEqual(blocks[0].label, "Refrain")
        self.assertTrue(blocks[2].is_repeated_chorus)


class GenreDisplayLabelTests(SimpleTestCase):
    def test_normalize_genre_group_display_name_removes_numeric_prefix(self):
        self.assertEqual(
            normalize_genre_group_display_name("1 - Scoutisme"), "Scoutisme"
        )

    def test_normalize_genre_group_display_name_keeps_non_matching_value(self):
        self.assertEqual(
            normalize_genre_group_display_name("Chretien / KTO"), "Chretien / KTO"
        )

    def test_build_genre_display_label_uses_clean_group_name(self):
        self.assertEqual(
            build_genre_display_label("2 - Chretien / KTO", "Louange"),
            "Chretien / KTO / Louange",
        )


class SongMetadataLabelAssemblyTests(SimpleTestCase):
    @patch("app_song.views._fetch_name_labels", return_value={})
    @patch(
        "app_song.views._fetch_genre_labels",
        return_value={1: ("1 - Scoutisme", "Louange")},
    )
    @patch("app_song.views.SongArtist.objects.filter")
    @patch("app_song.views.SongBand.objects.filter")
    @patch("app_song.views.SongGenre.objects.filter")
    def test_get_song_metadata_labels_builds_grouped_genres_without_crashing(
        self,
        song_genre_filter,
        song_band_filter,
        song_artist_filter,
        _fetch_genre_labels,
        _fetch_name_labels,
    ):
        song_genre_filter.return_value.values_list.return_value = (1,)
        song_band_filter.return_value.values_list.return_value = ()
        song_artist_filter.return_value.values_list.return_value = ()

        bands, artists, genre_groups = song_views._get_song_metadata_labels(
            SimpleNamespace(song_id=1)
        )

        self.assertEqual(bands, ())
        self.assertEqual(artists, ())
        self.assertEqual(genre_groups[0][0], "Scoutisme")
        self.assertEqual(len(genre_groups[0][1]), 1)
        self.assertTrue(genre_groups[0][1][0].endswith("Louange"))


class SongRenderingMarkupTests(SimpleTestCase):
    settings = SongRenderSettings(
        chorus_prefix="Refrain",
        verse_prefix1="Couplet ",
        verse_prefix2="",
        chorus_like_default_prefix="Refrain",
    )

    def test_table_html_to_plain_text_removes_table_markup_and_decodes_entities(self):
        self.assertEqual(
            _table_html_to_plain_text(
                "<table><tbody><tr><th>Couplet 1</th><td>A &amp; B<br>C</td></tr>"
                "</tbody></table>"
            ),
            "Couplet 1 A & B\nC",
        )

    def test_empty_chorus_blocks_are_ignored(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet", num_verse=1),
            ],
        )
        self.assertEqual([block.text for block in blocks], ["Couplet"])

    def test_song_model_display_properties_cover_markers_subtitle_and_license(self):
        song = Song(
            title="Titre",
            subtitle="Sous-titre",
            status=SongStatus.VALIDATED,
            licensed=True,
        )
        self.assertEqual(str(song), "Titre - Sous-titre ✔️ ©")
        self.assertTrue(song.is_validated)
        self.assertEqual(song.validation_marker, "✔️")

        song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.assertEqual(song.validation_marker, "✔️⁉️")
        song.status = SongStatus.NOT_VALIDATED
        song.subtitle = ""
        song.licensed = False
        self.assertEqual(song.display_title, "Titre")

    def test_full_mode_repeats_chorus_after_each_eligible_verse(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1),
                make_verse(3, 6, "Couplet deux", num_verse=2),
            ],
        )

        self.assertEqual(
            [block.kind for block in blocks],
            [
                RenderedSongBlockKind.CHORUS,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.CHORUS,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.CHORUS,
            ],
        )

    def test_single_mode_renders_chorus_only_once(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.SINGLE,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1),
                make_verse(3, 6, "Couplet deux", num_verse=2),
            ],
        )

        self.assertEqual(
            [block.kind for block in blocks],
            [
                RenderedSongBlockKind.CHORUS,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.VERSE,
            ],
        )


class ModifySongBlockLabelTests(SimpleTestCase):
    settings = SongRenderSettings(
        chorus_prefix="Refrain",
        verse_prefix1="Couplet ",
        verse_prefix2="",
        chorus_like_default_prefix="Refrain",
    )

    def test_not_c_num_hides_modify_song_display_and_drag_labels(self):
        block = song_views.ParsedSongBlock(
            row_key="a",
            block_id=1,
            position=2,
            block_type="verse",
            text="Suite du couplet",
            prefix="",
            followed=False,
            not_c_num=True,
            chorus=False,
            chorus_like=False,
            num=2,
            display_num=3,
            delete=False,
        )

        self.assertEqual(
            song_views._build_block_display_label(block, self.settings), ""
        )
        self.assertEqual(song_views._build_block_drag_label(block, self.settings), "")

    def test_chorus_like_without_prefix_hides_modify_song_display_and_drag_labels(self):
        block = song_views.ParsedSongBlock(
            row_key="b",
            block_id=2,
            position=4,
            block_type="special",
            text="Pont final",
            prefix="",
            followed=False,
            not_c_num=True,
            chorus=False,
            chorus_like=True,
            num=4,
            display_num=3,
            delete=False,
        )

        self.assertEqual(
            song_views._build_block_display_label(block, self.settings), ""
        )
        self.assertEqual(song_views._build_block_drag_label(block, self.settings), "")

    def test_chorus_like_with_prefix_keeps_prefix_for_modify_song_labels(self):
        block = song_views.ParsedSongBlock(
            row_key="c",
            block_id=3,
            position=6,
            block_type="special",
            text="Pont final",
            prefix="Pont",
            followed=False,
            not_c_num=True,
            chorus=False,
            chorus_like=True,
            num=6,
            display_num=3,
            delete=False,
        )

        self.assertEqual(
            song_views._build_block_display_label(block, self.settings), "Pont"
        )
        self.assertEqual(
            song_views._build_block_drag_label(block, self.settings), "Pont"
        )

    def test_followed_skips_next_chorus_insertion_point(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1, followed=True),
                make_verse(3, 6, "Couplet deux", num_verse=2),
            ],
        )

        self.assertEqual(
            [block.kind for block in blocks],
            [
                RenderedSongBlockKind.CHORUS,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.VERSE,
                RenderedSongBlockKind.CHORUS,
            ],
        )

    def test_song_with_only_choruses_still_renders_chorus_group(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain A", chorus=True, num_verse=0),
                make_verse(2, 4, "Refrain B", chorus=True, num_verse=0),
            ],
        )

        self.assertEqual([block.text for block in blocks], ["Refrain A", "Refrain B"])
        self.assertEqual(blocks[0].label, "Refrain")
        self.assertEqual(blocks[1].label, "")

    def test_chorus_like_block_uses_prefix_without_joining_repeated_choruses(self):
        blocks = render_song_blocks(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(
                    2, 4, "Pont final", num_verse=1, chorus_like=True, prefix="Pont"
                ),
            ],
        )

        self.assertEqual(blocks[1].kind, RenderedSongBlockKind.CHORUS_LIKE)
        self.assertEqual(blocks[1].label, "Pont")
        self.assertEqual(blocks[2].kind, RenderedSongBlockKind.CHORUS)

    def test_not_continue_numbering_removes_visible_verse_label(self):
        text = render_song_text(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            verses=[
                make_verse(
                    1, 2, "Suite du couplet", num_verse=1, notcontinuenumbering=True
                ),
            ],
        )

        self.assertIn("Suite du couplet", text)
        self.assertNotIn("Couplet 1", text)

    def test_popup_plain_text_puts_chorus_like_prefix_on_its_own_line(self):
        text = render_song_popup_plain_text(
            make_song(),
            ChorusRenderMode.SINGLE,
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(
                    2, 4, "Pont final", num_verse=1, chorus_like=True, prefix="Pont"
                ),
                make_verse(
                    3, 6, "Sans préfixe", num_verse=2, chorus_like=True, prefix=""
                ),
            ],
        )

        self.assertEqual(text, "Refrain Refrain\n\nPont\nPont final\n\nSans préfixe\n")


class SongSearchParamsTests(SimpleTestCase):
    def test_normalize_ids_handles_none_and_scalar_values(self):
        self.assertEqual(_normalize_ids(None), ())
        self.assertEqual(_normalize_ids(7), (7,))

    def test_guest_search_ignores_advanced_filters(self):
        request = RequestFactory().get(
            "/songs/",
            {
                "text": "été",
                "everywhere": "1",
                "validation": "validated_only",
                "favorites_only": "1",
                "genre_ids": ["1", "2"],
            },
        )
        request.user = AnonymousUser()

        params = get_active_song_search(request, member_id=None)

        self.assertEqual(params, SongSearchParams(text="été"))

    def test_params_from_query_supports_aliases_and_invalid_validation(self):
        query = QueryDict("", mutable=True)
        query["q"] = " ete "
        query["extended"] = "yes"
        query["search_logic"] = "and"
        query["validation"] = "unsupported"
        query["favorites_only"] = "on"
        query.setlist("genre_ids", ["1,2", "3"])
        query.setlist("band_ids", ["4"])
        query.setlist("artist_ids", ["5,nope"])

        params = _params_from_query(query)

        self.assertEqual(
            params,
            SongSearchParams(
                text="ete",
                everywhere=True,
                match_all_selected_refs=True,
                genre_ids=(1, 2, 3),
                band_ids=(4,),
                artist_ids=(5,),
                validation="all",
                favorites_only=True,
            ),
        )

    def test_params_from_mapping_normalizes_invalid_values(self):
        params = SongSearchParams.from_mapping(
            {
                "text": " paix ",
                "everywhere": True,
                "match_all_selected_refs": True,
                "genre_ids": [3, "bad", "5"],
                "band_ids": "7,not-a-number,9",
                "artist_ids": [],
                "validation": "unknown",
                "favorites_only": True,
            }
        )

        self.assertEqual(params.text, "paix")
        self.assertTrue(params.everywhere)
        self.assertEqual(params.genre_ids, (3, 5))
        self.assertEqual(params.band_ids, (7, 9))
        self.assertEqual(params.validation, "all")

    def test_validation_label_covers_validated_states(self):
        validated = Song(
            song_id=1,
            title="Validé",
            subtitle="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        with_concern = Song(
            song_id=2,
            title="Avec message",
            subtitle="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        free = Song(
            song_id=3,
            title="Libre",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )

        self.assertEqual(_validation_label(validated), "Chant validé")
        self.assertEqual(
            _validation_label(with_concern), "Chant validé avec des messages"
        )
        self.assertEqual(_validation_label(free), "Chant non validé")

    def test_build_search_query_serializes_multi_value_filters(self):
        query = build_song_search_query(
            SongSearchParams(
                text="gloire",
                everywhere=True,
                match_all_selected_refs=True,
                genre_ids=(1, 2),
                band_ids=(4,),
                artist_ids=(9,),
                validation="validated_only",
                favorites_only=True,
            ),
            favorites_only=False,
        )

        self.assertIn("text=gloire", query)
        self.assertIn("everywhere=1", query)
        self.assertIn("match_all_selected_refs=1", query)
        self.assertIn("genre_ids=1", query)
        self.assertIn("genre_ids=2", query)
        self.assertIn("band_ids=4", query)
        self.assertIn("artist_ids=9", query)
        self.assertIn("validation=validated_only", query)
        self.assertIn("favorites_only=0", query)

    def test_build_search_query_keeps_enabled_favorites_flag(self):
        query = build_song_search_query(SongSearchParams(favorites_only=True))

        self.assertEqual(query, "favorites_only=1")


class SongSearchPersistenceTests(TestCase):
    member_id = "88888888-8888-8888-8888-888888888888"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.member_id,
            username="search.persistence.user",
            first_name="Search",
            last_name="Persistence",
            email="search.persistence.user@example.test",
            enabled=True,
            email_verified=False,
        )

    def test_load_member_song_search_returns_empty_for_missing_invalid_and_errors(self):
        self.assertEqual(load_member_song_search(None), SongSearchParams.empty())
        self.assertEqual(
            load_member_song_search("not-a-uuid"), SongSearchParams.empty()
        )
        with patch(
            "app_song.search.MemberPreferences.objects.filter",
            side_effect=RuntimeError("db down"),
        ):
            self.assertEqual(
                load_member_song_search(self.member_id), SongSearchParams.empty()
            )

    def test_save_song_search_ignores_missing_and_invalid_member_id(self):
        params = SongSearchParams(text="ignored", favorites_only=True)

        save_song_search(None, params)
        save_song_search("not-a-uuid", params)

        self.assertEqual(MemberPreferences.objects.count(), 0)

    def test_get_active_song_search_reset_saves_empty_preferences_for_member(self):
        MemberPreferences.objects.create(
            member_id=self.member_id,
            song_search=SongSearchParams(
                text="ancien", favorites_only=True
            ).to_preferences(),
        )
        request = RequestFactory().get("/songs/", {"reset_search": "1"})
        request.user = SimpleNamespace(is_authenticated=True)

        params = get_active_song_search(request, member_id=self.member_id)

        self.assertEqual(params, SongSearchParams.empty())
        preferences = MemberPreferences.objects.get(member_id=self.member_id)
        self.assertEqual(
            preferences.song_search, SongSearchParams.empty().to_preferences()
        )

    def test_get_active_song_search_query_saves_authenticated_filters(self):
        request = RequestFactory().get(
            "/songs/",
            {
                "q": "louange",
                "extended": "1",
                "search_logic": "and",
                "genre_ids": ["2,3"],
                "validation": "non_validated_only",
                "favorites_only": "true",
            },
        )
        request.user = SimpleNamespace(is_authenticated=True)

        params = get_active_song_search(request, member_id=self.member_id)

        self.assertEqual(
            params,
            SongSearchParams(
                text="louange",
                everywhere=True,
                match_all_selected_refs=True,
                genre_ids=(2, 3),
                validation="non_validated_only",
                favorites_only=True,
            ),
        )
        preferences = MemberPreferences.objects.get(member_id=self.member_id)
        self.assertEqual(preferences.song_search, params.to_preferences())


class SongSearchFilteringCoverageTests(TestCase):
    member_id = "99999999-9999-9999-9999-999999999999"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.member_id,
            username="search.filter.user",
            first_name="Search",
            last_name="Filter",
            email="search.filter.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song_title = Song.objects.create(
            title="Titre simple",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.song_description = Song.objects.create(
            title="Description",
            subtitle="",
            description="Un été de lumière",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        self.song_verse = Song.objects.create(
            title="Couplet",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        self.song_both_refs = Song.objects.create(
            title="Double liens",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.song_one_ref = Song.objects.create(
            title="Référence unique",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(
            song=self.song_verse,
            num=2,
            num_verse=1,
            chorus=False,
            text="Encore la lumière revient",
        )

        SongFavorite.objects.create(
            song=self.song_description, member_id=self.member_id
        )

        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Test", "Genre A"],
            )
            self.genre_a_id = cursor.fetchone()[0]
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Test", "Genre B"],
            )
            self.genre_b_id = cursor.fetchone()[0]

        SongGenre.objects.create(song=self.song_both_refs, genre_id=self.genre_a_id)
        SongGenre.objects.create(song=self.song_both_refs, genre_id=self.genre_b_id)
        SongGenre.objects.create(song=self.song_one_ref, genre_id=self.genre_a_id)

        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."bands" ("name") VALUES (%s) RETURNING band_id',
                ["Les Testeurs"],
            )
            self.band_id = cursor.fetchone()[0]
            cursor.execute(
                'INSERT INTO "common"."artists" ("name") VALUES (%s) RETURNING artist_id',
                ["Artiste Test"],
            )
            self.artist_id = cursor.fetchone()[0]

        SongBand.objects.create(song=self.song_both_refs, band_id=self.band_id)
        SongArtist.objects.create(song=self.song_both_refs, artist_id=self.artist_id)

    def test_search_songs_everywhere_matches_description_and_verse_text(self):
        results = search_songs(
            SongSearchParams(text="lumiere", everywhere=True),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(
            [item.song.title for item in results.results],
            ["Couplet", "Description"],
        )

    def test_apply_reference_filter_supports_passthrough_any_and_all(self):
        queryset = Song.objects.filter(
            song_id__in=[self.song_both_refs.song_id, self.song_one_ref.song_id]
        )

        self.assertCountEqual(
            list(
                _apply_reference_filter(
                    queryset,
                    "genre_relations",
                    "genre_id",
                    (),
                    match_all=False,
                ).values_list("song_id", flat=True)
            ),
            [self.song_both_refs.song_id, self.song_one_ref.song_id],
        )
        self.assertCountEqual(
            list(
                _apply_reference_filter(
                    queryset,
                    "genre_relations",
                    "genre_id",
                    (self.genre_a_id, self.genre_b_id),
                    match_all=False,
                ).values_list("song_id", flat=True)
            ),
            [
                self.song_both_refs.song_id,
                self.song_both_refs.song_id,
                self.song_one_ref.song_id,
            ],
        )
        self.assertEqual(
            list(
                _apply_reference_filter(
                    queryset,
                    "genre_relations",
                    "genre_id",
                    (self.genre_a_id, self.genre_b_id),
                    match_all=True,
                ).values_list("song_id", flat=True)
            ),
            [self.song_both_refs.song_id],
        )

    def test_apply_filters_handles_validation_and_favorites(self):
        queryset = Song.objects.filter(
            song_id__in=[
                self.song_title.song_id,
                self.song_description.song_id,
                self.song_verse.song_id,
            ]
        )

        self.assertCountEqual(
            list(
                _apply_filters(
                    queryset,
                    SongSearchParams(validation="validated_only"),
                    member_id=self.member_id,
                ).values_list("song_id", flat=True)
            ),
            [self.song_description.song_id, self.song_verse.song_id],
        )
        self.assertEqual(
            list(
                _apply_filters(
                    queryset,
                    SongSearchParams(validation="non_validated_only"),
                    member_id=self.member_id,
                ).values_list("song_id", flat=True)
            ),
            [self.song_title.song_id],
        )
        self.assertEqual(
            list(
                _apply_filters(
                    queryset,
                    SongSearchParams(favorites_only=True),
                    member_id=self.member_id,
                ).values_list("song_id", flat=True)
            ),
            [self.song_description.song_id],
        )

    def test_fetch_name_labels_and_relation_maps_cover_band_and_artist_paths(self):
        self.assertEqual(_fetch_name_labels("bands", "band_id", set()), {})
        self.assertEqual(
            _fetch_name_labels("bands", "band_id", {self.band_id}),
            {self.band_id: "Les Testeurs"},
        )
        self.assertEqual(
            _fetch_name_labels("artists", "artist_id", {self.artist_id}),
            {self.artist_id: "Artiste Test"},
        )

        _genre_map, band_map, artist_map, _genres, _bands, _artists = (
            _get_relation_maps([self.song_both_refs.song_id])
        )

        self.assertEqual(band_map[self.song_both_refs.song_id], [self.band_id])
        self.assertEqual(artist_map[self.song_both_refs.song_id], [self.artist_id])

    def test_search_songs_without_matches_uses_empty_relation_maps_path(self):
        results = search_songs(
            SongSearchParams(text="introuvable"),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(results.displayed_count, 0)
        self.assertEqual(results.search_count, 0)


class SongTextArtifactsTests(SimpleTestCase):
    settings = SongRenderSettings(
        chorus_prefix="Refrain",
        verse_prefix1="",
        verse_prefix2=".",
        chorus_like_default_prefix="Refrain",
    )

    def test_full_title_and_title_with_tags(self):
        song = Song(
            song_id=1, title="Gloire", subtitle="Louange", status=0, licensed=False
        )
        self.assertEqual(build_song_full_title(song), "Gloire - Louange")
        self.assertEqual(build_song_full_title_with_tags(song), "Gloire - Louange")

        song.status = 1
        self.assertEqual(build_song_full_title_with_tags(song), "Gloire - Louange ✔️")

        song.status = 2
        song.licensed = True
        self.assertEqual(
            build_song_full_title_with_tags(song), "Gloire - Louange ✔️⁉️ 📄"
        )

    def test_full_title_without_subtitle_omits_separator(self):
        song = Song(song_id=1, title="Gloire", subtitle="", status=0, licensed=False)
        self.assertEqual(build_song_full_title(song), "Gloire")

    def test_short_and_long_html_modes_follow_chorus_policy(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1),
                make_verse(3, 6, "Couplet deux", num_verse=2),
            ],
        )
        self.assertIn('<table class="song-lyrics-table">', artifacts.short_text_html)
        self.assertEqual(
            artifacts.short_text_html.count(
                '<th scope="row">Refrain</th><td>Refrain</td>'
            ),
            1,
        )
        self.assertEqual(
            artifacts.long_text_html.count(
                '<th scope="row">Refrain</th><td>Refrain</td>'
            ),
            3,
        )

    def test_followed_skips_chorus_reinsertion(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1, followed=True),
            ],
        )
        self.assertEqual(
            artifacts.long_text_html.count(
                '<th scope="row">Refrain</th><td>Refrain</td>'
            ),
            1,
        )

    def test_empty_non_chorus_block_still_triggers_chorus_reinsertion(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "", num_verse=1, chorus=False, followed=False),
                make_verse(3, 6, "Couplet deux", num_verse=2),
            ],
        )
        self.assertEqual(
            artifacts.long_text_html.count(
                '<th scope="row">Refrain</th><td>Refrain</td>'
            ),
            3,
        )

    def test_chorus_like_uses_optional_prefix_and_bold(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[make_verse(1, 2, "Pont final", chorus_like=True, prefix="Pont")],
        )
        self.assertIn(
            '<th scope="row">Pont</th><td>Pont final</td>', artifacts.long_text_html
        )

        artifacts_no_prefix = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[make_verse(1, 2, "Pont final", chorus_like=True, prefix="")],
        )
        self.assertIn(
            '<th scope="row"></th><td>Pont final</td>',
            artifacts_no_prefix.long_text_html,
        )

    def test_not_continue_numbering_hides_verse_label(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=SongRenderSettings(
                chorus_prefix="Refrain",
                verse_prefix1="Couplet ",
                verse_prefix2="",
                chorus_like_default_prefix="Refrain",
            ),
            verses=[
                make_verse(
                    1, 2, "Suite du couplet", num_verse=1, notcontinuenumbering=True
                )
            ],
        )
        self.assertIn("Suite du couplet", artifacts.long_text_html)
        self.assertIn(
            '<th scope="row"></th><td>Suite du couplet</td>', artifacts.long_text_html
        )

    def test_chorus_multi_blocks_are_joined_with_single_line_break(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Ligne A", chorus=True, num_verse=0),
                make_verse(2, 4, "Ligne B", chorus=True, num_verse=0),
            ],
        )
        self.assertIn(
            '<th scope="row">Refrain</th><td>Ligne A<br>Ligne B</td>',
            artifacts.long_text_html,
        )

    def test_render_song_text_joins_multi_block_chorus_with_single_newline(self):
        text = render_song_text(
            make_song(),
            ChorusRenderMode.FULL,
            settings=self.settings,
            include_title=False,
            verses=[
                make_verse(1, 2, "Ligne A", chorus=True, num_verse=0),
                make_verse(2, 4, "Ligne B", chorus=True, num_verse=0),
            ],
        )
        self.assertEqual(text, "Refrain Ligne A\nLigne B\n")

    def test_html_output_escapes_dynamic_values(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "<script>alert(1)</script>", chorus=True, num_verse=0),
                make_verse(2, 4, "<em>Texte</em>", chorus_like=True, prefix="<tag>"),
            ],
        )
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", artifacts.long_text_html)
        self.assertIn("&lt;tag&gt;", artifacts.long_text_html)
        self.assertIn("&lt;em&gt;Texte&lt;/em&gt;", artifacts.long_text_html)
        self.assertNotIn("<script>", artifacts.long_text_html)


class SongViewsRenderingTests(TestCase):
    def setUp(self):
        self.user_id = "99999999-9999-9999-9999-999999999999"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="lyrics.reader",
            first_name="Lyrics",
            last_name="Reader",
            email="lyrics.reader@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Le Sud",
            subtitle="Nino Ferrer",
            description="Description",
            status=1,
            licensed=True,
        )
        Verse.objects.create(
            song=self.song,
            num=2,
            num_verse=0,
            chorus=True,
            text="On dirait le Sud",
        )
        Verse.objects.create(
            song=self.song,
            num=4,
            num_verse=1,
            chorus=False,
            text="C'est un endroit",
            followed=False,
        )

    def _insert_genre(self, group: str, name: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") '
                "VALUES (%s, %s) RETURNING genre_id",
                [group, name],
            )
            return cursor.fetchone()[0]

    def _login(self) -> None:
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "lyrics.reader",
            "email": "lyrics.reader@example.test",
            "first_name": "Lyrics",
            "last_name": "Reader",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_song_view_provides_tagged_navigation_title_and_text_without_title_duplication(
        self,
    ):
        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title_complete"], "Le Sud - Nino Ferrer")
        self.assertEqual(
            response.context["title_complete_with_tags"], "Le Sud - Nino Ferrer ✔️ 📄"
        )
        self.assertNotIn("Le Sud - Nino Ferrer", response.context["text_long_html"])

    def test_song_view_exposes_plain_copy_buttons_in_tools_and_mobile(self):
        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "<p>copier le texte sans mise en forme</p>",
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            "data-song-plain-copy-trigger",
            count=4,
        )
        self.assertContains(
            response,
            f'data-plain-url="{reverse("song_text", args=[self.song.song_id, "single-chorus"])}?format=plain&amp;layout=popup-copy"',
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            f'data-plain-url="{reverse("song_text", args=[self.song.song_id, "full-chorus"])}?format=plain&amp;layout=popup-copy"',
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            'data-popup-label="un seul refrain"',
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            'data-popup-label="toutes les répétitions de refrain"',
            count=2,
            html=False,
        )

    def test_song_view_hides_numeric_prefix_from_genre_group_heading(self):
        genre_id = self._insert_genre("1 - Scoutisme", "Louange")
        SongGenre.objects.create(song=self.song, genre_id=genre_id)

        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<h4 class="song-tag-group">Scoutisme</h4>', html=False
        )
        self.assertNotContains(response, "1 - Scoutisme")
        self.assertEqual(response.context["genre_groups"][0][0], "Scoutisme")
        self.assertEqual(len(response.context["genre_groups"][0][1]), 1)
        self.assertTrue(response.context["genre_groups"][0][1][0].endswith("Louange"))

    def test_song_text_print_page_uses_full_title_without_tags(self):
        self._login()
        response = self.client.get(
            reverse("song_text", args=[self.song.song_id, "full-chorus"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title_complete"], "Le Sud - Nino Ferrer")
        self.assertContains(response, "<title>Le Sud - Nino Ferrer</title>", html=True)
        self.assertContains(
            response,
            '<th scope="row">Refrain</th><td>On dirait le Sud</td>',
            html=False,
        )

    def test_song_text_plain_endpoint_returns_plain_text_blocks(self):
        self._login()
        response = self.client.get(
            reverse("song_text", args=[self.song.song_id, "single-chorus"])
            + "?format=plain"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("text/plain"))
        body = response.content.decode("utf-8")
        self.assertEqual(
            body, "Refrain On dirait le Sud\n\nCouplet 1 C'est un endroit\n"
        )
        self.assertNotIn("<th", body)
        self.assertNotIn("<td", body)
        self.assertNotIn("Le Sud - Nino Ferrer", body)

    def test_song_text_popup_copy_layout_puts_chorus_like_prefix_on_separate_line(self):
        Verse.objects.create(
            song=self.song,
            num=6,
            num_verse=2,
            chorus_like=True,
            prefix="Pont",
            text="Pont final",
        )
        self._login()
        response = self.client.get(
            reverse("song_text", args=[self.song.song_id, "full-chorus"])
            + "?format=plain&layout=popup-copy"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("text/plain"))
        body = response.content.decode("utf-8")
        self.assertIn("\n\nPont\nPont final\n", body)
        self.assertNotIn("\n\nPont Pont final\n", body)

    def test_song_text_popup_endpoint_returns_full_chorus_markdown(self):
        self._login()
        response = self.client.get(reverse("song_text_popup", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("title", payload)
        self.assertIn("markdown", payload)
        self.assertIn("Refrain", payload["markdown"])

    @patch("app_song.views._can_read_song", return_value=False)
    def test_song_text_popup_endpoint_refuses_unreadable_song(self, _can_read_song):
        response = self.client.get(reverse("song_text_popup", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 404)


class SongFavoriteActionsTests(TestCase):
    def setUp(self):
        self.user_id = "55555555-5555-5555-5555-555555555555"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="favorite.user",
            first_name="Favorite",
            last_name="User",
            email="favorite.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Favori",
            subtitle="Test",
            description="Description",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "favorite.user",
            "email": "favorite.user@example.test",
            "first_name": "Favorite",
            "last_name": "User",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def _assert_shared_song_actions(self, response, *, active_page: str) -> None:
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "☆ Pas encore favori")
        self.assertContains(response, "data-song-delete-form")
        self.assertContains(response, 'name="action" value="delete_song"', html=False)
        self.assertContains(
            response, 'name="song_id" value="{}"'.format(self.song.song_id), html=False
        )
        self.assertNotContains(response, "song-actions-list")

        html = response.content.decode("utf-8")
        self.assertLess(html.find("☆ Pas encore favori"), html.find("Supprimer"))
        if active_page != "song":
            self.assertIn(
                'href="{}"'.format(reverse("song", args=[self.song.song_id])), html
            )
        if active_page != "modify_song":
            self.assertIn(
                'href="{}"'.format(reverse("modify_song", args=[self.song.song_id])),
                html,
            )
        if active_page != "song_metadata":
            self.assertIn(
                'href="{}"'.format(reverse("song_metadata", args=[self.song.song_id])),
                html,
            )

    def test_song_toggle_creates_and_deletes_favorite(self):
        self._login()

        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "toggle_favorite"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("song", args=[self.song.song_id])
        )
        self.assertTrue(
            SongFavorite.objects.filter(
                song_id=self.song.song_id, member_id=self.user_id
            ).exists()
        )

        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "toggle_favorite"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("song", args=[self.song.song_id])
        )
        self.assertFalse(
            SongFavorite.objects.filter(
                song_id=self.song.song_id, member_id=self.user_id
            ).exists()
        )

    def test_toggle_requires_authenticated_user(self):
        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "toggle_favorite"},
        )
        self.assertEqual(response.status_code, 404)

    def test_modify_song_toggle_works_without_edit_rights(self):
        self._login()
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "toggle_favorite"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_song", args=[self.song.song_id]),
        )
        self.assertTrue(
            SongFavorite.objects.filter(
                song_id=self.song.song_id, member_id=self.user_id
            ).exists()
        )

    def test_song_metadata_toggle_works_without_edit_rights(self):
        self._login()
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])

        response = self.client.post(
            reverse("song_metadata", args=[self.song.song_id]),
            data={"action": "toggle_favorite"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("song_metadata", args=[self.song.song_id]),
        )
        self.assertTrue(
            SongFavorite.objects.filter(
                song_id=self.song.song_id, member_id=self.user_id
            ).exists()
        )

    def test_actions_show_toggle_on_all_song_pages_when_authenticated(self):
        self._login()

        song_response = self.client.get(reverse("song", args=[self.song.song_id]))
        self._assert_shared_song_actions(song_response, active_page="song")

        modify_response = self.client.get(
            reverse("modify_song", args=[self.song.song_id])
        )
        self._assert_shared_song_actions(modify_response, active_page="modify_song")

        metadata_response = self.client.get(
            reverse("song_metadata", args=[self.song.song_id])
        )
        self._assert_shared_song_actions(metadata_response, active_page="song_metadata")

    def test_validated_song_page_keeps_toggle_for_member_without_edit_rights(self):
        self._login()
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])

        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "☆ Pas encore favori")
        self.assertNotContains(response, "data-song-delete-form")
        self.assertNotContains(
            response,
            'href="{}"'.format(reverse("modify_song", args=[self.song.song_id])),
            html=False,
        )
        self.assertNotContains(
            response,
            'href="{}"'.format(reverse("song_metadata", args=[self.song.song_id])),
            html=False,
        )

    def test_song_metadata_delete_song_uses_shared_action(self):
        self._login()

        response = self.client.post(
            reverse("song_metadata", args=[self.song.song_id]),
            data={"action": "delete_song", "song_id": self.song.song_id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("songs"))
        self.assertFalse(Song.objects.filter(song_id=self.song.song_id).exists())

    def test_song_view_hides_toggle_for_guest(self):
        response = self.client.get(reverse("song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "☆ Pas encore favori")
        self.assertNotContains(response, "⭐ Favori")
        self.assertNotContains(response, "data-song-delete-form")


class ModifySongViewTests(TestCase):
    def setUp(self):
        self.user_id = "11111111-1111-1111-1111-111111111111"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="known.user",
            first_name="Known",
            last_name="User",
            email="known.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Chant",
            subtitle="Base",
            description="Description",
            status=0,
            licensed=False,
        )
        self.verse_1 = Verse.objects.create(
            song=self.song,
            num=2,
            num_verse=1,
            chorus=False,
            text="Couplet original",
        )
        self.verse_2 = Verse.objects.create(
            song=self.song,
            num=4,
            num_verse=0,
            chorus=True,
            text="Refrain original",
        )

    def _login(self, *, is_moderator=False, is_admin=False):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "known.user",
            "email": "known.user@example.test",
            "first_name": "Known",
            "last_name": "User",
            "is_moderator": is_moderator,
            "is_admin": is_admin,
        }
        session.save()
        MemberRole.objects.filter(member_id=self.user_id).delete()
        if is_moderator or is_admin:
            MemberRole.objects.create(
                member_id=self.user_id,
                is_moderator=is_moderator,
                is_admin=is_admin,
            )

    def _base_payload(self):
        return {
            "title": " Nouveau : titre ? ",
            "subtitle": " Sous titre ",
            "description": " Ligne 1 ;\\n\\n Ligne 2 ! ",
            "blocks[a][id]": str(self.verse_1.verse_id),
            "blocks[a][position]": "4",
            "blocks[a][type]": "verse",
            "blocks[a][text]": "  Couplet 1  !",
            "blocks[a][prefix]": "",
            "blocks[a][followed]": "0",
            "blocks[a][not_c_num]": "0",
            "blocks[a][delete]": "0",
            "blocks[b][id]": str(self.verse_2.verse_id),
            "blocks[b][position]": "2",
            "blocks[b][type]": "chorus",
            "blocks[b][text]": " Refrain : test ",
            "blocks[b][prefix]": "",
            "blocks[b][followed]": "0",
            "blocks[b][not_c_num]": "0",
            "blocks[b][delete]": "0",
            "blocks[c][id]": "",
            "blocks[c][position]": "6",
            "blocks[c][type]": "special",
            "blocks[c][text]": " Pont final ",
            "blocks[c][prefix]": "Pont final ;",
            "blocks[c][followed]": "1",
            "blocks[c][not_c_num]": "1",
            "blocks[c][delete]": "0",
            "submit_intent": "save",
        }

    def test_guest_cannot_access_modify_page(self):
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 404)

    def test_member_can_access_unvalidated_song(self):
        self._login()
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-reorder-list")
        self.assertContains(response, "data-reorder-drag-view hidden")
        self.assertContains(response, "data-reorder-normal-view")
        self.assertNotContains(response, "song-block-readonly-compact")
        self.assertContains(
            response,
            "data-song-block-drag-label>Couplet 1</strong>",
            html=False,
        )
        self.assertContains(
            response,
            "data-song-block-drag-label>Refrain</strong>",
            html=False,
        )
        self.assertContains(
            response,
            "data-song-block-drag-text>Couplet original</span>",
            html=False,
        )
        self.assertContains(
            response,
            "data-song-block-drag-text>Refrain original</span>",
            html=False,
        )
        self.assertContains(response, "Ajouter un couplet/refrain")
        self.assertContains(response, "data-song-add-block-action")
        self.assertContains(response, "data-song-block-delete-action")
        self.assertContains(response, "data-song-block-editor")
        self.assertContains(response, "data-song-block-read-view")
        self.assertContains(response, "data-song-block-edit-view")
        self.assertContains(
            response, "data-song-block-edit-view data-song-block-editor hidden"
        )
        self.assertContains(response, "data-song-block-open-text")
        self.assertContains(response, "data-song-block-open-prefix")
        self.assertNotContains(response, "Couplet (sans numérotation)")
        self.assertNotContains(response, "Section spéciale")

    def test_member_can_access_validated_song_read_only(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login()
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "☆ Pas encore favori")
        self.assertNotContains(response, "data-song-delete-form")
        self.assertNotContains(response, "Ajouter un couplet/refrain")
        self.assertNotContains(response, "data-song-add-block-action")
        self.assertNotContains(response, "data-song-block-delete-action")
        self.assertNotContains(response, "data-song-block-editor")
        self.assertContains(response, "data-song-block-read-view")
        self.assertNotContains(response, "data-song-block-edit-view")

    def test_moderator_can_access_validated_song_read_only(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ajouter un couplet/refrain")
        self.assertContains(response, "data-song-add-block-action")
        self.assertContains(response, "data-song-block-delete-action")
        self.assertContains(response, "data-song-block-editor")
        self.assertContains(response, "data-song-block-read-view")
        self.assertContains(response, "data-song-block-edit-view")

    def test_member_cannot_post_validated_song(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login()
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=self._base_payload()
        )
        self.assertEqual(response.status_code, 404)

    def test_moderator_can_post_validated_song(self):
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=self._base_payload()
        )
        self.assertEqual(response.status_code, 302)

    def test_member_cannot_devalidate_song(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login()
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "devalidate_song"},
        )
        self.assertEqual(response.status_code, 404)

    def test_moderator_can_devalidate_song_status_only(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "devalidate_song"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_song", args=[self.song.song_id]),
        )

        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.NOT_VALIDATED)
        self.assertEqual(self.song.title, "Chant")
        self.assertEqual(self.song.subtitle, "Base")
        self.assertEqual(self.song.description, "Description")

    def test_post_save_updates_identity_and_verses(self):
        self._login()
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=self._base_payload()
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_song", args=[self.song.song_id]),
        )

        self.song.refresh_from_db()
        self.assertEqual(self.song.title, "Nouveau\u00a0: titre\u00a0?")
        self.assertEqual(self.song.subtitle, "Sous titre")
        self.assertEqual(self.song.description, "Ligne 1\u00a0;\n\nLigne 2\u00a0!")

        verses = list(self.song.verses.all().order_by("num", "verse_id"))
        self.assertEqual(len(verses), 3)
        self.assertTrue(verses[0].chorus)
        self.assertEqual(verses[0].num, 2)
        self.assertEqual(verses[0].num_verse, 0)
        self.assertFalse(verses[1].chorus)
        self.assertEqual(verses[1].num, 4)
        self.assertEqual(verses[1].num_verse, 1)
        self.assertTrue(verses[2].chorus_like)
        self.assertTrue(verses[2].followed)
        self.assertEqual(verses[2].num, 6)
        self.assertEqual(verses[2].num_verse, 1)
        self.assertEqual(verses[2].prefix, "Pont final\u00a0;")

    def test_chorus_save_resets_incompatible_options_and_prefix_to_null(self):
        self._login()
        payload = self._base_payload()
        payload["blocks[b][type]"] = "chorus"
        payload["blocks[b][prefix]"] = "Prefix should be removed"
        payload["blocks[b][followed]"] = "1"
        payload["blocks[b][not_c_num]"] = "1"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)

        chorus_block = Verse.objects.get(song=self.song, chorus=True)
        self.assertFalse(chorus_block.chorus_like)
        self.assertFalse(chorus_block.followed)
        self.assertFalse(chorus_block.notcontinuenumbering)
        self.assertIsNone(chorus_block.prefix)

    def test_chorus_like_forces_not_continue_numbering(self):
        self._login()
        payload = self._base_payload()
        payload["blocks[c][type]"] = "special"
        payload["blocks[c][not_c_num]"] = "0"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)

        chorus_like_block = Verse.objects.get(song=self.song, chorus_like=True)
        self.assertTrue(chorus_like_block.notcontinuenumbering)

    def test_chorus_like_modify_editor_shows_not_c_num_checked_and_disabled(self):
        self._login()
        Verse.objects.create(
            song=self.song,
            num=6,
            num_verse=1,
            chorus=False,
            chorus_like=True,
            notcontinuenumbering=True,
            prefix="Pont",
            text="Pont final",
        )

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn(
            'type="checkbox"\n                                                                        checked\n                                                                        disabled\n                                                                        data-song-block-no-continue-numbering-checkbox',
            html,
        )

    def test_non_chorus_like_verse_clears_prefix_to_null(self):
        self._login()
        payload = self._base_payload()
        payload["blocks[a][type]"] = "verse"
        payload["blocks[a][prefix]"] = "Bridge"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)

        verse_block = Verse.objects.get(
            song=self.song, chorus=False, chorus_like=False, num=4
        )
        self.assertIsNone(verse_block.prefix)

    def test_member_cannot_change_status_via_checkbox(self):
        self._login()
        payload = self._base_payload()
        payload["status_validated"] = "1"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.NOT_VALIDATED)

    def test_moderator_can_validate_with_checkbox(self):
        self._login(is_moderator=True)
        payload = self._base_payload()
        payload["status_validated"] = "1"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED)

    def test_post_save_deletes_blocks_marked_for_deletion(self):
        self._login()
        payload = self._base_payload()
        payload["blocks[b][delete]"] = "1"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)

        verses = list(self.song.verses.all())
        self.assertEqual(len(verses), 2)
        self.assertFalse(any(item.chorus for item in verses))

    def test_save_and_exit_redirects_to_song_page(self):
        self._login()
        payload = self._base_payload()
        payload["submit_intent"] = "save_and_exit"
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("song", args=[self.song.song_id])
        )

    def test_save_and_exit_uses_safe_next_url(self):
        self._login()
        payload = self._base_payload()
        payload["submit_intent"] = "save_and_exit"
        payload["next_url"] = reverse("songs")
        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("songs"))


class ModifyGenresViewTests(TestCase):
    def setUp(self):
        self.user_id = "33333333-3333-3333-3333-333333333333"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="moderator.user",
            first_name="Moderator",
            last_name="User",
            email="moderator.user@example.test",
            enabled=True,
            email_verified=False,
        )

    def _login(self, *, is_moderator=False):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "moderator.user",
            "email": "moderator.user@example.test",
            "first_name": "Moderator",
            "last_name": "User",
            "is_moderator": is_moderator,
            "is_admin": False,
        }
        session.save()
        MemberRole.objects.filter(member_id=self.user_id).delete()
        if is_moderator:
            MemberRole.objects.create(
                member_id=self.user_id,
                is_moderator=True,
                is_admin=False,
            )

    @patch("app_song.views._fetch_genre_rows", return_value=[])
    def test_access_denied_for_non_moderator(self, _fetch_rows):
        response = self.client.get(reverse("modify_genres"))
        self.assertEqual(response.status_code, 404)

    @patch("app_song.views._fetch_genre_rows")
    def test_moderator_can_access_and_see_responsive_cards(self, fetch_rows):
        fetch_rows.return_value = [
            {
                "genre_id": 1,
                "group": "Louange",
                "name": "Prière",
                "usage_count": 1,
                "is_used": True,
            },
        ]
        self._login(is_moderator=True)
        response = self.client.get(reverse("modify_genres"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "groupe")
        self.assertContains(response, "nom")
        self.assertContains(response, "état")
        self.assertContains(response, "actions")
        self.assertContains(response, "⚡")
        self.assertContains(response, "Enregistrer", count=2)
        self.assertNotContains(response, "<table")

    @patch("app_song.views.messages.error")
    @patch("app_song.views.messages.success")
    @patch("app_song.views._fetch_genre_rows")
    @patch("app_song.views.connection.cursor")
    def test_post_save_runs_create_update_and_delete(
        self, cursor_factory, fetch_rows, success_mock, error_mock
    ):
        fetch_rows.return_value = [
            {
                "genre_id": 1,
                "group": "A",
                "name": "Alpha",
                "usage_count": 0,
                "is_used": False,
            },
            {
                "genre_id": 2,
                "group": "B",
                "name": "Beta",
                "usage_count": 2,
                "is_used": True,
            },
        ]
        cursor = MagicMock()
        cursor_factory.return_value.__enter__.return_value = cursor
        cursor.execute.return_value = None

        request = RequestFactory().post(
            reverse("modify_genres"),
            {
                "new_group": "Nouveau groupe",
                "new_name": "Nouveau nom",
                "rows[1][group]": "A2",
                "rows[1][name]": "Alpha2",
                "rows[2][group]": "B",
                "rows[2][name]": "Beta",
                "rows[2][delete]": "1",
            },
        )
        request.user = type(
            "User",
            (),
            {"is_authenticated": True, "is_moderator": True, "is_admin": False},
        )()

        song_views._save_genres(request)

        executed_sql = " ".join(
            str(call.args[0]) for call in cursor.execute.call_args_list
        )
        self.assertIn('INSERT INTO "common"."genres"', executed_sql)
        self.assertIn('UPDATE "common"."genres"', executed_sql)
        self.assertIn('DELETE FROM "common"."genres"', executed_sql)
        success_mock.assert_called()
        error_mock.assert_not_called()

    @patch("app_song.views.messages.error")
    @patch("app_song.views._fetch_genre_rows")
    @patch("app_song.views.connection.cursor")
    def test_delete_failure_shows_error_message(
        self, cursor_factory, fetch_rows, error_mock
    ):
        fetch_rows.return_value = [
            {
                "genre_id": 7,
                "group": "A",
                "name": "Alpha",
                "usage_count": 3,
                "is_used": True,
            },
        ]
        cursor = MagicMock()
        cursor_factory.return_value.__enter__.return_value = cursor

        def execute_side_effect(sql_statement, params=None):
            if 'DELETE FROM "common"."genres"' in str(sql_statement):
                raise IntegrityError("fk failure")
            return None

        cursor.execute.side_effect = execute_side_effect

        request = RequestFactory().post(
            reverse("modify_genres"),
            {
                "rows[7][group]": "A",
                "rows[7][name]": "Alpha",
                "rows[7][delete]": "1",
            },
        )
        request.user = type(
            "User",
            (),
            {"is_authenticated": True, "is_moderator": True, "is_admin": False},
        )()

        song_views._save_genres(request)
        error_mock.assert_called()


class ModifyArtistsAndBandsViewTests(TestCase):
    def setUp(self):
        self.user_id = "44444444-4444-4444-4444-444444444444"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="metadata.moderator",
            first_name="Meta",
            last_name="Moderator",
            email="metadata.moderator@example.test",
            enabled=True,
            email_verified=False,
        )

    def _login(self, *, is_moderator=False):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "metadata.moderator",
            "email": "metadata.moderator@example.test",
            "first_name": "Meta",
            "last_name": "Moderator",
            "is_moderator": is_moderator,
            "is_admin": False,
        }
        session.save()
        MemberRole.objects.filter(member_id=self.user_id).delete()
        if is_moderator:
            MemberRole.objects.create(
                member_id=self.user_id, is_moderator=True, is_admin=False
            )

    def test_artists_and_bands_are_404_for_non_moderator(self):
        self.assertEqual(self.client.get(reverse("modify_artists")).status_code, 404)
        self.assertEqual(self.client.get(reverse("modify_bands")).status_code, 404)

    @patch("app_song.views._fetch_name_item_rows")
    def test_artists_and_bands_render_responsive_cards(self, fetch_items):
        fetch_items.return_value = [
            {"item_id": 10, "name": "Nom", "usage_count": 1, "is_used": True}
        ]
        self._login(is_moderator=True)

        artists_response = self.client.get(reverse("modify_artists"))
        self.assertEqual(artists_response.status_code, 200)
        self.assertContains(artists_response, "song-meta-row--simple")
        self.assertNotContains(artists_response, "<table")
        self.assertContains(artists_response, "Enregistrer", count=2)

        bands_response = self.client.get(reverse("modify_bands"))
        self.assertEqual(bands_response.status_code, 200)
        self.assertContains(bands_response, "song-meta-row--simple")
        self.assertNotContains(bands_response, "<table")
        self.assertContains(bands_response, "Enregistrer", count=2)


class SongFavoritesSearchRegressionTests(TestCase):
    def setUp(self):
        self.user_id = "66666666-6666-6666-6666-666666666666"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="search.favorite.user",
            first_name="Search",
            last_name="Favorite",
            email="search.favorite.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.favorite_song = Song.objects.create(
            title="Chant favori",
            subtitle="A",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.other_song = Song.objects.create(
            title="Autre chant",
            subtitle="B",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        SongFavorite.objects.create(song=self.favorite_song, member_id=self.user_id)

    def test_favorites_only_search_still_filters_member_favorites(self):
        user = SimpleNamespace(is_authenticated=True)
        results = search_songs(
            SongSearchParams(favorites_only=True),
            user=user,
            member_id=self.user_id,
        )

        self.assertEqual(results.displayed_count, 1)
        self.assertEqual(results.results[0].song.song_id, self.favorite_song.song_id)


class SongFavoritesQuickViewTests(TestCase):
    def setUp(self):
        self.user_id = "77777777-7777-7777-7777-777777777777"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="quick.favorite.user",
            first_name="Quick",
            last_name="Favorite",
            email="quick.favorite.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.favorite_song = Song.objects.create(
            title="Mon favori",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.non_favorite_matching_saved_search = Song.objects.create(
            title="Saved Search Hit",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        SongFavorite.objects.create(song=self.favorite_song, member_id=self.user_id)
        MemberPreferences.objects.create(
            member_id=self.user_id,
            song_search={
                "text": "Saved Search",
                "everywhere": False,
                "match_all_selected_refs": False,
                "genre_ids": [],
                "band_ids": [],
                "artist_ids": [],
                "validation": "all",
                "favorites_only": False,
            },
        )

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "quick.favorite.user",
            "email": "quick.favorite.user@example.test",
            "first_name": "Quick",
            "last_name": "Favorite",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_favorites_quick_view_ignores_and_does_not_overwrite_saved_search(self):
        self._login()

        response = self.client.get(reverse("songs") + "?favorites_quick=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mon favori")
        displayed_titles = [
            item["song"].title for item in response.context["song_cards"]
        ]
        self.assertEqual(displayed_titles, ["Mon favori"])
        self.assertFalse(response.context["search_params"].favorites_only)
        self.assertEqual(response.context["search_params"].text, "Saved Search")
        self.assertContains(response, "Mode favoris temporaire actif.")
        self.assertContains(response, "Revenir à ma recherche enregistrée")

        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        self.assertEqual(preferences.song_search["text"], "Saved Search")
        self.assertFalse(preferences.song_search["favorites_only"])


class SongGenresDisplayViewTests(TestCase):
    user_id = "55555555-5555-5555-5555-555555555555"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="genre.display.user",
            first_name="Genre",
            last_name="Display",
            email="genre.display@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Chant de groupe",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") '
                "VALUES (%s, %s) RETURNING genre_id",
                ["2 - Chretien / KTO", "Louange"],
            )
            genre_id = cursor.fetchone()[0]
        SongGenre.objects.create(song=self.song, genre_id=genre_id)

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "genre.display.user",
            "email": "genre.display@example.test",
            "first_name": "Genre",
            "last_name": "Display",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_songs_page_displays_clean_genre_labels_in_filters_and_cards(self):
        self._login()

        response = self.client.get(reverse("songs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chretien / KTO / Louange")
        self.assertNotContains(response, "2 - Chretien / KTO / Louange")
        self.assertEqual(
            response.context["reference_options"].genres[0].label,
            "Chretien / KTO / Louange",
        )
        self.assertEqual(len(response.context["song_cards"][0]["genres"]), 1)
        self.assertTrue(
            response.context["song_cards"][0]["genres"][0].endswith(
                "Chretien / KTO / Louange"
            )
        )


class SongCreateFromSongsPageTests(TestCase):
    def setUp(self):
        self.user_id = "88888888-8888-8888-8888-888888888888"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="create.song.user",
            first_name="Create",
            last_name="Song",
            email="create.song.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.existing_song = Song.objects.create(
            title="Deja la",
            subtitle="Sous",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "create.song.user",
            "email": "create.song.user@example.test",
            "first_name": "Create",
            "last_name": "Song",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_authenticated_user_can_create_song_from_songs_page(self):
        self._login()
        response = self.client.post(
            reverse("songs"),
            data={
                "action": "create_song",
                "title": "  Nouveau titre  ",
                "subtitle": "  Nouveau sous titre  ",
            },
        )
        self.assertEqual(response.status_code, 302)

        created_song = Song.objects.get(
            title="Nouveau titre", subtitle="Nouveau sous titre"
        )
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_song", args=[created_song.song_id]),
        )
        self.assertEqual(created_song.description, "")
        self.assertEqual(created_song.status, SongStatus.NOT_VALIDATED)
        self.assertFalse(created_song.licensed)

    def test_guest_cannot_create_song(self):
        response = self.client.post(
            reverse("songs"),
            data={
                "action": "create_song",
                "title": "Nouveau titre",
                "subtitle": "",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_create_song_redirects_to_existing_song_when_duplicate(self):
        self._login()
        response = self.client.post(
            reverse("songs"),
            data={
                "action": "create_song",
                "title": "  Deja la ",
                "subtitle": " Sous  ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_song", args=[self.existing_song.song_id]),
        )
        self.assertEqual(
            Song.objects.filter(title="Deja la", subtitle="Sous").count(), 1
        )

    def test_create_song_requires_non_empty_title(self):
        self._login()
        response = self.client.post(
            reverse("songs"),
            data={
                "action": "create_song",
                "title": "   ",
                "subtitle": "Sous",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("songs"))
        self.assertFalse(Song.objects.filter(subtitle="Sous", title="").exists())


class ReferenceCatalogViewsTests(TestCase):
    user_id = "77777777-7777-7777-7777-777777777777"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="catalog.moderator",
            first_name="Catalog",
            last_name="Moderator",
            email="catalog@example.test",
            enabled=True,
            email_verified=False,
        )
        MemberRole.objects.create(
            member_id=self.user_id, is_moderator=True, is_admin=False
        )
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "catalog.moderator",
            "email": "catalog@example.test",
            "first_name": "Catalog",
            "last_name": "Moderator",
            "is_moderator": True,
            "is_admin": False,
        }
        session.save()

    def _insert_reference(self, table, columns, values):
        column_sql = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join(["%s"] * len(values))
        id_column = {
            "genres": "genre_id",
            "artists": "artist_id",
            "bands": "band_id",
        }[table]
        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO "common"."{table}" ({column_sql}) '
                f'VALUES ({placeholders}) RETURNING "{id_column}"',
                values,
            )
            return cursor.fetchone()[0]

    def _fetch_reference(self, table, id_column, item_id):
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT * FROM "common"."{table}" WHERE "{id_column}" = %s',
                [item_id],
            )
            return cursor.fetchone()

    def test_catalog_pages_require_moderator_and_render_database_rows(self):
        genre_id = self._insert_reference("genres", ("group", "name"), ("Style", "Pop"))
        artist_id = self._insert_reference("artists", ("name",), ("Artist A",))
        band_id = self._insert_reference("bands", ("name",), ("Band A",))

        for route_name, expected in (
            ("modify_genres", "Pop"),
            ("modify_artists", "Artist A"),
            ("modify_bands", "Band A"),
        ):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)

        self.assertIsNotNone(self._fetch_reference("genres", "genre_id", genre_id))
        self.assertIsNotNone(self._fetch_reference("artists", "artist_id", artist_id))
        self.assertIsNotNone(self._fetch_reference("bands", "band_id", band_id))

        MemberRole.objects.filter(member_id=self.user_id).delete()
        session = self.client.session
        session["lss_user"]["is_moderator"] = False
        session.save()
        self.assertEqual(self.client.get(reverse("modify_genres")).status_code, 404)

    def test_modify_genres_keeps_full_group_prefix_visible(self):
        self._insert_reference(
            "genres", ("group", "name"), ("1 - Scoutisme", "Louange")
        )

        response = self.client.get(reverse("modify_genres"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="1 - Scoutisme"', html=False)
        self.assertContains(response, "Louange")

    def test_unknown_catalog_actions_redirect_with_error(self):
        for route_name in ("modify_genres", "modify_artists", "modify_bands"):
            with self.subTest(route=route_name):
                response = self.client.post(
                    reverse(route_name), {"action": "unknown"}, follow=True
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Action inconnue")

    def test_genre_save_creates_updates_deletes_and_reports_invalid_rows(self):
        update_id = self._insert_reference(
            "genres", ("group", "name"), ("Old", "Update")
        )
        delete_id = self._insert_reference(
            "genres", ("group", "name"), ("Old", "Delete")
        )
        unchanged_id = self._insert_reference(
            "genres", ("group", "name"), ("Same", "Same")
        )

        response = self.client.post(
            reverse("modify_genres"),
            {
                "action": "save",
                "new_group": "New",
                "new_name": "Created",
                f"rows[{update_id}][group]": "Updated",
                f"rows[{update_id}][name]": "Renamed",
                f"rows[{delete_id}][delete]": "1",
                f"rows[{unchanged_id}][group]": "Same",
                f"rows[{unchanged_id}][name]": "Same",
                "rows[999999][group]": "Missing",
                "rows[999999][name]": "Ignored",
            },
            follow=True,
        )
        self.assertContains(response, "Genres enregistrés")
        self.assertIsNone(self._fetch_reference("genres", "genre_id", delete_id))
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT "group", "name" FROM "common"."genres" WHERE genre_id = %s',
                [update_id],
            )
            self.assertEqual(cursor.fetchone(), ("Updated", "Renamed"))
            cursor.execute(
                'SELECT 1 FROM "common"."genres" WHERE "group" = %s AND "name" = %s',
                ["New", "Created"],
            )
            self.assertIsNotNone(cursor.fetchone())

        invalid = self.client.post(
            reverse("modify_genres"),
            {
                "action": "save",
                "new_group": "Incomplete",
                f"rows[{update_id}][group]": "",
                f"rows[{update_id}][name]": "",
            },
            follow=True,
        )
        self.assertContains(invalid, "renseignez à la fois")
        self.assertContains(invalid, "groupe et nom obligatoires")

    def test_artist_and_band_save_cover_create_update_delete_and_invalid_name(self):
        for route_name, table, id_column, prefix in (
            ("modify_artists", "artists", "artist_id", "Artist"),
            ("modify_bands", "bands", "band_id", "Band"),
        ):
            with self.subTest(route=route_name):
                update_id = self._insert_reference(table, ("name",), (f"{prefix} old",))
                delete_id = self._insert_reference(
                    table, ("name",), (f"{prefix} delete",)
                )
                unchanged_id = self._insert_reference(
                    table, ("name",), (f"{prefix} same",)
                )
                response = self.client.post(
                    reverse(route_name),
                    {
                        "action": "save",
                        "new_name": f"{prefix} created",
                        f"rows[{update_id}][name]": f"{prefix} updated",
                        f"rows[{delete_id}][delete]": "1",
                        f"rows[{unchanged_id}][name]": f"{prefix} same",
                        "rows[999999][name]": "Ignored",
                    },
                    follow=True,
                )
                self.assertContains(response, "enregistrés")
                self.assertIsNone(self._fetch_reference(table, id_column, delete_id))

                invalid = self.client.post(
                    reverse(route_name),
                    {
                        "action": "save",
                        f"rows[{update_id}][name]": "",
                    },
                    follow=True,
                )
                self.assertContains(invalid, "nom obligatoire")


class SongMetadataPersistenceTests(TestCase):
    user_id = "88888888-8888-8888-8888-888888888888"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="metadata.user",
            first_name="Metadata",
            last_name="User",
            email="metadata@example.test",
            enabled=True,
            email_verified=False,
        )
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "metadata.user",
            "email": "metadata@example.test",
            "first_name": "Metadata",
            "last_name": "User",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()
        self.song = Song.objects.create(
            title="Metadata song",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )

    def _insert_reference(self, table, id_column, name, group=None):
        with connection.cursor() as cursor:
            if table == "genres":
                cursor.execute(
                    'INSERT INTO "common"."genres" ("group", "name") '
                    "VALUES (%s, %s) RETURNING genre_id",
                    [group, name],
                )
            else:
                cursor.execute(
                    f'INSERT INTO "common"."{table}" ("name") '
                    f'VALUES (%s) RETURNING "{id_column}"',
                    [name],
                )
            return cursor.fetchone()[0]

    def test_metadata_get_splits_selected_options_and_normalizes_audio_video(self):
        genre_selected = self._insert_reference(
            "genres", "genre_id", "Pop", group="1 - Scoutisme"
        )
        genre_available = self._insert_reference(
            "genres", "genre_id", "Rock", group="Style"
        )
        artist_id = self._insert_reference("artists", "artist_id", "Artist")
        band_id = self._insert_reference("bands", "band_id", "Band")
        SongGenre.objects.create(song=self.song, genre_id=genre_selected)
        SongArtist.objects.create(song=self.song, artist_id=artist_id)
        SongLink.objects.create(
            song=self.song, link="https://audio.test", type="audio-video"
        )

        response = self.client.get(reverse("song_metadata", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metadata_links"][0].display_type, "audio")
        self.assertEqual(
            response.context["metadata_genres_selected"][0]["id"], genre_selected
        )
        self.assertEqual(
            response.context["metadata_genres_selected"][0]["label"],
            "Scoutisme / Pop",
        )
        self.assertEqual(
            response.context["metadata_genres_available"][0]["id"], genre_available
        )
        self.assertEqual(
            response.context["metadata_genres_available"][0]["label"],
            "Style / Rock",
        )
        self.assertEqual(
            response.context["metadata_artists_selected"][0]["id"], artist_id
        )
        self.assertEqual(response.context["metadata_bands_available"][0]["id"], band_id)
        self.assertContains(response, "Scoutisme / Pop")
        self.assertNotContains(response, "1 - Scoutisme / Pop")

    def test_validated_metadata_page_keeps_toggle_without_edit_actions(self):
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])

        response = self.client.get(reverse("song_metadata", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "☆ Pas encore favori")
        self.assertNotContains(response, "data-song-delete-form")
        self.assertNotContains(
            response,
            'href="{}"'.format(reverse("modify_song", args=[self.song.song_id])),
            html=False,
        )

    def test_metadata_post_synchronizes_links_and_reference_relations(self):
        genre_old = self._insert_reference("genres", "genre_id", "Old", group="Style")
        genre_new = self._insert_reference("genres", "genre_id", "New", group="Style")
        artist_id = self._insert_reference("artists", "artist_id", "Artist")
        band_id = self._insert_reference("bands", "band_id", "Band")
        SongGenre.objects.create(song=self.song, genre_id=genre_old)
        SongLink.objects.create(song=self.song, link="https://a.test", type="web")
        SongLink.objects.create(song=self.song, link="https://b.test", type="score")
        SongLink.objects.create(song=self.song, link="https://c.test", type="internal")

        response = self.client.post(
            reverse("song_metadata", args=[self.song.song_id]),
            {
                "existing_0_original": "https://a.test",
                "existing_0_link": "https://renamed.test",
                "existing_0_type": "audio-video",
                "existing_1_original": "https://b.test",
                "existing_1_link": "",
                "existing_1_type": "score",
                "existing_1_delete": "1",
                "existing_2_original": "https://c.test",
                "existing_2_link": "https://c.test",
                "existing_2_type": "youtube",
                "new_link": "https://new.test",
                "new_type": "invalid-type",
                "genre_ids": [str(genre_new), str(genre_new), "bad", "-1"],
                "artist_ids": [str(artist_id)],
                "band_ids": [str(band_id)],
            },
        )
        self.assertRedirects(
            response, reverse("song_metadata", args=[self.song.song_id])
        )
        links = {
            item.link: item.type for item in SongLink.objects.filter(song=self.song)
        }
        self.assertEqual(
            links,
            {
                "https://renamed.test": "audio",
                "https://c.test": "youtube",
                "https://new.test": "web",
            },
        )
        self.assertEqual(
            set(
                SongGenre.objects.filter(song=self.song).values_list(
                    "genre_id", flat=True
                )
            ),
            {genre_new},
        )
        self.assertTrue(
            SongArtist.objects.filter(song=self.song, artist_id=artist_id).exists()
        )
        self.assertTrue(
            SongBand.objects.filter(song=self.song, band_id=band_id).exists()
        )

    def test_metadata_post_removes_colliding_link_targets(self):
        SongLink.objects.create(song=self.song, link="https://a.test", type="web")
        SongLink.objects.create(song=self.song, link="https://b.test", type="score")

        response = self.client.post(
            reverse("song_metadata", args=[self.song.song_id]),
            {
                "existing_0_original": "https://a.test",
                "existing_0_link": "https://b.test",
                "existing_0_type": "web",
                "existing_1_original": "https://b.test",
                "existing_1_link": "https://b.test",
                "existing_1_type": "score",
                "new_link": "https://b.test",
                "new_type": "web",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(
                SongLink.objects.filter(song=self.song).values_list("link", flat=True)
            ),
            [],
        )
