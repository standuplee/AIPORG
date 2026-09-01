import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.collectors.errors import CollectorError
from app.collectors.naver_news import NAVER_NEWS_URL, NaverNewsCollector
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


def test_search_sends_naver_auth_headers_and_parses_items() -> None:
    transport = MockTransport([
        HttpResponse(
            status_code=200,
            headers={},
            body=(
                '{"items": [{"title": "<b>충남</b> 소식", '
                '"link": "https://search.naver.com/1", '
                '"originallink": "https://press.example/1", '
                '"description": "<b>정책</b> 소식", '
                '"pubDate": "Mon, 20 Jul 2026 10:00:00 +0900"}]}'
            ),
        )
    ])
    collector = NaverNewsCollector(
        client_id="client-id", client_secret="client-secret", transport=transport
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == [
        SearchResult(
            source="naver",
            channel=ChannelType.NEWS,
            title="충남 소식",
            url="https://press.example/1",
            published_at=datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
            query="박수현 충남",
        )
    ]
    call = transport.calls[0]
    assert call["url"] == NAVER_NEWS_URL
    assert call["headers"] == {
        "X-Naver-Client-Id": "client-id",
        "X-Naver-Client-Secret": "client-secret",
    }


def test_search_falls_back_to_link_when_original_link_is_empty() -> None:
    transport = MockTransport([
        HttpResponse(
            status_code=200,
            headers={},
            body=(
                '{"items": [{"title": "제목", "link": "https://naver/1", '
                '"originallink": "", "description": "설명", '
                '"pubDate": "Tue, 21 Jul 2026 09:00:00 +0900"}]}'
            ),
        )
    ])
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    result = asyncio.run(collector.search(search_query()))[0]

    assert result.url == "https://naver/1"


def test_fetch_normalizes_html_and_uses_deterministic_document_id() -> None:
    response = HttpResponse(
        status_code=200,
        headers={"Content-Type": "text/html"},
        body="<html><script>bad()</script><body>첫 문장<br> 둘째 &amp; 셋째</body></html>",
    )
    transport = MockTransport([response, response])
    result = SearchResult(
        source="naver",
        channel=ChannelType.NEWS,
        title="제목",
        url="https://press.example/article/1",
        published_at=datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    first = asyncio.run(collector.fetch(result))
    second = asyncio.run(collector.fetch(result))

    assert first.document_id == second.document_id
    assert isinstance(first.document_id, UUID)
    assert first.platform == "naver"
    assert first.body == "첫 문장 둘째 & 셋째"
    assert first.title == "제목"
    assert first.metadata == {"content_type": "text/html", "description": None}
    assert first.collected_at.tzinfo is not None


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        ("not-json", "malformed_response"),
        ('{"items": {}}', "malformed_response"),
        ('{"items": [{"title": "제목"}]}', "malformed_response"),
    ],
)
def test_search_raises_structured_error_for_malformed_response(body: str, expected_code: str) -> None:
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=body)])
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.search(search_query()))

    assert raised.value.code == expected_code
    assert raised.value.retryable is False
    assert raised.value.details["provider"] == "naver"
