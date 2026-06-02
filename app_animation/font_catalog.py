from __future__ import annotations

from dataclasses import dataclass

FALLBACK_FONT_FAMILY = "Source Sans Pro"

GOOGLE_FONTS_STYLESHEET_HREF = (
    "https://fonts.googleapis.com/css2?family=Amatic+SC&family=Anton&family=Baloo+2&family=Bangers"
    "&family=Bree+Serif&family=Caveat&family=Caveat+Brush&family=Chewy&family=Concert+One&family=Fredoka"
    "&family=Fugaz+One&family=Gloria+Hallelujah&family=Indie+Flower&family=Lobster&family=Patrick+Hand"
    "&family=Poppins&family=Quicksand&family=Raleway&family=Righteous&family=Roboto+Slab&family=Sacramento"
    "&family=Sarabun&family=Source+Sans+Pro&family=Special+Elite&family=Staatliches&family=Ubuntu"
    "&family=Work+Sans&display=swap"
)

FONT_FAMILIES: tuple[str, ...] = (
    "Amatic SC",
    "Anton",
    "Baloo 2",
    "Bangers",
    "Bree Serif",
    "Caveat",
    "Caveat Brush",
    "Chewy",
    "Concert One",
    "Fredoka",
    "Fugaz One",
    "Gloria Hallelujah",
    "Indie Flower",
    "Lobster",
    "Patrick Hand",
    "Poppins",
    "Quicksand",
    "Raleway",
    "Righteous",
    "Roboto Slab",
    "Sacramento",
    "Sarabun",
    "Source Sans Pro",
    "Special Elite",
    "Staatliches",
    "Ubuntu",
    "Work Sans",
)

ALLOWED_FONT_FAMILIES = frozenset(FONT_FAMILIES)


@dataclass(frozen=True)
class FontPreview:
    family: str
    sample: str


def is_allowed_font_family(value: str | None) -> bool:
    return str(value or "").strip() in ALLOWED_FONT_FAMILIES


def normalize_animation_font_family(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in ALLOWED_FONT_FAMILIES else FALLBACK_FONT_FAMILY


def normalize_override_font_family(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return normalized if normalized in ALLOWED_FONT_FAMILIES else None


def list_font_choices() -> tuple[tuple[str, str], ...]:
    return tuple((family, family) for family in FONT_FAMILIES)


def list_font_previews(
    sample_text: str = "TEXT text àéèêïùôÔç",
) -> tuple[FontPreview, ...]:
    return tuple(
        FontPreview(family=family, sample=sample_text) for family in FONT_FAMILIES
    )
