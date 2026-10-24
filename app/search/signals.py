"""Deterministic, issue-independent signals for a search hit."""

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from app.search.schemas import (
    NumericMention,
    PeriodStatus,
    SearchChannel,
    SearchResult,
    SearchResultMetadata,
    SourceType,
)

_REGISTRY = Path(__file__).resolve().parents[2] / "config" / "source_registry.yaml"

_NUMERIC = [
    ("DATE", re.compile(r"\d{4}년(?:\s*\d{1,2}월)?(?:\s*\d{1,2}일)?|\d{1,2}월\s*\d{1,2}일")),
    ("PERCENT", re.compile(r"\d[\d,.]*\s*(?:%|퍼센트)")),
    ("MONEY", re.compile(r"\d[\d,.]*\s*(?:조|억|만)?\s*(?:원|달러)")),
    ("COUNT", re.compile(r"\d[\d,.]*\s*(?:곳|명|개|건|가구|대|호|개소|채|회|단계)")),
]
_NEWS_PATH = re.compile(r"article|/news|newsview|/view", re.I)
_LIST_PATH = re.compile(r"/(?:list|search|tag|category|newslist)\b|articleList|[?&]t=$", re.I)
_ERROR_TITLE = re.compile(r"404|not found|페이지를 찾을 수 없", re.I)


@lru_cache(maxsize=1)
def _registry() -> list[tuple[str, SourceType]]:
    data = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    entries = [(d, SourceType(t)) for t, domains in data.items() for d in domains]
    return sorted(entries, key=lambda e: len(e[0]), reverse=True)  # longest domain wins


def source_type(result: SearchResult) -> SourceType:
    url = result.original_url or result.url
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    for domain, kind in _registry():
        if host == domain or host.endswith("." + domain):
            return kind
    if result.channel is SearchChannel.BLOG:
        return SourceType.BLOG
    if result.channel is SearchChannel.CAFE:
        return SourceType.COMMUNITY
    if result.channel is SearchChannel.NEWS or _NEWS_PATH.search(url):
        return SourceType.NEWS
    return SourceType.OTHER


def numeric_mentions(text: str) -> list[NumericMention]:
    found, seen = [], set()
    for kind, pattern in _NUMERIC:
        for m in pattern.finditer(text):
            raw = m.group().strip()
            if (kind, raw) in seen:
                continue
            seen.add((kind, raw))
            found.append(NumericMention(raw=raw, type=kind, context=text[max(0, m.start() - 12) : m.end() + 12].strip()))
    return found


def noise_flags(result: SearchResult) -> list[str]:
    flags = []
    if not result.title.strip() or not (result.snippet.strip() or result.title.strip()):
        flags.append("EMPTY")
    if _ERROR_TITLE.search(result.title):
        flags.append("ERROR_PAGE")
    if _LIST_PATH.search(result.original_url or result.url):
        flags.append("LIST_OR_SEARCH_PAGE")
    return flags


def build_metadata(result: SearchResult, period_status: PeriodStatus) -> SearchResultMetadata:
    mentions = numeric_mentions(f"{result.title} {result.snippet}")
    return SearchResultMetadata(
        source_type=source_type(result),
        period_status=period_status,
        numeric_mentions=mentions,
        date_mentions=[m.raw for m in mentions if m.type == "DATE"],
        noise_flags=noise_flags(result),
    )
