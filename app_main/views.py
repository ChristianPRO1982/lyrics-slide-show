from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app_main.auth import (
    DisabledUserError,
    InvalidCallbackError,
    UnknownUserError,
    clear_session_user,
    get_directory_user,
    get_session_user,
    store_session_user,
    validate_callback_payload,
)


def homepage(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/homepage.html",
        {
            "session_user": get_session_user(request.session),
            "auth_mode": settings.AUTH_MODE,
        },
    )


def login(request: HttpRequest) -> HttpResponse:
    callback_url = request.build_absolute_uri(reverse("auth_callback"))
    query_string = urlencode({"return_to": callback_url})
    return redirect(f"{settings.AUTH_MOCK_BASE_URL}/login?{query_string}")


def auth_callback(request: HttpRequest) -> HttpResponse:
    try:
        payload = validate_callback_payload(request.GET)
        user = get_directory_user(payload["external_id"])
    except InvalidCallbackError as exc:
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")
    except UnknownUserError as exc:
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")
    except DisabledUserError as exc:
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")

    store_session_user(request.session, user)
    messages.success(request, f"Connected as {user.username}.")
    return redirect("homepage")


def logout(request: HttpRequest) -> HttpResponse:
    clear_session_user(request.session)
    messages.info(request, "Logged out.")
    return redirect("homepage")
