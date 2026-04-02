import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app_main.auth import (
    DisabledUserError,
    InvalidCallbackError,
    KeycloakAuthError,
    UnknownUserError,
    build_keycloak_login_url,
    build_keycloak_logout_url,
    clear_session_user,
    get_directory_user,
    get_session_user,
    store_session_user,
    validate_callback_payload,
    validate_keycloak_callback,
)

logger = logging.getLogger("app_main.auth")

AVAILABLE_THEMES = [
    {
        "slug": "normal",
        "label": _("Normal"),
        "description": _("Palette chaude et classique pour l'habillage principal."),
    },
    {
        "slug": "scout",
        "label": _("Scout"),
        "description": _("Palette plus fraîche, plus nette, avec une ambiance vert-bleu."),
    },
]


def homepage(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/homepage.html",
        {"auth_mode": settings.AUTH_MODE},
    )


def login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("account")

    if request.GET.get("start") == "1":
        if settings.AUTH_MODE == "mock":
            callback_url = request.build_absolute_uri(reverse("auth_callback"))
            query_string = urlencode({"return_to": callback_url})
            return redirect(f"{settings.AUTH_MOCK_BASE_URL}/login?{query_string}")
        if settings.AUTH_MODE == "keycloak":
            try:
                return redirect(build_keycloak_login_url(request.session))
            except KeycloakAuthError as exc:
                messages.error(request, str(exc))
                logger.warning("login_refused auth_mode=keycloak reason=configuration detail=%s", exc)
                return redirect("homepage")

        messages.error(request, "Interactive login is not configured for this environment.")
        logger.warning("login_refused auth_mode=%s reason=unsupported_auth_mode", settings.AUTH_MODE)
        return redirect("homepage")

    return render(
        request,
        "main/connexion.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "session_user": get_session_user(request.session),
            "page_mode": "login",
        },
    )


def auth_callback(request: HttpRequest) -> HttpResponse:
    try:
        if settings.AUTH_MODE == "mock":
            payload = validate_callback_payload(request.GET)
        elif settings.AUTH_MODE == "keycloak":
            payload = validate_keycloak_callback(request.GET, request.session)
        else:
            raise KeycloakAuthError("Unsupported authentication mode.")
        user = get_directory_user(payload["external_id"])
    except InvalidCallbackError as exc:
        logger.warning("login_refused reason=invalid_callback detail=%s", exc)
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")
    except KeycloakAuthError as exc:
        logger.warning("login_refused reason=keycloak_callback detail=%s", exc)
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")
    except UnknownUserError as exc:
        logger.warning("login_refused reason=unknown_user external_id=%s", request.GET.get("external_id", ""))
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")
    except DisabledUserError as exc:
        logger.warning("login_refused reason=disabled_user external_id=%s", request.GET.get("external_id", ""))
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")

    request.session.cycle_key()
    store_session_user(request.session, user)
    logger.info("login_success external_id=%s username=%s", user.external_id, user.username)
    messages.success(request, f"Connected as {user.username}.")
    return redirect("homepage")


def logout(request: HttpRequest) -> HttpResponse:
    session_user = get_session_user(request.session)
    if session_user:
        logger.info(
            "logout external_id=%s username=%s",
            session_user.get("external_id", ""),
            session_user.get("username", ""),
        )
    clear_session_user(request.session)
    request.session.cycle_key()
    messages.info(request, "Logged out.")
    if settings.AUTH_MODE == "keycloak":
        try:
            return redirect(build_keycloak_logout_url())
        except KeycloakAuthError as exc:
            logger.warning("logout_keycloak_redirect_failed detail=%s", exc)
    return redirect("homepage")


def account(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")

    return render(
        request,
        "main/connexion.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "session_user": get_session_user(request.session),
            "page_mode": "account",
        },
    )


def privacy_policy(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/privacy_policy.html",
        {"auth_mode": settings.AUTH_MODE},
    )


def theme_preferences(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/theme_preferences.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "available_themes": AVAILABLE_THEMES,
            "default_theme": AVAILABLE_THEMES[0]["slug"],
        },
    )
