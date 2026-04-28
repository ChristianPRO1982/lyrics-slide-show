from django.test import SimpleTestCase

from app_song.models import Song, Verse
from app_song.rendering import SongRenderSettings

from .song_text_artifacts import get_song_text_artifacts


class SongTextArtifactsAdapterTests(SimpleTestCase):
    def test_adapter_returns_shared_song_text_artifacts(self):
        song = Song(song_id=10, title="Le Sud", subtitle="Nino Ferrer", status=0, licensed=False)
        verses = [
            Verse(verse_id=1, num=2, num_verse=0, chorus=True, text="On dirait le Sud"),
            Verse(verse_id=2, num=4, num_verse=1, chorus=False, text="C'est un endroit"),
        ]
        settings = SongRenderSettings(
            chorus_prefix="Refrain",
            verse_prefix1="",
            verse_prefix2=".",
            chorus_like_default_prefix="Refrain",
        )

        artifacts = get_song_text_artifacts(song, settings=settings, verses=verses)

        self.assertEqual(artifacts.full_title, "Le Sud - Nino Ferrer")
        self.assertIn("<th scope=\"row\">Refrain</th><td>On dirait le Sud</td>", artifacts.long_text_html)
        self.assertIn("<th scope=\"row\">1.</th><td>C&#x27;est un endroit</td>", artifacts.short_text_html)
