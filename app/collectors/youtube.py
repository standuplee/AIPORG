"""YouTube Data API v3 collector (quota-conscious).

``search.list`` costs 100 of the free tier's 10,000 units/day (the most
expensive operation on this API), so this collector requests one page per
keyword by default. ``videos.list`` (1 unit/call) is used in ``fetch`` to
get each video's full description and stats -- it is not pre-fetched in
bulk during ``search`` because the 2.0 collector contract fetches one
``RawDocument`` per ``SearchResult`` (matching ``naver_news.py``/
``daum_news.py``), unlike ``aiporg/youtube/collector.py`` (1.0), which
batches ``videos.list`` across up to 50 ids per call.

Comment collection (2026-10-17 decision, see HANDOFF.md): each top-level
comment is modeled as its own ``SearchResult``/``RawDocument`` pair, exactly
like a video, with a synthetic URL (``...watch?v=<video>&lc=<comment id>``)
so ``fetch()`` can tell them apart with no extra state. A comment's
``RawDocument.metadata`` carries ``document_type="comment"`` and
``parent_document_id`` (the video's own deterministic document id) -- the
same free-form ``metadata`` convention already used for sentiment labels
(``docs/aiporg2/analytics.md``), not a new schema field. Fetching comments
for a video costs 1 unit (``commentThreads.list``) plus 1 unit per comment
fetched later (``comments.list``) -- cheap next to ``search.list``'s 100,
but not free, hence ``max_comments_per_video``. A video with comments
disabled (or any other per-video commentThreads failure) does not fail the
whole search -- that video is just skipped for comments, consistent with
``aiporg/youtube/collector.py`` (1.0) logging and continuing past a single
bad keyword.

Analytics counts comments separately from articles
(``app/workflows/issues_to_analytics.py``) -- that split is not done here,
this module only tags documents correctly.
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
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"


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
        include_comments: bool = True,
        max_comments_per_video: int = 20,
    ) -> None:
        if not api_key:
            raise ValueError("YouTube API key is required")
        if not 1 <= results_per_page <= 50:
            raise ValueError("results_per_page must be between 1 and 50")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if not 1 <= max_comments_per_video <= 100:
            raise ValueError("max_comments_per_video must be between 1 and 100")
        self.api_key = api_key
        self.transport = transport or RequestsTransport()
        self.region_code = region_code
        self.relevance_language = relevance_language
        self.results_per_page = results_per_page
        self.max_pages = max_pages
        self.include_comments = include_comments
        self.max_comments_per_video = max_comments_per_video

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
                if self.include_comments:
                    results.extend(
                        await self._comment_results(video_id, query=query.query)
                    )

            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            page_token = next_token

        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        video_id, comment_id = self._parse_watch_url(result.url)
        if comment_id is not None:
            return await self._fetch_comment(result, video_id=video_id, comment_id=comment_id)
        return await self._fetch_video(result, video_id=video_id)

    async def _fetch_video(self, result: SearchResult, *, video_id: str) -> RawDocument:
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
                "document_type": "article",
                "view_count": self._int_or_none(stats.get("viewCount")),
                "like_count": self._int_or_none(stats.get("likeCount")),
                "comment_count": self._int_or_none(stats.get("commentCount")),
            },
            collected_at=datetime.now(timezone.utc),
        )

    async def _fetch_comment(
        self, result: SearchResult, *, video_id: str, comment_id: str
    ) -> RawDocument:
        response = await self.transport.get(
            YOUTUBE_COMMENTS_URL,
            params={
                "part": "snippet",
                "id": comment_id,
                "textFormat": "plainText",
                "key": self.api_key,
            },
        )
        payload = self._parse_json_response(response, operation="fetch_comment")
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise CollectorError(
                code="malformed_response",
                message="YouTube comment lookup returned no items",
                details={"provider": "youtube", "comment_id": comment_id},
            )
        item = items[0]
        if not isinstance(item, Mapping):
            raise self._malformed("items[0] must be an object")
        snippet = item.get("snippet")
        if not isinstance(snippet, Mapping):
            raise self._malformed("items[0] is missing snippet")

        text = self._required_string(snippet.get("textDisplay")) or self._required_string(
            snippet.get("textOriginal")
        )
        if not text:
            raise CollectorError(
                code="malformed_response",
                message="YouTube comment body is empty after normalization",
                details={"provider": "youtube", "comment_id": comment_id},
            )

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        return RawDocument(
            document_id=uuid5(NAMESPACE_URL, result.url),
            source=result.source,
            channel=result.channel,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            query=result.query,
            platform="youtube",
            body=text,
            metadata={
                "document_type": "comment",
                # Same deterministic formula fetch() uses for a video's own
                # document_id -- the video need not already be fetched for
                # this to resolve to the right id.
                "parent_document_id": str(uuid5(NAMESPACE_URL, video_url)),
                "like_count": self._int_or_none(snippet.get("likeCount")),
            },
            collected_at=datetime.now(timezone.utc),
        )

    async def _comment_results(self, video_id: str, *, query: str) -> list[SearchResult]:
        try:
            response = await self.transport.get(
                YOUTUBE_COMMENT_THREADS_URL,
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": self.max_comments_per_video,
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": self.api_key,
                },
            )
            payload = self._parse_json_response(response, operation="comment_threads")
        except CollectorError:
            # Comments disabled on this video (or any other per-video
            # failure): skip comments for it rather than failing the whole
            # keyword search over one video.
            return []

        items = payload.get("items")
        if not isinstance(items, list):
            return []

        results: list[SearchResult] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            thread_snippet = item.get("snippet")
            if not isinstance(thread_snippet, Mapping):
                continue
            top_level_comment = thread_snippet.get("topLevelComment")
            if not isinstance(top_level_comment, Mapping):
                continue
            comment_id = self._required_string(top_level_comment.get("id"))
            comment_snippet = top_level_comment.get("snippet")
            if not comment_id or not isinstance(comment_snippet, Mapping):
                continue
            text = self._required_string(comment_snippet.get("textDisplay"))
            published_raw = comment_snippet.get("publishedAt")
            if not text or not isinstance(published_raw, str):
                continue
            try:
                published_at = self._parse_date(published_raw)
            except ValueError:
                continue
            results.append(
                SearchResult(
                    source="youtube",
                    channel=ChannelType.VIDEO,
                    title=text[:80],
                    url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                    published_at=published_at,
                    query=query,
                )
            )
        return results

    @staticmethod
    def _parse_watch_url(url: str) -> tuple[str, str | None]:
        """Return ``(video_id, comment_id)`` from a watch URL this collector built."""

        query_string = url.split("?", 1)[-1]
        params = dict(
            pair.split("=", 1) for pair in query_string.split("&") if "=" in pair
        )
        return params.get("v", ""), params.get("lc")

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
