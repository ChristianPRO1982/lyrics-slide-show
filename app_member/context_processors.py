import hashlib
import json

from django.utils.translation import gettext as _

from app_member.services import MAIN_PAGE_NAMES, get_site_params_for_language


def _build_section(
    section_id: str, title: str, message: str, cooldown_minutes: int
) -> dict[str, object]:
    normalized_message = str(message or "").strip()
    if not normalized_message:
        return {}

    version = hashlib.sha256(normalized_message.encode("utf-8")).hexdigest()
    return {
        "id": section_id,
        "title": title,
        "messageMarkdown": normalized_message,
        "cooldownMinutes": int(cooldown_minutes),
        "version": version,
    }


def site_popup(request) -> dict[str, str]:
    try:
        params = get_site_params_for_language(getattr(request, "LANGUAGE_CODE", None))
    except Exception:
        params = None

    sections: list[dict[str, object]] = []
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")

    if params is not None:
        admin_section = _build_section(
            "admin",
            _("Message des administrateurs"),
            params.admin_message,
            params.admin_message_cooldown_minutes,
        )
        if admin_section:
            sections.append(admin_section)

        if url_name in MAIN_PAGE_NAMES:
            moderator_section = _build_section(
                "moderator",
                _("Message de modération"),
                params.moderator_message,
                params.moderator_message_cooldown_minutes,
            )
            if moderator_section:
                sections.append(moderator_section)

    return {
        "lss_site_popup_json": json.dumps(
            {
                "title": _("Informations du site"),
                "sections": sections,
            }
        )
    }
