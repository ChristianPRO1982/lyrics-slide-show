import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from app_group.models import Group, GroupStatus
from app_group.services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
)
from app_song.models import Song, SongStatus, Verse

from .forms import AnimationForm
from .font_catalog import GOOGLE_FONTS_STYLESHEET_HREF
from .models import Animation, AnimationSong, AnimationVerseOverride
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.render_bundle import build_animation_render_bundle


class PlaylistParsingTests(SimpleTestCase):
    def test_parse_ordered_mix_keeps_valid_tokens(self):
        tokens = parse_ordered_mix("asid:10| sid:20 |bad|sid:nope|foo:1|asid:11")
        self.assertEqual([(token.token_type, token.token_id) for token in tokens], [("asid", 10), ("sid", 20), ("asid", 11)])


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
        song = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        verse_one = Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="Line one")
        verse_two = Verse.objects.create(song=song, num=4, num_verse=2, chorus=False, text="Line two")
        animation_song = AnimationSong.objects.create(animation=animation, song=song, position=2)

        AnimationVerseOverride.objects.create(
            animation_song=animation_song,
            source_verse_id=verse_two.verse_id,
            is_visible=False,
        )

        bundle = build_animation_render_bundle(animation)
        source_verse_ids = [slide.source_verse_id for slide in bundle]

        self.assertIn(verse_one.verse_id, source_verse_ids)
        self.assertNotIn(verse_two.verse_id, source_verse_ids)


class AnimationViewsTests(TestCase):
    def _select_group(self, group: Group, secret: str | None = None) -> None:
        session = self.client.session
        session[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
        if secret:
            session[SELECTED_GROUP_SECRET_SESSION_KEY] = secret
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

        private_group = Group.objects.create(name="Private Group", status=GroupStatus.PRIVATE)
        self._select_group(private_group)
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_base_template_loads_google_fonts_stylesheet(self):
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 302)
        self._select_group(Group.objects.create(name="Open Group", status=GroupStatus.OPEN))
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, GOOGLE_FONTS_STYLESHEET_HREF)

    def test_modify_animation_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        response = self.client.get(reverse("modify_animation", args=[animation.animation_id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_modify_animation_refuses_animation_outside_selected_group(self):
        selected_group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=other_group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        self._select_group(selected_group)
        response = self.client.get(reverse("modify_animation", args=[animation.animation_id]))
        self.assertEqual(response.status_code, 404)

    def test_modify_animation_get_renders_form(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        verse = Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="Line one")
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        self._select_group(group)
        response = self.client.get(reverse("modify_animation", args=[animation.animation_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-animation-edit-form')
        self.assertContains(response, 'id="id_title"')
        self.assertContains(response, 'name="ordered_mix"')
        self.assertContains(response, 'name="songs_payload"')
        self.assertContains(response, f"asid:{item.animation_song_id}")
        self.assertContains(response, '"songCatalog"')
        self.assertContains(response, f"data-verse-id=\"{verse.verse_id}\"")

    def test_modify_animation_post_updates_song_and_verse_overrides_from_payload(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        verse_one = Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="Verse one")
        verse_two = Verse.objects.create(song=song, num=4, num_verse=2, chorus=False, text="Verse two")
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
                        "font_family_override": "Arial",
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
        self.assertEqual(item.font_family_override, "Arial")
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

    def test_modify_animation_post_updates_values(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_b = Song.objects.create(title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_c = Song.objects.create(title="Song C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
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
        item_a = AnimationSong.objects.create(animation=animation, song=song_a, position=2)
        item_b = AnimationSong.objects.create(animation=animation, song=song_b, position=4)
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
        self.assertEqual(response.headers["Location"], reverse("modify_animation", args=[animation.animation_id]))
        animation.refresh_from_db()
        self.assertEqual(animation.title, "Updated Session")
        self.assertEqual(animation.description, "Updated description")
        self.assertEqual(animation.text_color, "#112233")
        self.assertEqual(animation.bg_color, "#334455")
        self.assertEqual(animation.font_family, "Source Sans Pro")
        self.assertEqual(animation.font_size, 66)
        self.assertEqual(animation.horizontal_padding, 92)
        self.assertEqual(animation.background_asset_code, "bg-asset-01")
        reordered = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        self.assertEqual(reordered[0].animation_song_id, item_b.animation_song_id)
        self.assertEqual(reordered[1].song_id, song_c.song_id)
        self.assertEqual(reordered[2].animation_song_id, item_a.animation_song_id)
        self.assertEqual([row.position for row in reordered], [2, 4, 6])

    def test_modify_animation_post_invalid_renders_errors(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_b = Song.objects.create(title="Song B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        verse_a = Verse.objects.create(song=song_a, num=2, num_verse=1, chorus=False, text="Verse A")
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        item_a = AnimationSong.objects.create(animation=animation, song=song_a, position=2)
        item_b = AnimationSong.objects.create(animation=animation, song=song_b, position=4)
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
                                    "font_family_override": "Arial",
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
        persisted = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        self.assertEqual([row.animation_song_id for row in persisted], [item_a.animation_song_id, item_b.animation_song_id])
        item_a.refresh_from_db()
        self.assertIsNone(item_a.font_family_override)
        self.assertIsNone(item_a.font_size_override)
        self.assertIsNone(item_a.text_color_override)
        self.assertIsNone(item_a.bg_color_override)
        existing_override.refresh_from_db()
        self.assertFalse(existing_override.is_visible)

    def test_modify_animation_post_ignores_inaccessible_sid_token(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song_a = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_hidden = Song.objects.create(title="Hidden", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=True)
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
        item_a = AnimationSong.objects.create(animation=animation, song=song_a, position=2)

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
        persisted = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0].animation_song_id, item_a.animation_song_id)


class PlaylistSyncTests(TestCase):
    def test_sync_playlist_creates_keeps_and_deletes_with_normalized_positions(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(group=group, title="Session", scheduled_at=timezone.now())

        song_a = Song.objects.create(title="A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_b = Song.objects.create(title="B", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        song_c = Song.objects.create(title="C", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)

        item_one = AnimationSong.objects.create(animation=animation, song=song_a, position=20)
        item_two = AnimationSong.objects.create(animation=animation, song=song_b, position=60)

        tokens = parse_ordered_mix(f"asid:{item_two.animation_song_id}|sid:{song_c.song_id}")
        result = sync_animation_playlist(animation, tokens, allowed_song_ids={song_a.song_id, song_b.song_id, song_c.song_id})

        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.deleted_count, 1)
        persisted = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        self.assertEqual(len(persisted), 2)
        self.assertEqual([row.position for row in persisted], [2, 4])
        self.assertEqual(persisted[0].animation_song_id, item_two.animation_song_id)
