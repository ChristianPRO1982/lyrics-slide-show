from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from app_group.models import Group, GroupStatus
from app_group.services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
)
from app_song.models import Song, SongStatus, Verse

from .models import Animation, AnimationSong, AnimationVerseOverride
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.render_bundle import build_animation_render_bundle


class PlaylistParsingTests(SimpleTestCase):
    def test_parse_ordered_mix_keeps_valid_tokens(self):
        tokens = parse_ordered_mix("asid:10| sid:20 |bad|sid:nope|foo:1|asid:11")
        self.assertEqual([(token.token_type, token.token_id) for token in tokens], [("asid", 10), ("sid", 20), ("asid", 11)])


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

    def _animation_payload(self) -> dict[str, str]:
        return {
            "action": "save_animation",
            "title": "Veillee",
            "description": "Description",
            "scheduled_at": timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M"),
            "text_color": "#ffffff",
            "bg_color": "#000000",
            "font_family": "Source Sans Pro",
            "font_size": "72",
            "horizontal_padding": "80",
            "background_asset_code": "",
        }

    def test_guest_can_crud_animation_in_open_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)

        create_response = self.client.post(reverse("new_animation"), self._animation_payload())
        self.assertEqual(create_response.status_code, 302)
        animation = Animation.objects.get()

        song = Song.objects.create(title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        playlist_response = self.client.post(
            reverse("edit_animation", args=[animation.animation_id]),
            {
                "action": "save_playlist",
                "ordered_mix": f"sid:{song.song_id}|sid:{song.song_id}",
            },
        )
        self.assertEqual(playlist_response.status_code, 302)
        self.assertEqual(AnimationSong.objects.filter(animation_id=animation.animation_id).count(), 2)

        items = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        ordered_mix = f"asid:{items[1].animation_song_id}|asid:{items[0].animation_song_id}"
        reorder_response = self.client.post(
            reverse("edit_animation", args=[animation.animation_id]),
            {
                "action": "save_playlist",
                "ordered_mix": ordered_mix,
            },
        )
        self.assertEqual(reorder_response.status_code, 302)
        reordered = list(AnimationSong.objects.filter(animation_id=animation.animation_id).order_by("position", "animation_song_id"))
        self.assertEqual(reordered[0].animation_song_id, items[1].animation_song_id)
        self.assertEqual([row.position for row in reordered], [2, 4])

        delete_response = self.client.post(reverse("delete_animation", args=[animation.animation_id]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(Animation.objects.count(), 0)

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
        self.assertEqual(response.status_code, 404)

        private_group = Group.objects.create(name="Private Group", status=GroupStatus.PRIVATE)
        self._select_group(private_group)
        response = self.client.get(reverse("animations"))
        self.assertEqual(response.status_code, 404)

    def test_song_selection_respects_guest_licensed_visibility(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        self._select_group(group)
        animation = Animation.objects.create(group=group, title="Session A", scheduled_at=timezone.now())
        visible_song = Song.objects.create(title="Visible", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False)
        Song.objects.create(title="Licensed", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=True)

        response = self.client.get(reverse("edit_animation", args=[animation.animation_id]), {"song_mode": "all"})
        self.assertEqual(response.status_code, 200)
        results = response.context["song_search"].results
        result_song_ids = {item.song.song_id for item in results}
        self.assertEqual(result_song_ids, {visible_song.song_id})


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
