import uuid
from types import SimpleNamespace

from django.http import HttpResponse, QueryDict
from django.contrib.messages import get_messages
from django.template.loader import get_template
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
    SongLinkType,
    SongMessage,
    SongSlideDisplayMode,
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
    add_song_search_reference,
    _fetch_name_labels,
    _get_relation_maps,
    _normalize_ids,
    _params_from_query,
    _validation_label,
    build_song_search_query,
    build_song_search_url,
    get_active_song_search,
    load_member_song_search,
    remove_song_search_reference,
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
        self.assertTrue(genre_groups[0][1][0]["label"].endswith("Louange"))

    @patch("app_song.views._fetch_name_labels", return_value={})
    @patch(
        "app_song.views._fetch_genre_labels",
        return_value={
            13: ("1 - Scoutisme", "SGDF"),
            14: ("1 - Scoutisme", "SGDF - Compagnons"),
            15: ("2 - Chrétien - KTO", "prière"),
            11: ("3 - #", "en langue étrangère"),
            12: ("3 - #", "variété française"),
        },
    )
    @patch("app_song.views.SongArtist.objects.filter")
    @patch("app_song.views.SongBand.objects.filter")
    @patch("app_song.views.SongGenre.objects.filter")
    def test_get_song_metadata_labels_keeps_database_group_order_before_display_cleanup(
        self,
        song_genre_filter,
        song_band_filter,
        song_artist_filter,
        _fetch_genre_labels,
        _fetch_name_labels,
    ):
        song_genre_filter.return_value.values_list.return_value = (12, 15, 11, 14, 13)
        song_band_filter.return_value.values_list.return_value = ()
        song_artist_filter.return_value.values_list.return_value = ()

        _bands, _artists, genre_groups = song_views._get_song_metadata_labels(
            SimpleNamespace(song_id=1)
        )

        self.assertEqual(
            tuple(group_name for group_name, _names in genre_groups),
            ("Scoutisme", "Chrétien - KTO", "#"),
        )
        self.assertEqual(
            tuple(tag["label"].endswith("SGDF") for tag in genre_groups[0][1]),
            (True, False),
        )
        self.assertTrue(genre_groups[0][1][1]["label"].endswith("SGDF - Compagnons"))
        self.assertTrue(genre_groups[1][1][0]["label"].endswith("prière"))
        self.assertEqual(
            tuple(
                tag["label"].endswith("en langue étrangère")
                for tag in genre_groups[2][1]
            ),
            (True, False),
        )
        self.assertTrue(genre_groups[2][1][1]["label"].endswith("variété française"))


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

    def test_build_song_search_url_uses_reset_marker_for_empty_search(self):
        self.assertEqual(
            build_song_search_url(SongSearchParams.empty()),
            f"{reverse('songs')}?reset_search=1",
        )

    def test_add_song_search_reference_preserves_other_filters_without_duplicates(self):
        params = SongSearchParams(
            text="louange",
            everywhere=True,
            match_all_selected_refs=True,
            genre_ids=(3,),
            validation="validated_only",
            favorites_only=True,
        )

        next_params = add_song_search_reference(
            params,
            kind="genre",
            reference_id=5,
        )
        duplicate_params = add_song_search_reference(
            next_params,
            kind="genre",
            reference_id=5,
        )

        self.assertEqual(next_params.text, "louange")
        self.assertTrue(next_params.everywhere)
        self.assertTrue(next_params.match_all_selected_refs)
        self.assertEqual(next_params.validation, "validated_only")
        self.assertTrue(next_params.favorites_only)
        self.assertEqual(next_params.genre_ids, (3, 5))
        self.assertEqual(duplicate_params.genre_ids, (3, 5))

    def test_remove_song_search_reference_removes_only_target_id(self):
        params = SongSearchParams(
            genre_ids=(3, 5),
            band_ids=(7,),
            artist_ids=(11,),
            match_all_selected_refs=True,
        )

        next_params = remove_song_search_reference(
            params,
            kind="genre",
            reference_id=5,
        )

        self.assertEqual(next_params.genre_ids, (3,))
        self.assertEqual(next_params.band_ids, (7,))
        self.assertEqual(next_params.artist_ids, (11,))
        self.assertTrue(next_params.match_all_selected_refs)


class SongSearchPersistenceTests(TestCase):
    def setUp(self):
        self.member_id = str(uuid.uuid4())
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

        self.assertFalse(
            MemberPreferences.objects.filter(member_id=self.member_id).exists()
        )

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
    def setUp(self):
        self.member_id = str(uuid.uuid4())
        self.scope_token = f"scope-{uuid.uuid4().hex[:8]}"
        self.everywhere_token = f"everywhere-{uuid.uuid4().hex[:8]}"
        self.wildcard_token = f"wild-{uuid.uuid4().hex[:8]}"
        DirectoryUserRecord.objects.create(
            id=self.member_id,
            username="search.filter.user",
            first_name="Search",
            last_name="Filter",
            email="search.filter.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.title_song_title = f"Titre simple {self.scope_token}"
        self.description_song_title = f"Description {self.scope_token}"
        self.verse_song_title = f"Couplet {self.scope_token}"
        self.both_refs_song_title = f"Double liens {self.scope_token}"
        self.one_ref_song_title = f"Reference unique {self.scope_token}"
        self.licensed_song_title = f"Alpha licence {self.scope_token}"
        self.punctuation_title_song_title = (
            f"Esprit de Dieu, souffle de vie {self.wildcard_token}"
        )
        self.punctuation_title_song_subtitle = f"Variante {uuid.uuid4().hex[:8]}"
        self.punctuation_description_song_title = (
            f"Description ponctuation {self.scope_token}"
        )
        self.punctuation_verse_song_title = f"Couplet ponctuation {self.scope_token}"
        self.song_title = Song.objects.create(
            title=self.title_song_title,
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.song_description = Song.objects.create(
            title=self.description_song_title,
            subtitle="",
            description=f"{self.everywhere_token} Un été de lumière",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        self.song_verse = Song.objects.create(
            title=self.verse_song_title,
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        self.song_both_refs = Song.objects.create(
            title=self.both_refs_song_title,
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.song_one_ref = Song.objects.create(
            title=self.one_ref_song_title,
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.song_licensed = Song.objects.create(
            title=self.licensed_song_title,
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=True,
        )
        self.song_punctuation_title = Song.objects.create(
            title=self.punctuation_title_song_title,
            subtitle=self.punctuation_title_song_subtitle,
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        self.song_punctuation_description = Song.objects.create(
            title=self.punctuation_description_song_title,
            subtitle="",
            description=f"Esprit de Dieu, souffle de vie dans nos coeurs {self.wildcard_token}",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        self.song_punctuation_verse = Song.objects.create(
            title=self.punctuation_verse_song_title,
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        Verse.objects.create(
            song=self.song_verse,
            num=2,
            num_verse=1,
            chorus=False,
            text=f"{self.everywhere_token} Encore la lumière revient",
        )
        Verse.objects.create(
            song=self.song_verse,
            num=4,
            num_verse=2,
            chorus=False,
            text=f"{self.everywhere_token} La lumiere revient encore",
        )
        Verse.objects.create(
            song=self.song_punctuation_verse,
            num=2,
            num_verse=1,
            chorus=False,
            text=f"Esprit de Dieu, souffle de vie pour nos jours {self.wildcard_token}",
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

        self.band_id = 100000 + uuid.uuid4().int % 1000000
        self.artist_id = 200000 + uuid.uuid4().int % 1000000
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."bands" ("band_id", "name") VALUES (%s, %s)',
                [self.band_id, "Les Testeurs"],
            )
            cursor.execute(
                'INSERT INTO "common"."artists" ("artist_id", "name") VALUES (%s, %s)',
                [self.artist_id, "Artiste Test"],
            )

        SongBand.objects.create(song=self.song_both_refs, band_id=self.band_id)
        SongArtist.objects.create(song=self.song_both_refs, artist_id=self.artist_id)
        self.member_catalog_count = Song.objects.count()
        self.guest_catalog_count = Song.objects.filter(licensed=False).count()

    def test_search_songs_everywhere_matches_description_and_verse_text(self):
        results = search_songs(
            SongSearchParams(text=self.everywhere_token, everywhere=True),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(
            [item.song.title for item in results.results],
            [self.verse_song_title, self.description_song_title],
        )
        self.assertEqual(results.search_count, 2)
        self.assertEqual(results.displayed_count, 2)

    def test_search_songs_title_matches_with_spaces_as_ordered_wildcards(self):
        results = search_songs(
            SongSearchParams(text=f"esprit de dieu souffle {self.wildcard_token}"),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(
            [item.song.title for item in results.results],
            [self.punctuation_title_song_title],
        )
        self.assertEqual(results.search_count, 1)

    def test_search_songs_everywhere_matches_punctuation_between_query_words(self):
        results = search_songs(
            SongSearchParams(
                text=f"esprit de dieu souffle {self.wildcard_token}",
                everywhere=True,
            ),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(
            [item.song.title for item in results.results],
            [
                self.punctuation_verse_song_title,
                self.punctuation_description_song_title,
                self.punctuation_title_song_title,
            ],
        )
        self.assertEqual(results.search_count, 3)

    def test_search_songs_reference_filters_support_any_and_all_without_duplicates(
        self,
    ):
        any_results = search_songs(
            SongSearchParams(
                text=self.scope_token,
                genre_ids=(self.genre_a_id, self.genre_b_id),
            ),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        self.assertEqual(
            [item.song.title for item in any_results.results],
            [self.both_refs_song_title, self.one_ref_song_title],
        )
        self.assertEqual(any_results.search_count, 2)

        all_results = search_songs(
            SongSearchParams(
                text=self.scope_token,
                genre_ids=(self.genre_a_id, self.genre_b_id),
                band_ids=(self.band_id,),
                artist_ids=(self.artist_id,),
                match_all_selected_refs=True,
            ),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        self.assertEqual(
            [item.song.title for item in all_results.results],
            [self.both_refs_song_title],
        )
        self.assertEqual(all_results.search_count, 1)

    def test_search_songs_handles_validation_and_favorites(self):
        validated_results = search_songs(
            SongSearchParams(text=self.scope_token, validation="validated_only"),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        self.assertEqual(
            [item.song.title for item in validated_results.results],
            [
                self.licensed_song_title,
                self.punctuation_verse_song_title,
                self.verse_song_title,
                self.punctuation_description_song_title,
                self.description_song_title,
            ],
        )

        non_validated_results = search_songs(
            SongSearchParams(text=self.scope_token, validation="non_validated_only"),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        self.assertEqual(
            [item.song.title for item in non_validated_results.results],
            [
                self.both_refs_song_title,
                self.one_ref_song_title,
                self.title_song_title,
            ],
        )

        favorite_results = search_songs(
            SongSearchParams(text=self.scope_token, favorites_only=True),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        self.assertEqual(
            [item.song.title for item in favorite_results.results],
            [self.description_song_title],
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
            SongSearchParams(text=f"{self.scope_token}-introuvable"),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(results.displayed_count, 0)
        self.assertEqual(results.search_count, 0)
        self.assertEqual(results.catalog_count, self.member_catalog_count)

    def test_search_songs_favorites_only_without_member_id_does_not_filter_results(
        self,
    ):
        results = search_songs(
            SongSearchParams(text=self.scope_token, favorites_only=True),
            user=SimpleNamespace(is_authenticated=True),
            member_id=None,
        )

        self.assertFalse(results.params.favorites_only)
        self.assertEqual(results.search_count, 8)
        self.assertEqual(results.catalog_count, self.member_catalog_count)
        self.assertEqual(
            [item.song.title for item in results.results],
            [
                self.licensed_song_title,
                self.punctuation_verse_song_title,
                self.verse_song_title,
                self.punctuation_description_song_title,
                self.description_song_title,
                self.both_refs_song_title,
                self.one_ref_song_title,
                self.title_song_title,
            ],
        )

    def test_search_songs_text_normalization_compacts_internal_spaces(self):
        results = search_songs(
            SongSearchParams(
                text=f"  esprit   de   dieu   souffle   {self.wildcard_token}  "
            ),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )

        self.assertEqual(
            [item.song.title for item in results.results],
            [self.punctuation_title_song_title],
        )

    def test_search_songs_guest_counts_and_order_exclude_licensed_song(self):
        member_results = search_songs(
            SongSearchParams(text=self.scope_token),
            user=SimpleNamespace(is_authenticated=True),
            member_id=self.member_id,
        )
        guest_results = search_songs(
            SongSearchParams(text=self.scope_token),
            user=SimpleNamespace(is_authenticated=False),
            member_id=None,
        )

        self.assertEqual(member_results.catalog_count, self.member_catalog_count)
        self.assertEqual(member_results.search_count, 8)
        self.assertEqual(
            [item.song.title for item in member_results.results],
            [
                self.licensed_song_title,
                self.punctuation_verse_song_title,
                self.verse_song_title,
                self.punctuation_description_song_title,
                self.description_song_title,
                self.both_refs_song_title,
                self.one_ref_song_title,
                self.title_song_title,
            ],
        )
        self.assertEqual(guest_results.catalog_count, self.guest_catalog_count)
        self.assertEqual(guest_results.search_count, 7)
        self.assertEqual(
            [item.song.title for item in guest_results.results],
            [
                self.punctuation_verse_song_title,
                self.verse_song_title,
                self.punctuation_description_song_title,
                self.description_song_title,
                self.both_refs_song_title,
                self.one_ref_song_title,
                self.title_song_title,
            ],
        )


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
        DirectoryUserRecord.objects.update_or_create(
            id=self.user_id,
            defaults={
                "username": "lyrics.reader",
                "first_name": "Lyrics",
                "last_name": "Reader",
                "email": "lyrics.reader@example.test",
                "enabled": True,
                "email_verified": False,
            },
        )
        self.song, _created = Song.objects.update_or_create(
            title="Le Sud",
            subtitle="Nino Ferrer",
            defaults={
                "description": "Description",
                "status": 1,
                "licensed": True,
            },
        )
        Verse.objects.filter(song=self.song).delete()
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

    def test_song_view_renders_single_chorus_mode(self):
        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["text_long_html"], response.context["text_short_html"]
        )

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

    def test_modify_song_view_exposes_plain_copy_buttons_in_tools_and_mobile(self):
        self._login()
        self.song.status = SongStatus.NOT_VALIDATED
        self.song.save(update_fields=["status"])
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

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
        self.assertTrue(
            response.context["genre_groups"][0][1][0]["label"].endswith("Louange")
        )

    def test_song_view_uses_translated_tags_heading(self):
        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2># Tags</h2>", html=False)
        self.assertNotContains(response, "<h2># tags</h2>", html=False)

    def test_song_view_has_floating_link_to_smartphone_lyrics_page(self):
        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'href="{}"'.format(
                reverse("song_text", args=[self.song.song_id, "full-chorus"])
            ),
            html=False,
        )
        self.assertContains(response, 'aria-label="Smartphone view"', html=False)
        self.assertContains(
            response,
            'class="site-floating-actions song-smartphone-floating-actions"',
            html=False,
        )
        self.assertContains(
            response,
            "data-song-smartphone-floating",
            html=False,
        )
        self.assertContains(
            response,
            'class="site-floating-action song-smartphone-floating-link"',
            html=False,
        )
        self.assertContains(response, "📱")
        self.assertNotContains(response, "ouvrir la vue smartphone")

    def test_song_text_print_page_uses_full_title_without_tags(self):
        self.song.licensed = False
        self.song.save(update_fields=["licensed"])
        self._login()
        response = self.client.get(
            reverse("song_text", args=[self.song.song_id, "full-chorus"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title_complete"], "Le Sud - Nino Ferrer")
        self.assertEqual(
            [template.name for template in response.templates if template.name],
            ["lyrics/lyrics.html"],
        )
        self.assertContains(
            response, "<title>Le Sud - Nino Ferrer | Paroles</title>", html=True
        )
        self.assertContains(
            response,
            '<main class="lyrics-layout is-single" data-lyrics-root>',
            html=False,
        )
        self.assertContains(response, "images/lyrics/Lyrics_dark.png", html=False)
        self.assertContains(
            response,
            "images/lyrics/all_lyrics-background_dark.webp",
            html=False,
        )
        self.assertContains(response, 'data-lyrics-asset="logo"', html=False)
        self.assertContains(
            response,
            '<div class="lyrics-topbar" hidden>',
            html=False,
        )
        self.assertContains(
            response,
            '<p class="lyrics-song-title">Le Sud - Nino Ferrer</p>',
            html=False,
        )
        self.assertContains(
            response,
            ".lyrics-song-title {\n      margin: 0 0 1rem;\n      font-weight: 700;\n      font-size: 1.5em;",
            html=False,
        )
        self.assertNotContains(
            response,
            'class="lyrics-animation-title"',
            html=False,
        )
        first_block = response.context["songs"][0]["blocks"][0]
        second_block = response.context["songs"][0]["blocks"][1]
        self.assertContains(
            response,
            f'<p class="lyrics-block lyrics-block--chorus"><em>{first_block["prefix"]}</em> {first_block["text"]}</p>',
            html=False,
        )
        self.assertContains(
            response,
            f'<p class="lyrics-block"><em>{second_block["prefix"]}</em> C&#x27;est un endroit</p>',
            html=False,
        )
        self.assertContains(
            response,
            "/static/images/lyrics/all_lyrics-hamburger_menu.webp",
            html=False,
        )
        self.assertContains(
            response,
            f'href="/songs/{self.song.song_id}/" class="lyrics-drawer-song-link"',
            html=False,
        )
        self.assertContains(
            response,
            'data-copy-success-label="👍"',
            html=False,
        )
        self.assertContains(response, "data-lyrics-theme-toggle", html=False)
        self.assertContains(
            response,
            'const fontSizeStorageKey = "lss-smartphone-lyrics:font-size";',
            html=False,
        )
        self.assertContains(response, 'theme: "auto"', html=False)
        self.assertContains(
            response,
            "window.localStorage.getItem(fontSizeStorageKey)",
            html=False,
        )
        self.assertContains(
            response,
            "window.localStorage.setItem(",
            html=False,
        )
        self.assertNotContains(
            response,
            "lss-smartphone-lyrics:${window.location.pathname}",
            html=False,
        )
        self.assertNotContains(response, "parsed.theme ===", html=False)
        self.assertNotContains(
            response,
            "state.theme = parsed.theme",
            html=False,
        )
        self.assertNotContains(response, "Lecture smartphone", html=False)
        self.assertNotContains(response, "Adresse de partage</p>", html=False)
        self.assertNotContains(response, "Chant courant", html=False)
        self.assertNotContains(response, 'data-lyrics-nav="prev"')
        self.assertNotContains(response, 'data-lyrics-nav="next"')

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

    def test_song_view_displays_distinct_localized_link_type_labels(self):
        SongLink.objects.create(song=self.song, link="https://score.test", type="score")
        SongLink.objects.create(song=self.song, link="https://audio.test", type="audio")
        SongLink.objects.create(
            song=self.song, link="https://youtube.test", type="youtube"
        )
        SongLink.objects.create(song=self.song, link="https://web.test", type="web")
        SongLink.objects.create(
            song=self.song, link="https://internal.test", type="internal"
        )

        self._login()
        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "(partition)")
        self.assertContains(response, "(audio)")
        self.assertContains(response, "(YouTube)")
        self.assertContains(response, "(page Web)")
        self.assertContains(response, "(lien interne - Lyrics Slide Show)")
        self.assertNotContains(response, "(Internal)")
        self.assertNotContains(response, "(Web)")
        self.assertNotContains(response, "(Score)")
        self.assertNotContains(response, "(Audio/video)")

    @patch("app_song.views._can_read_song", return_value=False)
    def test_song_text_popup_endpoint_refuses_unreadable_song(self, _can_read_song):
        response = self.client.get(reverse("song_text_popup", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 404)

    def test_song_view_shows_unread_messages_link_for_authenticated_user(self):
        SongMessage.objects.create(
            song=self.song,
            message="Corriger ce couplet",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login()

        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertContains(
            response,
            "Il y a des modifications demandées pour ce chant, voir les demandes ici",
        )

    def test_song_view_hides_unread_messages_link_for_status_zero_song(self):
        self.song.status = SongStatus.NOT_VALIDATED
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Message caché",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login()

        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertNotContains(
            response,
            "Il y a des modifications demandées pour ce chant, voir les demandes ici",
        )

    def test_song_view_uses_popup_button_for_correction_report(self):
        self._login()

        response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertContains(response, "data-song-report-trigger", count=2)
        self.assertContains(response, 'id="song-correction-form"', html=False)
        self.assertNotContains(response, 'textarea name="message"', html=False)
        self.assertContains(
            response,
            "reportPopupMessage:",
            html=False,
        )
        self.assertContains(
            response,
            'reportPopupMessage: "Ce chant est validé : les modérateurs l\\u0027ont estimé de qualité. Les modifications communautaires sont donc bloquées et seuls les modérateurs peuvent désormais le modifier. Si vous voyez une correction à faire, vous pouvez envoyer un message totalement anonyme."',
            html=False,
        )

    def test_add_message_moves_validated_song_to_validated_with_concern(self):
        self._login()

        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "add_message", "message": "Corriger le refrain"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("song", args=[self.song.song_id])
        )
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)
        created_message = SongMessage.objects.get(song=self.song)
        self.assertEqual(created_message.message, "Corriger le refrain")
        self.assertFalse(created_message.is_read)

    def test_add_message_keeps_validated_with_concern_song_status(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        self._login()

        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "add_message", "message": "Autre correction"},
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)
        self.assertEqual(SongMessage.objects.filter(song=self.song).count(), 1)

    def test_add_message_rejects_blank_message_without_status_change(self):
        self._login()

        response = self.client.post(
            reverse("song", args=[self.song.song_id]),
            data={"action": "add_message", "message": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED)
        self.assertFalse(SongMessage.objects.filter(song=self.song).exists())


class SongStatusWorkflowTests(TestCase):
    def test_recalculate_status_keeps_not_validated_song_unchanged_with_new_messages(
        self,
    ):
        song = Song.objects.create(
            title="Workflow",
            subtitle="Libre",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        SongMessage.objects.create(
            song=song,
            message="Message en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )

        song_views._recalculate_song_status_from_messages(song)

        song.refresh_from_db()
        self.assertEqual(song.status, SongStatus.NOT_VALIDATED)


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
            "slide_display_mode": SongSlideDisplayMode.SINGLE,
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
        self.assertContains(response, "data-song-slide-display-mode-edit")
        self.assertContains(response, 'value="single" selected', html=False)
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertContains(response, "data-reorder-list")
        self.assertContains(response, "data-reorder-cancel")
        self.assertContains(
            response, "data-reorder-cancel\n                        hidden"
        )
        self.assertContains(response, "song-reorder-cancel-button")
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

    def test_modify_song_with_chorus_shows_only_single_and_chorus_modes(self):
        self._login()

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(response, 'option value="single"', html=False)
        self.assertContains(response, 'option value="chorus_then_parallel"', html=False)
        self.assertContains(
            response, 'option value="chorus_always_parallel"', html=False
        )
        self.assertNotContains(response, 'option value="verses_by_pairs"', html=False)

    def test_modify_song_without_chorus_shows_only_single_and_verses_by_pairs(self):
        self.verse_2.delete()
        self._login()

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(response, 'option value="single"', html=False)
        self.assertContains(response, 'option value="verses_by_pairs"', html=False)
        self.assertNotContains(
            response, 'option value="chorus_then_parallel"', html=False
        )
        self.assertNotContains(
            response, 'option value="chorus_always_parallel"', html=False
        )

    def test_modify_song_with_only_chorus_like_does_not_unlock_chorus_modes(self):
        self.verse_2.delete()
        self.verse_1.chorus_like = True
        self.verse_1.notcontinuenumbering = True
        self.verse_1.prefix = "Pont"
        self.verse_1.save(
            update_fields=["chorus_like", "notcontinuenumbering", "prefix"]
        )
        self._login()

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(response, 'option value="verses_by_pairs"', html=False)
        self.assertNotContains(
            response, 'option value="chorus_then_parallel"', html=False
        )
        self.assertNotContains(
            response, 'option value="chorus_always_parallel"', html=False
        )

    def test_modify_song_get_normalizes_incompatible_saved_mode_without_chorus(self):
        self.verse_2.delete()
        self.song.slide_display_mode = SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL
        self.song.save(update_fields=["slide_display_mode"])
        self._login()

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(
            response,
            'option value="verses_by_pairs" selected',
            html=False,
        )

    def test_member_can_access_validated_song_read_only(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login()
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2># Tags</h2>", html=False)
        self.assertNotContains(response, "<h2># tags</h2>", html=False)
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

    def test_moderator_cannot_devalidate_song_with_unread_messages(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Correction en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "devalidate_song"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)
        flash_messages = [
            str(message) for message in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            "Impossible de dévalider ce chant tant qu'il reste des demandes de modification non lues.",
            flash_messages,
        )

    def test_devalidate_normalizes_inconsistent_status_two_without_direct_devalidation(
        self,
    ):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Ancienne demande traitee",
            is_read=True,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "devalidate_song"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED)
        flash_messages = [
            str(message) for message in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            "Le chant doit d'abord repasser explicitement par l'état validé avant d'être dévalidé.",
            flash_messages,
        )

        second_response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data={"action": "devalidate_song"},
        )

        self.assertEqual(second_response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.NOT_VALIDATED)

    def test_devalidate_button_hidden_for_status_two(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertNotContains(response, 'value="devalidate_song"', html=False)

    def test_devalidate_button_visible_for_status_one(self):
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(response, 'value="devalidate_song"', html=False)

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
        self.assertEqual(self.song.slide_display_mode, SongSlideDisplayMode.SINGLE)

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

    def test_post_save_persists_chorus_mode_when_chorus_exists(self):
        self._login()
        payload = self._base_payload()
        payload["slide_display_mode"] = SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(
            self.song.slide_display_mode,
            SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

    def test_post_save_persists_verses_by_pairs_without_chorus(self):
        self._login()
        payload = self._base_payload()
        payload["slide_display_mode"] = SongSlideDisplayMode.VERSES_BY_PAIRS
        payload["blocks[b][delete]"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(
            self.song.slide_display_mode,
            SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

    def test_post_save_remaps_chorus_mode_to_verses_by_pairs_when_last_chorus_is_removed(
        self,
    ):
        self.song.slide_display_mode = SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL
        self.song.save(update_fields=["slide_display_mode"])
        self._login()
        payload = self._base_payload()
        payload["slide_display_mode"] = SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL
        payload["blocks[b][delete]"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(
            self.song.slide_display_mode,
            SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

    def test_post_save_remaps_verses_by_pairs_to_chorus_then_parallel_when_chorus_appears(
        self,
    ):
        self.verse_2.delete()
        self.song.slide_display_mode = SongSlideDisplayMode.VERSES_BY_PAIRS
        self.song.save(update_fields=["slide_display_mode"])
        self._login()
        payload = self._base_payload()
        payload["slide_display_mode"] = SongSlideDisplayMode.VERSES_BY_PAIRS

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(
            self.song.slide_display_mode,
            SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

    def test_post_save_keeps_single_mode_even_when_chorus_structure_changes(self):
        self.song.slide_display_mode = SongSlideDisplayMode.SINGLE
        self.song.save(update_fields=["slide_display_mode"])
        self._login()
        payload = self._base_payload()
        payload["slide_display_mode"] = SongSlideDisplayMode.SINGLE
        payload["blocks[b][delete]"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.slide_display_mode, SongSlideDisplayMode.SINGLE)

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

    def test_moderator_can_unvalidate_status_one_with_checkbox(self):
        self.song.status = SongStatus.VALIDATED
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data=self._base_payload(),
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.NOT_VALIDATED)

    def test_moderator_validation_with_unread_messages_sets_status_with_concern(self):
        SongMessage.objects.create(
            song=self.song,
            message="Message en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)
        payload = self._base_payload()
        payload["status_validated"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)

    def test_moderator_save_keeps_status_two_when_checkbox_checked_and_unread_messages(
        self,
    ):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Message en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)
        payload = self._base_payload()
        payload["status_validated"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)

    def test_moderator_save_normalizes_status_two_to_one_when_all_messages_are_read(
        self,
    ):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Message traite",
            is_read=True,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)
        payload = self._base_payload()
        payload["status_validated"] = "1"

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]), data=payload
        )

        self.assertEqual(response.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED)

    def test_moderator_save_ignores_status_two_to_zero_attempt_and_saves_other_changes(
        self,
    ):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Message en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)
        payload = self._base_payload()

        response = self.client.post(
            reverse("modify_song", args=[self.song.song_id]),
            data=payload,
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertEqual(self.song.status, SongStatus.VALIDATED_WITH_CONCERN)
        self.assertEqual(self.song.title, "Nouveau\u00a0: titre\u00a0?")
        flash_messages = [
            str(message) for message in get_messages(response.wsgi_request)
        ]
        self.assertIn(
            "La devalidation directe depuis status=2 est ignoree. Le chant doit d'abord revenir explicitement a status=1.",
            flash_messages,
        )

    def test_modify_song_shows_messages_link_for_moderator(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Message visible",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        self._login(is_moderator=True)

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(response, "Voir toutes les demandes de modification")

    def test_modify_song_status_two_checkbox_is_checked_disabled_and_preserved(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        self.assertContains(
            response,
            'id="song-status-validated-edit"',
            html=False,
        )
        self.assertContains(response, "checked", html=False)
        self.assertContains(response, "disabled", html=False)
        self.assertContains(
            response,
            '<input type="hidden" name="status_validated" form="modify-song-form" value="1">',
            html=False,
        )

    def test_modify_song_popup_orders_unread_messages_first_then_newest(self):
        self.song.status = SongStatus.VALIDATED_WITH_CONCERN
        self.song.save(update_fields=["status"])
        SongMessage.objects.create(
            song=self.song,
            message="Lu le plus recent",
            is_read=True,
            date="2026-06-24T14:00:00Z",
        )
        SongMessage.objects.create(
            song=self.song,
            message="Non lu ancien",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        SongMessage.objects.create(
            song=self.song,
            message="Non lu recent",
            is_read=False,
            date="2026-06-24T13:00:00Z",
        )
        self._login(is_moderator=True)

        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))

        popup_markdown = response.context["all_messages_popup_markdown"]
        self.assertLess(
            popup_markdown.index("Non lu recent"),
            popup_markdown.index("Non lu ancien"),
        )
        self.assertLess(
            popup_markdown.index("Non lu ancien"),
            popup_markdown.index("Lu le plus recent"),
        )
        self.assertIn("\n\n---\n\n", popup_markdown)
        self.assertLess(
            popup_markdown.index("Non lu ancien"),
            popup_markdown.index("---"),
        )
        self.assertLess(
            popup_markdown.index("---"),
            popup_markdown.index("Lu le plus recent"),
        )

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


class SongMessageReadStateViewTests(TestCase):
    user_id = "66666666-6666-6666-6666-666666666666"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="message.moderator",
            first_name="Message",
            last_name="Moderator",
            email="message.moderator@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Message song",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        self.message = SongMessage.objects.create(
            song=self.song,
            message="A lire",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )

    def _login(self, *, is_moderator=False):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "message.moderator",
            "email": "message.moderator@example.test",
            "first_name": "Message",
            "last_name": "Moderator",
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

    def test_moderator_can_mark_message_read_and_song_returns_to_validated(self):
        self._login(is_moderator=True)

        response = self.client.post(
            reverse("song_message_read_state", args=[self.message.message_id]),
            data={"is_read": "1"},
        )

        self.assertEqual(response.status_code, 204)
        self.message.refresh_from_db()
        self.song.refresh_from_db()
        self.assertTrue(self.message.is_read)
        self.assertEqual(self.song.status, SongStatus.VALIDATED)

    def test_non_moderator_cannot_toggle_message_read_state(self):
        self._login(is_moderator=False)

        response = self.client.post(
            reverse("song_message_read_state", args=[self.message.message_id]),
            data={"is_read": "1"},
        )

        self.assertEqual(response.status_code, 404)
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_read)


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


class SongModerationQuickViewTests(TestCase):
    user_id = "77777777-7777-7777-7777-777777777777"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="quick.moderation.user",
            first_name="Quick",
            last_name="Moderation",
            email="quick.moderation.user@example.test",
            enabled=True,
            email_verified=False,
        )
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
        self.song_to_moderate = Song.objects.create(
            title="A moderer",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED_WITH_CONCERN,
            licensed=False,
        )
        SongMessage.objects.create(
            song=self.song_to_moderate,
            message="Message en attente",
            is_read=False,
            date="2026-06-24T12:00:00Z",
        )
        Song.objects.create(
            title="Autre chant",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "quick.moderation.user",
            "email": "quick.moderation.user@example.test",
            "first_name": "Quick",
            "last_name": "Moderation",
            "is_moderator": True,
            "is_admin": False,
        }
        session.save()
        MemberRole.objects.create(
            member_id=self.user_id,
            is_moderator=True,
            is_admin=False,
        )

    def test_moderation_quick_view_ignores_and_does_not_overwrite_saved_search(self):
        self._login()

        response = self.client.get(reverse("songs") + "?moderation_quick=1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A moderer")
        self.assertContains(response, "Mode modération temporaire actif.")
        displayed_titles = [
            item["song"].title for item in response.context["song_cards"]
        ]
        self.assertEqual(displayed_titles, ["A moderer"])
        self.assertEqual(response.context["search_params"].text, "Saved Search")
        self.assertTrue(response.context["moderation_quick_active"])

        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        self.assertEqual(preferences.song_search["text"], "Saved Search")


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

    def _render_songs_response(self):
        request = RequestFactory().get(reverse("songs"))
        request.user = SimpleNamespace(
            is_authenticated=True,
            external_id=self.user_id,
            is_moderator=False,
            is_admin=False,
        )
        request.session = {}
        request.LANGUAGE_CODE = "fr"

        def fake_render(_request, template_name, context):
            response = HttpResponse(
                get_template(template_name).render(context, request=_request)
            )
            response.context_data = context
            return response

        with patch("app_song.views.render", side_effect=fake_render):
            return song_views.songs(request)

    def test_songs_page_displays_clean_genre_labels_in_filters_and_cards(self):
        response = self._render_songs_response()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chretien / KTO / Louange")
        self.assertNotContains(response, "2 - Chretien / KTO / Louange")
        self.assertIn(
            "Chretien / KTO / Louange",
            [item.label for item in response.context_data["reference_options"].genres],
        )
        matching_cards = [
            card
            for card in response.context_data["song_cards"]
            if card["song"].song_id == self.song.song_id
        ]
        self.assertEqual(len(matching_cards), 1)
        self.assertEqual(len(matching_cards[0]["genres"]), 1)
        self.assertTrue(
            matching_cards[0]["genres"][0]["label"].endswith("Chretien / KTO / Louange")
        )

    def test_songs_page_exposes_info_popups_for_search_and_total_counts(self):
        response = self._render_songs_response()
        rendered = response.content.decode()

        self.assertContains(response, "data-song-inline-popup", count=4)
        self.assertContains(response, 'class="song-page-stats"', html=False)
        self.assertNotContains(response, 'class="song-tools-stats"', html=False)
        self.assertContains(
            response, 'class="song-inline-info-link"', count=4, html=False
        )
        self.assertNotContains(
            response,
            'class="song-inline-info-link site-action',
            html=False,
        )
        self.assertContains(
            response,
            'data-popup-title="Recherche ⓘ"',
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            'data-popup-title="Total ⓘ"',
            count=2,
            html=False,
        )
        self.assertContains(
            response,
            "Nombre de chants retournés par la recherche sauvegardée",
        )
        self.assertContains(
            response,
            "Nombre total de chants en base de données",
        )
        self.assertContains(
            response,
            'data-song-saved-search-text=""',
            html=False,
        )
        self.assertLess(
            rendered.index("<h1>Liste des chants</h1>"),
            rendered.index('class="song-page-stats"'),
        )

    def test_songs_search_form_targets_song_list_anchor(self):
        response = self._render_songs_response()

        self.assertContains(
            response,
            'form method="get" action="/songs/#song-list-section" class="song-search-form" id="song-search"',
            html=False,
        )
        self.assertContains(
            response,
            'id="song-list-section" class="song-list-section"',
            html=False,
        )

    def test_songs_page_moves_new_song_card_after_song_list_in_footer(self):
        response = self._render_songs_response()
        rendered = response.content.decode()

        self.assertLess(
            rendered.index('id="song-list-section" class="song-list-section"'),
            rendered.index('class="site-theme-card song-create-card"'),
        )
        self.assertLess(
            rendered.index('<section class="site-main-content">'),
            rendered.index('class="site-theme-card song-search-card"'),
        )
        self.assertNotIn(
            '<section class="site-main-content">\n    <article class="site-theme-card song-create-card"',
            rendered,
        )

    def test_songs_page_duplicates_quick_links_inside_search_card_for_mobile(self):
        response = self._render_songs_response()

        self.assertContains(response, 'class="song-mobile-quick-links"', html=False)

    def test_songs_page_exposes_compact_list_markup_for_tablet_and_mobile(self):
        SongFavorite.objects.create(song=self.song, member_id=self.user_id)
        response = self._render_songs_response()
        rendered = response.content.decode()

        self.assertContains(
            response,
            'class="song-list song-list--desktop"',
            html=False,
        )
        self.assertContains(
            response,
            'class="song-list song-compact-list"',
            html=False,
        )
        self.assertContains(
            response,
            'class="site-theme-card song-compact-item"',
            html=False,
        )
        self.assertContains(
            response,
            'class="song-compact-item-tools"',
            html=False,
        )
        self.assertContains(
            response,
            'class="song-compact-favorite"',
            html=False,
        )
        self.assertContains(
            response,
            "data-song-compact-options-toggle",
            html=False,
        )
        self.assertContains(response, "data-song-compact-options-panel", html=False)

        compact_start = rendered.index('class="song-list song-compact-list"')
        compact_end = rendered.index('class="site-theme-card song-create-card"')
        compact_markup = rendered[compact_start:compact_end]

        self.assertIn(
            f'href="/songs/{self.song.song_id}/text/full-chorus/"',
            compact_markup,
        )
        self.assertIn(
            'href="/songs/?genre_ids=',
            compact_markup,
        )
        self.assertNotIn("data-song-description", compact_markup)
        self.assertIn("data-song-print-menu", compact_markup)
        self.assertIn(">Afficher<", compact_markup)
        self.assertIn(">Modifier<", compact_markup)
        self.assertIn(">Supprimer<", compact_markup)
        self.assertIn(">Impression<", compact_markup)
        self.assertIn(">Smartphone view<", compact_markup)

    def test_songs_page_hides_compact_edit_actions_for_non_editable_song(self):
        validated_song = Song.objects.create(
            title="Validated song",
            subtitle="Locked",
            status=SongStatus.VALIDATED,
        )

        response = self.client.get(reverse("songs"))
        rendered = response.content.decode()
        compact_start = rendered.index('class="song-list song-compact-list"')
        compact_end = rendered.index('class="site-theme-card song-create-card"')
        compact_markup = rendered[compact_start:compact_end]
        validated_link = f'href="/songs/{validated_song.song_id}/"'
        validated_index = compact_markup.index(validated_link)
        validated_slice = compact_markup[validated_index : validated_index + 2200]

        self.assertIn(">Afficher<", validated_slice)
        self.assertIn(">Smartphone view<", validated_slice)
        self.assertIn(">Impression<", validated_slice)
        self.assertNotIn(">Modifier<", validated_slice)
        self.assertNotIn(">Supprimer<", validated_slice)

    def test_songs_page_summary_help_exposes_mobile_toggle_markup_and_labels(self):
        response = self._render_songs_response()

        self.assertContains(response, "data-song-summary-help", html=False)
        self.assertContains(response, "data-song-summary-toggle", html=False)
        self.assertContains(response, "data-song-summary-content", html=False)
        self.assertContains(
            response,
            'class="song-summary-help-toggle-label">Aide</span>',
            html=False,
        )
        self.assertContains(
            response,
            'class="song-summary-help-toggle-arrow" aria-hidden="true"></span>',
            html=False,
        )
        self.assertContains(
            response, 'aria-controls="song-summary-help-content"', html=False
        )
        self.assertContains(response, 'aria-expanded="false"', html=False)
        self.assertContains(
            response,
            'id="song-summary-help-content" class="song-legend" data-song-summary-content hidden',
            html=False,
        )
        self.assertContains(response, "💫 Afficher mes favoris", count=2)


class SongLocalSearchSavedTextRenderingTests(TestCase):
    user_id = "54545454-5454-5454-5454-545454545454"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="local.search.render.user",
            first_name="Local",
            last_name="Search",
            email="local.search.render.user@example.test",
            enabled=True,
            email_verified=False,
        )
        Song.objects.create(
            title="Saved Search Hit",
            subtitle="",
            description="Contient une description utile",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        MemberPreferences.objects.create(
            member_id=self.user_id,
            song_search={
                "text": "Été Glory",
                "everywhere": True,
                "match_all_selected_refs": False,
                "genre_ids": [],
                "band_ids": [],
                "artist_ids": [],
                "validation": "all",
                "favorites_only": False,
            },
        )

    def _render_songs_response(self, *, authenticated: bool):
        request = RequestFactory().get(reverse("songs"))
        if authenticated:
            request.user = SimpleNamespace(
                is_authenticated=True,
                external_id=self.user_id,
                is_moderator=False,
                is_admin=False,
            )
        else:
            request.user = AnonymousUser()
        request.session = {}
        request.LANGUAGE_CODE = "fr"

        def fake_render(_request, template_name, context):
            response = HttpResponse(
                get_template(template_name).render(context, request=_request)
            )
            response.context_data = context
            return response

        with patch("app_song.views.render", side_effect=fake_render):
            return song_views.songs(request)

    def test_songs_page_exposes_saved_text_for_local_search_guard(self):
        response = self._render_songs_response(authenticated=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-song-saved-search-text="Été Glory"',
            html=False,
        )
        self.assertEqual(response.context_data["search_params"].text, "Été Glory")

    def test_guest_songs_page_exposes_empty_saved_text_for_local_search_guard(self):
        response = self._render_songs_response(authenticated=False)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-song-saved-search-text=""',
            html=False,
        )


class SongClickableReferenceFiltersTests(TestCase):
    user_id = "56565656-5656-5656-5656-565656565656"

    def setUp(self):
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="clickable.tags.user",
            first_name="Clickable",
            last_name="Tags",
            email="clickable.tags@example.test",
            enabled=True,
            email_verified=False,
        )
        self.song = Song.objects.create(
            title="Saved Search Hit",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        Song.objects.create(
            title="Saved Search Other",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )
        SongFavorite.objects.create(song=self.song, member_id=self.user_id)

        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Louange"],
            )
            self.genre_id = cursor.fetchone()[0]
            cursor.execute(
                'INSERT INTO "common"."bands" ("name") VALUES (%s) RETURNING band_id',
                ["Les Veilleurs"],
            )
            self.band_id = cursor.fetchone()[0]
            cursor.execute(
                'INSERT INTO "common"."artists" ("name") VALUES (%s) RETURNING artist_id',
                ["Claire Lumiere"],
            )
            self.artist_id = cursor.fetchone()[0]

        SongGenre.objects.create(song=self.song, genre_id=self.genre_id)
        SongBand.objects.create(song=self.song, band_id=self.band_id)
        SongArtist.objects.create(song=self.song, artist_id=self.artist_id)

        self.saved_search = {
            "text": "Saved Search",
            "everywhere": False,
            "match_all_selected_refs": True,
            "genre_ids": [],
            "band_ids": [],
            "artist_ids": [],
            "validation": "validated_only",
            "favorites_only": True,
        }
        MemberPreferences.objects.create(
            member_id=self.user_id,
            song_search=self.saved_search.copy(),
        )

    def _login(self):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "clickable.tags.user",
            "email": "clickable.tags@example.test",
            "first_name": "Clickable",
            "last_name": "Tags",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_songs_card_tag_click_adds_reference_to_saved_search(self):
        self._login()

        response = self.client.get(reverse("songs"))
        add_url = response.context["song_cards"][0]["genres"][0]["add_url"]

        follow_response = self.client.get(add_url)

        self.assertEqual(follow_response.status_code, 200)
        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        self.assertEqual(preferences.song_search["text"], "Saved Search")
        self.assertTrue(preferences.song_search["match_all_selected_refs"])
        self.assertEqual(preferences.song_search["validation"], "validated_only")
        self.assertTrue(preferences.song_search["favorites_only"])
        self.assertEqual(preferences.song_search["genre_ids"], [self.genre_id])

    def test_songs_card_tag_click_does_not_duplicate_existing_reference(self):
        self._login()
        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        preferences.song_search = {
            **self.saved_search,
            "genre_ids": [self.genre_id],
        }
        preferences.save(update_fields=["song_search"])

        response = self.client.get(reverse("songs"))
        add_url = response.context["song_cards"][0]["genres"][0]["add_url"]
        self.client.get(add_url)

        preferences.refresh_from_db()
        self.assertEqual(preferences.song_search["genre_ids"], [self.genre_id])

    def test_active_tag_removal_keeps_other_filters_and_match_logic(self):
        self._login()
        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        preferences.song_search = {
            **self.saved_search,
            "genre_ids": [self.genre_id],
            "band_ids": [self.band_id],
            "artist_ids": [self.artist_id],
        }
        preferences.save(update_fields=["song_search"])

        response = self.client.get(reverse("songs"))
        self.assertContains(response, "song-tag-badge-link--removable")
        remove_url = next(
            tag["remove_url"]
            for tag in response.context["active_search_tags"]
            if tag["kind"] == "band"
        )
        follow_response = self.client.get(remove_url)

        self.assertEqual(follow_response.status_code, 200)
        preferences.refresh_from_db()
        self.assertTrue(preferences.song_search["match_all_selected_refs"])
        self.assertEqual(preferences.song_search["genre_ids"], [self.genre_id])
        self.assertEqual(preferences.song_search["band_ids"], [])
        self.assertEqual(preferences.song_search["artist_ids"], [self.artist_id])

    def test_active_tag_removal_of_last_filter_resets_saved_search(self):
        self._login()
        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        preferences.song_search = {
            **self.saved_search,
            "text": "",
            "match_all_selected_refs": False,
            "validation": "all",
            "favorites_only": False,
            "genre_ids": [self.genre_id],
            "band_ids": [],
            "artist_ids": [],
        }
        preferences.save(update_fields=["song_search"])

        response = self.client.get(reverse("songs"))
        remove_url = response.context["active_search_tags"][0]["remove_url"]

        self.assertEqual(remove_url, f"{reverse('songs')}?reset_search=1")

        follow_response = self.client.get(remove_url)

        self.assertEqual(follow_response.status_code, 200)
        preferences.refresh_from_db()
        self.assertEqual(
            preferences.song_search,
            SongSearchParams.empty().to_preferences(),
        )
        self.assertEqual(follow_response.context["active_search_tags"], ())

    def test_song_view_tag_click_routes_to_songs_and_updates_saved_search(self):
        self._login()

        response = self.client.get(reverse("song", args=[self.song.song_id]))
        add_url = response.context["genre_groups"][0][1][0]["add_url"]
        follow_response = self.client.get(add_url)

        self.assertEqual(follow_response.status_code, 200)
        self.assertContains(follow_response, "Liste des chants")
        preferences = MemberPreferences.objects.get(member_id=self.user_id)
        self.assertEqual(preferences.song_search["genre_ids"], [self.genre_id])

    def test_guests_do_not_get_clickable_reference_tags_or_active_filters(self):
        songs_response = self.client.get(reverse("songs"))

        self.assertEqual(songs_response.context["active_search_tags"], ())
        self.assertIsNone(
            songs_response.context["song_cards"][0]["genres"][0]["add_url"]
        )
        self.assertNotContains(songs_response, "song-tag-badge-link--removable")

        song_response = self.client.get(reverse("song", args=[self.song.song_id]))

        self.assertEqual(song_response.context["active_search_tags"], ())
        self.assertIsNone(song_response.context["genre_groups"][0][1][0]["add_url"])
        self.assertNotContains(song_response, "song-tag-badge-link--removable")


class SongModifyActionOnSongsPageTests(TestCase):
    def setUp(self):
        self.user_id = "12121212-1212-1212-1212-121212121212"
        DirectoryUserRecord.objects.create(
            id=self.user_id,
            username="songs.modify.user",
            first_name="Songs",
            last_name="Modify",
            email="songs.modify.user@example.test",
            enabled=True,
            email_verified=False,
        )
        self.non_validated_song = Song.objects.create(
            title="Chant libre",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        self.validated_song = Song.objects.create(
            title="Chant validé",
            subtitle="",
            description="",
            status=SongStatus.VALIDATED,
            licensed=False,
        )

    def _login(self, *, is_moderator=False):
        session = self.client.session
        session["lss_user"] = {
            "external_id": self.user_id,
            "username": "songs.modify.user",
            "email": "songs.modify.user@example.test",
            "first_name": "Songs",
            "last_name": "Modify",
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

    def test_non_moderator_sees_clickable_modify_link_for_non_validated_song(self):
        self._login()

        response = self.client.get(reverse("songs"))

        self.assertContains(
            response,
            'href="{}"'.format(
                reverse("modify_song", args=[self.non_validated_song.song_id])
            ),
            html=False,
        )
        self.assertNotContains(
            response,
            '<button type="button" class="site-action site-action--primary" disabled>Modifier</button>',
            html=False,
        )

    def test_non_moderator_does_not_see_modify_link_for_validated_song(self):
        self._login()

        response = self.client.get(reverse("songs"))

        self.assertNotContains(
            response,
            'href="{}"'.format(
                reverse("modify_song", args=[self.validated_song.song_id])
            ),
            html=False,
        )

    def test_smartphone_icon_points_to_shared_lyrics_template_route(self):
        self._login()

        response = self.client.get(reverse("songs"))

        self.assertContains(
            response,
            'href="{}"'.format(
                reverse(
                    "song_text", args=[self.non_validated_song.song_id, "full-chorus"]
                )
            ),
            html=False,
        )

    def test_moderator_sees_clickable_modify_link_for_validated_song(self):
        self._login(is_moderator=True)

        response = self.client.get(reverse("songs"))

        self.assertContains(
            response,
            'href="{}"'.format(
                reverse("modify_song", args=[self.validated_song.song_id])
            ),
            html=False,
        )
        self.assertNotContains(
            response,
            '<button type="button" class="site-action site-action--primary" disabled>Modifier</button>',
            html=False,
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
        self.assertEqual(created_song.slide_display_mode, SongSlideDisplayMode.SINGLE)
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
                self.assertContains(response, "data-song-meta-crud-form", html=False)
                self.assertContains(response, "data-unsaved-guard", html=False)
                self.assertContains(response, "/static/js/unsaved_changes.js")

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

    def test_song_link_defaults_to_score(self):
        link = SongLink.objects.create(song=self.song, link="https://default.test")
        self.assertEqual(link.type, SongLinkType.SCORE)

    def test_metadata_get_splits_selected_options_and_keeps_distinct_types(self):
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
        self.assertContains(response, "data-song-metadata-form", html=False)
        self.assertContains(response, "data-unsaved-guard", html=False)
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertEqual(response.context["metadata_links"][0].display_type, "audio")
        self.assertEqual(response.context["new_link_default_type"], SongLinkType.SCORE)
        self.assertEqual(
            response.context["link_type_options"],
            (
                ("score", "partition"),
                ("audio", "audio"),
                ("youtube", "YouTube"),
                ("web", "page Web"),
                ("internal", "lien interne - Lyrics Slide Show"),
            ),
        )
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
        html = response.content.decode("utf-8")
        self.assertLess(html.find(">partition</option>"), html.find(">audio</option>"))
        self.assertLess(html.find(">audio</option>"), html.find(">YouTube</option>"))
        self.assertLess(html.find(">YouTube</option>"), html.find(">page Web</option>"))
        self.assertLess(
            html.find(">page Web</option>"),
            html.find(">lien interne - Lyrics Slide Show</option>"),
        )
        self.assertIn('<option value="score" selected>partition</option>', html)
        self.assertNotIn(">lien</option>", html)
        self.assertNotIn(">lien interne</option>", html)

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
                "https://new.test": "score",
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
