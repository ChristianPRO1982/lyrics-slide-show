import json


HOME_CARD_ICON_SLUGS = (
    "account",
    "animations",
    "button",
    "close",
    "cookies",
    "groups",
    "hamburger",
    "home",
    "login",
    "logout",
    "lss",
    "signup",
    "songs",
    "theme",
)

HOME_CARD_ICON_CHOICES = [(slug, slug) for slug in HOME_CARD_ICON_SLUGS]
HOME_CARD_ICON_SET = frozenset(HOME_CARD_ICON_SLUGS)


def normalize_home_card_icon_slug(value: object) -> str:
    slug = str(value or "").strip()
    return slug if slug in HOME_CARD_ICON_SET else ""


def parse_home_cards(raw_value: str | None) -> list[dict[str, str]]:
    raw = str(raw_value or "").strip()
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [{"title": "", "text": raw, "image": ""}]

    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list):
        return []

    output: list[dict[str, str]] = []
    for item in cards[:6]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        image = normalize_home_card_icon_slug(item.get("image"))
        if not title and not text and not image:
            continue
        output.append({"title": title, "text": text, "image": image})
    return output


def filter_display_home_cards(cards: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        card
        for card in cards
        if str(card.get("title") or "").strip() and str(card.get("text") or "").strip()
    ]


def build_home_cards_payload(cards: list[dict[str, object]]) -> str:
    normalized_cards = []
    for card in cards[:6]:
        title = str(card.get("title") or "").strip()
        text = str(card.get("text") or "").strip()
        image = normalize_home_card_icon_slug(card.get("image"))
        if not title and not text and not image:
            continue
        normalized_cards.append({"title": title, "text": text, "image": image})
    return json.dumps({"cards": normalized_cards}, ensure_ascii=False)
