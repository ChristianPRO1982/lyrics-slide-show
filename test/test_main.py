import os
import sys
import types
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lyrics_slide_show.settings.base")

import django

django.setup()

import pytest
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

app_logs_module = types.ModuleType("app_logs")
app_logs_utils_module = types.ModuleType("app_logs.utils")


def _noop_delete_old_logs():
    return None


def _noop_create_sql_log(*args, **kwargs):
    return None


app_logs_utils_module.delete_old_logs = _noop_delete_old_logs
app_logs_utils_module.create_SQL_log = _noop_create_sql_log
app_logs_utils_module.create_log = _noop_create_sql_log
setattr(app_logs_module, "utils", app_logs_utils_module)
sys.modules.setdefault("app_logs", app_logs_module)
sys.modules.setdefault("app_logs.utils", app_logs_utils_module)

from app_main import views


class _DummyRedirect(HttpResponse):
    def __init__(self, target: str):
        super().__init__("", status=302)
        self.url = target


@pytest.fixture
def redirect_spy(monkeypatch):
    captured = {}

    def fake_redirect(target, *args, **kwargs):
        captured["target"] = target
        return _DummyRedirect(target)

    monkeypatch.setattr(views, "redirect", fake_redirect)
    return captured


def _add_session(request):
    """Attach a session to the request factory instance."""
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    return request


def test_error_404_renders_custom_template(monkeypatch):
    rf = RequestFactory()
    request = rf.get("/missing")
    captured = {}

    def fake_render(req, template, context=None, status=None):
        captured["request"] = req
        captured["template"] = template
        captured["context"] = context
        captured["status"] = status
        return HttpResponse("rendered", status=status)

    monkeypatch.setattr(views, "render", fake_render)

    response = views.error_404(request, Exception("not found"))

    assert response.status_code == 404
    assert captured["request"] is request
    assert captured["template"] == "root/404.html"
    assert captured["context"] == {"error": ""}
    assert captured["status"] == 404


@override_settings(DEBUG=True)
def test_debug_error_404_returns_custom_page(monkeypatch):
    rf = RequestFactory()
    request = rf.get("/debug-404")
    captured = {}

    def fake_render(req, template, context=None, status=None):
        captured["template"] = template
        captured["context"] = context
        captured["status"] = status
        return HttpResponse("rendered", status=status)

    monkeypatch.setattr(views, "render", fake_render)

    response = views.debug_error_404(request)

    assert response.status_code == 404
    assert captured["template"] == "root/404.html"
    assert captured["context"] == {"error": ""}
    assert captured["status"] == 404


@override_settings(DEBUG=False)
def test_debug_error_404_redirects_when_not_in_debug(redirect_spy):
    rf = RequestFactory()
    request = rf.get("/debug-404")

    response = views.debug_error_404(request)

    assert response.status_code == 302
    assert redirect_spy["target"] == "homepage"
    assert response.url == "homepage"


@pytest.mark.parametrize("language", [lang for lang, _ in settings.LANGUAGES])
def test_change_language_updates_session_and_cookie(monkeypatch, language):
    rf = RequestFactory()
    request = rf.get("/change_language", {"language": language}, HTTP_REFERER="/previous/")
    _add_session(request)

    activated = {}

    def fake_activate(lang):
        activated["lang"] = lang

    monkeypatch.setattr(views.translation, "activate", fake_activate)

    response = views.change_language(request)

    assert activated["lang"] == language
    assert request.session[settings.LANGUAGE_COOKIE_NAME] == language
    assert response.status_code == 302
    assert response["Location"] == "/previous/"
    assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == language


def test_change_language_invalid_value_redirects_to_homepage(redirect_spy):
    rf = RequestFactory()
    request = rf.get("/change_language", {"language": "xx"})
    _add_session(request)

    response = views.change_language(request)

    assert response.status_code == 302
    assert redirect_spy["target"] == "homepage"
    assert response.url == "homepage"


def test_kill_loader_sets_session_flags(redirect_spy):
    rf = RequestFactory()
    request = rf.get("/kill_loader")
    _add_session(request)

    response = views.kill_loader(request)

    assert request.session["no_loader"] is True
    assert "no_loader_date" in request.session
    assert response.status_code == 302
    assert redirect_spy["target"] == "homepage"
    assert response.url == "homepage"


def test_loader_resets_session_flags(redirect_spy):
    rf = RequestFactory()
    request = rf.get("/loader")
    _add_session(request)
    request.session["no_loader"] = True
    request.session["no_loader_date"] = 123

    response = views.loader(request)

    assert "no_loader" not in request.session
    assert "no_loader_date" not in request.session
    assert response.status_code == 302
    assert redirect_spy["target"] == "homepage"
    assert response.url == "homepage"


@pytest.mark.parametrize(
    "view_function, expected_theme",
    [
        (views.theme_normal, "normal.css"),
        (views.theme_scout, "scout.css"),
    ],
)
def test_theme_views_save_user_theme(monkeypatch, redirect_spy, view_function, expected_theme):
    rf = RequestFactory()
    request = rf.get("/theme")
    _add_session(request)

    saved = {}

    def fake_save_user_theme(req, theme):
        saved["request"] = req
        saved["theme"] = theme

    monkeypatch.setattr(views, "save_user_theme", fake_save_user_theme)

    response = view_function(request)

    assert saved["request"] is request
    assert saved["theme"] == expected_theme
    assert response.status_code == 302
    assert redirect_spy["target"] == "homepage"
    assert response.url == "homepage"
