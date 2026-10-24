"""Title, author and publication date from HTML metadata (no LLM)."""

import json
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from app.search.documents import PublishedAtSource

_KST = timezone(timedelta(hours=9))
_DATE_RE = re.compile(r"(\d{4})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})일?(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?")
_META_DATE_KEYS = [
    ("property", "article:published_time", PublishedAtSource.ARTICLE_META),
    ("name", "article:published_time", PublishedAtSource.ARTICLE_META),
    ("name", "pubdate", PublishedAtSource.ARTICLE_META),
    ("name", "date", PublishedAtSource.ARTICLE_META),
    ("itemprop", "datePublished", PublishedAtSource.ARTICLE_META),
    ("property", "og:article:published_time", PublishedAtSource.OPEN_GRAPH),
    ("property", "og:regDate", PublishedAtSource.OPEN_GRAPH),
]


def parse_date(value: str) -> datetime | None:
    """ISO 8601 or Korean-style dates; naive values are taken as KST."""
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        m = _DATE_RE.search(value)
        if not m:
            return None
        y, mo, d, h, mi, s = (int(g) if g else 0 for g in m.groups())
        try:
            parsed = datetime(y, mo, d, h, mi, s)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=_KST)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _json_ld(soup) -> tuple[dict, ...]:
    blocks = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            blocks += list(_walk(json.loads(tag.string or "")))
        except (ValueError, TypeError):
            continue  # malformed JSON-LD is common; other sources still apply
    return tuple(blocks)


def extract_metadata(html: str, text: str | None = None) -> dict:
    """Returns title, author, published_at, published_at_source (SEARCH_API fallback is the caller's)."""
    soup = BeautifulSoup(html, "lxml")
    ld = _json_ld(soup)

    def meta(attr, key):
        tag = soup.find("meta", attrs={attr: key})
        return (tag.get("content") or "").strip() if tag else ""

    title = meta("property", "og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    author = meta("name", "author") or meta("property", "article:author")
    for node in ld:
        a = node.get("author")
        if not author and isinstance(a, dict) and a.get("name"):
            author = str(a["name"])
        elif not author and isinstance(a, str):
            author = a

    published, source = None, PublishedAtSource.UNKNOWN
    candidates = [(str(n["datePublished"]), PublishedAtSource.JSON_LD) for n in ld if n.get("datePublished")]
    candidates += [(meta(a, k), s) for a, k, s in _META_DATE_KEYS if meta(a, k)]
    candidates += [(t["datetime"], PublishedAtSource.TIME_TAG) for t in soup.find_all("time") if t.get("datetime")]
    if text:  # last resort: a date near the top of the article body
        m = _DATE_RE.search(text[:400])
        if m:
            candidates.append((m.group(), PublishedAtSource.TEXT_PATTERN))
    for raw, src in candidates:
        parsed = parse_date(raw)
        if parsed:
            published, source = parsed, src
            break
    return {
        "title": title or None, "author": author or None,
        "published_at": published, "published_at_source": source,
    }
