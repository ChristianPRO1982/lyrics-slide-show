from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from app_main.models import DirectoryUserRecord
from app_member.models import MemberRole

from .models import Song, Verse
from .rendering import (
    ChorusRenderMode,
    RenderedSongBlockKind,
    SongRenderSettings,
    build_song_full_title,
    build_song_full_title_with_tags,
    build_song_text_artifacts,
    render_song_blocks,
    render_song_text,
)
from .search import SongSearchParams, build_song_search_query, get_active_song_search


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

        self.assertEqual([block.kind for block in blocks], [
            RenderedSongBlockKind.CHORUS,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.CHORUS,
        ])
        self.assertEqual(blocks[0].label, "Refrain")
        self.assertTrue(blocks[2].is_repeated_chorus)

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

        self.assertEqual([block.kind for block in blocks], [
            RenderedSongBlockKind.CHORUS,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.CHORUS,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.CHORUS,
        ])

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

        self.assertEqual([block.kind for block in blocks], [
            RenderedSongBlockKind.CHORUS,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.VERSE,
        ])

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

        self.assertEqual([block.kind for block in blocks], [
            RenderedSongBlockKind.CHORUS,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.VERSE,
            RenderedSongBlockKind.CHORUS,
        ])

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
                make_verse(2, 4, "Pont final", num_verse=1, chorus_like=True, prefix="Pont"),
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
                make_verse(1, 2, "Suite du couplet", num_verse=1, notcontinuenumbering=True),
            ],
        )

        self.assertIn("Suite du couplet", text)
        self.assertNotIn("Couplet 1", text)


class SongSearchParamsTests(SimpleTestCase):
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


class SongTextArtifactsTests(SimpleTestCase):
    settings = SongRenderSettings(
        chorus_prefix="Refrain",
        verse_prefix1="",
        verse_prefix2=".",
        chorus_like_default_prefix="Refrain",
    )

    def test_full_title_and_title_with_tags(self):
        song = Song(song_id=1, title="Gloire", subtitle="Louange", status=0, licensed=False)
        self.assertEqual(build_song_full_title(song), "Gloire - Louange")
        self.assertEqual(build_song_full_title_with_tags(song), "Gloire - Louange")

        song.status = 1
        self.assertEqual(build_song_full_title_with_tags(song), "Gloire - Louange ✔️")

        song.status = 2
        song.licensed = True
        self.assertEqual(build_song_full_title_with_tags(song), "Gloire - Louange ✔️⁉️ 📄")

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
        self.assertIn("<table class=\"song-lyrics-table\">", artifacts.short_text_html)
        self.assertEqual(artifacts.short_text_html.count("<th scope=\"row\">Refrain</th><td>Refrain</td>"), 1)
        self.assertEqual(artifacts.long_text_html.count("<th scope=\"row\">Refrain</th><td>Refrain</td>"), 3)

    def test_followed_skips_chorus_reinsertion(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Refrain", chorus=True, num_verse=0),
                make_verse(2, 4, "Couplet un", num_verse=1, followed=True),
            ],
        )
        self.assertEqual(artifacts.long_text_html.count("<th scope=\"row\">Refrain</th><td>Refrain</td>"), 1)

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
        self.assertEqual(artifacts.long_text_html.count("<th scope=\"row\">Refrain</th><td>Refrain</td>"), 3)

    def test_chorus_like_uses_optional_prefix_and_bold(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[make_verse(1, 2, "Pont final", chorus_like=True, prefix="Pont")],
        )
        self.assertIn("<th scope=\"row\">Pont</th><td>Pont final</td>", artifacts.long_text_html)

        artifacts_no_prefix = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[make_verse(1, 2, "Pont final", chorus_like=True, prefix="")],
        )
        self.assertIn("<th scope=\"row\">Refrain</th><td>Pont final</td>", artifacts_no_prefix.long_text_html)

    def test_not_continue_numbering_hides_verse_label(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=SongRenderSettings(
                chorus_prefix="Refrain",
                verse_prefix1="Couplet ",
                verse_prefix2="",
                chorus_like_default_prefix="Refrain",
            ),
            verses=[make_verse(1, 2, "Suite du couplet", num_verse=1, notcontinuenumbering=True)],
        )
        self.assertIn("Suite du couplet", artifacts.long_text_html)
        self.assertIn("<th scope=\"row\"></th><td>Suite du couplet</td>", artifacts.long_text_html)

    def test_chorus_multi_blocks_are_joined_with_blank_line(self):
        artifacts = build_song_text_artifacts(
            make_song(),
            settings=self.settings,
            verses=[
                make_verse(1, 2, "Ligne A", chorus=True, num_verse=0),
                make_verse(2, 4, "Ligne B", chorus=True, num_verse=0),
            ],
        )
        self.assertIn("<th scope=\"row\">Refrain</th><td>Ligne A<br><br>Ligne B</td>", artifacts.long_text_html)

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

    def test_song_view_provides_tagged_navigation_title_and_text_without_title_duplication(self):
        response = self.client.get(reverse("song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title_complete"], "Le Sud - Nino Ferrer")
        self.assertEqual(response.context["title_complete_with_tags"], "Le Sud - Nino Ferrer ✔️ 📄")
        self.assertNotIn("Le Sud - Nino Ferrer", response.context["text_long_html"])

    def test_song_text_print_page_uses_full_title_without_tags(self):
        response = self.client.get(reverse("song_text", args=[self.song.song_id, "full-chorus"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title_complete"], "Le Sud - Nino Ferrer")
        self.assertContains(response, "<title>Le Sud - Nino Ferrer</title>", html=True)
        self.assertContains(response, "<th scope=\"row\">Refrain</th><td>On dirait le Sud</td>", html=False)

    def test_song_text_plain_endpoint_returns_html_fragment(self):
        response = self.client.get(reverse("song_text", args=[self.song.song_id, "single-chorus"]) + "?format=plain")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("text/plain"))
        body = response.content.decode("utf-8")
        self.assertIn("<th scope=\"row\">Refrain</th><td>On dirait le Sud</td>", body)
        self.assertNotIn("Le Sud - Nino Ferrer", body)


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
        self.assertContains(response, '<strong class="song-edit-block-drag-label">Couplet 1</strong>', html=False)
        self.assertContains(response, '<strong class="song-edit-block-drag-label">Refrain</strong>', html=False)
        self.assertContains(response, '<span class="song-edit-block-drag-text">Couplet original</span>', html=False)
        self.assertContains(response, '<span class="song-edit-block-drag-text">Refrain original</span>', html=False)

    def test_member_cannot_access_validated_song(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login()
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 404)

    def test_moderator_cannot_access_validated_song(self):
        self.song.status = 1
        self.song.save(update_fields=["status"])
        self._login(is_moderator=True)
        response = self.client.get(reverse("modify_song", args=[self.song.song_id]))
        self.assertEqual(response.status_code, 404)

    def test_post_save_updates_identity_and_verses(self):
        self._login()
        response = self.client.post(reverse("modify_song", args=[self.song.song_id]), data=self._base_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("modify_song", args=[self.song.song_id]))

        self.song.refresh_from_db()
        self.assertEqual(self.song.title, "Nouveau\u00A0: titre\u00A0?")
        self.assertEqual(self.song.subtitle, "Sous titre")
        self.assertEqual(self.song.description, "Ligne 1\u00A0;\n\nLigne 2\u00A0!")

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
        self.assertEqual(verses[2].prefix, "Pont final\u00A0;")

    def test_post_save_deletes_blocks_marked_for_deletion(self):
        self._login()
        payload = self._base_payload()
        payload["blocks[b][delete]"] = "1"
        response = self.client.post(reverse("modify_song", args=[self.song.song_id]), data=payload)
        self.assertEqual(response.status_code, 302)

        verses = list(self.song.verses.all())
        self.assertEqual(len(verses), 2)
        self.assertFalse(any(item.chorus for item in verses))

    def test_save_and_exit_redirects_to_song_page(self):
        self._login()
        payload = self._base_payload()
        payload["submit_intent"] = "save_and_exit"
        response = self.client.post(reverse("modify_song", args=[self.song.song_id]), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("song", args=[self.song.song_id]))

    def test_save_and_exit_uses_safe_next_url(self):
        self._login()
        payload = self._base_payload()
        payload["submit_intent"] = "save_and_exit"
        payload["next_url"] = reverse("songs")
        response = self.client.post(reverse("modify_song", args=[self.song.song_id]), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("songs"))

    def test_preview_endpoint_returns_current_unsaved_render(self):
        self._login()
        payload = self._base_payload()
        payload["title"] = "Titre preview"
        response = self.client.post(reverse("modify_song_preview", args=[self.song.song_id]), data=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Titre preview", data["title"])
        self.assertIn("Couplet 1", data["markdown"])
        self.assertIn("Refrain", data["markdown"])
