import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse
from app.collectors.youtube import (
    YOUTUBE_COMMENT_THREADS_URL,
    YOUTUBE_COMMENTS_URL,
    YOUTUBE_SEARCH_URL,
    YOUTUBE_VIDEOS_URL,
    YouTubeCollector,
)
from app.core.enums import ChannelType
from app.schemas.document import SearchResult
from app.schemas.query import SearchQuery


class MockTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict[str, object]] = []

    async def get(self, url: str, *, params=None, headers=None) -> HttpResponse:
        self.calls.append({"url": url, "params": params, "headers": headers})
        return next(self.responses)


def search_query() -> SearchQuery:
    return SearchQuery(query="박수현 충남", channels=[ChannelType.VIDEO])


def _search_item(video_id: str, title: str) -> str:
    return (
        '{"id": {"videoId": "%s"}, "snippet": {"title": "%s", '
        '"publishedAt": "2026-07-20T10:00:00Z"}}' % (video_id, title)
    )


def test_constructor_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        YouTubeCollector(api_key="")
    with pytest.raises(ValueError):
        YouTubeCollector(api_key="key", results_per_page=0)
    with pytest.raises(ValueError):
        YouTubeCollector(api_key="key", results_per_page=51)
    with pytest.raises(ValueError):
        YouTubeCollector(api_key="key", max_pages=0)


def test_search_sends_key_region_and_relevance_language_and_parses_items() -> None:
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body='{"items": [' + _search_item("abc123", "박수현 충남 간담회") + "]}",
            )
        ]
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport, include_comments=False)

    results = asyncio.run(collector.search(search_query()))

    assert results == [
        SearchResult(
            source="youtube",
            channel=ChannelType.VIDEO,
            title="박수현 충남 간담회",
            url="https://www.youtube.com/watch?v=abc123",
            published_at=datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
            query="박수현 충남",
        )
    ]
    call = transport.calls[0]
    assert call["url"] == YOUTUBE_SEARCH_URL
    assert call["params"]["key"] == "yt-key"
    assert call["params"]["regionCode"] == "KR"
    assert call["params"]["relevanceLanguage"] == "ko"
    assert call["params"]["q"] == "박수현 충남"
    assert "pageToken" not in call["params"]


def test_search_follows_next_page_token_up_to_max_pages() -> None:
    first_page = (
        '{"items": [' + _search_item("v1", "영상1") + '], "nextPageToken": "page-2"}'
    )
    second_page = '{"items": [' + _search_item("v2", "영상2") + "]}"
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=first_page),
            HttpResponse(status_code=200, headers={}, body=second_page),
        ]
    )
    collector = YouTubeCollector(
        api_key="yt-key", transport=transport, max_pages=2, include_comments=False
    )

    results = asyncio.run(collector.search(search_query()))

    assert [r.url for r in results] == [
        "https://www.youtube.com/watch?v=v1",
        "https://www.youtube.com/watch?v=v2",
    ]
    assert transport.calls[1]["params"]["pageToken"] == "page-2"


def test_search_stops_at_max_pages_even_with_a_next_page_token() -> None:
    page = '{"items": [' + _search_item("v1", "영상1") + '], "nextPageToken": "more"}'
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=page)])
    collector = YouTubeCollector(
        api_key="yt-key", transport=transport, max_pages=1, include_comments=False
    )

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert len(transport.calls) == 1


def test_fetch_combines_title_and_description_and_captures_stats() -> None:
    response = HttpResponse(
        status_code=200,
        headers={},
        body=(
            '{"items": [{"snippet": {"description": "충남 간담회 설명"}, '
            '"statistics": {"viewCount": "1200", "likeCount": "34", '
            '"commentCount": "5"}}]}'
        ),
    )
    transport = MockTransport([response])
    result = SearchResult(
        source="youtube",
        channel=ChannelType.VIDEO,
        title="박수현 충남 간담회",
        url="https://www.youtube.com/watch?v=abc123",
        published_at=datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    document = asyncio.run(collector.fetch(result))

    assert document.body == "박수현 충남 간담회\n\n충남 간담회 설명"
    assert document.platform == "youtube"
    assert isinstance(document.document_id, UUID)
    assert document.metadata == {
        "document_type": "article",
        "view_count": 1200,
        "like_count": 34,
        "comment_count": 5,
    }
    assert transport.calls[0]["url"] == YOUTUBE_VIDEOS_URL
    assert transport.calls[0]["params"]["id"] == "abc123"


def test_fetch_raises_when_video_lookup_returns_no_items() -> None:
    transport = MockTransport(
        [HttpResponse(status_code=200, headers={}, body='{"items": []}')]
    )
    result = SearchResult(
        source="youtube",
        channel=ChannelType.VIDEO,
        title="제목",
        url="https://www.youtube.com/watch?v=missing",
        published_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        query="q",
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.fetch(result))

    assert raised.value.code == "malformed_response"


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        ("not-json", "malformed_response"),
        ('{"items": {}}', "malformed_response"),
        ('{"items": [{"id": {"videoId": "x"}}]}', "malformed_response"),
    ],
)
def test_search_raises_structured_error_for_malformed_response(body: str, expected_code: str) -> None:
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=body)])
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.search(search_query()))

    assert raised.value.code == expected_code
    assert raised.value.details["provider"] == "youtube"


def test_search_raises_retryable_error_on_server_failure() -> None:
    transport = MockTransport([HttpResponse(status_code=503, headers={}, body="")])
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.search(search_query()))

    assert raised.value.code == "http_status"
    assert raised.value.retryable is True


def _comment_thread_item(comment_id: str, text: str, published: str) -> str:
    return (
        '{"snippet": {"topLevelComment": {"id": "%s", "snippet": '
        '{"textDisplay": "%s", "publishedAt": "%s"}}}}'
        % (comment_id, text, published)
    )


def test_search_includes_top_level_comments_as_search_results() -> None:
    video_page = '{"items": [' + _search_item("abc123", "영상 제목") + "]}"
    comments_page = (
        '{"items": [' + _comment_thread_item("c1", "좋은 정책이네요", "2026-07-21T00:00:00Z") + "]}"
    )
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=video_page),
            HttpResponse(status_code=200, headers={}, body=comments_page),
        ]
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert [r.url for r in results] == [
        "https://www.youtube.com/watch?v=abc123",
        "https://www.youtube.com/watch?v=abc123&lc=c1",
    ]
    comment_result = results[1]
    assert comment_result.title == "좋은 정책이네요"
    assert comment_result.channel == ChannelType.VIDEO
    comment_call = transport.calls[1]
    assert comment_call["url"] == YOUTUBE_COMMENT_THREADS_URL
    assert comment_call["params"]["videoId"] == "abc123"


def test_search_skips_comments_for_a_video_with_comments_disabled() -> None:
    video_page = '{"items": [' + _search_item("abc123", "영상 제목") + "]}"
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=video_page),
            HttpResponse(status_code=403, headers={}, body=""),
        ]
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    # The video itself is still returned even though its comments call failed.
    assert [r.url for r in results] == ["https://www.youtube.com/watch?v=abc123"]


def test_fetch_comment_tags_document_type_and_parent_document_id() -> None:
    from uuid import NAMESPACE_URL, uuid5

    response = HttpResponse(
        status_code=200,
        headers={},
        body='{"items": [{"snippet": {"textDisplay": "좋은 정책이네요", "likeCount": 3}}]}',
    )
    transport = MockTransport([response])
    comment_result = SearchResult(
        source="youtube",
        channel=ChannelType.VIDEO,
        title="좋은 정책이네요",
        url="https://www.youtube.com/watch?v=abc123&lc=c1",
        published_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = YouTubeCollector(api_key="yt-key", transport=transport)

    document = asyncio.run(collector.fetch(comment_result))

    assert document.body == "좋은 정책이네요"
    assert document.metadata["document_type"] == "comment"
    assert document.metadata["parent_document_id"] == str(
        uuid5(NAMESPACE_URL, "https://www.youtube.com/watch?v=abc123")
    )
    assert document.metadata["like_count"] == 3
    assert transport.calls[0]["url"] == YOUTUBE_COMMENTS_URL
    assert transport.calls[0]["params"]["id"] == "c1"
