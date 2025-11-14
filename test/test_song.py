import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
class DummyResponse:
    def __init__(self, content: bytes):
        self.content = content

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

module_name = "app_song.views"
try:
    from app_song import views
except SyntaxError:
    source_path = ROOT_DIR / "app_song" / "views.py"
    source = source_path.read_text()
    source = source.replace("f'chk_band_{band['band_id']}'", "f\"chk_band_{band['band_id']}\"")
    source = source.replace("f'chk_artist_{artist['artist_id']}'", "f\"chk_artist_{artist['artist_id']}\"")
    source = source.replace(
        "f'box_verse_prefix_{prefix['prefix_id']}'",
        "f\"box_verse_prefix_{prefix['prefix_id']}\"",
    )

    stub_sql_song = ModuleType("app_song.SQL_song")
    stub_sql_song.Song = type("Song", (), {})
    stub_sql_song.Genre = type("Genre", (), {})
    sys.modules["app_song.SQL_song"] = stub_sql_song

    stub_utils = ModuleType("app_main.utils")
    for name in [
        "is_moderator",
        "is_no_loader",
        "strip_html",
        "get_song_params",
        "add_search_params",
        "get_search_params",
        "delete_genre_in_search_params",
        "delete_band_in_search_params",
        "delete_artist_in_search_params",
        "site_messages",
    ]:
        setattr(stub_utils, name, lambda *args, **kwargs: None)
    sys.modules["app_main.utils"] = stub_utils

    stub_sql_main = ModuleType("app_main.SQL_main")
    stub_sql_main.Site = type("Site", (), {})
    sys.modules["app_main.SQL_main"] = stub_sql_main

    stub_sql_animation = ModuleType("app_animation.SQL_animation")
    stub_sql_animation.Animation = type("Animation", (), {})
    sys.modules["app_animation.SQL_animation"] = stub_sql_animation

    module = ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__package__ = "app_song"
    exec(compile(source, str(source_path), "exec"), module.__dict__)
    sys.modules[module_name] = module
    from app_song import views


class DummyPost(dict):
    def copy(self):
        return DummyPost(self)


def _build_request(path: str):
    request = SimpleNamespace()
    request.method = "GET"
    request.path = path
    request.GET = {}
    request.POST = DummyPost()
    request.session = {}
    request.user = None
    return request


@pytest.fixture(autouse=True)
def patch_common_dependencies(monkeypatch):
    """Patch dependencies in app_song.views that are not relevant for the tests."""

    monkeypatch.setattr(views, "is_no_loader", lambda request: False, raising=False)
    monkeypatch.setattr(views, "is_moderator", lambda request: False, raising=False)
    monkeypatch.setattr(views, "site_messages", lambda request, moderator=False: [], raising=False)

    genres = [SimpleNamespace(genre_id=1), SimpleNamespace(genre_id=2)]
    monkeypatch.setattr(views.Genre, "get_all_genres", lambda: genres, raising=False)

    bands = [{"band_id": 10}]
    artists = [{"artist_id": 20}]
    monkeypatch.setattr(
        views.Song,
        "get_all_bands_and_artists",
        lambda: (bands, artists),
        raising=False,
    )

    search_params = {
        "search_txt": "hello",
        "search_everywhere": True,
        "search_logic": 1,
        "search_genres": "1,2",
        "search_bands": "10",
        "search_artists": "",
        "search_song_approved": 0,
        "search_favorites": 0,
    }
    monkeypatch.setattr(views, "get_search_params", lambda request: search_params, raising=False)


def test_songs_view_renders_expected_context(monkeypatch):
    request = _build_request("/songs/")

    class AnonymousUser:
        is_authenticated = False
        username = ""

    request.user = AnonymousUser()

    expected_songs = [{"title": "My song"}]
    monkeypatch.setattr(
        views.Song,
        "get_all_songs",
        lambda *args, **kwargs: expected_songs,
        raising=False,
    )
    monkeypatch.setattr(views.Song, "get_total_songs", lambda: 42, raising=False)

    captured = {}

    def fake_render(req, template, context):
        captured["template"] = template
        captured["context"] = context
        return DummyResponse(b"ok")

    monkeypatch.setattr(views, "render", fake_render, raising=False)

    response = views.songs(request)

    assert response.content == b"ok"
    assert captured["template"] == "app_song/songs.html"

    context = captured["context"]
    assert context["songs"] == expected_songs
    assert context["total_songs"] == 42
    assert context["search_genres"] == [1, 2]
    assert context["search_bands"] == [10]
    assert context["search_artists"] == []
    assert context["total_search_songs"] == len(expected_songs)
    assert context["css"] == "normal.css"
    assert context["no_loader"] is False


def test_songs_view_favorites_override_search_parameters(monkeypatch):
    class AuthenticatedUser:
        is_authenticated = True
        username = "john"

    request = _build_request("/songs/display_my_favorites")
    request.user = AuthenticatedUser()

    captured_call = {}

    def fake_get_all_songs(*args):
        captured_call["args"] = args
        return [{"title": "Favorite"}]

    monkeypatch.setattr(views.Song, "get_all_songs", fake_get_all_songs, raising=False)
    monkeypatch.setattr(views.Song, "get_total_songs", lambda: 1, raising=False)

    captured = {}

    def fake_render(req, template, context):
        captured["template"] = template
        captured["context"] = context
        return DummyResponse(b"ok")

    monkeypatch.setattr(views, "render", fake_render, raising=False)

    response = views.songs(request, display_my_favorites=True)

    assert response.content == b"ok"
    assert captured_call["args"] == (
        True,
        "",
        0,
        0,
        "",
        "",
        "",
        0,
        1,
    )
    assert captured["template"] == "app_song/songs.html"
    assert captured["context"]["songs"] == [{"title": "Favorite"}]
    assert captured["context"]["total_search_songs"] == 1
    assert captured["context"]["search_favorites"] == 0
