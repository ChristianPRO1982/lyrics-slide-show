import re, unicodedata


def strip_accents(text: str) -> str:
    """Return a copy of `text` with diacritics removed (é->e, ç->c, etc.)."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def build_like_pattern(
    text: str,
    use_user_wildcards: bool = True,
    collapse_separators: bool = True,
    accent_insensitive: bool = False,
    auto_wrap_percent: bool = True,
    escape_char: str = "\\",
) -> str:
    """Build a safe SQL LIKE pattern from user input for fuzzy lyric searches.

    Features:
    - Converts user wildcards: '*' -> '%', '?' -> '_'.
    - Escapes literal '%', '_' and the escape character.
    - Optionally collapses runs of separators (spaces, punctuation, quotes) to a single '%'.
    - Optional accent-insensitive normalization (é->e) to improve French matching.
    - Optionally wraps with leading/trailing '%' for substring search.
    - Returns an empty string if the input is falsy.
    """
    if not text:
        return ""

    value = text

    if accent_insensitive:
        value = strip_accents(value)

    esc = re.escape(escape_char)
    value = value.replace(escape_char, escape_char + escape_char)
    value = value.replace("%", escape_char + "%")
    value = value.replace("_", escape_char + "_")

    if use_user_wildcards:
        value = value.replace("*", "%").replace("?", "_")

    if collapse_separators:
        value = re.sub(r"[^\w%_]+", "%", value, flags=re.UNICODE)
        value = re.sub(r"%{2,}", "%", value).strip("%")

    if auto_wrap_percent:
        value = f"%{value}%"

    return value
