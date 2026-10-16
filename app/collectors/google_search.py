"""Google Programmable Search Engine (Custom Search JSON API) collector.

Google is a *discovery path* (requirements §3.2), not a content channel of
its own -- it can surface news, blog, or community pages. This collector
cannot reliably tell those apart from a search result alone, so (as an
explicit, documented simplification -- not a hidden guess) every result is
tagged ``ChannelType.NEWS``. Refining that with a URL/domain classifier is
future work, not done here.

Uses the official Custom Search JSON API (not scraping google.com's result
pages, which its terms of service prohibit) --
https://developers.google.com/custom-search/v1/overview . Requires both an
API key and a Programmable Search Engine ID (``cx``) configured to search the
entire web. The free tier is 100 queries/day; each ``search()`` page costs
one query, so keep ``max_pages`` modest for a free-tier budget.

The API does not reliably return a publish date for arbitrary web pages.
Rather than fabricate one, items whose date cannot be found in
``pagemap.metatags`` are dropped from the results entirely -- matching the
project rule that undated material is held back, not silently included
(requirements §3.4).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport
from app.core.enums import ChannelType
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Checked in this order; the first one present and parseable wins.
_PUBLISHED_AT_METATAG_KEYS = (
    "article:published_time",
    "og:article:published_time",
    "datepublished",
    "date",
    "og:updated_time",
)


class _Transport(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        ...


class _TextExtractor(HTMLParser):
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


class GoogleSearchCollector(BaseCollector):
    """Discover web documents via Google's Custom Search JSON API."""

    def __init__(
        self,
        *,
        api_key: str,
        search_engine_id: str,
        transport: _Transport | None = None,
        results_per_page: int = 10,
        max_pages: int = 1,
    ) -> None:
        if not api_key:
            raise ValueError("Google API key is required")
        if not search_engine_id:
            raise ValueError("Google search engine id (cx) is required")
        if not 1 <= results_per_page <= 10:
            raise ValueError("results_per_page must be between 1 and 10")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.transport = transport or RequestsTransport()
        self.results_per_page = results_per_page
        self.max_pages = max_pages

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        results: list[SearchResult] = []
        for page in range(self.max_pages):
            start = 1 + page * self.results_per_page
            if start > 91:  # the API rejects start > 91 (max 100 results total)
                break
            response = await self.transport.get(
                GOOGLE_SEARCH_URL,
                params={
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query.query,
                    "num": self.results_per_page,
                    "start": start,
                },
            )
            payload = self._parse_json_response(response)
            items = payload.get("items", [])
            # Google omits the "items" key entirely for a zero-result page --
            # that is a valid response, not a malformed one.
            if not isinstance(items, list):
                raise self._malformed("items must be a list when present")
            if not items:
                break

            for index, item in enumerate(items):
                if not isinstance(item, Mapping):
                    raise self._malformed(f"items[{index}] must be an object")
                try:
                    title = self._clean_inline(item["title"])
                    link = self._required_string(item["link"])
                except (KeyError, TypeError) as exc:
                    raise self._malformed(f"invalid items[{index}] fields: {exc}") from exc
                if not title or not link:
                    raise self._malformed(f"items[{index}] contains an empty required field")

                published_at = self._extract_published_at(item)
                if published_at is None:
                    continue  # undated result: held back, not fabricated or guessed

                source = self._required_string(item.get("displayLink")) or link
                results.append(
                    SearchResult(
                        source=source,
                        # Google is a discovery path across content types; see
                        # the module docstring for why NEWS is a deliberate
                        # simplification rather than real classification.
                        channel=ChannelType.NEWS,
                        title=title,
                        url=link,
                        published_at=published_at,
                        query=query.query,
                    )
                )

            if len(items) < self.results_per_page:
                break
        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        response = await self.transport.get(result.url)
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Google-discovered page returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "google", "url": result.url, "status_code": response.status_code},
            )
        body = self._clean_body(response.body)
        if not body:
            raise CollectorError(
                code="malformed_response",
                message="Google-discovered page body is empty after normalization",
                details={"provider": "google", "url": result.url},
            )
        content_type = next(
            (value for key, value in response.headers.items() if key.lower() == "content-type"),
            None,
        )
        return RawDocument(
            document_id=uuid5(NAMESPACE_URL, result.url),
            source=result.source,
            channel=result.channel,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            query=result.query,
            platform="google",
            body=body,
            metadata={"content_type": content_type},
            collected_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _extract_published_at(item: Mapping[str, object]) -> datetime | None:
        pagemap = item.get("pagemap")
        if not isinstance(pagemap, Mapping):
            return None
        metatags = pagemap.get("metatags")
        if not isinstance(metatags, list) or not metatags:
            return None
        first = metatags[0]
        if not isinstance(first, Mapping):
            return None
        for key in _PUBLISHED_AT_METATAG_KEYS:
            value = first.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    def _parse_json_response(self, response: HttpResponse) -> Mapping[str, object]:
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Google search returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "google", "status_code": response.status_code},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise self._malformed("response body is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise self._malformed("response JSON must be an object")
        return payload

    @staticmethod
    def _required_string(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _clean_inline(value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("must be a string")
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", "", value))).strip()

    @staticmethod
    def _clean_body(value: str) -> str:
        parser = _TextExtractor()
        parser.feed(value)
        parser.close()
        return re.sub(r"\s+", " ", unescape("".join(parser.parts))).strip()

    @staticmethod
    def _malformed(message: str) -> CollectorError:
        return CollectorError(
            code="malformed_response",
            message=f"Malformed Google response: {message}",
            details={"provider": "google"},
        )
