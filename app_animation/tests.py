import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from app_main.models import DirectoryUserRecord
from app_member.models import MemberPreferences
from app_group.models import Group, GroupStatus
from app_group.services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
)
from app_song.models import Song, SongFavorite, SongStatus, Verse

from .forms import AnimationForm
from .font_catalog import GOOGLE_FONTS_STYLESHEET_HREF
from .models import Animation, AnimationSong, AnimationVerseOverride
from . import views as animation_views
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.render_bundle import build_animation_render_bundle


class PlaylistParsingTests(SimpleTestCase):
    def test_parse_ordered_mix_keeps_valid_tokens(self):
        tokens = parse_ordered_mix("asid:10| sid:20 |bad|sid:nope|foo:1|asid:11")
        self.assertEqual(
            [(token.token_type, token.token_id) for token in tokens],
            [("asid", 10), ("sid", 20), ("asid", 11)],
        )


class AnimationFormFontValidationTests(SimpleTestCase):
    def test_animation_form_accepts_catalog_font(self):
        form = AnimationForm(
            data={
                "title": "Animation A",
                "description": "",
                "scheduled_at": "2026-05-06T10:00",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_animation_form_rejects_font_outside_catalog(self):
        form = AnimationForm(
            data={
                "title": "Animation B",
                "description": "",
                "scheduled_at": "2026-05-06T10:00",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Unknown Font",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("font_family", form.errors)


class AnimationRenderBundleTests(TestCase):
    def test_hidden_verse_override_removes_slide_from_bundle(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session A",
            scheduled_at=timezone.now(),
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse_one = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Line one"
        )
        verse_two = Verse.objects.create(
            song=song, num=4, num_verse=2, chorus=False, text="Line two"
        )
        animation_song = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )

        AnimationVerseOverride.objects.create(
            animation_song=animation_song,
            source_verse_id=verse_two.verse_id,
            is_visible=False,
        )

        bundle = build_animation_render_bundle(animation)
        source_verse_ids = [slide.source_verse_id for slide in bundle]

        self.assertIn(verse_one.verse_id, source_verse_ids)
        self.assertNotIn(verse_two.verse_id, source_verse_ids)

    def test_hidden_chorus_override_does_not_remove_chorus_from_bundle(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session B",
            scheduled_at=timezone.now(),
        )
        song = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        chorus = Verse.objects.create(
            song=song, num=2, num_verse=0, chorus=True, text="Refrain"
        )
        Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="Couplet"
        )
        animation_song = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )
        AnimationVerseOverride.objects.create(
            animation_song=animation_song,
            source_verse_id=chorus.verse_id,
            is_visible=False,
        )

        bundle = build_animation_render_bundle(animation)
        source_verse_ids = [slide.source_verse_id for slide in bundle]
        self.assertIn(chorus.verse_id, source_verse_ids)

    def test_bundle_marks_chorus_and_chorus_like_as_bold(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session C",
            scheduled_at=timezone.now(),
        )

        verse_song = Song.objects.create(
            title="Verse Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        verse = Verse.objects.create(
            song=verse_song, num=2, num_verse=1, chorus=False, text="Couplet"
        )

        chorus_song = Song.objects.create(
            title="Chorus Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus = Verse.objects.create(
            song=chorus_song, num=2, num_verse=0, chorus=True, text="Refrain"
        )

        chorus_like_song = Song.objects.create(
            title="Bridge Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus_like = Verse.objects.create(
            song=chorus_like_song,
            num=2,
            num_verse=1,
            chorus=False,
            chorus_like=True,
            prefix="Pont",
            text="Pont",
        )

        AnimationSong.objects.create(animation=animation, song=verse_song, position=2)
        AnimationSong.objects.create(animation=animation, song=chorus_song, position=4)
        AnimationSong.objects.create(
            animation=animation, song=chorus_like_song, position=6
        )

        bundle = build_animation_render_bundle(animation)
        slide_by_source_verse_id = {
            slide.source_verse_id: slide for slide in bundle if slide.source_verse_id
        }

        self.assertEqual(
            slide_by_source_verse_id[verse.verse_id].style.font_weight, "normal"
        )
        self.assertEqual(
            slide_by_source_verse_id[chorus.verse_id].style.font_weight, "bold"
        )
        self.assertEqual(
            slide_by_source_verse_id[chorus_like.verse_id].style.font_weight, "bold"
        )


class AnimationViewsTests(TestCase):
    def _select_group(self, group: Group, secret: str | None = None) -> None:
        session = self.client.session
        session[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
        if secret:
            session[SELECTED_GROUP_SECRET_SESSION_KEY] = secret
        session.save()

    def _login(self, user_id: str, username: str = "member.user") -> None:
        DirectoryUserRecord.objects.create(
            id=user_id,
            username=username,
            first_name="Member",
            last_name="User",
            email=f"{username}@example.test",
            enabled=True,
            email_verified=False,
        )
        session = self.client.session
        session["lss_user"] = {
            "external_id": user_id,
            "username": username,
            "email": f"{username}@example.test",
            "first_name": "Member",
            "last_name": "User",
            "is_moderator": False,
            "is_admin": False,
        }
        session.save()

    def test_guest_can_access_open_and_private_with_secret(self):
        open_group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(open_group)
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 200)

        secret_group = Group.objects.create(
            name="Secret Group",
            status=GroupStatus.PRIVATE,
            secret_ciphertext="secret-token",
        )
        self._select_group(secret_group, secret="secret-token")
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 200)

    def test_group_must_be_selected_and_private_without_access_is_refused(self):
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

        private_group = Group.objects.create(
            name="Private Group", status=GroupStatus.PRIVATE
        )
        self._select_group(private_group)
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_base_template_loads_google_fonts_stylesheet(self):
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 302)
        self._select_group(
            Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        )
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, GOOGLE_FONTS_STYLESHEET_HREF)

    def test_animations_page_contains_add_animation_link(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("add_animation"))

    def test_add_animation_requires_selected_group(self):
        response = self.client.get(reverse("add_animation"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_add_animation_get_renders_form(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        response = self.client.get(reverse("add_animation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-animation-create-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="scheduled_at"')

    def test_add_animation_post_creates_animation_in_selected_group(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        self._select_group(selected_group)
        response = self.client.post(
            reverse("add_animation"),
            data={
                "title": "Nouvelle animation",
                "description": "Description",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Animation.objects.get(title="Nouvelle animation")
        self.assertEqual(created.group_id, selected_group.group_id)
        self.assertNotEqual(created.group_id, other_group.group_id)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_animation", args=[created.animation_id]),
        )

    def test_modify_animation_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_modify_animation_refuses_animation_outside_selected_group(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=other_group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        self._select_group(selected_group)
        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_modify_animation_get_renders_form(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Line one"
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        self._select_group(group)
        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-animation-edit-form")
        self.assertContains(response, "data-unsaved-guard")
        self.assertContains(response, "/static/js/unsaved_changes.js")
        self.assertContains(response, 'id="id_title"')
        self.assertContains(response, 'name="ordered_mix"')
        self.assertContains(response, 'name="songs_payload"')
        self.assertContains(response, f"asid:{item.animation_song_id}")
        self.assertContains(response, '"songCatalog"')
        self.assertContains(response, f'data-verse-id="{verse.verse_id}"')
        self.assertContains(response, "data-song-text-swatch")
        self.assertContains(response, "data-song-bg-swatch")
        self.assertContains(response, "data-song-color-parent-trigger")
        self.assertContains(response, "data-song-style-parent-reset-trigger")
        self.assertContains(response, "unsavedChangesTitle")
        self.assertContains(response, "unsavedChangesMessage")

    def test_modify_animation_get_hides_chorus_rows_and_keeps_verse_rows(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        chorus = Verse.objects.create(
            song=song, num=2, num_verse=0, chorus=True, text="Refrain"
        )
        verse = Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="Couplet"
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        AnimationSong.objects.create(animation=animation, song=song, position=2)
        self._select_group(group)

        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'data-verse-id="{chorus.verse_id}"')
        self.assertContains(response, f'data-verse-id="{verse.verse_id}"')

    def test_modify_animation_get_member_exposes_advanced_favorites_and_all_song_catalogs(
        self,
    ):
        user_id = "88888888-8888-8888-8888-888888888888"
        self._login(user_id=user_id, username="catalog.member")
        MemberPreferences.objects.create(
            member_id=user_id,
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

        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        advanced_song = Song.objects.create(
            title="Saved Search Match",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        favorite_song = Song.objects.create(
            title="Favorite Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Song.objects.create(
            title="Other Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        SongFavorite.objects.create(song=favorite_song, member_id=user_id)

        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        popup_data = response.context["popup_data"]

        self.assertTrue(popup_data["canUseMemberSongTabs"])
        self.assertIn(
            {"id": advanced_song.song_id, "title": advanced_song.display_title},
            popup_data["advancedSongCatalog"],
        )
        self.assertNotIn(
            {"id": favorite_song.song_id, "title": favorite_song.display_title},
            popup_data["advancedSongCatalog"],
        )
        self.assertIn(
            {"id": favorite_song.song_id, "title": favorite_song.display_title},
            popup_data["favoriteSongCatalog"],
        )
        self.assertEqual(len(popup_data["allSongCatalog"]), 3)

    def test_modify_animation_get_guest_exposes_only_accessible_all_song_catalog(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        visible_song = Song.objects.create(
            title="Visible",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        hidden_song = Song.objects.create(
            title="Hidden Licensed",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=True,
        )

        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        popup_data = response.context["popup_data"]

        self.assertFalse(popup_data["canUseMemberSongTabs"])
        self.assertEqual(popup_data["advancedSongCatalog"], [])
        self.assertEqual(popup_data["favoriteSongCatalog"], [])
        self.assertIn(
            {"id": visible_song.song_id, "title": visible_song.display_title},
            popup_data["allSongCatalog"],
        )
        self.assertNotIn(
            {"id": hidden_song.song_id, "title": hidden_song.display_title},
            popup_data["allSongCatalog"],
        )

    def test_modify_animation_post_updates_song_and_verse_overrides_from_payload(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse_one = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse one"
        )
        verse_two = Verse.objects.create(
            song=song, num=4, num_verse=2, chorus=False, text="Verse two"
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=60,
            horizontal_padding=80,
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)

        payload = {
            "items": [
                {
                    "animation_song_id": item.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse_one.verse_id],
                    "song_style": {
                        "font_family_override": "Source Sans Pro",
                        "font_size_delta": 10,
                        "text_color_override": "#123456",
                        "bg_color_override": "#654321",
                    },
                    "verse_styles": {
                        str(verse_one.verse_id): {
                            "font_family_override": "Ubuntu",
                            "font_size_delta": -5,
                            "text_color_override": "#AABBCC",
                            "bg_color_override": "#112233",
                        },
                    },
                }
            ]
        }

        self._select_group(group)
        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "Session",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "60",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item.animation_song_id}",
                "songs_payload": json.dumps(payload),
            },
        )
        self.assertEqual(response.status_code, 302)

        item.refresh_from_db()
        self.assertEqual(item.font_family_override, "Source Sans Pro")
        self.assertEqual(item.font_size_override, 70)
        self.assertEqual(item.text_color_override, "#123456")
        self.assertEqual(item.bg_color_override, "#654321")

        verse_one_override = AnimationVerseOverride.objects.get(
            animation_song=item,
            source_verse_id=verse_one.verse_id,
        )
        self.assertTrue(verse_one_override.is_visible)
        self.assertEqual(verse_one_override.font_family_override, "Ubuntu")
        self.assertEqual(verse_one_override.font_size_override, 65)
        self.assertEqual(verse_one_override.text_color_override, "#AABBCC")
        self.assertEqual(verse_one_override.bg_color_override, "#112233")

        verse_two_override = AnimationVerseOverride.objects.get(
            animation_song=item,
            source_verse_id=verse_two.verse_id,
        )
        self.assertFalse(verse_two_override.is_visible)
        self.assertIsNone(verse_two_override.font_family_override)
        self.assertIsNone(verse_two_override.font_size_override)
        self.assertIsNone(verse_two_override.text_color_override)
        self.assertIsNone(verse_two_override.bg_color_override)

    def test_modify_animation_post_forces_chorus_visibility_even_if_payload_hides_it(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song D", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        chorus = Verse.objects.create(
            song=song, num=2, num_verse=0, chorus=True, text="Refrain"
        )
        verse = Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="Couplet"
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=60,
            horizontal_padding=80,
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)

        payload = {
            "items": [
                {
                    "animation_song_id": item.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse.verse_id],
                    "song_style": {},
                    "verse_styles": {},
                }
            ]
        }

        self._select_group(group)
        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "Session",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "60",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item.animation_song_id}",
                "songs_payload": json.dumps(payload),
            },
        )
        self.assertEqual(response.status_code, 302)

        chorus_override = AnimationVerseOverride.objects.filter(
            animation_song=item,
            source_verse_id=chorus.verse_id,
        ).first()
        if chorus_override is not None:
            self.assertTrue(chorus_override.is_visible)

    def test_modify_animation_post_updates_values(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_b = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_c = Song.objects.create(
            title="Song C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            description="Old",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=72,
            horizontal_padding=80,
            background_asset_code=None,
        )
        item_a = AnimationSong.objects.create(
            animation=animation, song=song_a, position=2
        )
        item_b = AnimationSong.objects.create(
            animation=animation, song=song_b, position=4
        )
        self._select_group(group)
        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "Updated Session",
                "description": "Updated description",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#112233",
                "bg_color": "#334455",
                "font_family": "Source Sans Pro",
                "font_size": "66",
                "horizontal_padding": "92",
                "background_asset_code": "bg-asset-01",
                "ordered_mix": f"asid:{item_b.animation_song_id}|sid:{song_c.song_id}|asid:{item_a.animation_song_id}",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_animation", args=[animation.animation_id]),
        )
        animation.refresh_from_db()
        self.assertEqual(animation.title, "Updated Session")
        self.assertEqual(animation.description, "Updated description")
        self.assertEqual(animation.text_color, "#112233")
        self.assertEqual(animation.bg_color, "#334455")
        self.assertEqual(animation.font_family, "Source Sans Pro")
        self.assertEqual(animation.font_size, 66)
        self.assertEqual(animation.horizontal_padding, 92)
        self.assertEqual(animation.background_asset_code, "bg-asset-01")
        reordered = list(
            AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(reordered[0].animation_song_id, item_b.animation_song_id)
        self.assertEqual(reordered[1].song_id, song_c.song_id)
        self.assertEqual(reordered[2].animation_song_id, item_a.animation_song_id)
        self.assertEqual([row.position for row in reordered], [2, 4, 6])

    def test_modify_animation_post_invalid_renders_errors(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_b = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse_a = Verse.objects.create(
            song=song_a, num=2, num_verse=1, chorus=False, text="Verse A"
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        item_a = AnimationSong.objects.create(
            animation=animation, song=song_a, position=2
        )
        item_b = AnimationSong.objects.create(
            animation=animation, song=song_b, position=4
        )
        existing_override = AnimationVerseOverride.objects.create(
            animation_song=item_a,
            source_verse_id=verse_a.verse_id,
            is_visible=False,
        )
        self._select_group(group)
        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Unknown Font",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item_b.animation_song_id}|asid:{item_a.animation_song_id}",
                "songs_payload": json.dumps(
                    {
                        "items": [
                            {
                                "animation_song_id": item_a.animation_song_id,
                                "song_id": song_a.song_id,
                                "visible_verse_ids": [verse_a.verse_id],
                                "song_style": {
                                    "font_family_override": "Source Sans Pro",
                                    "font_size_delta": 15,
                                    "text_color_override": "#111111",
                                    "bg_color_override": "#222222",
                                },
                                "verse_styles": {},
                            }
                        ]
                    }
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Des erreurs empêchent l'enregistrement")
        persisted = list(
            AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(
            [row.animation_song_id for row in persisted],
            [item_a.animation_song_id, item_b.animation_song_id],
        )
        item_a.refresh_from_db()
        self.assertIsNone(item_a.font_family_override)
        self.assertIsNone(item_a.font_size_override)
        self.assertIsNone(item_a.text_color_override)
        self.assertIsNone(item_a.bg_color_override)
        existing_override.refresh_from_db()
        self.assertFalse(existing_override.is_visible)

    def test_modify_animation_post_ignores_inaccessible_sid_token(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_hidden = Song.objects.create(
            title="Hidden", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=True
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=72,
            horizontal_padding=80,
        )
        item_a = AnimationSong.objects.create(
            animation=animation, song=song_a, position=2
        )

        self._select_group(group)
        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "Session",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"sid:{song_hidden.song_id}|asid:{item_a.animation_song_id}",
            },
        )
        self.assertEqual(response.status_code, 302)
        persisted = list(
            AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].animation_song_id, item_a.animation_song_id)

    def test_modify_animation_post_allows_sid_song_present_in_all_but_not_in_advanced_search(
        self,
    ):
        user_id = "99999999-9999-9999-9999-999999999999"
        self._login(user_id=user_id, username="advanced.filter.member")
        MemberPreferences.objects.create(
            member_id=user_id,
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

        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        song_saved = Song.objects.create(
            title="Saved Search Match",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        song_all_only = Song.objects.create(
            title="All Catalog Only",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=72,
            horizontal_padding=80,
        )
        item_saved = AnimationSong.objects.create(
            animation=animation, song=song_saved, position=2
        )

        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "Session",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item_saved.animation_song_id}|sid:{song_all_only.song_id}",
            },
        )
        self.assertEqual(response.status_code, 302)

        persisted = list(
            AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[0].animation_song_id, item_saved.animation_song_id)
        self.assertEqual(persisted[1].song_id, song_all_only.song_id)

    def test_modify_animation_tools_contains_link_to_lyrics_slide_show(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)

        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("lyrics_slide_show", args=[animation.animation_id])
        )

    def test_lyrics_slide_show_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_lyrics_slide_show_refuses_animation_outside_selected_group(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=other_group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(selected_group)

        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_lyrics_slide_show_display_requires_valid_session_id(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)

        response = self.client.get(
            reverse("lyrics_slide_show_display", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            reverse("lyrics_slide_show_display", args=[animation.animation_id]),
            data={"session": "invalid session"},
        )
        self.assertEqual(response.status_code, 404)

    def test_lyrics_slide_show_display_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        response = self.client.get(
            reverse("lyrics_slide_show_display", args=[animation.animation_id]),
            data={"session": "abcd1234-valid"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_lyrics_slide_show_display_refuses_animation_outside_selected_group(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=other_group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(selected_group)

        response = self.client.get(
            reverse("lyrics_slide_show_display", args=[animation.animation_id]),
            data={"session": "abcd1234-valid"},
        )
        self.assertEqual(response.status_code, 404)

    def test_lyrics_slide_show_display_loads_google_fonts_stylesheet(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)

        response = self.client.get(
            reverse("lyrics_slide_show_display", args=[animation.animation_id]),
            data={"session": "abcd1234-valid"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, GOOGLE_FONTS_STYLESHEET_HREF.replace("&", "&amp;")
        )

    def test_lyrics_slide_show_public_is_accessible_without_group_selection(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        response = self.client.get(
            reverse("lyrics_slide_show_public", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-lyrics-public-root")

    def test_lyrics_slide_show_master_context_contains_runtime_payload_and_qr(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse = Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=False,
            text="Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.",
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        animation_song = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        self.assertEqual(payload["animationId"], animation.animation_id)
        self.assertIn("slides", payload)
        self.assertTrue(
            payload["publicUrl"].endswith(
                reverse("lyrics_slide_show_public", args=[animation.animation_id])
            )
        )
        if animation_views.qrcode is None:
            self.assertEqual(payload["qrCodePngBase64"], "")
        else:
            self.assertTrue(payload["qrCodePngBase64"])

        slides = payload["slides"]
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]["animationSongId"], animation_song.animation_song_id)
        self.assertEqual(slides[0]["sourceVerseId"], verse.verse_id)
        self.assertIn("[...]", slides[0]["excerpt"])
        self.assertLessEqual(len(slides[0]["excerpt"]), 55)
        self.assertEqual(
            slides[0]["style"],
            {
                "textColor": "#FFFFFF",
                "bgColor": "#000000",
                "fontFamily": "Source Sans Pro",
                "fontWeight": "normal",
                "fontSize": 72,
                "horizontalPadding": 80,
                "backgroundAssetCode": "",
                "backgroundUrl": "",
            },
        )

    def test_lyrics_slide_show_runtime_payload_exposes_resolved_style_and_font_weight(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#123456",
            bg_color="#654321",
            font_family="Ubuntu",
            font_size=72,
            horizontal_padding=24,
        )

        verse_song = Song.objects.create(
            title="Verse Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        verse = Verse.objects.create(
            song=verse_song, num=2, num_verse=1, chorus=False, text="Couplet"
        )
        verse_item = AnimationSong.objects.create(
            animation=animation, song=verse_song, position=2
        )

        chorus_song = Song.objects.create(
            title="Chorus Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus = Verse.objects.create(
            song=chorus_song, num=2, num_verse=0, chorus=True, text="Refrain"
        )
        chorus_item = AnimationSong.objects.create(
            animation=animation,
            song=chorus_song,
            position=4,
            font_family_override="Raleway",
            font_size_override=68,
        )

        chorus_like_song = Song.objects.create(
            title="Bridge Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus_like = Verse.objects.create(
            song=chorus_like_song,
            num=2,
            num_verse=1,
            chorus=False,
            chorus_like=True,
            prefix="Pont",
            text="Pont",
        )
        chorus_like_item = AnimationSong.objects.create(
            animation=animation, song=chorus_like_song, position=6
        )
        AnimationVerseOverride.objects.create(
            animation_song=chorus_like_item,
            source_verse_id=chorus_like.verse_id,
            font_family_override="Anton",
            font_size_override=64,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        slides = response.context["runtime_payload"]["slides"]
        slide_by_animation_song_id = {
            slide["animationSongId"]: slide for slide in slides
        }

        self.assertEqual(
            slide_by_animation_song_id[verse_item.animation_song_id]["style"],
            {
                "textColor": "#123456",
                "bgColor": "#654321",
                "fontFamily": "Ubuntu",
                "fontWeight": "normal",
                "fontSize": 72,
                "horizontalPadding": 24,
                "backgroundAssetCode": "",
                "backgroundUrl": "",
            },
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_item.animation_song_id]["style"][
                "fontWeight"
            ],
            "bold",
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_item.animation_song_id]["style"][
                "fontFamily"
            ],
            "Raleway",
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_item.animation_song_id]["style"][
                "fontSize"
            ],
            68,
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_like_item.animation_song_id]["style"][
                "fontWeight"
            ],
            "bold",
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_like_item.animation_song_id]["style"][
                "fontFamily"
            ],
            "Anton",
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_like_item.animation_song_id]["style"][
                "fontSize"
            ],
            64,
        )

        self.assertEqual(
            slide_by_animation_song_id[verse_item.animation_song_id]["sourceVerseId"],
            verse.verse_id,
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_item.animation_song_id]["sourceVerseId"],
            chorus.verse_id,
        )
        self.assertEqual(
            slide_by_animation_song_id[chorus_like_item.animation_song_id][
                "sourceVerseId"
            ],
            chorus_like.verse_id,
        )

    def test_lyrics_slide_show_runtime_payload_preserves_zero_animation_padding(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            horizontal_padding=0,
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="Texte")
        animation_song = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        slide = next(
            item
            for item in response.context["runtime_payload"]["slides"]
            if item["animationSongId"] == animation_song.animation_song_id
        )
        self.assertEqual(slide["style"]["horizontalPadding"], 0)

    def test_lyrics_slide_show_runtime_payload_preserves_zero_song_and_verse_padding(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            horizontal_padding=24,
        )

        song_with_song_override = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_override_verse = Verse.objects.create(
            song=song_with_song_override,
            num=2,
            num_verse=1,
            chorus=False,
            text="Song override",
        )
        song_override_item = AnimationSong.objects.create(
            animation=animation,
            song=song_with_song_override,
            position=2,
            horizontal_padding_override=0,
        )

        song_with_verse_override = Song.objects.create(
            title="Song C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse_override_verse = Verse.objects.create(
            song=song_with_verse_override,
            num=2,
            num_verse=1,
            chorus=False,
            text="Verse override",
        )
        verse_override_item = AnimationSong.objects.create(
            animation=animation,
            song=song_with_verse_override,
            position=4,
            horizontal_padding_override=36,
        )
        AnimationVerseOverride.objects.create(
            animation_song=verse_override_item,
            source_verse_id=verse_override_verse.verse_id,
            horizontal_padding_override=0,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        slides = response.context["runtime_payload"]["slides"]
        slide_by_animation_song_id = {
            slide["animationSongId"]: slide for slide in slides
        }
        self.assertEqual(
            slide_by_animation_song_id[song_override_item.animation_song_id]["style"][
                "horizontalPadding"
            ],
            0,
        )
        self.assertEqual(
            slide_by_animation_song_id[verse_override_item.animation_song_id]["style"][
                "horizontalPadding"
            ],
            0,
        )
        self.assertEqual(
            slide_by_animation_song_id[song_override_item.animation_song_id][
                "sourceVerseId"
            ],
            song_override_verse.verse_id,
        )
        self.assertEqual(
            slide_by_animation_song_id[verse_override_item.animation_song_id][
                "sourceVerseId"
            ],
            verse_override_verse.verse_id,
        )

    def test_lyrics_slide_show_runtime_matches_render_bundle_order_and_visibility(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse_visible = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Visible"
        )
        verse_hidden = Verse.objects.create(
            song=song, num=4, num_verse=2, chorus=False, text="Hidden"
        )
        animation_song = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )
        AnimationVerseOverride.objects.create(
            animation_song=animation_song,
            source_verse_id=verse_hidden.verse_id,
            is_visible=False,
        )

        expected_bundle = build_animation_render_bundle(animation)

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload_slides = response.context["runtime_payload"]["slides"]
        self.assertEqual(len(payload_slides), len(expected_bundle))
        self.assertEqual(
            [slide["sourceVerseId"] for slide in payload_slides],
            [entry.source_verse_id for entry in expected_bundle],
        )
        self.assertIn(
            verse_visible.verse_id, [slide["sourceVerseId"] for slide in payload_slides]
        )
        self.assertNotIn(
            verse_hidden.verse_id, [slide["sourceVerseId"] for slide in payload_slides]
        )

    def test_lyrics_slide_show_runtime_payload_keeps_zero_index_for_first_song(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song_one = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_two = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=song_one, num=2, num_verse=1, chorus=False, text="Couplet A"
        )
        Verse.objects.create(
            song=song_two, num=2, num_verse=1, chorus=False, text="Couplet B"
        )
        item_one = AnimationSong.objects.create(
            animation=animation, song=song_one, position=2
        )
        AnimationSong.objects.create(animation=animation, song=song_two, position=4)

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        self.assertGreaterEqual(len(payload["slides"]), 1)
        self.assertEqual(payload["slides"][0]["globalIndex"], 0)

        first_song_entry = next(
            (
                entry
                for entry in payload["songs"]
                if entry["animationSongId"] == item_one.animation_song_id
            ),
            None,
        )
        self.assertIsNotNone(first_song_entry)
        self.assertGreaterEqual(len(first_song_entry["slideIndexes"]), 1)
        self.assertEqual(first_song_entry["slideIndexes"][0], 0)
        self.assertIn(0, first_song_entry["slideIndexes"])

    def test_lyrics_slide_show_runtime_payload_has_contiguous_global_indexes(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song_one = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_two = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=song_one, num=2, num_verse=1, chorus=False, text="Couplet A1"
        )
        Verse.objects.create(
            song=song_one, num=4, num_verse=2, chorus=False, text="Couplet A2"
        )
        Verse.objects.create(
            song=song_two, num=2, num_verse=1, chorus=False, text="Couplet B1"
        )
        Verse.objects.create(
            song=song_two, num=4, num_verse=2, chorus=False, text="Couplet B2"
        )
        AnimationSong.objects.create(animation=animation, song=song_one, position=2)
        AnimationSong.objects.create(animation=animation, song=song_two, position=4)

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        global_indexes = [slide["globalIndex"] for slide in payload["slides"]]
        self.assertEqual(global_indexes, list(range(len(global_indexes))))

        max_index = len(payload["slides"])
        for song_entry in payload["songs"]:
            self.assertEqual(
                song_entry["slideIndexes"], sorted(song_entry["slideIndexes"])
            )
            self.assertEqual(
                song_entry["chorusIndexes"], sorted(song_entry["chorusIndexes"])
            )
            self.assertEqual(
                len(song_entry["slideIndexes"]), len(set(song_entry["slideIndexes"]))
            )
            self.assertEqual(
                len(song_entry["chorusIndexes"]), len(set(song_entry["chorusIndexes"]))
            )
            for index in song_entry["slideIndexes"]:
                self.assertGreaterEqual(index, 0)
                self.assertLess(index, max_index)
            for index in song_entry["chorusIndexes"]:
                self.assertGreaterEqual(index, 0)
                self.assertLess(index, max_index)

    def test_lyrics_slide_show_contains_floating_navigation_and_song_targets(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song_one = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_two = Song.objects.create(
            title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=song_one, num=2, num_verse=1, chorus=False, text="Couplet A"
        )
        Verse.objects.create(
            song=song_two, num=2, num_verse=1, chorus=False, text="Couplet B"
        )
        item_one = AnimationSong.objects.create(
            animation=animation, song=song_one, position=2
        )
        item_two = AnimationSong.objects.create(
            animation=animation, song=song_two, position=4
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-lyrics-floating-nav")
        self.assertContains(response, "data-lyrics-floating-slides-link")
        self.assertContains(response, 'title="Diapo en cours / Diapo suivante"')
        self.assertContains(response, 'id="lyrics-master-slides-anchor"')
        self.assertContains(
            response, f'id="lyrics-song-group-{item_one.animation_song_id}"'
        )
        self.assertContains(
            response, f'id="lyrics-song-group-{item_two.animation_song_id}"'
        )

        content = response.content.decode("utf-8")
        context_pos = content.index("lyrics-master-context")
        slides_anchor_pos = content.index("data-lyrics-slides-anchor")
        toolbar_pos = content.index("lyrics-master-toolbar")
        self.assertLess(context_pos, slides_anchor_pos)
        self.assertLess(slides_anchor_pos, toolbar_pos)


class PlaylistSyncTests(TestCase):
    def test_sync_playlist_creates_keeps_and_deletes_with_normalized_positions(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        song_a = Song.objects.create(
            title="A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_b = Song.objects.create(
            title="B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        song_c = Song.objects.create(
            title="C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )

        AnimationSong.objects.create(animation=animation, song=song_a, position=20)
        item_two = AnimationSong.objects.create(
            animation=animation, song=song_b, position=60
        )

        tokens = parse_ordered_mix(
            f"asid:{item_two.animation_song_id}|sid:{song_c.song_id}"
        )
        result = sync_animation_playlist(
            animation,
            tokens,
            allowed_song_ids={song_a.song_id, song_b.song_id, song_c.song_id},
        )

        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.deleted_count, 1)
        persisted = list(
            AnimationSong.objects.filter(animation_id=animation.animation_id).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(len(persisted), 2)
        self.assertEqual([row.position for row in persisted], [2, 4])
        self.assertEqual(persisted[0].animation_song_id, item_two.animation_song_id)
