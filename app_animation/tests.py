import json
import shutil
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app_main.models import DirectoryUserRecord
from app_member.models import MemberPreferences, MemberRole
from app_group.models import Group, GroupStatus
from app_group.services import (
    SELECTED_GROUP_ID_SESSION_KEY,
    SELECTED_GROUP_SECRET_SESSION_KEY,
)
from app_song.models import Song, SongFavorite, SongStatus, Verse

from .forms import AnimationForm
from .font_catalog import GOOGLE_FONTS_STYLESHEET_HREF
from .models import (
    Animation,
    AnimationRemoteShortcut,
    AnimationSong,
    AnimationVerseOverride,
    BackgroundImage,
    BackgroundImageStatus,
)
from .services.background_images import (
    STORAGE_FILENAME_ALPHABET,
    build_background_context_slug,
    generate_storage_name,
    resolve_background_asset_url,
)
from .utils import _open_image, validate_image
from . import views as animation_views
from .services.playlist import parse_ordered_mix, sync_animation_playlist
from .services.render_bundle import build_animation_render_bundle
from .services.shortcuts import (
    build_effective_shortcut_bindings,
    build_form_shortcut_bindings,
    validate_shortcut_submission,
)


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

    def test_animation_form_allows_empty_bg_color_when_background_image_is_set(self):
        form = AnimationForm(
            data={
                "title": "Animation C",
                "description": "",
                "scheduled_at": "2026-05-06T10:00",
                "text_color": "#FFFFFF",
                "bg_color": "",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "bg-asset-01",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["bg_color"])


class BackgroundImageValidationTests(SimpleTestCase):
    def _build_upload(
        self,
        *,
        size: tuple[int, int] = (1600, 900),
        image_format: str = "PNG",
        filename: str = "background.png",
        content_type: str = "image/png",
    ) -> SimpleUploadedFile:
        from PIL import Image

        buffer = BytesIO()
        image = Image.new("RGB", size, color=(120, 60, 40))
        image.save(buffer, format=image_format)
        return SimpleUploadedFile(
            filename,
            buffer.getvalue(),
            content_type=content_type,
        )

    def test_open_image_reads_dimensions_and_restores_cursor(self):
        upload = self._build_upload()
        upload.read(5)
        width, height, fmt = _open_image(upload)
        self.assertEqual((width, height, fmt), (1600, 900, "PNG"))
        self.assertEqual(upload.tell(), 5)

    def test_validate_image_accepts_valid_upload(self):
        upload = self._build_upload()
        result = validate_image(
            upload,
            {
                "allowed_ext": [".png"],
                "allowed_mime": ["image/png"],
                "max_bytes": 2 * 1024 * 1024,
                "min_w": 800,
                "min_h": 600,
                "max_w": 4096,
                "max_h": 3072,
                "ratio_min": 1.3,
                "ratio_max": 2.0,
            },
        )
        self.assertEqual(result, "")


class BackgroundImageStorageNamingTests(TestCase):
    def _build_upload(
        self,
        *,
        size: tuple[int, int] = (1600, 900),
        image_format: str = "PNG",
        filename: str = "background.png",
        content_type: str = "image/png",
    ) -> SimpleUploadedFile:
        from PIL import Image

        buffer = BytesIO()
        image = Image.new("RGB", size, color=(120, 60, 40))
        image.save(buffer, format=image_format)
        return SimpleUploadedFile(
            filename,
            buffer.getvalue(),
            content_type=content_type,
        )

    def _insert_genre(self, group: str, name: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                [group, name],
            )
            return int(cursor.fetchone()[0])

    def _insert_target(self, name: str, sort_order: int) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."targets" ("name", "sort_order") VALUES (%s, %s) RETURNING target_id',
                [name, sort_order],
            )
            return int(cursor.fetchone()[0])

    def test_generate_storage_name_uses_business_format(self):
        filename = generate_storage_name("scoutisme", "Mon image.JPEG")
        stem, extension = filename.rsplit(".", 1)
        prefix, random_part = stem.rsplit("_", 1)
        self.assertEqual(prefix, "scoutisme")
        self.assertEqual(extension, "jpeg")
        self.assertEqual(len(random_part), 10)
        self.assertTrue(set(random_part) <= set(STORAGE_FILENAME_ALPHABET))

    def test_build_background_context_slug_uses_single_clean_group(self):
        genre_id = self._insert_genre("1 - Scoutisme", "Veillee")
        self.assertEqual(build_background_context_slug([genre_id]), "scoutisme")

    def test_build_background_context_slug_uses_same_group_for_multiple_genres(self):
        genre_one = self._insert_genre("1 - scoutisme", "Veillee")
        genre_two = self._insert_genre("1  -  Scoutisme", "Camp")
        self.assertEqual(
            build_background_context_slug([genre_two, genre_one]),
            "scoutisme",
        )

    def test_build_background_context_slug_falls_back_for_multiple_groups(self):
        genre_one = self._insert_genre("1 - scoutisme", "Veillee")
        genre_two = self._insert_genre("2 - liturgie", "Louange")
        self.assertEqual(
            build_background_context_slug([genre_one, genre_two]),
            "background",
        )

    def test_build_background_context_slug_falls_back_for_empty_group(self):
        genre_id = self._insert_genre("1 - ", "Veillee")
        self.assertEqual(build_background_context_slug([genre_id]), "background")

    def test_build_background_context_slug_slugifies_accents_and_punctuation(self):
        genre_id = self._insert_genre("2 - Prière & louange", "Veillee")
        self.assertEqual(
            build_background_context_slug([genre_id]),
            "priere-louange",
        )

    def test_validate_image_rejects_extension_mime_dimensions_and_ratio(self):
        valid_cfg = {
            "allowed_ext": [".png"],
            "allowed_mime": ["image/png"],
            "max_bytes": 2 * 1024 * 1024,
            "min_w": 800,
            "min_h": 600,
            "max_w": 4096,
            "max_h": 3072,
            "ratio_min": 1.3,
            "ratio_max": 2.0,
        }
        self.assertEqual(
            validate_image(
                self._build_upload(filename="background.jpg"),
                valid_cfg,
            ),
            "invalid_extension",
        )
        self.assertEqual(
            validate_image(
                self._build_upload(content_type="image/jpeg"),
                valid_cfg,
            ),
            "invalid_mime",
        )
        self.assertEqual(
            validate_image(
                self._build_upload(size=(640, 480)),
                valid_cfg,
            ),
            "too_small",
        )
        self.assertEqual(
            validate_image(
                self._build_upload(size=(5000, 2800)),
                valid_cfg,
            ),
            "too_large_dimensions",
        )
        self.assertEqual(
            validate_image(
                self._build_upload(size=(800, 800)),
                valid_cfg,
            ),
            "invalid_ratio",
        )

    def test_validate_image_rejects_corrupted_payload(self):
        upload = SimpleUploadedFile(
            "broken.png",
            b"not-an-image",
            content_type="image/png",
        )
        result = validate_image(
            upload,
            {"allowed_ext": [".png"], "allowed_mime": ["image/png"]},
        )
        self.assertEqual(result, "invalid_image")


class LyricsSlideShowMasterScriptTests(SimpleTestCase):
    def test_keydown_ignore_logic_keeps_remote_buttons_active_and_popup_buttons_ignored(
        self,
    ):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()
        self.assertIn(
            'const popupRoot = target.closest("#lss-messagebox-root");',
            script,
        )
        self.assertIn(
            "if (popupRoot instanceof HTMLElement && !popupRoot.hidden) {",
            script,
        )
        self.assertIn(
            'if (tagName === "button") {',
            script,
        )
        self.assertIn(
            'return !Boolean(target.closest("[data-lyrics-master-root]"));',
            script,
        )

    def test_customize_popup_uses_shortcut_slot_fields(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()
        self.assertIn('type: "shortcut-slots"', script)
        self.assertIn('emptySlotLabel: ""', script)
        self.assertIn('captureSlotLabel: label("shortcutsCaptureLabel")', script)
        self.assertIn('clearSlotLabel: label("shortcutsClearSlotLabel")', script)

    def test_toggle_buttons_refresh_active_visual_states(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()
        self.assertIn(
            'blackModeButtonNode.classList.toggle("is-alert-active", state.blackMode)',
            script,
        )
        self.assertIn(
            'qrToggleButtonNode.classList.toggle("is-alert-active", state.qrMode)',
            script,
        )
        self.assertIn(
            'blackoutFrameNode.classList.toggle("is-visible", state.blackMode)', script
        )


class MessageBoxShortcutSlotTests(SimpleTestCase):
    def test_message_box_supports_shortcut_slot_field_type(self):
        script = Path("static/js/message_box.js").read_text()
        self.assertIn('"shortcut-slots"', script)
        self.assertIn("serializeShortcutSlotTokens", script)
        self.assertIn("normalizeShortcutCaptureToken", script)
        self.assertIn('if (event.key === "Escape") {', script)
        self.assertIn(
            'hiddenInput.dispatchEvent(new Event("input", { bubbles: true }))', script
        )
        self.assertIn("dataset.shortcutSlotIndex", script)

    def test_message_box_styles_define_shortcut_slot_layout(self):
        stylesheet = Path("static/css/normal.css").read_text()
        self.assertIn(".lss-messagebox-shortcut-slots", stylesheet)
        self.assertIn(".lss-messagebox-shortcut-slot-wrapper", stylesheet)
        self.assertIn(".lss-messagebox-shortcut-slot-clear", stylesheet)


class LyricsSlideShowTemplateContractsTests(SimpleTestCase):
    def test_animations_page_uses_homepage_style_main_grid(self):
        template = Path("app_animation/templates/animation/animations.html").read_text()
        self.assertIn('<section class="site-theme-selection">', template)
        self.assertNotIn('<section class="animation-list-section">', template)

    def test_animation_actions_partial_uses_flat_song_like_panel_structure(self):
        template = Path(
            "app_animation/templates/animation/includes/_animation_actions.html"
        ).read_text()
        self.assertNotIn('class="animation-actions-list"', template)
        add_index = template.index('{% trans "Ajouter une animation" %}')
        background_index = template.index('{% trans "Banque d\'images" %}')
        upload_index = template.index('{% trans "Ajouter une image" %}')
        self.assertLess(add_index, background_index)
        self.assertLess(background_index, upload_index)
        self.assertNotIn('{% trans "Voir l\'historique" %}', template)
        self.assertNotIn('{% trans "← Retour aux animations à venir" %}', template)

    def test_animation_context_actions_partial_uses_separator_for_context_only(self):
        template = Path(
            "app_animation/templates/animation/includes/_animation_context_actions.html"
        ).read_text()
        self.assertIn('class="animation-tools-separator"', template)
        self.assertIn('{% trans "Voir l\'historique" %}', template)
        self.assertIn('{% trans "← Retour aux animations à venir" %}', template)

    def test_background_image_pages_reuse_animation_section_panel_contract(self):
        background_images_template = Path(
            "app_animation/templates/animation/background_images.html"
        ).read_text()
        background_picker_template = Path(
            "app_animation/templates/animation/background_picker.html"
        ).read_text()
        upload_background_image_template = Path(
            "app_animation/templates/animation/upload_background_image.html"
        ).read_text()
        animation_history_template = Path(
            "app_animation/templates/animation/animation_history.html"
        ).read_text()

        for template in (
            background_images_template,
            background_picker_template,
            upload_background_image_template,
            animation_history_template,
        ):
            self.assertIn(
                '{% block section_title %}{% if selected_group %}{{ selected_group.name }}{% else %}{% trans "Animations" %}{% endif %}{% endblock %}',
                template,
            )
            self.assertIn("{% block section_nav %}", template)
            self.assertIn('data-theme-icon="animations"', template)
        self.assertIn("{% block page_summary %}", background_images_template)
        self.assertIn("data-background-search-card", background_images_template)
        self.assertIn("data-background-results-grid", background_images_template)
        self.assertIn("data-picker-grid", background_picker_template)
        self.assertIn("data-picker-overlay", background_picker_template)

    def test_animations_page_adds_history_as_contextual_action(self):
        template = Path("app_animation/templates/animation/animations.html").read_text()
        self.assertIn(
            '{% include "animation/includes/_animation_context_actions.html" with show_animation_history_action=True %}',
            template,
        )

    def test_modify_animation_adds_contextual_tools_for_back_save_and_lyrics(self):
        template = Path(
            "app_animation/templates/animation/modify_animation.html"
        ).read_text()
        self.assertIn("show_back_to_animations_action=True", template)
        self.assertIn("show_save_action=True", template)
        self.assertIn("show_lyrics_slide_show_action=True", template)

    def test_remote_template_contains_blackout_frame(self):
        template = Path(
            "app_animation/templates/animation/lyrics_slide_show.html"
        ).read_text()
        self.assertIn("data-lyrics-blackout-frame", template)

    def test_remote_styles_define_alert_active_button_and_blackout_frame(self):
        stylesheet = Path("static/css/app_animation.css").read_text()
        self.assertIn(".site-tools-panel .animation-tool-link", stylesheet)
        self.assertIn(".site-tools-panel .animation-tools-separator", stylesheet)
        self.assertIn(".animation-background-summary-grid", stylesheet)
        self.assertIn(".animation-background-genres-scroll", stylesheet)
        self.assertIn(".animation-background-picker-grid", stylesheet)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", stylesheet)
        self.assertIn(".animation-background-picker-overlay", stylesheet)
        self.assertIn(".lyrics-master-blackout-frame", stylesheet)
        self.assertIn(".lyrics-master-blackout-frame.is-visible", stylesheet)
        self.assertIn(
            ".lyrics-master-actions-row .animation-tool-button.is-alert-active",
            stylesheet,
        )

    def test_normal_and_taize_themes_define_shared_action_radius(self):
        normal_stylesheet = Path("static/css/normal.css").read_text()
        taize_stylesheet = Path("static/css/taize.css").read_text()
        self.assertIn("--site-action-radius: 18px;", normal_stylesheet)
        self.assertIn("border-radius: var(--site-action-radius);", normal_stylesheet)
        self.assertIn("--site-action-radius: 18px;", taize_stylesheet)


class ShortcutValidationTests(SimpleTestCase):
    def test_validation_rejects_escape_and_combinations_but_keeps_other_values(self):
        labels = {
            "black": "BLACK MODE",
            "prev_slide": "Previous slide",
            "next_slide": "Next slide",
            "chorus": "Chorus",
            "open_display": "Display current slide window",
            "prev_song": "Previous song",
            "next_song": "Next song",
            "toggle_chorus": "Display/hide choruses",
            "toggle_scroll": "Scroll on ↕️ or not 🧱",
            "toggle_qr": "📱 QR code for lyrics",
        }
        result = validate_shortcut_submission(
            {
                "black": "Escape, x",
                "prev_slide": "Ctrl+A, b",
                "next_slide": "",
                "chorus": "",
                "open_display": "",
                "prev_song": "",
                "next_song": "",
                "toggle_chorus": "",
                "toggle_scroll": "",
                "toggle_qr": "",
            },
            action_labels=labels,
        )

        self.assertEqual(result.saved_bindings["black"], ["x"])
        self.assertEqual(result.saved_bindings["prev_slide"], ["b"])
        self.assertIn("Escape", result.field_errors["black"])
        self.assertIn("combinaison", result.field_errors["prev_slide"])

    def test_effective_bindings_keep_escape_for_black_mode(self):
        effective = build_effective_shortcut_bindings(
            {
                "black": ["x"],
                "prev_slide": ["b"],
                "next_slide": [],
                "chorus": [],
                "open_display": [],
                "prev_song": [],
                "next_song": [],
                "toggle_chorus": [],
                "toggle_scroll": [],
                "toggle_qr": [],
            }
        )
        self.assertEqual(effective["black"], ["escape", "x"])


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

    def test_song_color_override_masks_parent_background_image(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session Mask",
            scheduled_at=timezone.now(),
            bg_color="#000000",
            background_asset_code="bg-animation",
        )
        song = Song.objects.create(
            title="Song Mask",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
        )
        AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            bg_color_override="#223344",
        )

        bundle = build_animation_render_bundle(animation)
        slide = next(item for item in bundle if item.source_verse_id == verse.verse_id)
        self.assertEqual(slide.style.bg_color, "#223344")
        self.assertIsNone(slide.style.background_asset_code)

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

    def _login(
        self,
        user_id: str,
        username: str = "member.user",
        *,
        is_moderator: bool = False,
        is_admin: bool = False,
    ) -> None:
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
            "is_moderator": is_moderator or is_admin,
            "is_admin": is_admin,
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

    def test_add_animation_with_background_image_clears_bg_color(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        self._select_group(selected_group)
        response = self.client.post(
            reverse("add_animation"),
            data={
                "title": "Nouvelle animation image",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "bg-asset-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Animation.objects.get(title="Nouvelle animation image")
        self.assertIsNone(created.bg_color)
        self.assertEqual(created.background_asset_code, "bg-asset-01")

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

    def test_modify_animation_post_redirects_to_background_picker_after_save(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
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
                "font_size": "60",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item.animation_song_id}",
                "songs_payload": json.dumps({"items": []}),
                "background_picker_level": "verse",
                "background_picker_animation_song_id": str(item.animation_song_id),
                "background_picker_source_verse_id": str(verse.verse_id),
                "background_picker_after_save": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            f"{reverse('animation_background_picker', args=[animation.animation_id])}?level=verse&animation_song_id={item.animation_song_id}&verse_id={verse.verse_id}",
        )

    def test_modify_animation_post_invalid_does_not_redirect_to_background_picker(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        self._select_group(group)

        response = self.client.post(
            reverse("modify_animation", args=[animation.animation_id]),
            data={
                "title": "",
                "description": "",
                "scheduled_at": "2026-05-08T19:45",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "60",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "ordered_mix": f"asid:{item.animation_song_id}",
                "songs_payload": json.dumps({"items": []}),
                "background_picker_level": "animation",
                "background_picker_after_save": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Des erreurs empêchent l'enregistrement")

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

    def test_background_picker_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_background_picker_refuses_animation_outside_selected_group(self):
        selected_group = Group.objects.create(
            name="Open Group", status=GroupStatus.OPEN
        )
        other_group = Group.objects.create(name="Other Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=other_group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(selected_group)
        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_background_picker_filters_active_images_by_genre(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Veillée"],
            )
            selected_genre_id = int(cursor.fetchone()[0])
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["2 - Liturgie", "Louange"],
            )
            other_genre_id = int(cursor.fetchone()[0])
        image_match = BackgroundImage.objects.create(
            asset_code="bg-match",
            storage_filename="match.png",
            title="Match",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/match.png",
            original_name="match.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        image_other = BackgroundImage.objects.create(
            asset_code="bg-other",
            storage_filename="other.png",
            title="Other",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/other.png",
            original_name="other.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        animation_views.replace_image_genres(image_match, [selected_genre_id])
        animation_views.replace_image_genres(image_other, [other_genre_id])
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation", "genre_ids": [selected_genre_id]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_match.title)
        self.assertNotContains(response, image_other.title)

    def test_background_picker_post_animation_saves_image_and_clears_bg_color(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            bg_color="#000000",
        )
        image = BackgroundImage.objects.create(
            asset_code="bg-active",
            storage_filename="active.png",
            title="Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/active.png",
            original_name="active.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self._select_group(group)

        response = self.client.post(
            f"{reverse('animation_background_picker', args=[animation.animation_id])}?level=animation",
            data={"selected_asset_code": image.asset_code},
        )
        self.assertEqual(response.status_code, 302)
        animation.refresh_from_db()
        self.assertEqual(animation.background_asset_code, image.asset_code)
        self.assertIsNone(animation.bg_color)

    def test_background_picker_post_song_and_verse_save_image_and_clear_bg_color_override(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            background_asset_code="bg-parent",
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            bg_color_override="#223344",
        )
        AnimationVerseOverride.objects.create(
            animation_song=item,
            source_verse_id=verse.verse_id,
            bg_color_override="#445566",
            is_visible=True,
        )
        image = BackgroundImage.objects.create(
            asset_code="bg-active",
            storage_filename="active.png",
            title="Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/active.png",
            original_name="active.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self._select_group(group)

        response = self.client.post(
            f"{reverse('animation_background_picker', args=[animation.animation_id])}?level=song&animation_song_id={item.animation_song_id}",
            data={"selected_asset_code": image.asset_code},
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.background_asset_code_override, image.asset_code)
        self.assertIsNone(item.bg_color_override)

        response = self.client.post(
            f"{reverse('animation_background_picker', args=[animation.animation_id])}?level=verse&animation_song_id={item.animation_song_id}&verse_id={verse.verse_id}",
            data={"selected_asset_code": image.asset_code},
        )
        self.assertEqual(response.status_code, 302)
        override = AnimationVerseOverride.objects.get(
            animation_song=item,
            source_verse_id=verse.verse_id,
        )
        self.assertEqual(override.background_asset_code_override, image.asset_code)
        self.assertIsNone(override.bg_color_override)

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
        self.assertFalse(response.context["shortcuts_config"]["canCustomizeShortcuts"])
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"]["black"],
            ["escape", "m"],
        )

    def test_lyrics_slide_show_toolbar_mentions_customizable_shortcuts(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Raccourcis clavier (personnalisable)")

    def test_lyrics_slide_show_uses_member_shortcuts_when_present(self):
        user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        self._login(user_id=user_id, username="shortcut.member")
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        AnimationRemoteShortcut.objects.create(
            member_id=user_id,
            lyrics_slide_show_bindings={
                "black": ["x"],
                "prev_slide": ["k"],
                "next_slide": ["j"],
                "chorus": ["h"],
                "open_display": ["p"],
                "prev_song": ["u"],
                "next_song": ["i"],
                "toggle_chorus": ["y"],
                "toggle_scroll": ["t"],
                "toggle_qr": ["g"],
            },
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["shortcuts_config"]["canCustomizeShortcuts"])
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"]["black"],
            ["escape", "x"],
        )
        self.assertEqual(
            response.context["shortcuts_config"]["formBindings"]["open_display"],
            ["p"],
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

    def test_lyrics_slide_show_shortcuts_context_exposes_structured_help_data(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Couplet A"
        )
        AnimationSong.objects.create(animation=animation, song=song, position=2)

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["lyrics_i18n"]["shortcutsPopupFooter"],
            "⌨️👈 in upper or lower case",
        )
        self.assertEqual(
            response.context["lyrics_i18n"]["shortcutsCaptureLabel"],
            "Appuyer sur une touche",
        )
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"]["open_display"],
            ["o"],
        )
        self.assertEqual(
            response.context["shortcuts_config"]["actionLabels"]["open_display"],
            "Display current slide window",
        )

    def test_lyrics_slide_show_shortcuts_endpoint_requires_authenticated_member(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)
        response = self.client.post(
            reverse("lyrics_slide_show_shortcuts", args=[animation.animation_id]),
            data={"black": "x"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)

    def test_lyrics_slide_show_shortcuts_endpoint_saves_partial_bindings(self):
        user_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        self._login(user_id=user_id, username="shortcut.save.member")
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        self._select_group(group)
        response = self.client.post(
            reverse("lyrics_slide_show_shortcuts", args=[animation.animation_id]),
            data={
                "black": "x, escape",
                "prev_slide": "x, b",
                "next_slide": "j",
                "chorus": "r",
                "open_display": "o",
                "prev_song": "u",
                "next_song": "i",
                "toggle_chorus": "y",
                "toggle_scroll": "t",
                "toggle_qr": "g",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Escape", payload["fieldErrors"]["black"])
        self.assertIn("Previous slide", payload["globalMessage"])
        self.assertEqual(payload["savedBindings"]["black"], ["x"])
        self.assertEqual(payload["savedBindings"]["prev_slide"], ["b"])
        self.assertEqual(payload["effectiveBindings"]["black"], ["escape", "x"])

        record = AnimationRemoteShortcut.objects.get(member_id=user_id)
        self.assertEqual(record.lyrics_slide_show_bindings["prev_slide"], ["b"])

    def test_lyrics_slide_show_shortcuts_endpoint_deletes_record_when_reverting_to_site(
        self,
    ):
        user_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        self._login(user_id=user_id, username="shortcut.reset.member")
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        AnimationRemoteShortcut.objects.create(
            member_id=user_id,
            lyrics_slide_show_bindings={
                "black": ["x"],
                "prev_slide": ["k"],
                "next_slide": ["j"],
                "chorus": ["h"],
                "open_display": ["p"],
                "prev_song": ["u"],
                "next_song": ["i"],
                "toggle_chorus": ["y"],
                "toggle_scroll": ["t"],
                "toggle_qr": ["g"],
            },
        )
        self._select_group(group)
        site_defaults = build_form_shortcut_bindings(None)
        response = self.client.post(
            reverse("lyrics_slide_show_shortcuts", args=[animation.animation_id]),
            data={
                **{
                    action: ", ".join(values)
                    for action, values in site_defaults.items()
                },
                "use_site_defaults": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["usedSiteDefaults"])
        self.assertFalse(
            AnimationRemoteShortcut.objects.filter(member_id=user_id).exists()
        )

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


class BackgroundImageViewsTests(TestCase):
    def setUp(self):
        super().setUp()
        self._media_root_dir = tempfile.mkdtemp(prefix="lss-bg-images-")
        self.override = override_settings(MEDIA_ROOT=self._media_root_dir)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self._media_root_dir, ignore_errors=True)
        super().tearDown()

    def _login(self, *, moderator: bool = False):
        user_id = str(uuid.uuid4())
        DirectoryUserRecord.objects.create(
            id=user_id,
            username="image.user",
            first_name="Image",
            last_name="User",
            email="image.user@example.test",
            enabled=True,
            email_verified=False,
        )
        session = self.client.session
        session["lss_user"] = {
            "external_id": user_id,
            "username": "image.user",
            "email": "image.user@example.test",
            "first_name": "Image",
            "last_name": "User",
            "is_moderator": moderator,
            "is_admin": False,
        }
        session.save()
        if moderator:
            MemberRole.objects.create(member_id=user_id, is_moderator=True)
        return user_id

    def _build_upload(self, *, size=(1600, 900)):
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, color=(30, 50, 90)).save(buffer, format="PNG")
        return SimpleUploadedFile(
            "background.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def _insert_genre(self, group: str, name: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                [group, name],
            )
            return int(cursor.fetchone()[0])

    def _insert_target(self, name: str, sort_order: int) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."targets" ("name", "sort_order") VALUES (%s, %s) RETURNING target_id',
                [name, sort_order],
            )
            return int(cursor.fetchone()[0])

    def test_upload_background_image_requires_authenticated_user(self):
        response = self.client.get(reverse("upload_background_image"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("login"))

    def test_background_images_requires_moderator(self):
        self._login(moderator=False)
        response = self.client.get(reverse("background_images"))
        self.assertEqual(response.status_code, 404)

    def test_upload_page_hides_background_bank_link_for_non_moderator(self):
        self._login(moderator=False)
        response = self.client.get(reverse("upload_background_image"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Banque d'images")

    def test_upload_background_image_creates_pending_row_with_member_id(self):
        self._login()
        self._insert_target("Scout", 10)
        response = self.client.post(
            reverse("upload_background_image"),
            data={
                "title": "Sky",
                "target": "Scout",
                "description": "Blue sky",
                "image_file": self._build_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        image = BackgroundImage.objects.get()
        self.assertEqual(image.status, BackgroundImageStatus.PENDING)
        self.assertIsNotNone(image.member_id)
        self.assertEqual(image.storage_filename, Path(image.stored_path).name)
        self.assertTrue(Path(self._media_root_dir, image.stored_path).exists())

    def test_upload_background_image_page_renders_target_select_with_first_option_selected(
        self,
    ):
        self._login()
        self._insert_target("Louange", 20)
        self._insert_target("Autre", 5)

        response = self.client.get(reverse("upload_background_image"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="target"', html=False)
        self.assertContains(
            response,
            '<option value="Autre" selected>Autre</option>',
            html=False,
        )

    def test_upload_background_image_page_shows_explicit_message_when_no_target_exists(
        self,
    ):
        self._login()

        response = self.client.get(reverse("upload_background_image"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Aucune cible n&#x27;est disponible. Un modérateur doit d&#x27;abord en créer une.",
        )

    def test_upload_background_image_rejects_unknown_target_value(self):
        self._login()
        self._insert_target("Scout", 10)

        response = self.client.post(
            reverse("upload_background_image"),
            data={
                "title": "Sky",
                "target": "Inconnue",
                "description": "Blue sky",
                "image_file": self._build_upload(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BackgroundImage.objects.count(), 0)
        self.assertContains(response, "Sélectionnez un choix valide")

    def test_background_images_context_summary_shows_only_active_entries_and_caps_at_15(
        self,
    ):
        self._login(moderator=True)
        created_active_ids: list[int] = []
        for index in range(18):
            image = BackgroundImage.objects.create(
                asset_code=f"bg-active-{index}",
                storage_filename=f"active-{index}.png",
                title=f"Active {index}",
                target="Scout",
                status=BackgroundImageStatus.ACTIVE,
                stored_path=f"background-images/active/active-{index}.png",
                original_name=f"active-{index}.png",
                extension=".png",
                mime="image/png",
                size_bytes=100,
                width=1600,
                height=900,
            )
            created_active_ids.append(image.image_id)
        BackgroundImage.objects.create(
            asset_code="bg-inactive",
            storage_filename="inactive.png",
            title="Inactive",
            target="Scout",
            status=BackgroundImageStatus.INACTIVE,
            stored_path="background-images/inactive/inactive.png",
            original_name="inactive.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )

        response = self.client.get(reverse("background_images"))
        self.assertEqual(response.status_code, 200)
        summary_items = response.context["summary_background_images"]
        self.assertLessEqual(len(summary_items), 15)
        self.assertEqual(len(summary_items), 15)
        self.assertTrue(
            all(int(item["image_id"]) in created_active_ids for item in summary_items)
        )

    def test_background_images_render_contains_summary_search_and_results_blocks(self):
        self._login(moderator=True)
        image = BackgroundImage.objects.create(
            asset_code="bg-active",
            storage_filename="active.png",
            title="Active",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/active.png",
            original_name="active.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )

        response = self.client.get(reverse("background_images"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-background-summary-grid")
        self.assertContains(response, "data-background-search-card")
        self.assertContains(response, "data-background-genres-scroll")
        self.assertContains(response, "data-background-results-grid")
        self.assertContains(response, "Images à modérer")
        self.assertContains(response, "Images inactives")
        self.assertContains(response, image.title)

    def test_upload_background_image_retries_on_storage_name_collision(self):
        self._login()
        self._insert_target("Scout", 10)
        pending_dir = Path(self._media_root_dir, "background-images", "pending")
        pending_dir.mkdir(parents=True, exist_ok=True)
        existing_path = pending_dir / "duplicate.png"
        existing_path.write_bytes(b"existing-file")

        with patch(
            "app_animation.services.background_images.generate_storage_name",
            side_effect=["duplicate.png", "unique.png"],
        ):
            response = self.client.post(
                reverse("upload_background_image"),
                data={
                    "title": "Sky",
                    "target": "Scout",
                    "description": "Blue sky",
                    "image_file": self._build_upload(),
                },
            )

        self.assertEqual(response.status_code, 302)
        image = BackgroundImage.objects.get()
        self.assertEqual(image.storage_filename, "unique.png")
        self.assertEqual(image.stored_path, "background-images/pending/unique.png")
        self.assertEqual(existing_path.read_bytes(), b"existing-file")
        self.assertTrue(Path(self._media_root_dir, image.stored_path).exists())

    def test_upload_background_image_uses_group_slug_in_storage_filename(self):
        self._login()
        self._insert_target("Scout", 10)
        genre_id = self._insert_genre("1 - Scoutisme", "Veillee")
        response = self.client.post(
            reverse("upload_background_image"),
            data={
                "title": "Sky",
                "target": "Scout",
                "description": "Blue sky",
                "genre_ids": [str(genre_id)],
                "image_file": self._build_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        image = BackgroundImage.objects.get()
        self.assertRegex(image.storage_filename, r"^scoutisme_[a-z2-9]{10}\.png$")

    def test_upload_background_image_uses_background_slug_for_multiple_groups(self):
        self._login()
        self._insert_target("Scout", 10)
        genre_one = self._insert_genre("1 - Scoutisme", "Veillee")
        genre_two = self._insert_genre("2 - Liturgie", "Louange")
        response = self.client.post(
            reverse("upload_background_image"),
            data={
                "title": "Sky",
                "target": "Scout",
                "description": "Blue sky",
                "genre_ids": [str(genre_one), str(genre_two)],
                "image_file": self._build_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        image = BackgroundImage.objects.get()
        self.assertRegex(image.storage_filename, r"^background_[a-z2-9]{10}\.png$")

    def test_upload_background_image_retries_on_storage_filename_db_collision(self):
        self._login()
        self._insert_target("Scout", 10)
        active_dir = Path(self._media_root_dir, "background-images", "active")
        active_dir.mkdir(parents=True, exist_ok=True)
        active_path = active_dir / "duplicate.png"
        active_path.write_bytes(b"active-file")
        BackgroundImage.objects.create(
            asset_code="bg-existing",
            storage_filename="duplicate.png",
            title="Existing",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/duplicate.png",
            original_name="duplicate.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )

        with patch(
            "app_animation.services.background_images.generate_storage_name",
            side_effect=["duplicate.png", "unique.png"],
        ):
            response = self.client.post(
                reverse("upload_background_image"),
                data={
                    "title": "Sky",
                    "target": "Scout",
                    "description": "Blue sky",
                    "image_file": self._build_upload(),
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(BackgroundImage.objects.count(), 2)
        image = BackgroundImage.objects.exclude(asset_code="bg-existing").get()
        self.assertEqual(image.storage_filename, "unique.png")
        self.assertFalse(
            Path(
                self._media_root_dir,
                "background-images",
                "pending",
                "duplicate.png",
            ).exists()
        )

    def test_upload_background_image_stops_after_twenty_attempts(self):
        self._login()
        self._insert_target("Scout", 10)
        pending_dir = Path(self._media_root_dir, "background-images", "pending")
        pending_dir.mkdir(parents=True, exist_ok=True)
        existing_path = pending_dir / "duplicate.png"
        existing_path.write_bytes(b"existing-file")

        with patch(
            "app_animation.services.background_images.generate_storage_name",
            side_effect=["duplicate.png"] * 20,
        ):
            response = self.client.post(
                reverse("upload_background_image"),
                data={
                    "title": "Sky",
                    "target": "Scout",
                    "description": "Blue sky",
                    "image_file": self._build_upload(),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Impossible d&#x27;enregistrer l&#x27;image pour le moment.",
            response.content.decode("utf-8"),
        )
        self.assertEqual(BackgroundImage.objects.count(), 0)
        self.assertEqual(existing_path.read_bytes(), b"existing-file")

    def test_modify_background_targets_requires_moderator(self):
        self._login(moderator=False)
        response = self.client.get(reverse("modify_background_targets"))
        self.assertEqual(response.status_code, 404)

    def test_modify_background_targets_renders_rows_sorted_by_order(self):
        self._login(moderator=True)
        self._insert_target("Louange", 20)
        self._insert_target("Autre", 5)

        response = self.client.get(reverse("modify_background_targets"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertLess(content.index('value="5"'), content.index('value="20"'))
        self.assertLess(
            content.index('value="Autre"'), content.index('value="Louange"')
        )

    def test_modify_background_targets_can_create_update_and_delete_rows(self):
        self._login(moderator=True)
        keep_id = self._insert_target("Scout", 10)
        delete_id = self._insert_target("Autre", 20)

        response = self.client.post(
            reverse("modify_background_targets"),
            data={
                "action": "save",
                "new_sort_order": "5",
                "new_name": "Louange",
                f"rows[{keep_id}][sort_order]": "15",
                f"rows[{keep_id}][name]": "Scouts",
                f"rows[{delete_id}][sort_order]": "20",
                f"rows[{delete_id}][name]": "Autre",
                f"rows[{delete_id}][delete]": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT name, sort_order FROM "common"."targets" ORDER BY sort_order, target_id'
            )
            rows = cursor.fetchall()
        self.assertEqual(rows, [("Louange", 5), ("Scouts", 15)])

    def test_modify_background_targets_rejects_duplicate_name(self):
        self._login(moderator=True)
        existing_id = self._insert_target("Scout", 10)

        response = self.client.post(
            reverse("modify_background_targets"),
            data={
                "action": "save",
                f"rows[{existing_id}][sort_order]": "10",
                f"rows[{existing_id}][name]": "Scout",
                "new_sort_order": "20",
                "new_name": "Scout",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Création impossible pour la cible &quot;Scout&quot;."
        )

    def test_background_image_keeps_stored_target_after_catalog_change(self):
        self._login()
        target_id = self._insert_target("Scout", 10)
        response = self.client.post(
            reverse("upload_background_image"),
            data={
                "title": "Sky",
                "target": "Scout",
                "description": "Blue sky",
                "image_file": self._build_upload(),
            },
        )
        self.assertEqual(response.status_code, 302)
        image = BackgroundImage.objects.get()

        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE "common"."targets" SET name = %s WHERE target_id = %s',
                ["Renamed", target_id],
            )
            cursor.execute(
                'DELETE FROM "common"."targets" WHERE target_id = %s', [target_id]
            )

        image.refresh_from_db()
        self.assertEqual(image.target, "Scout")

    def test_moderator_validation_anonymizes_image(self):
        member_id = uuid.uuid4()
        image = BackgroundImage.objects.create(
            asset_code="bg-test",
            storage_filename="example.png",
            title="Sky",
            target="Scout",
            status=BackgroundImageStatus.PENDING,
            stored_path="background-images/pending/example.png",
            original_name="example.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
            member_id=member_id,
        )
        pending_path = Path(self._media_root_dir, image.stored_path)
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_bytes(b"png")

        self._login(moderator=True)
        response = self.client.post(
            reverse("background_images"),
            data={"image_id": image.image_id, "action": "validate"},
        )
        self.assertEqual(response.status_code, 302)
        image.refresh_from_db()
        self.assertEqual(image.status, BackgroundImageStatus.INACTIVE)
        self.assertIsNone(image.member_id)
        self.assertEqual(image.storage_filename, "example.png")
        self.assertIn("/inactive/", image.stored_path)

    def test_deactivate_image_clears_animation_references(self):
        self._login(moderator=True)
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        image = BackgroundImage.objects.create(
            asset_code="bg-test",
            storage_filename="example.png",
            title="Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/example.png",
            original_name="example.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
            member_id=None,
        )
        active_path = Path(self._media_root_dir, image.stored_path)
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_bytes(b"png")
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            background_asset_code=image.asset_code,
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
        )
        animation_song = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            background_asset_code_override=image.asset_code,
        )
        AnimationVerseOverride.objects.create(
            animation_song=animation_song,
            source_verse_id=verse.verse_id,
            background_asset_code_override=image.asset_code,
        )

        response = self.client.post(
            reverse("background_images"),
            data={"image_id": image.image_id, "action": "deactivate"},
        )
        self.assertEqual(response.status_code, 302)
        image.refresh_from_db()
        animation.refresh_from_db()
        animation_song.refresh_from_db()
        override = AnimationVerseOverride.objects.get(
            animation_song=animation_song,
            source_verse_id=verse.verse_id,
        )
        self.assertEqual(image.status, BackgroundImageStatus.INACTIVE)
        self.assertEqual(image.storage_filename, "example.png")
        self.assertIsNone(animation.background_asset_code)
        self.assertIsNone(animation_song.background_asset_code_override)
        self.assertIsNone(override.background_asset_code_override)

    def test_modify_animation_can_save_background_image_overrides(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        payload = {
            "items": [
                {
                    "animation_song_id": item.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse.verse_id],
                    "song_style": {"background_asset_code_override": "bg-song"},
                    "verse_styles": {
                        str(verse.verse_id): {
                            "background_asset_code_override": "bg-verse"
                        }
                    },
                }
            ]
        }
        session = self.client.session
        session[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
        session.save()

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
                "background_asset_code": "bg-animation",
                "ordered_mix": f"asid:{item.animation_song_id}",
                "songs_payload": json.dumps(payload),
            },
        )
        self.assertEqual(response.status_code, 302)
        animation.refresh_from_db()
        item.refresh_from_db()
        override = AnimationVerseOverride.objects.get(
            animation_song=item,
            source_verse_id=verse.verse_id,
        )
        self.assertEqual(animation.background_asset_code, "bg-animation")
        self.assertEqual(item.background_asset_code_override, "bg-song")
        self.assertEqual(override.background_asset_code_override, "bg-verse")

    def test_resolve_background_asset_url_uses_library_entry(self):
        image = BackgroundImage.objects.create(
            asset_code="bg-test",
            storage_filename="example.png",
            title="Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/example.png",
            original_name="example.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self.assertEqual(
            resolve_background_asset_url(image.asset_code),
            "/media/background-images/active/example.png",
        )


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
