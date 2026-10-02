import re
from urllib.parse import urlsplit

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe


_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
_EM_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_BARE_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}"
    r"(?::[0-9]{1,5})?(?:[/?#].*)?$",
    re.IGNORECASE,
)
_ALLOWED_LINK_SCHEMES = {"http", "https", "mailto", "tel"}
_ALLOWED_RELATIVE_PREFIXES = ("#", "/", "./", "../")


def _normalize_homepage_link_url(url: str) -> str | None:
    if not url or any(character in url for character in "\r\n\t"):
        return None

    if url.startswith("//"):
        return None

    parsed = urlsplit(url)
    if parsed.scheme:
        if parsed.scheme.lower() in _ALLOWED_LINK_SCHEMES:
            return url
        return None

    if url.startswith(_ALLOWED_RELATIVE_PREFIXES):
        return url

    if _BARE_DOMAIN_RE.match(url):
        return f"https://{url}"

    return None


def _render_inline_formatting(text: str) -> str:
    escaped = escape(text)
    escaped = _STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _EM_RE.sub(r"<em>\1</em>", escaped)
    return escaped


def _render_inline(text: str) -> str:
    rendered_parts: list[str] = []
    position = 0

    for match in _LINK_RE.finditer(text):
        rendered_parts.append(_render_inline_formatting(text[position : match.start()]))
        label = match.group(1)
        url = match.group(2)
        normalized_url = _normalize_homepage_link_url(url)

        if normalized_url:
            rendered_parts.append(
                f'<a href="{escape(normalized_url)}">'
                f"{_render_inline_formatting(label)}</a>"
            )
        else:
            rendered_parts.append(_render_inline_formatting(match.group(0)))

        position = match.end()

    rendered_parts.append(_render_inline_formatting(text[position:]))
    return "".join(rendered_parts)


def render_homepage_markdown(value: str | None) -> SafeString:
    normalized = str(value or "").replace("\r\n", "\n").strip()
    if not normalized:
        return mark_safe("")

    lines = normalized.split("\n")
    blocks: list[str] = []
    paragraph_lines: list[str] = []
    quote_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        blocks.append(
            f"<p>{'<br>'.join(_render_inline(line) for line in paragraph_lines)}</p>"
        )
        paragraph_lines.clear()

    def flush_quote() -> None:
        if not quote_lines:
            return
        blocks.append(
            '<blockquote class="site-home-markdown-quote">'
            f"{'<br>'.join(_render_inline(line) for line in quote_lines)}"
            "</blockquote>"
        )
        quote_lines.clear()

    for line in lines:
        if line.startswith("> "):
            flush_paragraph()
            quote_lines.append(line[2:])
            continue

        if quote_lines:
            flush_quote()

        paragraph_lines.append(line)

    flush_quote()
    flush_paragraph()
    return mark_safe("".join(blocks))
