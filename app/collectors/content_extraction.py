"""Shared article-body extraction for HTML-fetching collectors.

``naver_news.py``/``daum_news.py``/``google_search.py`` each fetch arbitrary
publisher pages. Until now they kept a page's *entire* visible text as the
article body -- nav/menu/related-article widgets included -- because their
own ``_TextExtractor`` only skipped ``<script>``/``<style>``/``<noscript>``/
``<template>`` content. On real collected data this contaminated Fact claims
and TOP10 keyword frequencies with site-chrome text ("바로가기", "기사보내기",
"닫기"; see HANDOFF.md's 2026-10-19 real-data test). ``trafilatura`` does
real main-content extraction (boilerplate removal tuned on real news sites)
and is tried first; its heuristics reject tiny or atypical inputs (returns
``None``), so a whole-page fallback is kept rather than making ``fetch()``
raise just because trafilatura couldn't identify an "article" shape.
"""

from html import unescape
from html.parser import HTMLParser
import re

import trafilatura


class _LegacyWholePageExtractor(HTMLParser):
    """Whole-page text extractor -- the previous behaviour, kept as a fallback."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "section"}:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "section"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _whole_page_text(html: str) -> str:
    parser = _LegacyWholePageExtractor()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def extract_article_text(html: str) -> str:
    """Extract the main article text from a fetched HTML page.

    Tries trafilatura's main-content extraction first (reader-comment
    sections excluded -- comments are collected as separate documents, see
    the ``document_type`` convention in ``app/collectors/naver_news.py`` and
    ``app/collectors/youtube.py``). Falls back to a whole-page text dump only
    when trafilatura can't identify an article at all (returns ``None`` --
    e.g. an unusually small or non-article page).
    """

    extracted = trafilatura.extract(html, include_comments=False)
    if extracted is None:
        extracted = _whole_page_text(html)
    return re.sub(r"\s+", " ", unescape(extracted)).strip()
