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


def test_search_accepts_an_empty_description_confirmed_live_on_a_real_article() -> None:
    # Naver's API legitimately returns description="" for some real articles
    # (confirmed live against a production response while adding comment
    # collection) -- description is never stored anywhere, so requiring it
    # to be non-empty used to discard this and every other result on the
    # same page for no benefit.
    transport = MockTransport([
        HttpResponse(
            status_code=200,
            headers={},
            body=(
                '{"items": [{"title": "충남도청 투자통상국 선발대, 뉴욕한인회와 업무 논의", '
                '"link": "https://www.koreadaily.com/article/20261013213240507", '
                '"originallink": "https://www.koreadaily.com/article/20261013213240507", '
                '"description": "", '
                '"pubDate": "Wed, 14 Oct 2026 13:34:00 +0900"}]}'
            ),
        )
    ])
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert results[0].url == "https://www.koreadaily.com/article/20261013213240507"


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


def _item(index: int) -> str:
    return (
        f'{{"title": "소식 {index}", '
        f'"link": "https://press.example/{index}", '
        '"originallink": "", '
        f'"description": "설명 {index}", '
        '"pubDate": "Mon, 20 Jul 2026 10:00:00 +0900"}'
    )


def test_search_pages_through_the_full_start_budget_when_a_page_is_full() -> None:
    first_page = "{\"items\": [" + ",".join(_item(i) for i in range(100)) + "]}"
    second_page = "{\"items\": [" + _item(100) + "]}"
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=first_page),
            HttpResponse(status_code=200, headers={}, body=second_page),
        ]
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 101
    assert [call["params"]["start"] for call in transport.calls] == [1, 101]
    assert [call["params"]["display"] for call in transport.calls] == [100, 100]


def test_search_stops_at_the_naver_api_start_ceiling() -> None:
    full_page = "{\"items\": [" + ",".join(_item(i) for i in range(100)) + "]}"
    responses = [HttpResponse(status_code=200, headers={}, body=full_page) for _ in range(10)]
    transport = MockTransport(responses)
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1000
    assert len(transport.calls) == 10
    assert transport.calls[-1]["params"]["start"] == 901


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
    assert first.metadata == {
        "document_type": "article",
        "content_type": "text/html",
        "description": None,
    }
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


def _article_item(link: str = "https://n.news.naver.com/mnews/article/001/0016380638") -> str:
    return (
        '{"title": "충남 소식", '
        f'"link": "{link}", '
        '"originallink": "https://press.example/1", '
        '"description": "정책 소식", '
        '"pubDate": "Mon, 20 Jul 2026 10:00:00 +0900"}'
    )


def _cbox_jsonp(status: str, comments: list[dict]) -> str:
    import json

    payload = {
        "result": {
            "exposureConfig": {"status": status},
            "commentList": comments,
        }
    }
    # Confirmed live: the real endpoint wraps as "_callback({...});" with a
    # trailing semicolon after the closing paren -- keep the fixture honest
    # about that rather than the easier-to-parse shape without it.
    return "_callback(" + json.dumps(payload) + ");"


def test_search_includes_comments_when_a_naver_hosted_link_is_present() -> None:
    article_page = '{"items": [' + _article_item() + "]}"
    comments_page = _cbox_jsonp(
        "COMMENT_ON",
        [
            {
                "commentNo": "999",
                "contents": "좋은 정책이네요",
                "regTime": "2026-07-21T10:00:00+0900",
                "deleted": False,
                "blind": False,
            }
        ],
    )
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=article_page),
            HttpResponse(status_code=200, headers={}, body=comments_page),
        ]
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 2
    article, comment = results
    assert article.url == "https://press.example/1"  # originallink still preferred
    assert comment.title == "좋은 정책이네요"
    from uuid import NAMESPACE_URL, uuid5

    assert f"pid={uuid5(NAMESPACE_URL, article.url)}" in comment.url
    assert "cm=999" in comment.url
    comment_call = transport.calls[1]
    assert comment_call["url"] == "https://apis.naver.com/commentBox/cbox/web_neo_list_jsonp.json"
    assert comment_call["params"]["objectId"] == "news001,0016380638"


def test_search_skips_comments_when_no_naver_hosted_link_is_present() -> None:
    article_page = '{"items": [' + _article_item(link="https://search.naver.com/1") + "]}"
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=article_page)])
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert len(transport.calls) == 1


def test_search_skips_comments_disabled_on_the_article() -> None:
    article_page = '{"items": [' + _article_item() + "]}"
    comments_page = _cbox_jsonp("COMMENT_OFF", [])
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=article_page),
            HttpResponse(status_code=200, headers={}, body=comments_page),
        ]
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1


def test_search_skips_comments_on_a_per_article_comment_api_failure() -> None:
    article_page = '{"items": [' + _article_item() + "]}"
    transport = MockTransport(
        [
            HttpResponse(status_code=200, headers={}, body=article_page),
            HttpResponse(status_code=403, headers={}, body=""),
        ]
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    results = asyncio.run(collector.search(search_query()))

    # The article itself is still returned even though its comments call failed.
    assert len(results) == 1


def test_fetch_comment_tags_document_type_and_parent_document_id() -> None:
    from uuid import NAMESPACE_URL, uuid5

    parent_id = str(uuid5(NAMESPACE_URL, "https://press.example/1"))
    comments_page = _cbox_jsonp(
        "COMMENT_ON",
        [
            {
                "commentNo": "999",
                "contents": "좋은 정책이네요",
                "regTime": "2026-07-21T10:00:00+0900",
                "deleted": False,
                "blind": False,
                "sympathyCount": 5,
                "antipathyCount": 1,
            }
        ],
    )
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=comments_page)])
    comment_result = SearchResult(
        source="naver",
        channel=ChannelType.NEWS,
        title="좋은 정책이네요",
        url=(
            "https://n.news.naver.com/mnews/article/001/0016380638"
            f"?cm=999&pid={parent_id}"
        ),
        published_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    document = asyncio.run(collector.fetch(comment_result))

    assert document.body == "좋은 정책이네요"
    assert document.metadata["document_type"] == "comment"
    assert document.metadata["parent_document_id"] == parent_id
    assert document.metadata["sympathy_count"] == 5
    assert document.metadata["antipathy_count"] == 1


def test_fetch_comment_raises_when_not_found_on_refetch() -> None:
    comments_page = _cbox_jsonp("COMMENT_ON", [])
    transport = MockTransport([HttpResponse(status_code=200, headers={}, body=comments_page)])
    comment_result = SearchResult(
        source="naver",
        channel=ChannelType.NEWS,
        title="삭제된 댓글",
        url="https://n.news.naver.com/mnews/article/001/0016380638?cm=999&pid=" + "0" * 32,
        published_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        query="박수현 충남",
    )
    collector = NaverNewsCollector(client_id="id", client_secret="secret", transport=transport)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(collector.fetch(comment_result))

    assert raised.value.code == "malformed_response"
