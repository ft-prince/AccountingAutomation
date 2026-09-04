"""Inbound HTML is sanitised with bleach before storage (PROJECT_SPECS §12).
Scripts, styles, iframes and every <img> (tracking pixels included) are dropped; remote images
are never fetched."""

import re
from html.parser import HTMLParser

import bleach

ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title"], "td": ["colspan", "rowspan"], "th": ["colspan"]}
ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
# Remove these elements WITH their contents (bleach's strip=True would keep the inner text).
DROP_WITH_CONTENT = re.compile(
    r"<(script|style|iframe|object|embed|noscript|head|title)\b[^>]*>.*?</\1\s*>", re.I | re.S
)
WHITESPACE = re.compile(r"[ \t\xa0]+")
BLANK_LINES = re.compile(r"\n{3,}")
BLOCK_TAGS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"}
SKIP_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "head", "title"}


def sanitize_html(raw: str) -> str:
    stripped = DROP_WITH_CONTENT.sub("", raw)
    return bleach.clean(
        stripped,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )


class _TextExtractor(HTMLParser):
    """Text nodes joined with one line break per block boundary; skipped subtrees vanish."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def _break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "br" or tag in BLOCK_TAGS:
            self._break()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_TAGS:
            self._break()

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    """Best-effort text for classification when the provider gave no text/plain part."""
    extractor = _TextExtractor()
    extractor.feed(raw)
    extractor.close()
    lines = [WHITESPACE.sub(" ", line).strip() for line in "".join(extractor.parts).splitlines()]
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()
