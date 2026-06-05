import logging
import mimetypes
import json
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app_group.services import get_selected_group_state
from app_main.auth import (
    DisabledUserError,
    HOME_PROVISION_TARGET_SESSION_KEY,
    HomeProvisioningError,
    InvalidCallbackError,
    KeycloakAuthError,
    UnknownUserError,
    build_home_provision_start_url,
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
from app_member.forms import (
    MemberRoleActionForm,
    MemberSearchForm,
    ModeratorMessageForm,
    SiteParamsAdminForm,
)
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
        "description": _(
            "Palette plus fraîche, plus nette, avec une ambiance vert-bleu."
        ),
    },
    {
        "slug": "taize",
        "label": _("Taizé"),
        "description": _(
            "Palette rouge et ocre, inspirée du parchemin et de la lumière des bougies."
        ),
    },
    {
        "slug": "me†al",
        "label": _("Me†al"),
        "description": _("Palette métal avec des néons de couleurs"),
    },
]

HEAVY_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


def _get_selected_group(request: HttpRequest):
    selected_group, _selected_via_secret = get_selected_group_state(request)
    return selected_group


def homepage(request: HttpRequest) -> HttpResponse:
    current_language = _current_language_code(request)
    site_params = get_site_params_for_language(current_language)
    home_cards = _parse_home_cards(site_params.home_text if site_params else "")

    return render(
        request,
        "main/homepage.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "selected_group": _get_selected_group(request),
            "home_site_title": (
                site_params.title
                if site_params and site_params.title
                else "Lyrics Slide Show"
            ),
            "home_site_title_h1": (
                site_params.title_h1
                if site_params and site_params.title_h1
                else "Lyrics Slide Show"
            ),
            "home_text": (
                site_params.home_text if site_params and site_params.home_text else ""
            ),
            "home_cards": home_cards,
            "home_bloc1_text": (
                site_params.bloc1_text if site_params and site_params.bloc1_text else ""
            ),
            "home_bloc2_text": (
                site_params.bloc2_text if site_params and site_params.bloc2_text else ""
            ),
        },
    )


def _parse_home_cards(raw_value: str | None) -> list[dict[str, str]]:
    raw = str(raw_value or "").strip()
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [{"title": "", "text": raw}]

    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list):
        return []

    output: list[dict[str, str]] = []
    for item in cards[:6]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        if not title and not text:
            continue
        output.append({"title": title, "text": text})
    return output


def _collect_heavy_images(root: Path, *, source: str) -> list[dict[str, str]]:
    try:
        resolved_root = root.resolve(strict=True)
        if not resolved_root.is_dir():
            return []

        image_paths = sorted(
            (
                path
                for path in resolved_root.rglob("*")
                if path.is_file() and path.suffix.lower() in HEAVY_IMAGE_EXTENSIONS
            ),
            key=lambda path: path.relative_to(resolved_root).as_posix().lower(),
        )
    except (OSError, RuntimeError):
        return []

    images = []
    for path in image_paths:
        relative_path = path.relative_to(resolved_root).as_posix()
        if source == "lss":
            image_url = reverse("heavy_asset", kwargs={"asset_path": relative_path})
        else:
            image_url = static(relative_path)

        images.append(
            {
                "name": path.name,
                "relative_path": relative_path,
                "url": image_url,
            }
        )

    return images


def heavy(request: HttpRequest) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404

    images = _collect_heavy_images(settings.BASE_DIR / "LSS", source="lss")
    image_source = "LSS"

    if not images:
        images = _collect_heavy_images(settings.BASE_DIR / "static", source="static")
        image_source = "static"

    return render(
        request,
        "main/heavy.html",
        {
            "images": images,
            "image_source": image_source,
            "selected_group": _get_selected_group(request),
        },
    )


def heavy_asset(request: HttpRequest, asset_path: str) -> FileResponse:
    if not settings.DEBUG:
        raise Http404

    root = (settings.BASE_DIR / "LSS").resolve()
    requested_path = (root / asset_path).resolve()

    try:
        requested_path.relative_to(root)
    except ValueError as exc:
        raise Http404 from exc

    if (
        not requested_path.is_file()
        or requested_path.suffix.lower() not in HEAVY_IMAGE_EXTENSIONS
    ):
        raise Http404

    content_type, _encoding = mimetypes.guess_type(requested_path.name)
    return FileResponse(
        requested_path.open("rb"),
        content_type=content_type or "application/octet-stream",
    )


def _current_language_code(request: HttpRequest) -> str:
    return (
        getattr(request, "LANGUAGE_CODE", None)
        or get_language()
        or settings.LANGUAGE_CODE
    )[:2].lower()


def _account_redirect(request: HttpRequest, member_search: str = "") -> HttpResponse:
    redirect_url = reverse("account")
    normalized_search = str(member_search or "").strip()
    if normalized_search:
        redirect_url = (
            f"{redirect_url}?{urlencode({'member_search': normalized_search})}"
        )
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
        admin_instance = (
            site_params
            if site_params is not None
            else SiteParams(language=current_language)
        )
        admin_form = SiteParamsAdminForm(
            instance=admin_instance, prefix="admin-settings"
        )

    return {
        "auth_mode": settings.AUTH_MODE,
        "session_user": get_session_user(request.session),
        "selected_group": _get_selected_group(request),
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
        "account_heading": _("Compte de %(username)s")
        % {"username": request.user.username},
    }


def login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("account")

    if settings.AUTH_MODE not in {"mock", "keycloak"}:
        messages.error(
            request,
            _("La connexion interactive n'est pas configurée pour cet environnement."),
        )
        logger.warning(
            "login_refused auth_mode=%s reason=unsupported_auth_mode",
            settings.AUTH_MODE,
        )
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
                logger.warning(
                    "login_refused auth_mode=keycloak reason=configuration detail=%s",
                    exc,
                )
                return redirect("homepage")

    return render(
        request,
        "main/connexion.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "session_user": get_session_user(request.session),
            "selected_group": _get_selected_group(request),
            "page_mode": "login",
        },
    )


def _store_home_provision_target(request: HttpRequest, target_url: str) -> None:
    request.session[HOME_PROVISION_TARGET_SESSION_KEY] = str(target_url or "").strip()
    request.session.modified = True


def auth_callback(request: HttpRequest) -> HttpResponse:
    payload = None
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
        clear_session_user(request.session)
        external_id = ""
        if isinstance(payload, dict):
            external_id = str(payload.get("external_id", "")).strip()
        if settings.AUTH_MODE == "keycloak":
            try:
                provision_url = build_home_provision_start_url()
            except HomeProvisioningError as provision_exc:
                logger.warning(
                    "login_provision_signed_url_failed external_id=%s detail=%s",
                    external_id,
                    provision_exc,
                )
                messages.error(request, str(provision_exc))
                return redirect("homepage")

            logger.info("login_provision_redirect external_id=%s", external_id)
            messages.info(
                request,
                _(
                    "Votre compte Lyrics Slide Show doit être synchronisé depuis cARThographie."
                ),
            )
            _store_home_provision_target(request, provision_url)
            return redirect("provision_redirect")

        logger.warning(
            "login_refused reason=unknown_user external_id=%s",
            external_id or request.GET.get("external_id", ""),
        )
        messages.error(request, str(exc))
        return redirect("homepage")
    except DisabledUserError as exc:
        logger.warning(
            "login_refused reason=disabled_user external_id=%s",
            request.GET.get("external_id", ""),
        )
        messages.error(request, str(exc))
        clear_session_user(request.session)
        return redirect("homepage")

    request.session.cycle_key()
    store_session_user(request.session, user)
    logger.info(
        "login_success external_id=%s username=%s", user.external_id, user.username
    )
    messages.success(
        request, _("Connecté en tant que %(username)s.") % {"username": user.username}
    )
    return redirect("homepage")


def provision_redirect(request: HttpRequest) -> HttpResponse:
    provision_url = str(
        request.session.pop(HOME_PROVISION_TARGET_SESSION_KEY, "") or ""
    ).strip()
    request.session.modified = True
    if not provision_url:
        messages.info(
            request,
            _("Aucune synchronisation de compte n'est en attente."),
        )
        return redirect("homepage")

    return render(
        request,
        "main/provision_redirect.html",
        {
            "selected_group": _get_selected_group(request),
            "provision_url": provision_url,
        },
    )


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
    messages.info(request, _("Vous êtes déconnecté."))
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
                messages.error(
                    request,
                    _("Les paramètres du site sont introuvables pour cette langue."),
                )
                return _account_redirect(request, posted_member_search)

            moderator_form = ModeratorMessageForm(
                request.POST, instance=site_params, prefix="moderation"
            )
            if moderator_form.is_valid():
                moderator_form.save()
                messages.success(
                    request, _("Les réglages de modération ont été enregistrés.")
                )
                return _account_redirect(request, posted_member_search)

            if can_manage_site_members(request.user) and posted_member_search:
                member_results = search_directory_members(posted_member_search)
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                moderator_form=moderator_form,
                member_search_form=MemberSearchForm(
                    initial={"member_search": posted_member_search}
                ),
                member_results=member_results,
                member_search=posted_member_search,
            )
            return render(request, "main/connexion.html", context)

        if action == "save_site_settings":
            if not can_manage_site_settings(request.user):
                return HttpResponseForbidden(_("Accès refusé."))

            admin_instance = (
                site_params
                if site_params is not None
                else SiteParams(language=current_language)
            )
            admin_form = SiteParamsAdminForm(
                request.POST, instance=admin_instance, prefix="admin-settings"
            )
            if admin_form.is_valid():
                saved_params = admin_form.save(commit=False)
                saved_params.language = admin_instance.language
                saved_params.save()
                messages.success(
                    request, _("Les paramètres administrateur ont été enregistrés.")
                )
                return _account_redirect(request, posted_member_search)

            if posted_member_search:
                member_results = search_directory_members(posted_member_search)
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                admin_form=admin_form,
                member_search_form=MemberSearchForm(
                    initial={"member_search": posted_member_search}
                ),
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
                role_label = (
                    _("administrateur")
                    if cleaned["role_name"] == "admin"
                    else _("modérateur")
                )
                if cleaned["enabled"]:
                    messages.success(
                        request,
                        _("Le rôle %(role)s a été attribué.") % {"role": role_label},
                    )
                else:
                    messages.success(
                        request,
                        _("Le rôle %(role)s a été retiré.") % {"role": role_label},
                    )
                return _account_redirect(request, cleaned["member_search"])

            if posted_member_search:
                member_results = search_directory_members(posted_member_search)
            messages.error(
                request, _("La demande de mise à jour des rôles est invalide.")
            )
            context = _build_account_context(
                request,
                current_language=current_language,
                site_params=site_params,
                member_search_form=MemberSearchForm(
                    initial={"member_search": posted_member_search}
                ),
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
            member_search_form=MemberSearchForm(
                initial={"member_search": member_search}
            ),
            member_results=member_results,
            member_search=member_search,
        ),
    )


def site_params(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect("login")
    if not can_manage_site_settings(request.user):
        raise Http404

    selected_language = (
        request.GET.get("language") or _current_language_code(request) or "fr"
    )[:2].lower()
    if selected_language not in {"fr", "en"}:
        selected_language = "fr"

    language_db_value = selected_language.upper()
    current_params = SiteParams.objects.filter(
        language__iexact=language_db_value
    ).first()
    admin_instance = (
        current_params
        if current_params is not None
        else SiteParams(language=language_db_value)
    )

    if request.method == "POST":
        posted_language = (request.POST.get("language") or selected_language)[
            :2
        ].lower()
        if posted_language not in {"fr", "en"}:
            posted_language = selected_language
        posted_language_db = posted_language.upper()
        posted_current = SiteParams.objects.filter(
            language__iexact=posted_language_db
        ).first()
        posted_instance = (
            posted_current
            if posted_current is not None
            else SiteParams(language=posted_language_db)
        )
        admin_form = SiteParamsAdminForm(
            request.POST, instance=posted_instance, prefix="admin-settings"
        )
        if admin_form.is_valid():
            saved_params = admin_form.save(commit=False)
            saved_params.language = posted_language_db
            saved_params.save()
            return redirect(
                f"{reverse('site_params')}?{urlencode({'language': posted_language})}"
            )
        missing_or_invalid_fields = []
        for field_name, errors in admin_form.errors.items():
            if field_name == "__all__":
                continue
            field = admin_form.fields.get(field_name)
            label = str(field.label) if field else field_name
            if errors:
                missing_or_invalid_fields.append(label)
        if missing_or_invalid_fields:
            messages.error(
                request,
                _(
                    "Enregistrement impossible: informations manquantes ou invalides (%(fields)s)."
                )
                % {
                    "fields": ", ".join(missing_or_invalid_fields),
                },
            )
        else:
            messages.error(
                request,
                _("Enregistrement impossible: informations manquantes ou invalides."),
            )
        selected_language = posted_language
    else:
        admin_form = SiteParamsAdminForm(
            instance=admin_instance, prefix="admin-settings"
        )

    return render(
        request,
        "main/site_params.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "selected_group": _get_selected_group(request),
            "selected_language": selected_language,
            "admin_form": admin_form,
            "is_admin": True,
        },
    )


def privacy_policy(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/privacy_policy.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "selected_group": _get_selected_group(request),
        },
    )


def theme_preferences(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "main/theme_preferences.html",
        {
            "auth_mode": settings.AUTH_MODE,
            "selected_group": _get_selected_group(request),
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
            "selected_group": _get_selected_group(request),
            "current_language": getattr(request, "LANGUAGE_CODE", None)
            or get_language()
            or settings.LANGUAGE_CODE,
        },
    )
