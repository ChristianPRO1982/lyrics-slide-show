from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _


DEFAULT_ROBOTS = "noindex, follow"
INDEX_ROBOTS = "index, follow"
SITE_NAME = "Lyrics Slide Show"
DEFAULT_DESCRIPTION = _(
    "Lyrics Slide Show est un outil gratuit pour gérer, rechercher, organiser et projeter des chants lors d'animations, célébrations ou concerts."
)
HOMEPAGE_DESCRIPTION = DEFAULT_DESCRIPTION
SONGS_DESCRIPTION = _(
    "Recherchez dans le catalogue public de chants de Lyrics Slide Show et ouvrez les paroles disponibles pour préparer vos projections."
)
GROUPS_DESCRIPTION = _(
    "Les groupes Lyrics Slide Show permettent d'organiser les animations, les chants préparés et la collaboration autour des projections."
)
LOGIN_DESCRIPTION = _(
    "Connectez-vous à Lyrics Slide Show pour accéder aux fonctionnalités personnelles et collaboratives de gestion des chants, groupes et animations."
)
PRIVACY_DESCRIPTION = _(
    "Consultez la politique de confidentialité de Lyrics Slide Show et les règles de traitement des données nécessaires au service."
)

WHITESPACE_RE = re.compile(r"\s+")


def canonical_base_url() -> str:
    raw_value = str(
        getattr(settings, "LSS_CANONICAL_BASE_URL", "https://lss.carthographie.fr")
    ).strip()
    if not raw_value:
        raw_value = "https://lss.carthographie.fr"
    parsed = urlsplit(raw_value)
    if not parsed.scheme or not parsed.netloc:
        raw_value = "https://lss.carthographie.fr"
        parsed = urlsplit(raw_value)
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def canonical_url(path: str) -> str:
    normalized_path = str(path or "/").strip() or "/"
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return f"{canonical_base_url()}{normalized_path}"


def canonical_reverse(viewname: str, args=None, kwargs=None) -> str:
    return canonical_url(reverse(viewname, args=args, kwargs=kwargs))


def seo_context(
    *,
    title: str,
    description: str,
    path: str | None = None,
    index: bool = False,
    canonical: str | None = None,
    og_type: str = "website",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    canonical_value = (
        canonical
        if canonical is not None
        else canonical_url(path)
        if path
        else ""
    )
    normalized_description = normalize_text(description) or normalize_text(
        DEFAULT_DESCRIPTION
    )
    data: dict[str, object] = {
        "seo_title": normalize_text(title) or SITE_NAME,
        "seo_description": normalized_description,
        "seo_robots": INDEX_ROBOTS if index else DEFAULT_ROBOTS,
        "seo_canonical_url": canonical_value,
        "seo_og_title": normalize_text(title) or SITE_NAME,
        "seo_og_description": normalized_description,
        "seo_og_url": canonical_value,
        "seo_og_type": normalize_text(og_type) or "website",
        "seo_site_name": SITE_NAME,
    }
    if extra:
        data.update(extra)
    return data


def homepage_json_ld() -> str:
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": SITE_NAME,
                "url": canonical_url("/"),
                "description": str(HOMEPAGE_DESCRIPTION),
            },
            {
                "@type": "SoftwareApplication",
                "name": SITE_NAME,
                "applicationCategory": "MultimediaApplication",
                "operatingSystem": "Web",
                "url": canonical_url("/"),
                "description": str(HOMEPAGE_DESCRIPTION),
                "offers": {
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "EUR",
                },
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003C"
    )


def normalize_text(value: object) -> str:
    raw_value = "" if value is None else str(value)
    text = unescape(strip_tags(raw_value))
    return WHITESPACE_RE.sub(" ", text).strip()


def truncate_text(value: object, *, max_length: int = 155) -> str:
    text = normalize_text(value)
    if len(text) <= max_length:
        return text
    truncated = text[: max_length + 1].rsplit(" ", 1)[0].rstrip(" .,;:")
    if not truncated:
        truncated = text[:max_length].rstrip(" .,;:")
    return f"{truncated}…"


def _labels(items) -> list[str]:
    labels: list[str] = []
    for item in items or ():
        if isinstance(item, dict):
            label = normalize_text(item.get("label"))
        else:
            label = normalize_text(item)
        if label:
            labels.append(label)
    return labels


def _genre_labels(genre_groups) -> list[str]:
    labels: list[str] = []
    for _group_name, genres in genre_groups or ():
        labels.extend(_labels(genres))
    return labels


def build_song_meta_description(song, *, bands=(), artists=(), genre_groups=()) -> str:
    title = normalize_text(getattr(song, "title", ""))
    subtitle = normalize_text(getattr(song, "subtitle", ""))
    description = truncate_text(getattr(song, "description", ""), max_length=130)
    metadata = []
    if subtitle:
        metadata.append(subtitle)
    metadata.extend(_labels(artists)[:2])
    metadata.extend(_labels(bands)[:2])
    metadata.extend(_genre_labels(genre_groups)[:2])

    parts = [part for part in [description, ", ".join(metadata)] if part]
    if parts:
        return truncate_text(
            _("Chant %(title)s sur Lyrics Slide Show. %(details)s")
            % {"title": title, "details": " ".join(parts)},
            max_length=160,
        )
    return truncate_text(
        _("Paroles et informations du chant %(title)s sur Lyrics Slide Show.")
        % {"title": title or SITE_NAME},
        max_length=160,
    )


def robots_txt(_request) -> HttpResponse:
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {canonical_url('/sitemap.xml')}",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")
