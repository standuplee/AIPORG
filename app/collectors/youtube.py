"""YouTube Data API v3 collector (quota-conscious).

``search.list`` costs 100 of the free tier's 10,000 units/day (the most
expensive operation on this API), so this collector requests one page per
keyword by default. ``videos.list`` (1 unit/call) is used in ``fetch`` to
get each video's full description and stats -- it is not pre-fetched in
bulk during ``search`` because the 2.0 collector contract fetches one
``RawDocument`` per ``SearchResult`` (matching ``naver_news.py``/
``daum_news.py``), unlike ``aiporg/youtube/collector.py`` (1.0), which
batches ``videos.list`` across up to 50 ids per call. Comment collection
is not implemented here -- see HANDOFF.md's decision to model comments via
``metadata["document_type"]`` once a collector adds them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport
from app.core.enums import ChannelType
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class _Transport(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        ...


class YouTubeCollector(BaseCollector):
    """Collect video search results and details from YouTube Data API v3."""

    def __init__(
        self,
        *,
        api_key: str,
        transport: _Transport | None = None,
        region_code: str = "KR",
        relevance_language: str = "ko",
        results_per_page: int = 50,
        max_pages: int = 1,
    ) -> None:
        if not api_key:
            raise ValueError("YouTube API key is required")
        if not 1 <= results_per_page <= 50:
            raise ValueError("results_per_page must be between 1 and 50")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        self.api_key = api_key
        self.transport = transport or RequestsTransport()
        self.region_code = region_code
        self.relevance_language = relevance_language
        self.results_per_page = results_per_page
        self.max_pages = max_pages

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        results: list[SearchResult] = []
        page_token: str | None = None

        for _ in range(self.max_pages):
            params: dict[str, object] = {
                "part": "snippet",
                "type": "video",
                "q": query.query,
                "maxResults": self.results_per_page,
                "regionCode": self.region_code,
                "relevanceLanguage": self.relevance_language,
                "order": "relevance",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            response = await self.transport.get(YOUTUBE_SEARCH_URL, params=params)
            payload = self._parse_json_response(response, operation="search")
            items = payload.get("items")
            if not isinstance(items, list):
                raise self._malformed("items must be a list")

            for index, item in enumerate(items):
                if not isinstance(item, Mapping):
                    raise self._malformed(f"items[{index}] must be an object")
                video_id = self._video_id(item)
                snippet = item.get("snippet")
                if not video_id or not isinstance(snippet, Mapping):
                    raise self._malformed(f"items[{index}] is missing id/snippet")
                try:
                    title = self._required_string(snippet["title"])
                    published_at = self._parse_date(snippet["publishedAt"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise self._malformed(f"invalid items[{index}] snippet: {exc}") from exc
                if not title:
                    raise self._malformed(f"items[{index}] has an empty title")
                results.append(
                    SearchResult(
                        source="youtube",
                        channel=ChannelType.VIDEO,
                        title=title,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        published_at=published_at,
                        query=query.query,
                    )
                )

            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            page_token = next_token

        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        video_id = result.url.rsplit("v=", 1)[-1]
        response = await self.transport.get(
            YOUTUBE_VIDEOS_URL,
            params={"part": "snippet,statistics", "id": video_id, "key": self.api_key},
        )
        payload = self._parse_json_response(response, operation="fetch")
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise CollectorError(
                code="malformed_response",
                message="YouTube video lookup returned no items",
                details={"provider": "youtube", "video_id": video_id},
            )
        item = items[0]
        if not isinstance(item, Mapping):
            raise self._malformed("items[0] must be an object")
        snippet = item.get("snippet")
        if not isinstance(snippet, Mapping):
            raise self._malformed("items[0] is missing snippet")
        statistics = item.get("statistics")
        stats = statistics if isinstance(statistics, Mapping) else {}

        description = self._required_string(snippet.get("description"))
        body = f"{result.title}\n\n{description}".strip()
        if not body:
            raise CollectorError(
                code="malformed_response",
                message="YouTube video body is empty after normalization",
                details={"provider": "youtube", "video_id": video_id},
            )

        return RawDocument(
            document_id=uuid5(NAMESPACE_URL, result.url),
            source=result.source,
            channel=result.channel,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            query=result.query,
            platform="youtube",
            body=body,
            metadata={
                "view_count": self._int_or_none(stats.get("viewCount")),
                "like_count": self._int_or_none(stats.get("likeCount")),
                "comment_count": self._int_or_none(stats.get("commentCount")),
            },
            collected_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _video_id(item: Mapping[str, object]) -> str:
        id_field = item.get("id")
        if isinstance(id_field, Mapping):
            value = id_field.get("videoId")
            return value.strip() if isinstance(value, str) else ""
        return ""

    def _parse_json_response(self, response: HttpResponse, *, operation: str) -> Mapping[str, object]:
        if not 200 <= response.status_code < 300:
            raise CollectorError(
                code="http_status",
                message=f"YouTube {operation} returned status {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                details={"provider": "youtube", "status_code": response.status_code},
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
    def _int_or_none(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_date(value: object) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("publishedAt must be a non-empty string")
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("publishedAt must be ISO 8601") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _malformed(message: str) -> CollectorError:
        return CollectorError(
            code="malformed_response",
            message=f"Malformed YouTube response: {message}",
            details={"provider": "youtube"},
        )
