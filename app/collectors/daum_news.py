"""Daum News collection through Kakao Web Search API."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport
from app.core.enums import ChannelType
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


DAUM_WEB_SEARCH_URL = "https://dapi.kakao.com/v2/search/web"
_ALLOWED_HOSTS = frozenset({"news.daum.net", "v.daum.net"})


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


class DaumNewsCollector(BaseCollector):
    """Collect Daum-hosted news documents from Kakao web search."""

    def __init__(
        self,
        *,
        api_key: str,
        transport: _Transport | None = None,
        page_size: int = 50,
    ) -> None:
        if not api_key:
            raise ValueError("Kakao API key is required")
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")
        self.api_key = api_key
        self.transport = transport or RequestsTransport()
        self.page_size = page_size

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        results: list[SearchResult] = []
        page = 1
        while True:
            response = await self.transport.get(
                DAUM_WEB_SEARCH_URL,
                params={
                    "query": query.query,
                    "page": page,
                    "size": self.page_size,
                    "sort": "recency",
                },
                headers={"Authorization": f"KakaoAK {self.api_key}"},
            )
            payload = self._parse_json_response(response, operation="search")
            documents = payload.get("documents")
            meta = payload.get("meta")
            if not isinstance(documents, list) or not isinstance(meta, Mapping):
                raise self._malformed("documents must be a list and meta must be an object")
            is_end = meta.get("is_end")
            if not isinstance(is_end, bool):
                raise self._malformed("meta.is_end must be a boolean")

            for index, document in enumerate(documents):
                if not isinstance(document, Mapping):
                    raise self._malformed(f"documents[{index}] must be an object")
                url = self._required_string(document.get("url"))
                if not self._is_allowed_url(url):
                    continue
                try:
                    title = self._clean_inline(document["title"])
                    published_at = self._parse_date(document["datetime"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise self._malformed(f"invalid documents[{index}] fields: {exc}") from exc
                if not title:
                    raise self._malformed(f"documents[{index}] contains an empty title")
                results.append(
                    SearchResult(
                        source="daum",
                        channel=ChannelType.NEWS,
                        title=title,
                        url=url,
                        published_at=published_at,
                        query=query.query,
                    )
                )
            if is_end:
                return results
            page += 1

    async def fetch(self, result: SearchResult) -> RawDocument:
        response = await self.transport.get(result.url, headers={"User-Agent": "AIPORG/2.0"})
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Daum article returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "daum", "url": result.url, "status_code": response.status_code},
            )
        body = self._clean_body(response.body)
        if not body:
            raise CollectorError(
                code="malformed_response",
                message="Daum article body is empty after normalization",
                details={"provider": "daum", "url": result.url},
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
            platform="daum",
            body=body,
            metadata={"content_type": content_type},
            collected_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_json_response(response: HttpResponse, *, operation: str) -> Mapping[str, object]:
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Daum {operation} returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "daum", "status_code": response.status_code},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise DaumNewsCollector._malformed("response body is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise DaumNewsCollector._malformed("response JSON must be an object")
        return payload

    @staticmethod
    def _is_allowed_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and parsed.hostname in _ALLOWED_HOSTS

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
            raise ValueError("datetime must be a non-empty string")
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("datetime must be ISO 8601") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _malformed(message: str) -> CollectorError:
        return CollectorError(
            code="malformed_response",
            message=f"Malformed Daum response: {message}",
            details={"provider": "daum"},
        )
