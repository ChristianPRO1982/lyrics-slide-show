import json
import shutil
import tempfile
import uuid
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ImproperlyConfigured
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
from app_song.models import Song, SongFavorite, SongSlideDisplayMode, SongStatus, Verse

from .forms import AnimationForm
from .font_catalog import GOOGLE_FONTS_STYLESHEET_HREF
from .models import (
    Animation,
    AnimationRemoteConnection,
    AnimationRemoteConnectionRole,
    AnimationRemoteSession,
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
    normalize_stored_bindings,
    validate_shortcut_submission,
)
from .transitions import (
    get_default_transition_id,
    list_enabled_transition_choices,
    list_enabled_transition_options,
    list_enabled_transition_runtime_options,
    list_enabled_transitions,
)
from .services.remote_protocol import (
    RemoteCommand,
    RemoteCommandAcceptedMessage,
    RemoteCommandMessage,
    RemoteCommandRejectedMessage,
    RemoteMessageType,
    RemoteRejectReason,
    RemoteStateMessage,
)
from .services.remote_sessions import (
    accept_remote_command,
    authenticate_master_session,
    authenticate_remote_session,
    cancel_remote_command_reservation,
    create_remote_session,
    deactivate_remote_session,
    get_remote_connection_stale_after,
    get_remote_command_cooldown,
    register_master_connection,
    register_remote_connection,
    store_remote_state,
    touch_remote_connection,
    unregister_master_connection,
    unregister_remote_connection,
)


class PlaylistParsingTests(SimpleTestCase):
    def test_parse_ordered_mix_keeps_valid_tokens(self):
        tokens = parse_ordered_mix("asid:10| sid:20 |bad|sid:nope|foo:1|asid:11")
        self.assertEqual(
            [(token.token_type, token.token_id) for token in tokens],
            [("asid", 10), ("sid", 20), ("asid", 11)],
        )


class AnimationRemoteProtocolTests(SimpleTestCase):
    def _state_payload(self, revision: int) -> dict[str, object]:
        return {
            "type": RemoteMessageType.STATE,
            "state": {
                "revision": revision,
                "current_projection_step": {
                    "projection_index": 4,
                    "label": "Couplet 1",
                    "excerpt": "Texte courant",
                },
                "next_projection_step": {
                    "projection_index": 5,
                    "label": "Couplet 2",
                    "excerpt": "Texte suivant",
                },
                "current_song": {
                    "animation_song_id": 8,
                    "title": "Chant A",
                    "selected": True,
                },
                "previous_song": None,
                "next_song": {
                    "animation_song_id": 9,
                    "title": "Chant B",
                    "selected": False,
                },
                "black_mode": False,
                "songs": [
                    {"animation_song_id": 8, "title": "Chant A", "selected": True}
                ],
                "chorus_available": True,
                "current_transition": {"transition_id": "fade", "label": "Fondu"},
                "available_transitions": [{"transition_id": "fade", "label": "Fondu"}],
                "qr_mode": False,
                "master_status": "MASTER_CONNECTED",
            },
        }

    def test_command_and_response_messages_are_json_serializable(self):
        command = RemoteCommandMessage(
            command=RemoteCommand.GO_TO_SONG,
            target={"animation_song_id": 12},
        )

        self.assertEqual(
            command.to_payload(),
            {
                "type": RemoteMessageType.COMMAND,
                "command": RemoteCommand.GO_TO_SONG,
                "target": {"animation_song_id": 12},
            },
        )
        self.assertEqual(
            RemoteCommandMessage.from_payload(command.to_payload()), command
        )
        self.assertEqual(
            RemoteCommandAcceptedMessage(RemoteCommand.NEXT_SLIDE).to_payload()["type"],
            RemoteMessageType.COMMAND_ACCEPTED,
        )
        self.assertEqual(
            RemoteCommandRejectedMessage(RemoteRejectReason.COOLDOWN).to_payload()[
                "reason"
            ],
            RemoteRejectReason.COOLDOWN,
        )
        self.assertEqual(
            RemoteStateMessage.from_payload(self._state_payload(0)).revision,
            0,
        )
        json.dumps(command.to_payload())
        json.dumps(RemoteCommandAcceptedMessage(RemoteCommand.NEXT_SLIDE).to_payload())
        json.dumps(
            RemoteCommandRejectedMessage(RemoteRejectReason.COOLDOWN).to_payload()
        )
        json.dumps(RemoteStateMessage.from_payload(self._state_payload(0)).to_payload())

    def test_state_requires_the_compact_protocol_fields(self):
        payload = self._state_payload(1)
        del payload["state"]["master_status"]

        with self.assertRaises(ValueError):
            RemoteStateMessage.from_payload(payload)

    def test_state_rejects_incomplete_nested_summaries(self):
        payload = self._state_payload(1)
        del payload["state"]["current_projection_step"]["excerpt"]

        with self.assertRaises(ValueError):
            RemoteStateMessage.from_payload(payload)


class AnimationRemoteSessionServiceTests(TestCase):
    def _animation(self) -> Animation:
        group = Group.objects.create(
            name=f"Open Group {uuid.uuid4()}", status=GroupStatus.OPEN
        )
        return Animation.objects.create(
            group=group,
            title="Remote session",
            scheduled_at=timezone.now(),
        )

    def _state_payload(self, revision: int) -> dict[str, object]:
        return {
            "type": RemoteMessageType.STATE,
            "state": {
                "revision": revision,
                "current_projection_step": None,
                "next_projection_step": None,
                "current_song": None,
                "previous_song": None,
                "next_song": None,
                "black_mode": False,
                "songs": [],
                "chorus_available": False,
                "current_transition": None,
                "available_transitions": [],
                "qr_mode": False,
                "master_status": "MASTER_CONNECTED",
            },
        }

    def test_create_session_keeps_only_token_digest_and_uses_eight_hour_ttl(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        other = create_remote_session(created.session.animation, now=now)
        session = created.session

        self.assertIsInstance(session.session_id, uuid.UUID)
        self.assertTrue(created.access_token)
        self.assertTrue(created.master_token)
        self.assertNotEqual(session.access_token_digest, created.access_token)
        self.assertNotEqual(session.master_token_digest, created.master_token)
        self.assertNotEqual(created.access_token, created.master_token)
        self.assertNotEqual(session.session_id, other.session.session_id)
        self.assertNotEqual(created.access_token, other.access_token)
        self.assertIsNone(
            authenticate_remote_session(
                other.session.session_id, created.access_token, now=now
            )
        )
        self.assertEqual(session.expires_at, now + timedelta(hours=8))
        self.assertEqual(session.latest_state_revision, -1)
        self.assertTrue(
            authenticate_remote_session(
                session.session_id, created.access_token, now=now
            )
        )
        self.assertTrue(
            authenticate_master_session(
                session.session_id, created.master_token, now=now
            )
        )

    def test_token_inactive_and_expired_sessions_are_refused(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)

        self.assertIsNone(
            authenticate_remote_session(created.session.session_id, "wrong", now=now)
        )
        self.assertIsNone(
            authenticate_master_session(
                created.session.session_id, created.access_token, now=now
            )
        )
        created.session.active = False
        created.session.save(update_fields=["active"])
        self.assertIsNone(
            authenticate_remote_session(
                created.session.session_id, created.access_token, now=now
            )
        )

        expired = create_remote_session(self._animation(), now=now)
        self.assertIsNone(
            authenticate_remote_session(
                expired.session.session_id,
                expired.access_token,
                now=expired.session.expires_at,
            )
        )

        deactivated = create_remote_session(self._animation(), now=now)
        self.assertIsNotNone(
            deactivate_remote_session(
                deactivated.session.session_id, deactivated.master_token
            )
        )
        self.assertIsNone(
            authenticate_remote_session(
                deactivated.session.session_id, deactivated.access_token, now=now
            )
        )

    def test_command_cooldown_is_persisted_and_invalid_commands_do_not_consume_it(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        command = {"type": RemoteMessageType.COMMAND, "command": "NEXT_SLIDE"}

        invalid = accept_remote_command(
            created.session.session_id,
            created.access_token,
            {"type": RemoteMessageType.COMMAND, "command": "UNKNOWN"},
            now=now,
        )
        self.assertFalse(invalid.accepted)
        self.assertEqual(invalid.reason, RemoteRejectReason.INVALID_COMMAND)
        created.session.refresh_from_db()
        self.assertIsNone(created.session.last_remote_command_at)
        unavailable = accept_remote_command(
            created.session.session_id, created.access_token, command, now=now
        )
        self.assertFalse(unavailable.accepted)
        self.assertEqual(unavailable.reason, RemoteRejectReason.MASTER_UNAVAILABLE)
        created.session.refresh_from_db()
        self.assertIsNone(created.session.last_remote_command_at)
        register_master_connection(
            created.session.session_id,
            created.master_token,
            "test-master-channel",
            now=now,
        )

        accepted = accept_remote_command(
            created.session.session_id, created.access_token, command, now=now
        )
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.session.last_remote_command_at, now)

        rejected = accept_remote_command(
            created.session.session_id,
            created.access_token,
            command,
            now=now + timedelta(milliseconds=599),
        )
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, RemoteRejectReason.COOLDOWN)
        self.assertTrue(
            accept_remote_command(
                created.session.session_id,
                created.access_token,
                command,
                now=now + timedelta(milliseconds=600),
            ).accepted
        )

    def test_deactivated_token_cannot_access_a_new_session_for_same_animation(self):
        now = timezone.now()
        old = create_remote_session(self._animation(), now=now)
        self.assertIsNotNone(
            deactivate_remote_session(old.session.session_id, old.master_token, now=now)
        )
        replacement = create_remote_session(old.session.animation, now=now)

        self.assertIsNone(
            authenticate_remote_session(
                old.session.session_id, old.access_token, now=now
            )
        )
        self.assertIsNone(
            authenticate_remote_session(
                replacement.session.session_id, old.access_token, now=now
            )
        )

    def test_state_storage_accepts_newer_revision_only(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)

        first = store_remote_state(
            created.session.session_id,
            created.master_token,
            self._state_payload(0),
            now=now,
        )
        self.assertTrue(first.stored)
        stale = store_remote_state(
            created.session.session_id,
            created.master_token,
            self._state_payload(0),
            now=now,
        )
        self.assertFalse(stale.stored)
        newest = store_remote_state(
            created.session.session_id,
            created.master_token,
            self._state_payload(1),
            now=now,
        )
        self.assertTrue(newest.stored)
        created.session.refresh_from_db()
        self.assertEqual(created.session.latest_state_revision, 1)
        self.assertEqual(created.session.latest_state["revision"], 1)

    def test_master_connection_and_cooldown_configuration_are_validated(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)

        connected = register_master_connection(
            created.session.session_id,
            created.master_token,
            "first-master-channel",
            now=now,
        )
        self.assertEqual(connected.session.master_connected_at, now)
        self.assertEqual(connected.session.master_channel_name, "first-master-channel")

        replacement = register_master_connection(
            created.session.session_id,
            created.master_token,
            "second-master-channel",
            now=now,
        )
        self.assertEqual(replacement.replaced_channel_name, "first-master-channel")
        unregister_master_connection(
            created.session.session_id, connected.connection_id
        )
        created.session.refresh_from_db()
        self.assertEqual(created.session.master_channel_name, "second-master-channel")
        unregister_master_connection(
            created.session.session_id, replacement.connection_id
        )
        created.session.refresh_from_db()
        self.assertIsNone(created.session.master_channel_name)

        with self.settings(REMOTE_COMMAND_COOLDOWN_MS=500):
            with self.assertRaises(ImproperlyConfigured):
                get_remote_command_cooldown()
        with self.settings(
            REMOTE_CONNECTION_HEARTBEAT_SECONDS=5,
            REMOTE_CONNECTION_STALE_SECONDS=5,
        ):
            with self.assertRaises(ImproperlyConfigured):
                get_remote_connection_stale_after()

    def test_remote_connection_count_is_persisted_and_never_negative(self):
        created = create_remote_session(self._animation())

        registered = register_remote_connection(
            created.session.session_id, created.access_token
        )
        self.assertIsNotNone(registered)
        self.assertEqual(registered.session.remote_connection_count, 1)
        unregistered = unregister_remote_connection(created.session.session_id)
        self.assertIsNotNone(unregistered)
        self.assertEqual(unregistered.session.remote_connection_count, 0)
        still_zero = unregister_remote_connection(created.session.session_id)
        self.assertIsNotNone(still_zero)
        self.assertEqual(still_zero.session.remote_connection_count, 0)

    def test_leases_expire_atomically_and_recompute_the_remote_count(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        master = register_master_connection(
            created.session.session_id,
            created.master_token,
            "master-channel",
            now=now,
        )
        self.assertIsNotNone(master)
        remote = register_remote_connection(
            created.session.session_id,
            created.access_token,
            channel_name="remote-channel",
            now=now,
        )
        self.assertIsNotNone(remote)
        self.assertEqual(remote.session.remote_connection_count, 1)
        self.assertEqual(
            AnimationRemoteConnection.objects.filter(
                session=created.session,
                role=AnimationRemoteConnectionRole.REMOTE,
            ).count(),
            1,
        )

        stale_at = now + get_remote_connection_stale_after() + timedelta(seconds=1)
        decision = accept_remote_command(
            created.session.session_id,
            created.access_token,
            {"type": "COMMAND", "command": "NEXT_SLIDE"},
            now=stale_at,
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, RemoteRejectReason.MASTER_UNAVAILABLE)
        self.assertTrue(decision.master_lost)
        created.session.refresh_from_db()
        self.assertIsNone(created.session.master_channel_name)
        self.assertEqual(created.session.remote_connection_count, 0)

    def test_heartbeat_preserves_a_lease_and_rejects_a_replaced_master(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        first = register_master_connection(
            created.session.session_id,
            created.master_token,
            "first-master-channel",
            now=now,
        )
        self.assertIsNotNone(first)
        heartbeat = touch_remote_connection(
            created.session.session_id,
            first.connection_id,
            AnimationRemoteConnectionRole.MASTER,
            now=now + timedelta(seconds=1),
        )
        self.assertTrue(heartbeat.alive)
        replacement = register_master_connection(
            created.session.session_id,
            created.master_token,
            "second-master-channel",
            now=now + timedelta(seconds=2),
        )
        self.assertIsNotNone(replacement)
        stale_heartbeat = touch_remote_connection(
            created.session.session_id,
            first.connection_id,
            AnimationRemoteConnectionRole.MASTER,
            now=now + timedelta(seconds=3),
        )
        self.assertFalse(stale_heartbeat.alive)
        self.assertTrue(stale_heartbeat.replaced)
        self.assertFalse(stale_heartbeat.lease_expired)

    def test_expired_lease_is_reconnectable_and_not_a_disabled_session(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        remote = register_remote_connection(
            created.session.session_id,
            created.access_token,
            now=now,
        )
        self.assertIsNotNone(remote)
        heartbeat = touch_remote_connection(
            created.session.session_id,
            remote.connection_id,
            AnimationRemoteConnectionRole.REMOTE,
            now=now + get_remote_connection_stale_after() + timedelta(seconds=1),
        )
        self.assertFalse(heartbeat.alive)
        self.assertTrue(heartbeat.lease_expired)
        self.assertFalse(heartbeat.session_invalid)

    def test_cancelled_master_receipt_releases_its_cooldown_reservation(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        master = register_master_connection(
            created.session.session_id,
            created.master_token,
            "master-channel",
            now=now,
        )
        self.assertIsNotNone(master)
        command = {"type": "COMMAND", "command": "NEXT_SLIDE"}
        reserved = accept_remote_command(
            created.session.session_id, created.access_token, command, now=now
        )
        self.assertTrue(reserved.accepted)
        cancelled = cancel_remote_command_reservation(
            created.session.session_id,
            reserved.accepted_at,
            reserved.master_connection_id,
            invalidate_master=False,
            now=now + timedelta(milliseconds=1),
        )
        self.assertIsNotNone(cancelled)
        self.assertTrue(
            accept_remote_command(
                created.session.session_id,
                created.access_token,
                command,
                now=now + timedelta(milliseconds=2),
            ).accepted
        )

    def test_replacement_master_adopts_a_revision_strictly_after_persisted_state(self):
        now = timezone.now()
        created = create_remote_session(self._animation(), now=now)
        first = register_master_connection(
            created.session.session_id,
            created.master_token,
            "first-master-channel",
            now=now,
        )
        self.assertIsNotNone(first)
        self.assertTrue(
            store_remote_state(
                created.session.session_id,
                created.master_token,
                self._state_payload(4),
                connection_id=first.connection_id,
                now=now,
            ).stored
        )
        replacement = register_master_connection(
            created.session.session_id,
            created.master_token,
            "second-master-channel",
            now=now + timedelta(seconds=1),
        )
        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.next_state_revision, 5)
        self.assertFalse(
            store_remote_state(
                created.session.session_id,
                created.master_token,
                self._state_payload(4),
                connection_id=replacement.connection_id,
                now=now + timedelta(seconds=1),
            ).stored
        )
        self.assertTrue(
            store_remote_state(
                created.session.session_id,
                created.master_token,
                self._state_payload(5),
                connection_id=replacement.connection_id,
                now=now + timedelta(seconds=1),
            ).stored
        )


class AnimationFormFontValidationTests(SimpleTestCase):
    def test_transition_manifest_exposes_enabled_transitions(self):
        transition_ids = tuple(item["id"] for item in list_enabled_transitions())
        self.assertEqual(transition_ids, ("direct", "fade", "wipe"))
        self.assertEqual(get_default_transition_id(), "direct")
        self.assertNotIn("wipe_horizontal", transition_ids)

    def test_transition_choices_follow_manifest_order(self):
        choices = tuple(value for value, _label in list_enabled_transition_choices())
        self.assertEqual(choices, ("direct", "fade", "wipe"))
        option_values = tuple(
            item["value"] for item in list_enabled_transition_options()
        )
        self.assertEqual(option_values, choices)
        runtime_values = tuple(
            item["id"] for item in list_enabled_transition_runtime_options()
        )
        self.assertEqual(runtime_values, choices)
        self.assertEqual(
            list_enabled_transition_runtime_options()[2]["params"]["direction"],
            "left_to_right",
        )

    def test_transition_manifest_uses_i18n_label_keys_only(self):
        manifest = json.loads(Path("app_animation/transitions.json").read_text())
        transitions = manifest["transitions"]
        self.assertEqual(
            tuple(item["label_key"] for item in transitions),
            ("transition_direct", "transition_fade", "transition_wipe"),
        )
        self.assertFalse(any("label" in item for item in transitions))

    def test_transition_labels_are_translated_from_keys_in_po_files(self):
        fr_catalog = Path("locale/fr/LC_MESSAGES/django.po").read_text()
        en_catalog = Path("locale/en/LC_MESSAGES/django.po").read_text()

        self.assertIn('msgid "transition_direct"\nmsgstr "Direct"', fr_catalog)
        self.assertIn('msgid "transition_fade"\nmsgstr "Fondu"', fr_catalog)
        self.assertIn('msgid "transition_wipe"\nmsgstr "Balayage"', fr_catalog)
        self.assertIn('msgid "transition_direct"\nmsgstr "Direct"', en_catalog)
        self.assertIn('msgid "transition_fade"\nmsgstr "Fade"', en_catalog)
        self.assertIn('msgid "transition_wipe"\nmsgstr "Wipe"', en_catalog)
        self.assertNotIn('msgid "Balayge"', fr_catalog)
        self.assertNotIn('msgid "Balayge"', en_catalog)

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
                "default_transition": "fade",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["default_transition"], "fade")

    def test_animation_form_defaults_empty_transition_to_direct(self):
        form = AnimationForm(
            data={
                "title": "Animation Direct",
                "description": "",
                "scheduled_at": "2026-05-06T10:00",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "default_transition": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["default_transition"], "direct")


class AnimationSongSlideDisplayModeModelTests(TestCase):
    def test_animation_song_defaults_to_single_slide_display_mode(self):
        group = Group.objects.create(name="Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song",
            subtitle="",
            description="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        animation = Animation.objects.create(
            group=group,
            title="Animation",
            description="",
            scheduled_at=timezone.now(),
        )

        item = AnimationSong.objects.create(animation=animation, song=song, position=2)

        self.assertEqual(item.slide_display_mode, SongSlideDisplayMode.SINGLE)

    def test_animation_song_exposes_same_slide_display_mode_choices_as_song(self):
        self.assertEqual(
            tuple(
                value
                for value, _label in AnimationSong._meta.get_field(
                    "slide_display_mode"
                ).choices
            ),
            (
                SongSlideDisplayMode.SINGLE,
                SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
                SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
                SongSlideDisplayMode.VERSES_BY_PAIRS,
            ),
        )

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
                "default_transition": "direct",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("font_family", form.errors)

    def test_animation_form_rejects_unknown_transition(self):
        form = AnimationForm(
            data={
                "title": "Animation Transition",
                "description": "",
                "scheduled_at": "2026-05-06T10:00",
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "font_family": "Ubuntu",
                "font_size": "72",
                "horizontal_padding": "80",
                "background_asset_code": "",
                "default_transition": "wipe_horizontal",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("default_transition", form.errors)

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
                "default_transition": "direct",
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
        self.assertIn(
            "const shouldIgnoreKeydownTarget = (target, key) => {",
            script,
        )
        self.assertIn(
            'target.matches("select[data-lyrics-transition-select]")',
            script,
        )
        self.assertIn(
            "return !buildShortcutActionIndex().has(key);",
            script,
        )
        self.assertIn("event.preventDefault();", script)

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

    def test_master_script_uses_projection_steps_and_projection_targets(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()
        self.assertIn("const projectionSteps =", script)
        self.assertIn("projectionStepByIndex", script)
        self.assertIn("dataset.targetProjectionIndex", script)
        self.assertIn('card.getAttribute("data-projection-index")', script)

    def test_master_script_carries_transition_state_and_messages(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()
        self.assertIn("const transitions = Array.isArray(payload.transitions)", script)
        self.assertIn("activeTransitionId: defaultTransitionId", script)
        self.assertIn("renderTransitionChoices", script)
        self.assertIn("transition: transitionFromState()", script)
        self.assertIn('action === "next-transition"', script)
        self.assertIn('action === "force-direct"', script)
        self.assertNotIn("wipe_horizontal", script)

    def test_master_script_exposes_external_command_adapter_and_remote_state(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()

        self.assertIn("window.LSSLyricsMasterAdapter = Object.freeze({", script)
        self.assertIn("handleExternalCommand,", script)
        self.assertIn("getRemoteState,", script)
        self.assertIn("subscribeRemoteState,", script)
        self.assertIn("ensureRemoteStateRevision,", script)
        self.assertIn("validateExternalCommand,", script)
        self.assertIn('message.type !== "COMMAND"', script)
        self.assertIn('return rejectedExternalCommand("INVALID_COMMAND");', script)
        self.assertIn('return rejectedExternalCommand("INVALID_TARGET");', script)

    def test_master_script_maps_external_commands_to_existing_actions(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()

        expected_mappings = (
            ('command === "PREVIOUS_SLIDE"', "navigateSlide(-1);"),
            ('command === "NEXT_SLIDE"', "navigateSlide(1);"),
            (
                'command === "PREVIOUS_SONG"',
                "setCurrentSong(state.selectedSongIndex - 1);",
            ),
            ('command === "NEXT_SONG"', "setCurrentSong(state.selectedSongIndex + 1);"),
            ('command === "TOGGLE_BLACK"', "toggleBlackMode();"),
            ('command === "GO_TO_SONG"', "setCurrentSong(songIndex);"),
            ('command === "GO_TO_CHORUS"', "navigateChorus();"),
            ('command === "SET_TRANSITION"', "setActiveTransition(transitionId);"),
            ('command === "TOGGLE_QR"', "toggleQrMode();"),
            (
                'command === "GO_TO_PROJECTION_STEP"',
                "projectProjectionStep(projectionIndex);",
            ),
        )
        for command, action in expected_mappings:
            self.assertIn(command, script)
            self.assertIn(action, script)

        self.assertIn("songIndexByAnimationSongId.get(animationSongId)", script)
        self.assertIn("projectionStepByIndex(projectionIndex)", script)
        self.assertIn("transitionById.has(transitionId)", script)

    def test_master_script_builds_and_publishes_compact_remote_state(self):
        script = Path("static/js/lyrics_slide_show_master.js").read_text()

        self.assertIn("const buildRemoteState = () => {", script)
        for field_name in (
            "revision:",
            "current_projection_step:",
            "next_projection_step:",
            "current_song:",
            "previous_song:",
            "next_song:",
            "black_mode:",
            "songs:",
            "chorus_available:",
            "current_transition:",
            "available_transitions:",
            "qr_mode:",
            'master_status: "INACTIVE"',
        ):
            self.assertIn(field_name, script)
        self.assertIn("remoteStateRevision: state.remoteStateRevision", script)
        self.assertIn("const publishRemoteState = () => {", script)
        self.assertIn("remoteStateSubscribers.forEach", script)
        self.assertEqual(script.count("publishRemoteState();"), 5)
        self.assertNotIn("new WebSocket", script)

    def test_passive_remote_transport_uses_first_message_authentication(self):
        script = Path("static/js/lyrics_remote_transport.js").read_text()

        self.assertIn("window.LSSRemoteTransport = Object.freeze({", script)
        self.assertIn("connectMaster:", script)
        self.assertIn("connectRemote:", script)
        self.assertIn('type: "AUTH", token', script)
        self.assertIn('socket.send(JSON.stringify({ type: "AUTH", token }));', script)
        self.assertIn("window.setTimeout(connect, reconnectDelayMs)", script)
        self.assertIn('message.type === "MASTER_REPLACED"', script)
        self.assertIn('type: "HEARTBEAT"', script)
        self.assertIn("startHeartbeat();", script)
        self.assertIn("stopHeartbeat();", script)
        self.assertIn('message.type === "MASTER_UNAVAILABLE"', script)
        self.assertIn('type: "MASTER_COMMAND_RECEIVED"', script)
        self.assertIn(
            'message.type === "COMMAND_REJECTED" && role === "remote"', script
        )
        self.assertNotIn("pendingCommands", script)
        self.assertNotIn("commandQueue", script)
        self.assertNotIn("?token=", script)

    def test_remote_management_keeps_lifecycle_outside_the_projection_bridge(self):
        management_script = Path("static/js/lyrics_remote_management.js").read_text()
        transport_script = Path("static/js/lyrics_remote_transport.js").read_text()

        self.assertIn("pagehide", management_script)
        self.assertIn("keepalive", management_script)
        self.assertIn("master_token", management_script)
        self.assertIn("window.LSSMessageBox?.alert", management_script)
        self.assertNotIn("BroadcastChannel", management_script)
        self.assertNotIn("localStorage", management_script)
        self.assertIn('"REMOTE_COUNT"', transport_script)
        self.assertIn('"SESSION_DISABLED"', transport_script)
        self.assertIn("onRemoteCount", transport_script)


class RemoteTransportConfigurationTests(SimpleTestCase):
    def test_asgi_routes_redis_and_daphne_are_configured_without_touching_local_bridge(
        self,
    ):
        asgi = Path("lyrics_slide_show/asgi.py").read_text()
        routing = Path("app_animation/routing.py").read_text()
        settings = Path("lyrics_slide_show/settings.py").read_text()
        development_compose = Path("compose.dev.yaml").read_text()
        production_compose = Path("compose.prod.yaml").read_text()
        production_start = Path("scripts/start-web-prod.sh").read_text()
        master_script = Path("static/js/lyrics_slide_show_master.js").read_text()

        self.assertIn("ProtocolTypeRouter", asgi)
        self.assertIn("AllowedHostsOriginValidator", asgi)
        self.assertIn('"websocket":', asgi)
        self.assertIn("RemoteMasterConsumer", routing)
        self.assertIn("RemoteMobileConsumer", routing)
        self.assertIn("<uuid:session_id>/master", routing)
        self.assertIn("<uuid:session_id>/remote", routing)
        self.assertIn(
            'ASGI_APPLICATION = "lyrics_slide_show.asgi.application"', settings
        )
        self.assertIn("channels_redis.core.RedisChannelLayer", settings)
        self.assertIn("REMOTE_CHANNEL_REDIS_URL", settings)
        for compose in (development_compose, production_compose):
            self.assertIn("remote_redis:", compose)
            self.assertNotIn('"6379:6379"', compose)
        self.assertIn("exec daphne", production_start)
        self.assertNotIn("gunicorn", production_start)
        self.assertIn("new window.BroadcastChannel", master_script)
        self.assertIn("window.localStorage", master_script)
        display_script = Path("static/js/lyrics_slide_show_display.js").read_text()
        self.assertNotIn("LSSRemoteTransport", display_script)
        self.assertNotIn("WebSocket", display_script)
        urls = Path("app_animation/urls.py").read_text()
        self.assertIn("lyrics_remote_session_create", urls)
        self.assertIn("lyrics_remote_session_deactivate", urls)
        self.assertIn("lyrics_remote_access", urls)


class LyricsSlideShowDisplayScriptTests(SimpleTestCase):
    def test_display_script_supports_double_projection_steps(self):
        script = Path("static/js/lyrics_slide_show_display.js").read_text()
        self.assertIn("frame.projectionStep", script)
        self.assertIn("renderDoubleProjectionStep", script)
        self.assertIn('wrapper.className = "lyrics-display-double"', script)
        self.assertIn("lyrics-display-column", script)

    def test_display_script_declares_transition_engine(self):
        script = Path("static/js/lyrics_slide_show_display.js").read_text()
        self.assertIn("const transitionRegistry =", script)
        self.assertIn("const processedNonces = new Set()", script)
        self.assertIn("writeDebugEntry", script)
        self.assertIn('event: "transition-start"', script)
        self.assertIn('event: "transition-finish"', script)
        self.assertIn('event: "transitionend"', script)
        self.assertIn("data-lyrics-display-debug-log", script)
        self.assertIn("data-lyrics-display-debug-copy", script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn('isCollapsed ? "🔼" : "🔽"', script)
        self.assertIn('debugCopyNode.textContent = "copied"', script)
        self.assertIn("}, 1000)", script)
        self.assertIn('if (type === "heartbeat")', script)
        self.assertIn("renderFrameIntoLayer", script)
        self.assertIn('transitionId === "fade"', script)
        self.assertIn('transitionId === "wipe"', script)
        self.assertIn("opacity", script)
        self.assertIn("clipPath", script)
        self.assertIn("void incomingLayer.offsetWidth", script)
        self.assertNotIn("wipe_horizontal", script)

    def test_display_stylesheet_declares_double_layout_classes(self):
        stylesheet = Path("static/css/app_animation.css").read_text()
        self.assertIn(".lyrics-display-double", stylesheet)
        self.assertIn(".lyrics-display-column", stylesheet)
        self.assertIn(".lyrics-display-layer", stylesheet)
        self.assertIn(".lyrics-display-debug-panel", stylesheet)

    def test_remote_slide_cards_hidden_attribute_overrides_grid_display(self):
        stylesheet = Path("static/css/app_animation.css").read_text()
        self.assertIn(".lyrics-master-slide-card[hidden]", stylesheet)
        hidden_rule_start = stylesheet.index(".lyrics-master-slide-card[hidden]")
        hidden_rule_end = stylesheet.index("}", hidden_rule_start)
        hidden_rule = stylesheet[hidden_rule_start:hidden_rule_end]
        self.assertIn("display: none !important", hidden_rule)

    def test_remote_slide_cards_style_chorus_and_chorus_like_kinds(self):
        stylesheet = Path("static/css/app_animation.css").read_text()
        self.assertIn('.lyrics-master-slide-card[data-kind="chorus"]', stylesheet)
        self.assertIn('.lyrics-master-slide-card[data-kind="chorus_like"]', stylesheet)
        self.assertIn("@media (prefers-color-scheme: dark)", stylesheet)
        self.assertIn("border-left: 10px solid rgb(255, 100, 100)", stylesheet)
        self.assertIn("border-left: 10px solid rgb(100, 255, 150)", stylesheet)
        self.assertIn("border-left-color: rgb(150, 0, 0)", stylesheet)
        self.assertIn("border-left-color: rgb(0, 100, 0)", stylesheet)


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


class MessageBoxActionListTests(SimpleTestCase):
    def test_message_box_supports_action_list_items(self):
        script = Path("static/js/message_box.js").read_text()
        self.assertIn("const normalizeActionList = (actionList) => {", script)
        self.assertIn("data-action-list-id", script)
        self.assertIn("actionListItemId", script)
        self.assertIn("buttonId: null", script)

    def test_message_box_styles_define_action_list_layout(self):
        stylesheet = Path("static/css/normal.css").read_text()
        self.assertIn(".lss-messagebox-action-list", stylesheet)
        self.assertIn(".lss-messagebox-action-list-item", stylesheet)
        self.assertIn(".lss-messagebox-action-list-description", stylesheet)


class LyricsSlideShowTemplateContractsTests(SimpleTestCase):
    def test_master_template_loads_the_passive_remote_transport_client(self):
        template = Path(
            "app_animation/templates/animation/lyrics_slide_show.html"
        ).read_text()
        self.assertIn("js/lyrics_slide_show_master.js", template)
        self.assertIn("js/lyrics_remote_transport.js", template)
        self.assertIn("js/lyrics_remote_management.js", template)
        self.assertIn("data-remote-management-panel", template)
        self.assertIn("data-remote-management-toggle", template)

    def test_remote_access_renders_the_mobile_operator_interface(self):
        template = Path(
            "app_animation/templates/animation/lyrics_remote_access.html"
        ).read_text()
        script = Path("static/js/lyrics_remote_access.js").read_text()
        self.assertIn("data-remote-access-root", template)
        self.assertIn("lyrics_remote_transport.js", template)
        self.assertIn("data-remote-menu-toggle", template)
        self.assertIn('data-remote-section="next-slide"', template)
        self.assertIn("data-remote-song-select", template)
        self.assertIn('data-remote-command="TOGGLE_BLACK"', template)
        self.assertIn("window.history.replaceState", script)
        self.assertIn(
            'sendCommand("GO_TO_SONG", { animation_song_id: animationSongId })', script
        )
        self.assertIn(
            'sendCommand("SET_TRANSITION", { transition_id: transitionId })', script
        )
        self.assertIn(
            'const preferenceKey = "lss.remote.access.preferences.v1"', script
        )
        self.assertIn("window.localStorage", script)
        self.assertIn("onCommandAccepted", script)
        self.assertIn("onCommandRejected", script)
        self.assertNotIn("BroadcastChannel", script)
        self.assertNotIn("GO_TO_PROJECTION_STEP", script)

    def test_remote_transport_exposes_remote_command_feedback_callbacks(self):
        script = Path("static/js/lyrics_remote_transport.js").read_text()

        self.assertIn("onCommandAccepted", script)
        self.assertIn("onCommandRejected", script)
        self.assertIn(
            'message.type === "COMMAND_ACCEPTED" && role === "remote"', script
        )
        self.assertIn(
            'message.type === "COMMAND_REJECTED" && role === "remote"', script
        )
        self.assertIn('message.reason === "MASTER_UNAVAILABLE"', script)

    def test_animations_page_uses_homepage_style_main_grid(self):
        template = Path("app_animation/templates/animation/animations.html").read_text()
        self.assertIn('<section class="site-theme-selection">', template)
        self.assertNotIn('<section class="animation-list-section">', template)
        self.assertIn(
            "{% url 'lyrics_slide_show_public' animation.animation_id %}",
            template,
        )
        self.assertIn("📱", template)

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
        style_picker_template = Path(
            "app_animation/templates/animation/style_picker.html"
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
            style_picker_template,
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
        self.assertIn('name="q"', background_picker_template)
        self.assertIn("data-picker-query-input", background_picker_template)
        self.assertIn("data-style-picker-grid", style_picker_template)
        self.assertIn("data-style-picker-overlay", style_picker_template)
        self.assertNotIn('name="q"', style_picker_template)

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
        self.assertIn('id="animation-song-{{ card.animation_song_id }}"', template)

    def test_lyrics_slide_show_template_links_to_public_smartphone_view(self):
        template = Path(
            "app_animation/templates/animation/lyrics_slide_show.html"
        ).read_text()
        self.assertIn('{% trans "Modifier cette animation" %}', template)
        self.assertIn(
            "{% url 'lyrics_slide_show_public' animation.animation_id %}",
            template,
        )
        self.assertIn("📱", template)
        self.assertIn('data-lyrics-action="open-display"', template)
        self.assertIn('data-lyrics-action="toggle-qr"', template)
        self.assertIn("data-lyrics-current-song-title", template)

    def test_modify_animation_script_restores_targeted_song_from_hash(self):
        script = Path("static/js/app_animation.js").read_text()
        self.assertIn("const restoreSongCardFromHash = () => {", script)
        self.assertIn("/^#animation-song-(\\d+)$/.exec(hash)", script)
        self.assertIn("setSongCardExpandedState(card, true)", script)
        self.assertIn(
            'toggle.setAttribute("aria-expanded", isOpen ? "true" : "false")', script
        )
        self.assertIn('card.scrollIntoView({ block: "start" });', script)

    def test_modify_animation_script_scrolls_only_when_opening_song_options(self):
        script = Path("static/js/app_animation.js").read_text()
        self.assertIn("const shouldOpen = !isExpanded;", script)
        self.assertIn("if (shouldOpen) {", script)
        self.assertIn('card.scrollIntoView({ block: "start" });', script)
        self.assertIn(
            'const stylePickerBaseUrl = String(popupData.stylePickerUrl || "").trim();',
            script,
        )
        self.assertIn('if (action === "open-style-picker") {', script)
        self.assertIn('kind === "style"', script)

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
        self.assertIn(".animation-dual-action-row", stylesheet)
        self.assertIn(".animation-style-picker-grid", stylesheet)
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
            "next_transition": "Next transition",
            "force_direct": "Force Direct",
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
                "next_transition": "",
                "force_direct": "",
            },
            action_labels=labels,
        )

        self.assertEqual(result.saved_bindings["black"], ["x"])
        self.assertEqual(result.saved_bindings["prev_slide"], ["b"])
        self.assertIn("Escape", result.field_errors["black"])
        self.assertIn("combinaison", result.field_errors["prev_slide"])

    def test_validation_reports_transition_shortcut_conflicts(self):
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
            "next_transition": "Next transition",
            "force_direct": "Force Direct",
        }
        result = validate_shortcut_submission(
            {
                "black": "",
                "prev_slide": "",
                "next_slide": "",
                "chorus": "",
                "open_display": "",
                "prev_song": "",
                "next_song": "",
                "toggle_chorus": "",
                "toggle_scroll": "t",
                "toggle_qr": "i",
                "next_transition": "t",
                "force_direct": "i",
            },
            action_labels=labels,
        )

        self.assertEqual(result.saved_bindings["toggle_scroll"], ["t"])
        self.assertEqual(result.saved_bindings["toggle_qr"], ["i"])
        self.assertEqual(result.saved_bindings["next_transition"], [])
        self.assertEqual(result.saved_bindings["force_direct"], [])
        self.assertIn("Scroll on", result.field_errors["next_transition"])
        self.assertIn("QR code", result.field_errors["force_direct"])

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
                "next_transition": [],
                "force_direct": [],
            }
        )
        self.assertEqual(effective["black"], ["escape", "x"])

    def test_stored_bindings_add_missing_transition_defaults_without_conflict(self):
        normalized = normalize_stored_bindings(
            {
                "black": ["x"],
                "prev_slide": ["k"],
                "next_slide": ["j"],
                "chorus": ["h"],
                "open_display": ["p"],
                "prev_song": ["u"],
                "next_song": ["n"],
                "toggle_chorus": ["y"],
                "toggle_scroll": ["l"],
                "toggle_qr": ["q"],
            }
        )

        self.assertEqual(normalized["next_transition"], ["t"])
        self.assertEqual(normalized["force_direct"], ["i"])

    def test_stored_bindings_skip_missing_transition_defaults_on_conflict(self):
        normalized = normalize_stored_bindings(
            {
                "black": ["x"],
                "prev_slide": ["k"],
                "next_slide": ["j"],
                "chorus": ["h"],
                "open_display": ["p"],
                "prev_song": ["u"],
                "next_song": ["i"],
                "toggle_chorus": ["y"],
                "toggle_scroll": ["t"],
                "toggle_qr": ["q"],
            }
        )

        self.assertEqual(normalized["next_transition"], [])
        self.assertEqual(normalized["force_direct"], [])


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
        self.assertContains(response, 'name="default_transition"')

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
                "default_transition": "fade",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Animation.objects.get(title="Nouvelle animation")
        self.assertEqual(created.group_id, selected_group.group_id)
        self.assertEqual(created.default_transition, "fade")
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
                "default_transition": "direct",
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
        self.assertContains(response, 'id="id_default_transition"')
        self.assertContains(response, 'name="ordered_mix"')
        self.assertContains(response, 'name="songs_payload"')
        self.assertContains(response, f"asid:{item.animation_song_id}")
        self.assertContains(response, '"songCatalog"')
        self.assertContains(response, "data-song-slide-display-mode")
        self.assertContains(response, f'data-verse-id="{verse.verse_id}"')
        self.assertContains(response, "data-song-text-swatch")
        self.assertContains(response, "data-song-bg-swatch")
        self.assertContains(response, "data-song-color-parent-trigger")
        self.assertContains(response, "data-song-style-parent-reset-trigger")
        self.assertContains(response, "unsavedChangesTitle")
        self.assertContains(response, "unsavedChangesMessage")
        self.assertIn("transitionChoices", response.context["popup_data"])
        payload = json.loads(response.context["songs_payload_initial_json"])
        self.assertEqual(
            payload["items"][0]["song_style"]["slide_display_mode"],
            SongSlideDisplayMode.SINGLE,
        )

    def test_modify_animation_get_with_chorus_shows_only_single_and_chorus_modes(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=0, chorus=True, text="R")
        Verse.objects.create(song=song, num=4, num_verse=1, chorus=False, text="C1")
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
        self.assertContains(
            response,
            f'id="song-slide-display-mode-{item.animation_song_id}"',
            html=False,
        )
        self.assertContains(response, 'option value="single"', html=False)
        self.assertContains(response, 'option value="chorus_then_parallel"', html=False)
        self.assertContains(
            response, 'option value="chorus_always_parallel"', html=False
        )
        self.assertNotContains(response, 'option value="verses_by_pairs"', html=False)

    def test_modify_animation_get_without_chorus_shows_single_and_verses_by_pairs_only(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Verses",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=False,
            text="C1",
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
        self.assertContains(response, 'option value="single"', html=False)
        self.assertContains(response, 'option value="verses_by_pairs"', html=False)
        self.assertNotContains(
            response, 'option value="chorus_then_parallel"', html=False
        )
        self.assertNotContains(
            response, 'option value="chorus_always_parallel"', html=False
        )

    def test_modify_animation_get_with_only_chorus_like_does_not_expose_chorus_modes(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Special",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=False,
            chorus_like=True,
            notcontinuenumbering=True,
            prefix="Pont",
            text="Pont",
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
        self.assertContains(response, 'option value="verses_by_pairs"', html=False)
        self.assertNotContains(
            response, 'option value="chorus_then_parallel"', html=False
        )
        self.assertNotContains(
            response, 'option value="chorus_always_parallel"', html=False
        )

    def test_modify_animation_get_normalizes_incompatible_saved_mode(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song No Chorus",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        verse = Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=False,
            text="C1",
        )
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )
        self._select_group(group)

        response = self.client.get(
            reverse("modify_animation", args=[animation.animation_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<option value="verses_by_pairs" selected>',
            html=False,
        )
        payload = json.loads(response.context["songs_payload_initial_json"])
        self.assertEqual(
            payload["items"],
            [
                {
                    "animation_song_id": item.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse.verse_id],
                    "song_style": {
                        "slide_display_mode": "verses_by_pairs",
                        "font_family_override": "",
                        "font_size_delta": 0,
                        "text_color_override": "",
                        "bg_color_override": "",
                        "background_asset_code_override": "",
                    },
                    "verse_styles": {},
                }
            ],
        )

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
                        "slide_display_mode": "verses_by_pairs",
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
        self.assertEqual(item.slide_display_mode, SongSlideDisplayMode.VERSES_BY_PAIRS)

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

    def test_modify_animation_post_persists_chorus_mode_when_song_has_chorus(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
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
                    "visible_verse_ids": [verse.verse_id, chorus.verse_id],
                    "song_style": {
                        "slide_display_mode": "chorus_always_parallel",
                    },
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
        item.refresh_from_db()
        self.assertEqual(
            item.slide_display_mode,
            SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

    def test_modify_animation_post_remaps_chorus_mode_to_verses_by_pairs_without_chorus(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Verses",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Couplet"
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
                    "song_style": {
                        "slide_display_mode": "chorus_then_parallel",
                    },
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
        item.refresh_from_db()
        self.assertEqual(
            item.slide_display_mode,
            SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

    def test_modify_animation_post_remaps_verses_by_pairs_to_chorus_then_parallel_with_chorus(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
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
                    "visible_verse_ids": [verse.verse_id, chorus.verse_id],
                    "song_style": {
                        "slide_display_mode": "verses_by_pairs",
                    },
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
        item.refresh_from_db()
        self.assertEqual(
            item.slide_display_mode,
            SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

    def test_modify_animation_post_can_persist_different_modes_for_two_occurrences_of_same_song(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Shared",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
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
        item_one = AnimationSong.objects.create(
            animation=animation, song=song, position=2
        )
        item_two = AnimationSong.objects.create(
            animation=animation, song=song, position=4
        )

        payload = {
            "items": [
                {
                    "animation_song_id": item_one.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse.verse_id, chorus.verse_id],
                    "song_style": {
                        "slide_display_mode": "single",
                    },
                    "verse_styles": {},
                },
                {
                    "animation_song_id": item_two.animation_song_id,
                    "song_id": song.song_id,
                    "visible_verse_ids": [verse.verse_id, chorus.verse_id],
                    "song_style": {
                        "slide_display_mode": "chorus_then_parallel",
                    },
                    "verse_styles": {},
                },
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
                "ordered_mix": f"asid:{item_one.animation_song_id}|asid:{item_two.animation_song_id}",
                "songs_payload": json.dumps(payload),
            },
        )

        self.assertEqual(response.status_code, 302)
        item_one.refresh_from_db()
        item_two.refresh_from_db()
        self.assertEqual(item_one.slide_display_mode, SongSlideDisplayMode.SINGLE)
        self.assertEqual(
            item_two.slide_display_mode,
            SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

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
            default_transition="direct",
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
                "default_transition": "wipe",
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
        self.assertEqual(animation.default_transition, "wipe")
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
                "default_transition": "direct",
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

    def test_modify_animation_post_rejects_wipe_horizontal_transition(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            default_transition="direct",
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
                "default_transition": "wipe_horizontal",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transition invalide.")
        animation.refresh_from_db()
        self.assertEqual(animation.default_transition, "direct")

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

    def test_modify_animation_post_redirects_to_style_picker_after_save(self):
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
                "picker_kind": "style",
                "background_picker_level": "verse",
                "background_picker_animation_song_id": str(item.animation_song_id),
                "background_picker_source_verse_id": str(verse.verse_id),
                "background_picker_after_save": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            f"{reverse('animation_style_picker', args=[animation.animation_id])}?level=verse&animation_song_id={item.animation_song_id}&verse_id={verse.verse_id}",
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

    def test_background_picker_filters_active_images_by_case_insensitive_query(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        image_match = BackgroundImage.objects.create(
            asset_code="bg-alpha",
            storage_filename="alpha.png",
            title="Alpha Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/alpha.png",
            original_name="alpha.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        image_other = BackgroundImage.objects.create(
            asset_code="bg-zebra",
            storage_filename="zebra.png",
            title="Zebra Night",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/zebra.png",
            original_name="zebra.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation", "q": "aLP"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_match.title)
        self.assertNotContains(response, image_other.title)
        self.assertContains(response, 'value="aLP"', html=False)

    def test_background_picker_ignores_query_shorter_than_three_characters(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        image_match = BackgroundImage.objects.create(
            asset_code="bg-ab",
            storage_filename="ab.png",
            title="AB",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/ab.png",
            original_name="ab.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        image_other = BackgroundImage.objects.create(
            asset_code="bg-zebra-short",
            storage_filename="zebra-short.png",
            title="Zebra",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/zebra-short.png",
            original_name="zebra-short.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation", "q": "ab"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_match.title)
        self.assertContains(response, image_other.title)
        self.assertContains(response, 'value="ab"', html=False)

    def test_background_picker_combines_query_and_genre_filters(self):
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
            asset_code="bg-alpha-match",
            storage_filename="alpha-match.png",
            title="Alpha Sky",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/alpha-match.png",
            original_name="alpha-match.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        image_wrong_query = BackgroundImage.objects.create(
            asset_code="bg-zebra-match",
            storage_filename="zebra-match.png",
            title="Zebra Night",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/zebra-match.png",
            original_name="zebra-match.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        image_wrong_genre = BackgroundImage.objects.create(
            asset_code="bg-alpha-other",
            storage_filename="alpha-other.png",
            title="Alpha River",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/alpha-other.png",
            original_name="alpha-other.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        animation_views.replace_image_genres(image_match, [selected_genre_id])
        animation_views.replace_image_genres(image_wrong_query, [selected_genre_id])
        animation_views.replace_image_genres(image_wrong_genre, [other_genre_id])
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation", "q": "alp", "genre_ids": [selected_genre_id]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_match.title)
        self.assertNotContains(response, image_wrong_query.title)
        self.assertNotContains(response, image_wrong_genre.title)

    def test_background_picker_shows_only_genres_used_by_active_images(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Visible active"],
            )
            active_genre_id = int(cursor.fetchone()[0])
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Inactive only"],
            )
            inactive_genre_id = int(cursor.fetchone()[0])
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Pending only"],
            )
            pending_genre_id = int(cursor.fetchone()[0])
            cursor.execute(
                'INSERT INTO "common"."genres" ("group", "name") VALUES (%s, %s) RETURNING genre_id',
                ["1 - Scoutisme", "Unused"],
            )
            unused_genre_id = int(cursor.fetchone()[0])

        active_image = BackgroundImage.objects.create(
            asset_code="bg-active-genre",
            storage_filename="active-genre.png",
            title="Visible",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/active-genre.png",
            original_name="active-genre.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        inactive_image = BackgroundImage.objects.create(
            asset_code="bg-inactive-genre",
            storage_filename="inactive-genre.png",
            title="Inactive",
            target="Scout",
            status=BackgroundImageStatus.INACTIVE,
            stored_path="background-images/inactive/inactive-genre.png",
            original_name="inactive-genre.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        pending_image = BackgroundImage.objects.create(
            asset_code="bg-pending-genre",
            storage_filename="pending-genre.png",
            title="Pending",
            target="Scout",
            status=BackgroundImageStatus.PENDING,
            stored_path="background-images/pending/pending-genre.png",
            original_name="pending-genre.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        animation_views.replace_image_genres(active_image, [active_genre_id])
        animation_views.replace_image_genres(inactive_image, [inactive_genre_id])
        animation_views.replace_image_genres(pending_image, [pending_genre_id])
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible active")
        self.assertNotContains(response, "Inactive only")
        self.assertNotContains(response, "Pending only")
        self.assertNotContains(response, "Unused")
        self.assertContains(response, f'value="{active_genre_id}"', html=False)
        self.assertNotContains(response, f'value="{inactive_genre_id}"', html=False)
        self.assertNotContains(response, f'value="{pending_genre_id}"', html=False)
        self.assertNotContains(response, f'value="{unused_genre_id}"', html=False)

    def test_background_picker_sorts_images_by_title_and_renders_picker_actions(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        BackgroundImage.objects.create(
            asset_code="bg-zebra",
            storage_filename="zebra.png",
            title="Zebra",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/zebra.png",
            original_name="zebra.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        BackgroundImage.objects.create(
            asset_code="bg-alpha",
            storage_filename="alpha.png",
            title="Alpha",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/alpha.png",
            original_name="alpha.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "animation"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index("Alpha"), content.index("Zebra"))
        self.assertContains(response, "Sauvegarder et revenir à l'animation")
        self.assertContains(response, "Revenir sans sauvegarder")
        self.assertNotContains(response, "Modifier cette animation")
        self.assertNotContains(
            response, reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertContains(response, "data-picker-filter-form")
        self.assertContains(response, "data-picker-query-input")

    def test_background_picker_back_link_targets_song_anchor_for_song_scope(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {"level": "song", "animation_song_id": item.animation_song_id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("modify_animation", args=[animation.animation_id])}#animation-song-{item.animation_song_id}"',
            html=False,
        )

    def test_background_picker_back_link_targets_parent_song_anchor_for_verse_scope(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        item = AnimationSong.objects.create(animation=animation, song=song, position=2)
        verse = Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, text="Verse"
        )
        self._select_group(group)

        response = self.client.get(
            reverse("animation_background_picker", args=[animation.animation_id]),
            {
                "level": "verse",
                "animation_song_id": item.animation_song_id,
                "verse_id": verse.verse_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("modify_animation", args=[animation.animation_id])}#animation-song-{item.animation_song_id}"',
            html=False,
        )

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
        self.assertEqual(
            response.headers["Location"],
            reverse("modify_animation", args=[animation.animation_id]),
        )
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
        self.assertEqual(
            response.headers["Location"],
            f"{reverse('modify_animation', args=[animation.animation_id])}#animation-song-{item.animation_song_id}",
        )
        item.refresh_from_db()
        self.assertEqual(item.background_asset_code_override, image.asset_code)
        self.assertIsNone(item.bg_color_override)

        response = self.client.post(
            f"{reverse('animation_background_picker', args=[animation.animation_id])}?level=verse&animation_song_id={item.animation_song_id}&verse_id={verse.verse_id}",
            data={"selected_asset_code": image.asset_code},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            f"{reverse('modify_animation', args=[animation.animation_id])}#animation-song-{item.animation_song_id}",
        )
        override = AnimationVerseOverride.objects.get(
            animation_song=item,
            source_verse_id=verse.verse_id,
        )
        self.assertEqual(override.background_asset_code_override, image.asset_code)
        self.assertIsNone(override.bg_color_override)

    def test_style_picker_requires_selected_group(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        response = self.client.get(
            reverse("animation_style_picker", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("groups"))

    def test_style_picker_deduplicates_styles_and_renders_preview_occurrences(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#123456",
            bg_color="#654321",
            font_family="Ubuntu",
            font_size=72,
        )
        for index, title in enumerate(
            ["Song A", "Song B", "Song C", "Song D"], start=1
        ):
            song = Song.objects.create(
                title=title,
                subtitle="",
                status=SongStatus.NOT_VALIDATED,
                licensed=False,
            )
            Verse.objects.create(
                song=song, num=2, num_verse=1, chorus=False, text=f"Verse {title}"
            )
            AnimationSong.objects.create(
                animation=animation,
                song=song,
                position=index * 2,
            )
        self._select_group(group)

        response = self.client.get(
            reverse("animation_style_picker", args=[animation.animation_id]),
            {"level": "animation"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertEqual(
            content.count('data-style-key="Ubuntu|72|#123456|#654321|"'), 1
        )
        self.assertContains(response, "Song A - Couplet 1")
        self.assertContains(response, "Song B - Couplet 1")
        self.assertContains(response, "Song C - Couplet 1")
        self.assertContains(response, "...")
        self.assertNotContains(response, 'name="q"')

    def test_style_picker_post_song_to_song_copies_font_size(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=72,
        )
        source_song = Song.objects.create(
            title="Source", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=source_song, num=2, num_verse=1, chorus=False, text="Source verse"
        )
        source_item = AnimationSong.objects.create(
            animation=animation,
            song=source_song,
            position=2,
            font_family_override="Anton",
            font_size_override=88,
            text_color_override="#AABBCC",
            bg_color_override="#112233",
        )
        target_song = Song.objects.create(
            title="Target", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=target_song, num=2, num_verse=1, chorus=False, text="Target verse"
        )
        target_item = AnimationSong.objects.create(
            animation=animation,
            song=target_song,
            position=4,
            font_size_override=66,
        )
        self._select_group(group)

        get_response = self.client.get(
            reverse("animation_style_picker", args=[animation.animation_id]),
            {"level": "song", "animation_song_id": target_item.animation_song_id},
        )
        option = next(
            item
            for item in get_response.context["style_options"]
            if item["font_family"] == "Anton"
        )
        token = next(
            occurrence["token"]
            for occurrence in option["occurrences"]
            if occurrence["source_scope"] == "song"
        )
        response = self.client.post(
            f"{reverse('animation_style_picker', args=[animation.animation_id])}?level=song&animation_song_id={target_item.animation_song_id}",
            data={"selected_occurrence_token": token},
        )
        self.assertEqual(response.status_code, 302)
        source_item.refresh_from_db()
        target_item.refresh_from_db()
        self.assertEqual(
            target_item.font_family_override, source_item.font_family_override
        )
        self.assertEqual(
            target_item.text_color_override, source_item.text_color_override
        )
        self.assertEqual(target_item.bg_color_override, source_item.bg_color_override)
        self.assertEqual(target_item.font_size_override, source_item.font_size_override)

    def test_style_picker_post_animation_to_song_keeps_target_font_size(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#ABCDEF",
            bg_color="#102030",
            font_family="Montserrat",
            font_size=72,
        )
        source_song = Song.objects.create(
            title="Source", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=source_song, num=2, num_verse=1, chorus=False, text="Source verse"
        )
        AnimationSong.objects.create(animation=animation, song=source_song, position=2)
        target_song = Song.objects.create(
            title="Target", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=target_song, num=2, num_verse=1, chorus=False, text="Target verse"
        )
        target_item = AnimationSong.objects.create(
            animation=animation,
            song=target_song,
            position=4,
            font_size_override=61,
            font_family_override="Ubuntu",
        )
        self._select_group(group)

        get_response = self.client.get(
            reverse("animation_style_picker", args=[animation.animation_id]),
            {"level": "song", "animation_song_id": target_item.animation_song_id},
        )
        option = next(
            item
            for item in get_response.context["style_options"]
            if item["font_family"] == "Montserrat"
        )
        token = next(
            occurrence["token"]
            for occurrence in option["occurrences"]
            if occurrence["source_scope"] == "animation"
        )
        response = self.client.post(
            f"{reverse('animation_style_picker', args=[animation.animation_id])}?level=song&animation_song_id={target_item.animation_song_id}",
            data={"selected_occurrence_token": token},
        )
        self.assertEqual(response.status_code, 302)
        target_item.refresh_from_db()
        self.assertEqual(target_item.font_family_override, "Montserrat")
        self.assertEqual(target_item.text_color_override, "#ABCDEF")
        self.assertEqual(target_item.bg_color_override, "#102030")
        self.assertEqual(target_item.font_size_override, 61)

    def test_style_picker_post_verse_to_verse_copies_font_size(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            text_color="#FFFFFF",
            bg_color="#000000",
            font_family="Ubuntu",
            font_size=72,
        )
        source_song = Song.objects.create(
            title="Source", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        source_verse = Verse.objects.create(
            song=source_song, num=2, num_verse=1, chorus=False, text="Source verse"
        )
        source_item = AnimationSong.objects.create(
            animation=animation, song=source_song, position=2
        )
        AnimationVerseOverride.objects.create(
            animation_song=source_item,
            source_verse_id=source_verse.verse_id,
            is_visible=True,
            font_family_override="Anton",
            font_size_override=64,
            text_color_override="#F1E2D3",
            background_asset_code_override="bg-source",
        )
        BackgroundImage.objects.create(
            asset_code="bg-source",
            storage_filename="bg-source.png",
            title="Source image",
            target="Scout",
            status=BackgroundImageStatus.ACTIVE,
            stored_path="background-images/active/bg-source.png",
            original_name="bg-source.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        target_song = Song.objects.create(
            title="Target", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        target_verse = Verse.objects.create(
            song=target_song, num=2, num_verse=1, chorus=False, text="Target verse"
        )
        target_item = AnimationSong.objects.create(
            animation=animation, song=target_song, position=4
        )
        AnimationVerseOverride.objects.create(
            animation_song=target_item,
            source_verse_id=target_verse.verse_id,
            is_visible=True,
            font_size_override=58,
        )
        self._select_group(group)

        get_response = self.client.get(
            reverse("animation_style_picker", args=[animation.animation_id]),
            {
                "level": "verse",
                "animation_song_id": target_item.animation_song_id,
                "verse_id": target_verse.verse_id,
            },
        )
        option = next(
            item
            for item in get_response.context["style_options"]
            if item["font_family"] == "Anton"
        )
        token = next(
            occurrence["token"]
            for occurrence in option["occurrences"]
            if occurrence["source_scope"] == "verse"
        )
        response = self.client.post(
            f"{reverse('animation_style_picker', args=[animation.animation_id])}?level=verse&animation_song_id={target_item.animation_song_id}&verse_id={target_verse.verse_id}",
            data={"selected_occurrence_token": token},
        )
        self.assertEqual(response.status_code, 302)
        target_override = AnimationVerseOverride.objects.get(
            animation_song=target_item,
            source_verse_id=target_verse.verse_id,
        )
        self.assertEqual(target_override.font_family_override, "Anton")
        self.assertEqual(target_override.text_color_override, "#F1E2D3")
        self.assertEqual(target_override.background_asset_code_override, "bg-source")
        self.assertIsNone(target_override.bg_color_override)
        self.assertEqual(target_override.font_size_override, 64)

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

    @patch("app_animation.views.get_channel_layer")
    def test_remote_session_activation_and_deactivation_are_group_scoped(
        self, get_channel_layer
    ):
        from channels.layers import InMemoryChannelLayer

        get_channel_layer.return_value = InMemoryChannelLayer()
        group = Group.objects.create(
            group_id=100, name="Open Group", status=GroupStatus.OPEN
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        other_group = Group.objects.create(
            group_id=101, name="Other Group", status=GroupStatus.OPEN
        )
        other_animation = Animation.objects.create(
            group=other_group, title="Other", scheduled_at=timezone.now()
        )

        def select_group_for_request() -> None:
            session_store = self.client.session
            session_store[SELECTED_GROUP_ID_SESSION_KEY] = group.group_id
            session_store.save()
            self.client.cookies[settings.SESSION_COOKIE_NAME] = (
                session_store.session_key
            )

        select_group_for_request()
        activated = self.client.post(
            reverse("lyrics_remote_session_create", args=[animation.animation_id])
        )
        self.assertEqual(
            activated.status_code,
            200,
            msg=activated.content.decode("utf-8", errors="replace"),
        )
        self.assertEqual(activated.headers["Cache-Control"], "no-store")
        payload = activated.json()
        self.assertNotIn("access_token", payload)
        self.assertIn("master_token", payload)
        self.assertIn("#token=", payload["access_url"])
        self.assertIn("/remote-access/", payload["access_url"])
        session = AnimationRemoteSession.objects.get(session_id=payload["session_id"])
        self.assertNotEqual(session.access_token_digest, payload["access_url"])
        self.assertNotEqual(session.master_token_digest, payload["master_token"])

        access = self.client.get(
            reverse("lyrics_remote_access", args=[session.session_id])
        )
        self.assertEqual(access.status_code, 200)
        self.assertEqual(access.headers["Cache-Control"], "no-store")
        self.assertContains(access, "data-remote-access-root")
        self.assertNotContains(access, payload["master_token"])

        rejected = self.client.post(
            reverse(
                "lyrics_remote_session_deactivate",
                args=[animation.animation_id, session.session_id],
            ),
            {"master_token": "wrong"},
        )
        self.assertEqual(rejected.status_code, 403)
        session.refresh_from_db()
        self.assertTrue(session.active)

        deactivated = self.client.post(
            reverse(
                "lyrics_remote_session_deactivate",
                args=[animation.animation_id, session.session_id],
            ),
            {"master_token": payload["master_token"]},
        )
        self.assertEqual(deactivated.status_code, 200)
        session.refresh_from_db()
        self.assertFalse(session.active)
        self.assertEqual(session.remote_connection_count, 0)
        self.assertIsNone(
            authenticate_remote_session(session.session_id, "wrong", now=timezone.now())
        )

        select_group_for_request()
        denied = self.client.post(
            reverse("lyrics_remote_session_create", args=[other_animation.animation_id])
        )
        self.assertEqual(denied.status_code, 404)

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

    @override_settings(DEBUG=True)
    def test_lyrics_slide_show_display_shows_debug_panel_when_debug_enabled(self):
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
        self.assertContains(response, "data-lyrics-display-debug-panel")
        self.assertContains(response, "data-lyrics-display-debug-log")
        self.assertContains(response, "data-lyrics-display-debug-copy")
        self.assertContains(response, "data-lyrics-display-debug-toggle")

    @override_settings(DEBUG=False)
    def test_lyrics_slide_show_display_hides_debug_panel_when_debug_disabled(self):
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
        self.assertNotContains(response, "data-lyrics-display-debug-panel")

    def test_lyrics_slide_show_public_is_accessible_without_group_selection(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )

        response = self.client.get(
            reverse("lyrics_slide_show_public", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="lyrics-rail"', html=False)
        self.assertContains(response, "<title>Session | Paroles</title>", html=True)
        self.assertContains(
            response,
            "images/lyrics/all_lyrics-hamburger_menu_dark.webp",
            html=False,
        )
        self.assertContains(
            response,
            "images/lyrics/all_lyrics-background_dark.webp",
            html=False,
        )

    def test_lyrics_slide_show_public_uses_shared_template_and_keeps_playlist_order(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song A", subtitle="", status=SongStatus.NOT_VALIDATED, licensed=False
        )
        Verse.objects.create(
            song=song,
            num=2,
            num_verse=1,
            chorus=False,
            text="Premier couplet",
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        AnimationSong.objects.create(animation=animation, song=song, position=2)
        AnimationSong.objects.create(animation=animation, song=song, position=4)

        response = self.client.get(
            reverse("lyrics_slide_show_public", args=[animation.animation_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_title"], "Session")
        self.assertEqual(response.context["animation_title"], "Session")
        self.assertEqual(response.context["drawer_title"], "Session")
        self.assertEqual(response.context["drawer_link_url"], reverse("songs"))
        self.assertEqual(response.context["drawer_link_label"], "Liste des chants")
        self.assertTrue(response.context["is_animation_view"])
        self.assertEqual(
            [item["song_id"] for item in response.context["songs"]],
            [song.song_id, song.song_id],
        )
        self.assertEqual(
            [item["anchor_id"] for item in response.context["songs"]],
            ["lyrics-song-1", "lyrics-song-2"],
        )
        if animation_views.qrcode is None:
            self.assertEqual(response.context["qr_code_png_base64"], "")
        else:
            self.assertTrue(response.context["qr_code_png_base64"])
        self.assertContains(response, 'value="lyrics-song-1"', html=False)
        self.assertContains(response, 'value="lyrics-song-2"', html=False)
        self.assertContains(
            response,
            '<p class="lyrics-animation-title">Session</p>',
            html=False,
        )
        self.assertContains(
            response,
            '<a href="/songs/" class="lyrics-drawer-song-link">Liste des chants</a>',
            html=False,
        )
        self.assertContains(response, '<hr class="lyrics-separator">', html=False)
        self.assertContains(
            response,
            'const fontSizeStorageKey = "lss-smartphone-lyrics:font-size";',
            html=False,
        )
        self.assertContains(response, 'theme: "auto"', html=False)
        self.assertNotContains(
            response,
            "lss-smartphone-lyrics:${window.location.pathname}",
            html=False,
        )
        self.assertNotContains(response, "parsed.theme ===", html=False)
        self.assertNotContains(response, "Chant courant", html=False)
        self.assertNotContains(response, "data-lyrics-current-song-link", html=False)

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
        self.assertIn("projectionSteps", payload)
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
        self.assertEqual(
            payload["projectionSteps"],
            [
                {
                    "projectionIndex": 0,
                    "animationSongId": animation_song.animation_song_id,
                    "songId": song.song_id,
                    "songTitle": song.display_title,
                    "mode": "simple",
                    "left": slides[0],
                    "right": None,
                    "primarySourceGlobalIndex": 0,
                    "sourceGlobalIndexes": [0],
                }
            ],
        )
        self.assertEqual(
            payload["songs"],
            [
                {
                    "animationSongId": animation_song.animation_song_id,
                    "songId": song.song_id,
                    "songTitle": song.display_title,
                    "slideIndexes": [0],
                    "chorusIndexes": [],
                    "projectionIndexes": [0],
                    "chorusProjectionIndexes": [],
                }
            ],
        )
        self.assertFalse(response.context["shortcuts_config"]["canCustomizeShortcuts"])
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"]["black"],
            ["escape", "m"],
        )
        self.assertEqual(
            [item["id"] for item in payload["transitions"]],
            ["direct", "fade", "wipe"],
        )
        self.assertEqual(payload["defaultTransitionId"], "direct")
        manifest_transitions = json.loads(
            Path("app_animation/transitions.json").read_text()
        )["transitions"]
        self.assertEqual(
            payload["transitions"][1]["params"]["duration_ms"],
            manifest_transitions[1]["params"]["duration_ms"],
        )
        self.assertEqual(
            payload["transitions"][2]["params"]["duration_ms"],
            manifest_transitions[2]["params"]["duration_ms"],
        )
        self.assertNotIn("wipe_horizontal", json.dumps(payload["transitions"]))

    def test_lyrics_slide_show_runtime_payload_uses_animation_transition(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group,
            title="Session",
            scheduled_at=timezone.now(),
            default_transition="wipe",
        )
        self._select_group(group)

        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["runtime_payload"]["defaultTransitionId"], "wipe"
        )

    def test_lyrics_slide_show_runtime_payload_falls_back_from_unknown_transition(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        Animation.objects.filter(pk=animation.pk).update(
            default_transition="wipe_horizontal"
        )
        animation.refresh_from_db()
        self._select_group(group)

        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["runtime_payload"]["defaultTransitionId"], "direct"
        )

    def test_lyrics_slide_show_remote_grid_keeps_current_behavior_for_single_mode(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Single",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus = Verse.objects.create(
            song=song, num=2, num_verse=0, chorus=True, text="Refrain visible"
        )
        verse = Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="Couplet visible"
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.SINGLE,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        card_groups = response.context["runtime_payload"]["cardGroups"]
        cards = next(
            group_item["cards"]
            for group_item in card_groups
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(
            [card["kind"] for card in cards],
            ["chorus", "verse", "chorus"],
        )
        self.assertEqual(
            [card["label"] for card in cards],
            ["Refrain", "Couplet 1", "Refrain"],
        )
        self.assertContains(response, "Refrain visible")
        self.assertContains(response, "Couplet visible")
        self.assertEqual(
            [
                slide["sourceVerseId"]
                for slide in response.context["runtime_payload"]["slides"]
            ],
            [chorus.verse_id, verse.verse_id, chorus.verse_id],
        )

    def test_lyrics_slide_show_remote_grid_keeps_current_behavior_for_chorus_then_parallel(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus Then Parallel",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=0, chorus=True, text="R")
        Verse.objects.create(song=song, num=4, num_verse=1, chorus=False, text="C1")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        cards = next(
            group_item["cards"]
            for group_item in response.context["runtime_payload"]["cardGroups"]
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(
            [card["kind"] for card in cards], ["chorus", "verse", "chorus"]
        )
        self.assertTrue(all("projectionIndex" in card for card in cards))

    def test_lyrics_slide_show_remote_grid_hides_chorus_cards_for_chorus_always_parallel(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus Always Parallel",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        chorus = Verse.objects.create(
            song=song, num=2, num_verse=0, chorus=True, text="Refrain remote hidden"
        )
        verse_one = Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="Couplet 1 remote visible"
        )
        verse_two = Verse.objects.create(
            song=song, num=6, num_verse=2, chorus=False, text="Couplet 2 remote visible"
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        cards = next(
            group_item["cards"]
            for group_item in response.context["runtime_payload"]["cardGroups"]
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual([card["kind"] for card in cards], ["verse", "verse"])
        self.assertEqual(
            [card["label"] for card in cards],
            ["Couplet 1", "Couplet 2"],
        )
        page_html = response.content.decode("utf-8").split(
            '<script id="lss-lyrics-runtime-payload"', 1
        )[0]
        self.assertNotIn("Refrain remote hidden", page_html)
        self.assertIn("Couplet 1 remote visible", page_html)
        self.assertIn("Couplet 2 remote visible", page_html)

        slides = [
            slide
            for slide in response.context["runtime_payload"]["slides"]
            if slide["animationSongId"] == item.animation_song_id
        ]
        self.assertEqual(
            [slide["sourceVerseId"] for slide in slides],
            [
                chorus.verse_id,
                verse_one.verse_id,
                chorus.verse_id,
                verse_two.verse_id,
                chorus.verse_id,
            ],
        )
        song_entry = next(
            song_entry
            for song_entry in response.context["runtime_payload"]["songs"]
            if song_entry["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(song_entry["chorusIndexes"], [0, 2, 4])

    def test_lyrics_slide_show_remote_grid_shows_only_odd_logical_verses_for_verses_by_pairs(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Verses By Pairs",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="C1")
        Verse.objects.create(song=song, num=4, num_verse=2, chorus=False, text="C2")
        Verse.objects.create(song=song, num=6, num_verse=3, chorus=False, text="C3")
        Verse.objects.create(song=song, num=8, num_verse=4, chorus=False, text="C4")
        Verse.objects.create(song=song, num=10, num_verse=5, chorus=False, text="C5")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        cards = next(
            group_item["cards"]
            for group_item in response.context["runtime_payload"]["cardGroups"]
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(
            [card["label"] for card in cards],
            ["Couplet 1", "Couplet 3", "Couplet 5"],
        )
        page_html = response.content.decode("utf-8").split(
            '<script id="lss-lyrics-runtime-payload"', 1
        )[0]
        self.assertIn("C1", page_html)
        self.assertNotIn("C2", page_html)
        self.assertIn("C3", page_html)
        self.assertNotIn("C4", page_html)
        self.assertIn("C5", page_html)

    def test_lyrics_slide_show_remote_grid_keeps_odd_continuations_and_special_blocks_in_verses_by_pairs(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Split Verses",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="C1a")
        Verse.objects.create(
            song=song,
            num=4,
            num_verse=1,
            chorus=False,
            notcontinuenumbering=True,
            text="C1b",
        )
        Verse.objects.create(song=song, num=6, num_verse=2, chorus=False, text="C2a")
        Verse.objects.create(
            song=song,
            num=8,
            num_verse=2,
            chorus=False,
            notcontinuenumbering=True,
            text="C2b",
        )
        Verse.objects.create(
            song=song,
            num=10,
            num_verse=2,
            chorus=False,
            chorus_like=True,
            prefix="Pont",
            text="Pont visible",
        )
        Verse.objects.create(song=song, num=12, num_verse=3, chorus=False, text="C3")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        cards = next(
            group_item["cards"]
            for group_item in response.context["runtime_payload"]["cardGroups"]
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(
            [card["kind"] for card in cards],
            ["verse", "verse", "chorus_like", "verse"],
        )
        self.assertEqual(
            [card["label"] for card in cards],
            ["Couplet 1", "", "Pont", "Couplet 3"],
        )
        page_html = response.content.decode("utf-8").split(
            '<script id="lss-lyrics-runtime-payload"', 1
        )[0]
        self.assertIn("C1a", page_html)
        self.assertIn("C1b", page_html)
        self.assertNotIn("C2a", page_html)
        self.assertNotIn("C2b", page_html)
        self.assertIn("Pont visible", page_html)
        self.assertIn("C3", page_html)

    def test_lyrics_slide_show_remote_grid_normalizes_incompatible_mode_before_filtering(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Normalize",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=1, chorus=False, text="C1")
        Verse.objects.create(song=song, num=4, num_verse=2, chorus=False, text="C2")
        Verse.objects.create(song=song, num=6, num_verse=3, chorus=False, text="C3")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        cards = next(
            group_item["cards"]
            for group_item in response.context["runtime_payload"]["cardGroups"]
            if group_item["animationSongId"] == item.animation_song_id
        )
        self.assertEqual(
            [card["label"] for card in cards],
            ["Couplet 1", "Couplet 3"],
        )

    def test_lyrics_slide_show_projection_steps_follow_chorus_then_parallel_sequence(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus Then Parallel Projection",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=0, chorus=True, text="R")
        verse = Verse.objects.create(
            song=song, num=4, num_verse=1, chorus=False, text="C1"
        )
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        song_entry = next(
            entry
            for entry in payload["songs"]
            if entry["animationSongId"] == item.animation_song_id
        )
        projection_steps = [
            payload["projectionSteps"][index]
            for index in song_entry["projectionIndexes"]
        ]
        self.assertEqual(
            [step["mode"] for step in projection_steps[:2]],
            ["simple", "double"],
        )
        self.assertEqual(projection_steps[0]["left"]["kind"], "chorus")
        self.assertEqual(projection_steps[1]["left"]["kind"], "chorus")
        self.assertEqual(projection_steps[1]["right"]["sourceVerseId"], verse.verse_id)
        self.assertEqual(song_entry["chorusProjectionIndexes"], [0, 2])

    def test_lyrics_slide_show_projection_steps_keep_only_double_steps_in_chorus_always_parallel(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Chorus Always Parallel Projection",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(song=song, num=2, num_verse=0, chorus=True, text="R")
        Verse.objects.create(song=song, num=4, num_verse=1, chorus=False, text="C1")
        Verse.objects.create(song=song, num=6, num_verse=2, chorus=False, text="C2")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        song_entry = next(
            entry
            for entry in payload["songs"]
            if entry["animationSongId"] == item.animation_song_id
        )
        projection_steps = [
            payload["projectionSteps"][index]
            for index in song_entry["projectionIndexes"]
        ]
        self.assertEqual(
            [step["mode"] for step in projection_steps], ["double", "double"]
        )
        self.assertTrue(
            all(step["left"]["kind"] == "chorus" for step in projection_steps)
        )
        self.assertTrue(
            all(step["right"]["kind"] == "verse" for step in projection_steps)
        )
        self.assertTrue(song_entry["chorusProjectionIndexes"])

    def test_lyrics_slide_show_projection_steps_pair_verses_by_pairs_and_repeat_last_shorter_block(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        song = Song.objects.create(
            title="Song Verses Projection",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
        )
        Verse.objects.create(
            song=song, num=2, num_verse=1, chorus=False, followed=True, text="C1a"
        )
        Verse.objects.create(
            song=song,
            num=4,
            num_verse=1,
            chorus=False,
            notcontinuenumbering=True,
            text="C1b",
        )
        Verse.objects.create(
            song=song, num=6, num_verse=2, chorus=False, followed=True, text="C2a"
        )
        Verse.objects.create(
            song=song,
            num=8,
            num_verse=2,
            chorus=False,
            followed=True,
            notcontinuenumbering=True,
            text="C2b",
        )
        Verse.objects.create(
            song=song,
            num=10,
            num_verse=2,
            chorus=False,
            notcontinuenumbering=True,
            text="C2c",
        )
        Verse.objects.create(song=song, num=12, num_verse=3, chorus=False, text="C3")
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        item = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.VERSES_BY_PAIRS,
        )

        self._select_group(group)
        response = self.client.get(
            reverse("lyrics_slide_show", args=[animation.animation_id])
        )
        self.assertEqual(response.status_code, 200)

        payload = response.context["runtime_payload"]
        song_entry = next(
            entry
            for entry in payload["songs"]
            if entry["animationSongId"] == item.animation_song_id
        )
        projection_steps = [
            payload["projectionSteps"][index]
            for index in song_entry["projectionIndexes"]
        ]
        self.assertEqual(
            [step["mode"] for step in projection_steps],
            ["double", "double", "double", "simple"],
        )
        self.assertEqual(projection_steps[0]["left"]["text"], "C1a")
        self.assertEqual(projection_steps[0]["right"]["text"], "C2a")
        self.assertEqual(projection_steps[1]["left"]["text"], "C1b")
        self.assertEqual(projection_steps[1]["right"]["text"], "C2b")
        self.assertEqual(projection_steps[2]["left"]["text"], "C1b")
        self.assertEqual(projection_steps[2]["right"]["text"], "C2c")
        self.assertEqual(projection_steps[3]["left"]["text"], "C3")

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
        self.assertContains(response, "data-lyrics-transition-select")

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
            "⌨️👈 en majuscules ou en minuscules",
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
            "Afficher la fenêtre de la diapo en cours",
        )
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"][
                "next_transition"
            ],
            ["t"],
        )
        self.assertEqual(
            response.context["shortcuts_config"]["effectiveBindings"]["force_direct"],
            ["i"],
        )
        self.assertEqual(
            response.context["shortcuts_config"]["actionToRemoteAction"][
                "next_transition"
            ],
            "next-transition",
        )
        self.assertEqual(
            response.context["shortcuts_config"]["actionToRemoteAction"][
                "force_direct"
            ],
            "force-direct",
        )
        self.assertEqual(
            response.context["shortcuts_config"]["actionLabels"]["next_transition"],
            "Transition suivante",
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
        self.assertIn("Diapo précédente", payload["globalMessage"])
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

    def test_background_images_render_shows_edit_button_only_for_inactive_images(self):
        self._login(moderator=True)
        BackgroundImage.objects.create(
            asset_code="bg-pending",
            storage_filename="pending.png",
            title="Pending",
            target="Scout",
            status=BackgroundImageStatus.PENDING,
            stored_path="background-images/pending/pending.png",
            original_name="pending.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        BackgroundImage.objects.create(
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
        content = response.content.decode("utf-8")
        self.assertIn("data-background-edit-trigger", content)
        self.assertIn('action" value="delete"', content)
        self.assertIn('action" value="activate"', content)

    def test_background_images_edit_inactive_metadata_requires_moderator(self):
        self._login(moderator=False)
        image = BackgroundImage.objects.create(
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

        response = self.client.post(
            reverse("background_images"),
            data={
                "image_id": image.image_id,
                "action": "edit_inactive_metadata",
                "title": "Edited",
                "target": "Scout",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_edit_inactive_metadata_updates_fields_without_touching_storage(self):
        self._login(moderator=True)
        old_genre = self._insert_genre("1 - Scoutisme", "Veillee")
        new_genre = self._insert_genre("2 - Liturgie", "Louange")
        self._insert_target("Scout", 10)
        self._insert_target("Louange", 20)
        image = BackgroundImage.objects.create(
            asset_code="bg-inactive",
            storage_filename="inactive.png",
            title="Inactive",
            target="Scout",
            description="Old description",
            status=BackgroundImageStatus.INACTIVE,
            stored_path="background-images/inactive/inactive.png",
            original_name="inactive.png",
            extension=".png",
            mime="image/png",
            size_bytes=100,
            width=1600,
            height=900,
        )
        animation_views.replace_image_genres(image, [old_genre])

        response = self.client.post(
            reverse("background_images"),
            data={
                "image_id": image.image_id,
                "action": "edit_inactive_metadata",
                "title": "Edited title",
                "description": "New description",
                "target": "Louange",
                "genre_ids": [str(new_genre)],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        image.refresh_from_db()
        self.assertEqual(image.title, "Edited title")
        self.assertEqual(image.description, "New description")
        self.assertEqual(image.target, "Louange")
        self.assertEqual(image.asset_code, "bg-inactive")
        self.assertEqual(image.storage_filename, "inactive.png")
        self.assertEqual(image.stored_path, "background-images/inactive/inactive.png")
        self.assertEqual(
            sorted(
                image.genre_relations.order_by("genre_id").values_list(
                    "genre_id", flat=True
                )
            ),
            [new_genre],
        )

    def test_edit_inactive_metadata_rejects_non_inactive_images(self):
        self._login(moderator=True)
        self._insert_target("Scout", 10)
        for status in (
            BackgroundImageStatus.PENDING,
            BackgroundImageStatus.ACTIVE,
        ):
            image = BackgroundImage.objects.create(
                asset_code=f"bg-{status}",
                storage_filename=f"{status}.png",
                title=f"{status} image",
                target="Scout",
                status=status,
                stored_path=f"background-images/{status}/{status}.png",
                original_name=f"{status}.png",
                extension=".png",
                mime="image/png",
                size_bytes=100,
                width=1600,
                height=900,
            )
            response = self.client.post(
                reverse("background_images"),
                data={
                    "image_id": image.image_id,
                    "action": "edit_inactive_metadata",
                    "title": "Edited",
                    "target": "Scout",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 400)
            image.refresh_from_db()
            self.assertNotEqual(image.title, "Edited")

    def test_edit_inactive_metadata_requires_current_target_when_legacy_target_missing(
        self,
    ):
        self._login(moderator=True)
        target_id = self._insert_target("Scout", 10)
        self._insert_target("Louange", 20)
        image = BackgroundImage.objects.create(
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
        with connection.cursor() as cursor:
            cursor.execute(
                'DELETE FROM "common"."targets" WHERE target_id = %s', [target_id]
            )

        response = self.client.post(
            reverse("background_images"),
            data={
                "image_id": image.image_id,
                "action": "edit_inactive_metadata",
                "title": "Edited",
                "target": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("target", payload["fieldErrors"])
        image.refresh_from_db()
        self.assertEqual(image.target, "Scout")

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
        self.assertEqual(persisted[1].slide_display_mode, SongSlideDisplayMode.SINGLE)

    def test_sync_playlist_copies_song_slide_display_mode_for_new_item(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Parallel Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

        result = sync_animation_playlist(
            animation,
            parse_ordered_mix(f"sid:{song.song_id}"),
            allowed_song_ids={song.song_id},
        )

        self.assertEqual(result.created_count, 1)
        created = AnimationSong.objects.get(animation=animation, song=song)
        self.assertEqual(
            created.slide_display_mode,
            SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )

    def test_sync_playlist_new_duplicate_occurrence_uses_song_mode_not_existing_item(
        self,
    ):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song = Song.objects.create(
            title="Song",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
            slide_display_mode=SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )
        existing = AnimationSong.objects.create(
            animation=animation,
            song=song,
            position=2,
            slide_display_mode=SongSlideDisplayMode.SINGLE,
        )

        sync_animation_playlist(
            animation,
            parse_ordered_mix(f"asid:{existing.animation_song_id}|sid:{song.song_id}"),
            allowed_song_ids={song.song_id},
        )

        persisted = list(
            AnimationSong.objects.filter(animation=animation).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[0].animation_song_id, existing.animation_song_id)
        self.assertEqual(persisted[0].slide_display_mode, SongSlideDisplayMode.SINGLE)
        self.assertEqual(
            persisted[1].slide_display_mode,
            SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

    def test_sync_playlist_reorder_existing_items_keeps_their_slide_display_modes(self):
        group = Group.objects.create(name="Open Group", status=GroupStatus.OPEN)
        animation = Animation.objects.create(
            group=group, title="Session", scheduled_at=timezone.now()
        )
        song_a = Song.objects.create(
            title="A",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
            slide_display_mode=SongSlideDisplayMode.CHORUS_ALWAYS_PARALLEL,
        )
        song_b = Song.objects.create(
            title="B",
            subtitle="",
            status=SongStatus.NOT_VALIDATED,
            licensed=False,
            slide_display_mode=SongSlideDisplayMode.VERSES_BY_PAIRS,
        )
        item_a = AnimationSong.objects.create(
            animation=animation,
            song=song_a,
            position=2,
            slide_display_mode=SongSlideDisplayMode.SINGLE,
        )
        item_b = AnimationSong.objects.create(
            animation=animation,
            song=song_b,
            position=4,
            slide_display_mode=SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
        )

        sync_animation_playlist(
            animation,
            parse_ordered_mix(
                f"asid:{item_b.animation_song_id}|asid:{item_a.animation_song_id}"
            ),
            allowed_song_ids={song_a.song_id, song_b.song_id},
        )

        persisted = list(
            AnimationSong.objects.filter(animation=animation).order_by(
                "position", "animation_song_id"
            )
        )
        self.assertEqual(
            [row.animation_song_id for row in persisted],
            [item_b.animation_song_id, item_a.animation_song_id],
        )
        self.assertEqual(
            [row.slide_display_mode for row in persisted],
            [
                SongSlideDisplayMode.CHORUS_THEN_PARALLEL,
                SongSlideDisplayMode.SINGLE,
            ],
        )
