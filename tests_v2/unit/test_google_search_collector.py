import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.collectors.errors import CollectorError
from app.collectors.google_search import GOOGLE_SEARCH_URL, GoogleSearchCollector
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


def _item(url: str, title: str, published: str | None) -> dict:
    item: dict = {"title": title, "link": url, "displayLink": "press.example"}
    if published is not None:
        item["pagemap"] = {"metatags": [{"article:published_time": published}]}
    return item


def test_constructor_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        GoogleSearchCollector(api_key="", search_engine_id="cx")
    with pytest.raises(ValueError):
        GoogleSearchCollector(api_key="key", search_engine_id="")
    with pytest.raises(ValueError):
        GoogleSearchCollector(api_key="key", search_engine_id="cx", results_per_page=11)
    with pytest.raises(ValueError):
        GoogleSearchCollector(api_key="key", search_engine_id="cx", max_pages=0)


def test_search_sends_key_cx_and_parses_dated_items() -> None:
    import json

    body = json.dumps(
        {
            "items": [
                _item(
                    "https://press.example/1", "충남 소식",
                    "2026-07-20T10:00:00+09:00",
                )
            ]
        }
    )
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=body)])
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert results == [
        SearchResult(
            source="press.example",
            channel=ChannelType.NEWS,
            title="충남 소식",
            url="https://press.example/1",
            published_at=datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
            query="박수현 충남",
        )
    ]
    call = transport.calls[0]
    assert call["url"] == GOOGLE_SEARCH_URL
    assert call["params"]["key"] == "key"
    assert call["params"]["cx"] == "cx"
    assert call["params"]["q"] == "박수현 충남"
    assert call["params"]["start"] == 1


def test_search_drops_undated_items_instead_of_fabricating_a_date() -> None:
    import json

    body = json.dumps(
        {
            "items": [
                _item("https://press.example/dated", "날짜 있음", "2026-07-20T10:00:00Z"),
                _item("https://press.example/undated", "날짜 없음", None),
            ]
        }
    )
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=body)])
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert results[0].url == "https://press.example/dated"


def test_search_treats_a_missing_items_key_as_zero_results_not_malformed() -> None:
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body="{}")])
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert results == []


def test_search_stops_once_a_page_returns_fewer_than_a_full_page() -> None:
    import json

    body = json.dumps(
        {"items": [_item("https://press.example/1", "소식", "2026-07-20T10:00:00Z")]}
    )
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=body)])
    collector = GoogleSearchCollector(
        api_key="key", search_engine_id="cx", transport=transport,
        results_per_page=10, max_pages=3,
    )

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert len(transport.calls) == 1


def test_fetch_normalizes_html_and_uses_deterministic_document_id() -> None:
    response = HttpResponse(
        status_code=200,
        headers={"Content-Type": "text/html"},
        body="<html><script>bad()</script><body>첫 문장<br> 둘째 &amp; 셋째</body></html>",
    )
    transport = MockTransport([response, response])
    result = SearchResult(
        source="press.example",
        channel=ChannelType.NEWS,
        title="제목",
        url="https://press.example/article/1",
        published_at=datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    first = asyncio.run(collector.fetch(result))
    second = asyncio.run(collector.fetch(result))

    assert first.document_id == second.document_id
    assert isinstance(first.document_id, UUID)
    assert first.platform == "google"
    assert first.body == "첫 문장 둘째 & 셋째"


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
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.search(search_query()))

    assert raised.value.code == expected_code
    assert raised.value.details["provider"] == "google"


def test_search_raises_retryable_error_on_server_failure() -> None:
    transport = MockTransport([HttpResponse(status_code=503, headers={}, body="")])
    collector = GoogleSearchCollector(api_key="key", search_engine_id="cx", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.search(search_query()))

    assert raised.value.code == "http_status"
    assert raised.value.retryable is True
