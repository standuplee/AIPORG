import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.collectors.daum_news import DAUM_WEB_SEARCH_URL, DaumNewsCollector
from app.collectors.transport import HttpResponse
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
    return SearchQuery(query="박수현 충남", channels=[ChannelType.NEWS])


def test_search_filters_to_daum_news_domains_and_paginates_until_is_end() -> None:
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body=(
                    '{"meta": {"is_end": false}, "documents": ['
                    '{"title": "<b>첫 뉴스</b>", "url": "https://news.daum.net/1", '
                    '"datetime": "2026-07-20T10:00:00+09:00", "contents": "본문"},'
                    '{"title": "제외", "url": "https://example.com/2", '
                    '"datetime": "2026-07-20T11:00:00+09:00", "contents": "본문"}'
                    ']}'
                ),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=(
                    '{"meta": {"is_end": true}, "documents": ['
                    '{"title": "둘째 뉴스", "url": "https://v.daum.net/v/2", '
                    '"datetime": "2026-07-21T01:00:00Z", "contents": "본문"}'
                    ']}'
                ),
            ),
        ]
    )
    collector = DaumNewsCollector(api_key="secret", transport=transport, page_size=50)

    results = asyncio.run(collector.search(search_query()))

    assert results == [
        SearchResult(
            source="daum",
            channel=ChannelType.NEWS,
            title="첫 뉴스",
            url="https://news.daum.net/1",
            published_at=datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
            query="박수현 충남",
        ),
        SearchResult(
            source="daum",
            channel=ChannelType.NEWS,
            title="둘째 뉴스",
            url="https://v.daum.net/v/2",
            published_at=datetime(2026, 7, 21, 1, tzinfo=timezone.utc),
            query="박수현 충남",
        ),
    ]
    assert [call["url"] for call in transport.calls] == [DAUM_WEB_SEARCH_URL] * 2
    assert transport.calls[0]["params"] == {
        "query": "박수현 충남",
        "page": 1,
        "size": 50,
        "sort": "recency",
    }
    assert transport.calls[1]["params"]["page"] == 2
    assert transport.calls[0]["headers"] == {"Authorization": "KakaoAK secret"}


@pytest.mark.parametrize(
    "value",
    [
        "https://news.daum.net.evil.example/article",
        "https://m.news.daum.net/article",
        "https://daum.net/article",
    ],
)
def test_search_rejects_non_exact_daum_news_hosts(value: str) -> None:
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body=(
                    '{"meta": {"is_end": true}, "documents": ['
                    f'{{"title": "제외", "url": "{value}", '
                    '"datetime": "2026-07-20T10:00:00+09:00", "contents": "본문"}'
                    ']}'
                ),
            )
        ]
    )
    collector = DaumNewsCollector(api_key="secret", transport=transport)

    assert asyncio.run(collector.search(search_query())) == []


def test_fetch_cleans_html_and_uses_deterministic_document_id() -> None:
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body="<html><script>bad()</script><body>첫 문장<br> 둘째 &amp; 셋째</body></html>",
            ),
            HttpResponse(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body="<html><script>bad()</script><body>첫 문장<br> 둘째 &amp; 셋째</body></html>",
            ),
        ]
    )
    result = SearchResult(
        source="daum",
        channel=ChannelType.NEWS,
        title="제목",
        url="https://news.daum.net/article/1",
        published_at=datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = DaumNewsCollector(api_key="secret", transport=transport)

    first = asyncio.run(collector.fetch(result))
    second = asyncio.run(collector.fetch(result))

    assert first.document_id == second.document_id
    assert isinstance(first.document_id, UUID)
    assert first.platform == "daum"
    assert first.body == "첫 문장 둘째 & 셋째"
    assert first.metadata == {"content_type": "text/html; charset=utf-8"}
    assert first.collected_at.tzinfo is not None
    assert transport.calls[0]["headers"] == {"User-Agent": "AIPORG/2.0"}


def test_search_normalizes_naive_datetime_as_utc() -> None:
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body=(
                    '{"meta": {"is_end": true}, "documents": ['
                    '{"title": "제목", "url": "https://news.daum.net/1", '
                    '"datetime": "2026-07-20T10:00:00", "contents": "본문"}'
                    ']}'
                ),
            )
        ]
    )
    collector = DaumNewsCollector(api_key="secret", transport=transport)

    result = asyncio.run(collector.search(search_query()))[0]

    assert result.published_at == datetime(2026, 7, 20, 10, tzinfo=timezone.utc)
