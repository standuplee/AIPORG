"""Naver News Search API collector.

Comment collection (2026-10-17 decision) uses a different, more fragile
source than the search/fetch calls above: Naver's news articles render
comments through an unauthenticated AJAX widget ("CBOX") --
``apis.naver.com/commentBox/cbox/web_neo_list_jsonp.json`` -- that any
visitor's browser calls when it loads the comment section, not a product in
Naver's registered Open API Developer Center (unlike the search endpoint
above, which needs ``client_id``/``client_secret``). It needs no
authentication and returns public comment text, so this is the same kind of
access ``fetch()`` already does for the article page itself (an
unauthenticated GET of what a visitor's browser would load) rather than
circumventing any access control, but it is undocumented and can change
without notice -- verified against several live articles while building
this (exact param names, response shape, and an ISO 8601 ``regTime`` like
``2026-10-16T10:15:19+0900``), not from an official API reference. Treat it
as more fragile than the registered search API and keep ``include_comments``
easy to turn off if it breaks.

The CBOX endpoint is keyed by the Naver-hosted article id (``oid``/``aid``,
extractable only from an ``n.news.naver.com`` URL), but ``search()`` prefers
``originallink`` (the press's own domain) for the article's own
``SearchResult.url`` when available -- so the two ids a comment needs (which
article it belongs to, and which Naver-hosted ids to query CBOX with) do not
always come from the same URL. ``SearchResult`` has no field to carry both,
so a comment's synthetic URL embeds everything ``fetch()`` needs directly as
query parameters (``cm`` for the comment number, ``pid`` for the article's
own precomputed document id) -- the same technique
``app/collectors/youtube.py`` uses for its ``&lc=`` comment URLs, chosen
over adding a schema field.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Protocol
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.collectors.content_extraction import extract_article_text
from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport
from app.core.enums import ChannelType
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_COMMENT_API_URL = "https://apis.naver.com/commentBox/cbox/web_neo_list_jsonp.json"
_NAVER_ARTICLE_ID_RE = re.compile(r"n\.news\.naver\.com/(?:mnews/)?article/(\d+)/(\d+)")


class _Transport(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        ...


class NaverNewsCollector(BaseCollector):
    """Collect news search results and article HTML from Naver."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: _Transport | None = None,
        include_comments: bool = True,
        max_comments_per_article: int = 20,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Naver API credentials are required")
        if not 1 <= max_comments_per_article <= 100:
            raise ValueError("max_comments_per_article must be between 1 and 100")
        self.client_id = client_id
        self.client_secret = client_secret
        self.transport = transport or RequestsTransport()
        self.include_comments = include_comments
        self.max_comments_per_article = max_comments_per_article

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
                    # description is present in the API response but never
                    # actually stored (the RawDocument's body comes from
                    # fetch()-ing the real page, not this search snippet;
                    # metadata["description"] below is always None). Naver
                    # legitimately returns an empty description for some
                    # articles (confirmed live) -- requiring it to be
                    # non-empty used to discard every result on the same
                    # page as one such article for no benefit, so it is no
                    # longer required. Still type-checked so a non-string
                    # value is caught as malformed.
                    if not isinstance(item["description"], str):
                        raise TypeError("description must be a string")
                    published_at = self._parse_date(item["pubDate"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise self._malformed(f"invalid items[{index}] fields: {exc}") from exc
                if not link:
                    raise self._malformed(f"items[{index}] contains an empty required field")
                article_result = SearchResult(
                    source="naver",
                    channel=ChannelType.NEWS,
                    title=title,
                    url=link,
                    published_at=published_at,
                    query=query.query,
                )
                results.append(article_result)

                if self.include_comments:
                    naver_url = self._required_string(item.get("link"))
                    article_ids = _NAVER_ARTICLE_ID_RE.search(naver_url)
                    if article_ids:
                        oid, aid = article_ids.group(1), article_ids.group(2)
                        results.extend(
                            await self._comment_results(
                                oid, aid, article_result=article_result
                            )
                        )

            if len(items) < display:
                break
            start += display
        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        comment_params = self._parse_comment_url(result.url)
        if comment_params is not None:
            return await self._fetch_comment(result, **comment_params)

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
            metadata={"document_type": "article", "content_type": content_type, "description": None},
            collected_at=datetime.now(timezone.utc),
        )

    async def _comment_results(
        self, oid: str, aid: str, *, article_result: SearchResult
    ) -> list[SearchResult]:
        parent_document_id = str(uuid5(NAMESPACE_URL, article_result.url))
        try:
            payload = await self._call_comment_api(oid, aid, page_size=self.max_comments_per_article)
        except CollectorError:
            # Comments off, article not found by CBOX, or any other
            # per-article failure: skip comments for this one article rather
            # than failing the whole keyword search.
            return []

        result = payload.get("result")
        if not isinstance(result, Mapping):
            return []
        exposure_config = result.get("exposureConfig")
        if not isinstance(exposure_config, Mapping) or exposure_config.get("status") != "COMMENT_ON":
            return []
        comment_list = result.get("commentList")
        if not isinstance(comment_list, list):
            return []

        results: list[SearchResult] = []
        for comment in comment_list:
            if not isinstance(comment, Mapping):
                continue
            if comment.get("deleted") or comment.get("blind"):
                continue
            comment_no = self._required_string(comment.get("commentNo"))
            text = self._required_string(comment.get("contents"))
            reg_time = comment.get("regTime")
            if not comment_no or not text or not isinstance(reg_time, str):
                continue
            try:
                published_at = self._parse_comment_date(reg_time)
            except ValueError:
                continue
            comment_url = (
                f"https://n.news.naver.com/mnews/article/{oid}/{aid}"
                f"?{urlencode({'cm': comment_no, 'pid': parent_document_id})}"
            )
            results.append(
                SearchResult(
                    source=article_result.source,
                    channel=article_result.channel,
                    title=text[:80],
                    url=comment_url,
                    published_at=published_at,
                    query=article_result.query,
                )
            )
        return results

    async def _fetch_comment(
        self, result: SearchResult, *, oid: str, aid: str, comment_no: str, parent_document_id: str
    ) -> RawDocument:
        payload = await self._call_comment_api(oid, aid, page_size=self.max_comments_per_article)
        payload_result = payload.get("result")
        comment_list = payload_result.get("commentList") if isinstance(payload_result, Mapping) else None
        if not isinstance(comment_list, list):
            raise self._malformed("comment list missing on re-fetch")
        match = next(
            (
                item for item in comment_list
                if isinstance(item, Mapping)
                and self._required_string(item.get("commentNo")) == comment_no
            ),
            None,
        )
        if match is None:
            raise CollectorError(
                code="malformed_response",
                message="Naver comment was not found on re-fetch (removed or re-sorted)",
                details={"provider": "naver", "oid": oid, "aid": aid, "comment_no": comment_no},
            )
        text = self._required_string(match.get("contents"))
        if not text:
            raise CollectorError(
                code="malformed_response",
                message="Naver comment body is empty after normalization",
                details={"provider": "naver", "comment_no": comment_no},
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
            body=text,
            metadata={
                "document_type": "comment",
                "parent_document_id": parent_document_id,
                "sympathy_count": self._int_or_none(match.get("sympathyCount")),
                "antipathy_count": self._int_or_none(match.get("antipathyCount")),
            },
            collected_at=datetime.now(timezone.utc),
        )

    async def _call_comment_api(self, oid: str, aid: str, *, page_size: int) -> Mapping[str, object]:
        response = await self.transport.get(
            NAVER_COMMENT_API_URL,
            params={
                "ticket": "news",
                "templateId": "default_society",
                "pool": "cbox5",
                "lang": "ko",
                "country": "KR",
                "objectId": f"news{oid},{aid}",
                "pageSize": page_size,
                "indexSize": 10,
                "listType": "OBJECT",
                "pageType": "more",
                "page": 1,
                "initialize": "true",
                "useAltSort": "true",
                "sort": "favorite",
            },
            headers={
                "Referer": f"https://n.news.naver.com/mnews/article/{oid}/{aid}",
                # Confirmed live: this endpoint returns an HTTP 200 wrapping
                # a Forbidden error page for requests.request()'s default
                # User-Agent ("python-requests/..."); any browser-like value
                # is accepted.
                "User-Agent": "Mozilla/5.0",
            },
        )
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"Naver comment API returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "naver", "oid": oid, "aid": aid, "status_code": response.status_code},
            )
        # Response is JSONP, not plain JSON: confirmed live as
        # ``_callback({...});`` -- note the trailing semicolon *after* the
        # closing paren, which a naive single-char strip of only ")" misses
        # (leaving ");" unparsed and json.loads failing with "Extra data").
        body = response.body.strip()
        prefix = "_callback("
        if not body.startswith(prefix):
            raise self._malformed("comment response is not the expected JSONP shape")
        body = body[len(prefix):].rstrip()
        if body.endswith(";"):
            body = body[:-1]
        if body.endswith(")"):
            body = body[:-1]
        try:
            payload = json.loads(body)
        except (TypeError, ValueError) as exc:
            raise self._malformed("comment response is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise self._malformed("comment response JSON must be an object")
        return payload

    @staticmethod
    def _parse_comment_url(url: str) -> dict[str, str] | None:
        parsed = urlsplit(url)
        article_ids = _NAVER_ARTICLE_ID_RE.search(url)
        query = parse_qs(parsed.query)
        comment_no = query.get("cm", [None])[0]
        parent_document_id = query.get("pid", [None])[0]
        if not article_ids or not comment_no or not parent_document_id:
            return None
        return {
            "oid": article_ids.group(1),
            "aid": article_ids.group(2),
            "comment_no": comment_no,
            "parent_document_id": parent_document_id,
        }

    @staticmethod
    def _parse_comment_date(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.strip())
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
        return extract_article_text(value)

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
