import re

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe


_STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
_EM_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _render_inline(text: str) -> str:
    escaped = escape(text)
    escaped = _STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _EM_RE.sub(r"<em>\1</em>", escaped)
    return escaped


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
