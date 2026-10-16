"""Naver News Search API collector."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"


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


class NaverNewsCollector(BaseCollector):
    """Collect news search results and article HTML from Naver."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: _Transport | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Naver API credentials are required")
        self.client_id = client_id
        self.client_secret = client_secret
        self.transport = transport or RequestsTransport()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        # Naver's search API caps a single call at `display<=100` results and
        # `start<=1000`. The previous implementation only ever requested
        # start=1, silently discarding everything past the first 100 results
        # for any keyword with more coverage than that. Page through the full
        # start<=1000 budget (sort=date keeps paging deterministic) so a
        # month's worth of articles for a busy keyword is not truncated.
        results: list[SearchResult] = []
        start = 1
        display = 100
        while start <= 1000:
            response = await self.transport.get(
                NAVER_NEWS_URL,
                params={"query": query.query, "display": display, "start": start, "sort": "date"},
                headers={
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                },
            )
            payload = self._parse_json_response(response, operation="search")
            items = payload.get("items")
            if not isinstance(items, list):
                raise self._malformed("items must be a list")

            for index, item in enumerate(items):
                if not isinstance(item, Mapping):
                    raise self._malformed(f"items[{index}] must be an object")
                try:
                    title = self._clean_inline(item["title"])
                    link = self._required_string(
                        item.get("originallink")
                    ) or self._required_string(item.get("link"))
                    description = self._clean_inline(item["description"])
                    published_at = self._parse_date(item["pubDate"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise self._malformed(f"invalid items[{index}] fields: {exc}") from exc
                if not link or not description:
                    raise self._malformed(f"items[{index}] contains an empty required field")
                results.append(
                    SearchResult(
                        source="naver",
                        channel=ChannelType.NEWS,
                        title=title,
                        url=link,
                        published_at=published_at,
                        query=query.query,
                    )
                )

            if len(items) < display:
                break
            start += display
        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        response = await self.transport.get(result.url)
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Naver article returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "naver", "url": result.url, "status_code": response.status_code},
            )
        body = self._clean_body(response.body)
        if not body:
            raise CollectorError(
                code="malformed_response",
                message="Naver article body is empty after normalization",
                details={"provider": "naver", "url": result.url},
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
            platform="naver",
            body=body,
            metadata={"content_type": content_type, "description": None},
            collected_at=datetime.now(timezone.utc),
        )

    def _parse_json_response(self, response: HttpResponse, *, operation: str) -> Mapping[str, object]:
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Naver {operation} returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "naver", "status_code": response.status_code},
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
    def _parse_date(value: object) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("pubDate must be a non-empty string")
        parsed = parsedate_to_datetime(value)
        if parsed is None:
            raise ValueError("pubDate is not RFC 822 date")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _malformed(message: str) -> CollectorError:
        return CollectorError(
            code="malformed_response",
            message=f"Malformed Naver response: {message}",
            details={"provider": "naver"},
        )
