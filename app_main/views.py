import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language
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
from app_main.models import SiteParams
from app_member.forms import MemberRoleActionForm, MemberSearchForm, ModeratorMessageForm, SiteParamsAdminForm
from app_member.services import (
    can_manage_moderator_popup,
    can_manage_site_members,
    can_manage_site_settings,
    get_site_params_for_language,
    search_directory_members,
    set_member_role,
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
    {
        "slug": "taize",
        "label": _("Taizé"),
        "description": _("Palette rouge et ocre, inspirée du parchemin et de la lumière des bougies."),
    },
    {
        "slug": "me†al",
        "label": _("Me†al"),
        "description": _("Palette métal avec des néons de couleurs"),
    },
]


def homepage(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/homepage.html",
        {"auth_mode": settings.AUTH_MODE},
    )


def _current_language_code(request: HttpRequest) -> str:
    return (getattr(request, "LANGUAGE_CODE", None) or get_language() or settings.LANGUAGE_CODE)[:2].lower()


def _account_redirect(request: HttpRequest, member_search: str = "") -> HttpResponse:
    redirect_url = reverse("account")
    normalized_search = str(member_search or "").strip()
    if normalized_search:
        redirect_url = f"{redirect_url}?{urlencode({'member_search': normalized_search})}"
    return redirect(redirect_url)


def _build_account_context(
    request: HttpRequest,
    *,
    current_language: str,
    site_params: SiteParams | None,
    moderator_form: ModeratorMessageForm | None = None,
    admin_form: SiteParamsAdminForm | None = None,
    member_search_form: MemberSearchForm | None = None,
    member_results=None,
    member_search: str = "",
) -> dict[str, object]:
    is_moderator = can_manage_moderator_popup(request.user)
    is_admin = can_manage_site_settings(request.user)

    if member_search_form is None:
        member_search_form = MemberSearchForm(initial={"member_search": member_search})

    if member_results is None:
        member_results = []

    if moderator_form is None and is_moderator and site_params is not None:
        moderator_form = ModeratorMessageForm(instance=site_params, prefix="moderation")

    if admin_form is None and is_admin:
        admin_instance = site_params if site_params is not None else SiteParams(language=current_language)
        admin_form = SiteParamsAdminForm(instance=admin_instance, prefix="admin-settings")

    return {
        "auth_mode": settings.AUTH_MODE,
        "session_user": get_session_user(request.session),
        "page_mode": "account",
        "available_themes": AVAILABLE_THEMES,
        "default_theme": AVAILABLE_THEMES[0]["slug"],
        "current_language": current_language,
        "is_moderator": is_moderator,
        "is_admin": is_admin,
        "moderator_form": moderator_form,
        "admin_form": admin_form,
        "member_search_form": member_search_form,
        "member_results": member_results,
        "member_search": member_search,
        "site_params_missing": site_params is None,
        "account_heading": _("Compte de %(username)s") % {"username": request.user.username},
    }


def login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("account")

    if settings.AUTH_MODE not in {"mock", "keycloak"}:
        messages.error(request, "Interactive login is not configured for this environment.")
        logger.warning("login_refused auth_mode=%s reason=unsupported_auth_mode", settings.AUTH_MODE)
        return redirect("homepage")

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

    current_language = _current_language_code(request)
    site_params = get_site_params_for_language(current_language)
    member_search = request.GET.get("member_search", "").strip()
    member_results = []

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        posted_member_search = request.POST.get("member_search", "").strip()

        if action == "save_moderation_settings":
            if not can_manage_moderator_popup(request.user):
                return HttpResponseForbidden(_("Accès refusé."))

            if site_params is None:
                messages.error(request, _("Les paramètres du site sont introuvables pour cette langue."))
                return _account_redirect(request, posted_member_search)

            moderator_form = ModeratorMessageForm(request.POST, instance=site_params, prefix="moderation")
            if moderator_form.is_valid():
                moderator_form.save()
                messages.success(request, _("Les réglages de modération ont été enregistrés."))
                return _account_redirect(request, posted_member_search)

            if can_manage_site_members(request.user) and posted_member_search:
                member_results = search_directory_members(posted_member_search)
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                moderator_form=moderator_form,
                member_search_form=MemberSearchForm(initial={"member_search": posted_member_search}),
                member_results=member_results,
                member_search=posted_member_search,
            )
            return render(request, "main/connexion.html", context)

        if action == "save_site_settings":
            if not can_manage_site_settings(request.user):
                return HttpResponseForbidden(_("Accès refusé."))

            admin_instance = site_params if site_params is not None else SiteParams(language=current_language)
            admin_form = SiteParamsAdminForm(request.POST, instance=admin_instance, prefix="admin-settings")
            if admin_form.is_valid():
                saved_params = admin_form.save(commit=False)
                saved_params.language = admin_instance.language
                saved_params.save()
                messages.success(request, _("Les paramètres administrateur ont été enregistrés."))
                return _account_redirect(request, posted_member_search)

            if posted_member_search:
                member_results = search_directory_members(posted_member_search)
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                admin_form=admin_form,
                member_search_form=MemberSearchForm(initial={"member_search": posted_member_search}),
                member_results=member_results,
                member_search=posted_member_search,
            )
            return render(request, "main/connexion.html", context)

        if action == "update_member_role":
            if not can_manage_site_members(request.user):
                return HttpResponseForbidden(_("Accès refusé."))

            role_form = MemberRoleActionForm(request.POST)
            if role_form.is_valid():
                cleaned = role_form.cleaned_data
                set_member_role(
                    member_id=str(cleaned["member_id"]),
                    role_name=cleaned["role_name"],
                    enabled=bool(cleaned["enabled"]),
                )
                role_label = _("administrateur") if cleaned["role_name"] == "admin" else _("modérateur")
                if cleaned["enabled"]:
                    messages.success(request, _("Le rôle %(role)s a été attribué.") % {"role": role_label})
                else:
                    messages.success(request, _("Le rôle %(role)s a été retiré.") % {"role": role_label})
                return _account_redirect(request, cleaned["member_search"])

            if posted_member_search:
                member_results = search_directory_members(posted_member_search)
            messages.error(request, _("La demande de mise à jour des rôles est invalide."))
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                member_search_form=MemberSearchForm(initial={"member_search": posted_member_search}),
                member_results=member_results,
                member_search=posted_member_search,
            )
            return render(request, "main/connexion.html", context)

        messages.error(request, _("Action de compte inconnue."))
        return _account_redirect(request, posted_member_search)

    if can_manage_site_members(request.user) and member_search:
        member_results = search_directory_members(member_search)

    return render(
        request,
        "main/connexion.html",
        _build_account_context(
            request,
            current_language=current_language,
            site_params=site_params,
            member_search_form=MemberSearchForm(initial={"member_search": member_search}),
            member_results=member_results,
            member_search=member_search,
        ),
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


def language_preferences(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/language.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "current_language": getattr(request, "LANGUAGE_CODE", None) or get_language() or settings.LANGUAGE_CODE,
        },
    )
