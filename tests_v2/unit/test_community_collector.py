import asyncio
from datetime import datetime, timezone

import pytest

from app.collectors.community import CommunityCollector, SitePolicy
from app.collectors.community.collector import NAVER_WEBKR_URL
from app.collectors.errors import CollectorError
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
    return SearchQuery(query="대전", channels=[ChannelType.COMMUNITY])


def _policy(**overrides) -> SitePolicy:
    defaults = dict(
        name="testsite",
        enabled=True,
        domains=("example.com",),
        search_hints=("테스트",),
        user_agent="AIPORG-Test/1.0",
        min_interval_sec=0.0,
        max_requests_per_run=25,
        request_timeout_sec=10,
        respect_robots=True,
        exclude_patterns=(),
    )
    defaults.update(overrides)
    return SitePolicy(**defaults)


def _webkr_response(links: list[tuple[str, str]]) -> HttpResponse:
    import json

    items = [{"link": link, "title": title, "description": ""} for link, title in links]
    return HttpResponse(status_code=200, headers={}, body=json.dumps({"items": items}))


def _robots_allow_all() -> HttpResponse:
    return HttpResponse(status_code=404, headers={}, body="")


def _robots_disallow_all() -> HttpResponse:
    return HttpResponse(status_code=200, headers={}, body="User-agent: *\nDisallow: /")


def _post_html(*, title: str = "Test Title", published: str | None = "2026-07-20T10:00:00+09:00") -> str:
    meta = f'<meta property="article:published_time" content="{published}">' if published else ""
    return (
        f"<html><head><title>{title}</title>{meta}</head>"
        "<body><article>This is a sufficiently long post body for the generic parser to accept.</article>"
        "</body></html>"
    )


def test_search_returns_empty_without_any_calls_when_no_site_enabled() -> None:
    transport = MockTransport([])
    collector = CommunityCollector(
        client_id="id",
        client_secret="secret",
        transport=transport,
        policies={"testsite": _policy(enabled=False)},
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []
    assert transport.calls == []


def test_search_discovers_gates_fetches_and_parses_a_candidate() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://example.com/post/1", "snippet title")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body=_post_html()),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == [
        SearchResult(
            source="testsite",
            channel=ChannelType.COMMUNITY,
            title="Test Title",
            url="https://example.com/post/1",
            published_at=datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
            query="대전",
        )
    ]
    discovery_call = transport.calls[0]
    assert discovery_call["url"] == NAVER_WEBKR_URL
    assert discovery_call["headers"] == {
        "X-Naver-Client-Id": "id",
        "X-Naver-Client-Secret": "secret",
    }
    assert discovery_call["params"]["query"] == "대전 테스트"


def test_search_skips_candidates_outside_the_site_domain() -> None:
    transport = MockTransport(
        [_webkr_response([("https://other.example.org/post/1", "off domain")])]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []
    # No robots/fetch call should have been attempted for a URL outside the policy's domains.
    assert len(transport.calls) == 1


def test_search_skips_excluded_urls_before_fetching() -> None:
    transport = MockTransport(
        [_webkr_response([("https://example.com/login/1", "login page")])]
    )
    collector = CommunityCollector(
        client_id="id",
        client_secret="secret",
        transport=transport,
        policies={"testsite": _policy(exclude_patterns=("/login",))},
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []
    assert len(transport.calls) == 1  # only the discovery call


def test_search_drops_candidates_disallowed_by_robots_txt() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://example.com/post/1", "snippet")]),
            _robots_disallow_all(),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []
    assert len(transport.calls) == 2  # discovery + robots.txt, no page fetch


def test_search_stops_once_a_sites_rate_limit_budget_is_used() -> None:
    transport = MockTransport(
        [
            _webkr_response(
                [
                    ("https://example.com/post/1", "first"),
                    ("https://example.com/post/2", "second"),
                ]
            ),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body=_post_html()),
        ]
    )
    collector = CommunityCollector(
        client_id="id",
        client_secret="secret",
        transport=transport,
        policies={"testsite": _policy(max_requests_per_run=1)},
    )

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert results[0].url == "https://example.com/post/1"
    # Second candidate must not have triggered a robots check or fetch.
    assert len(transport.calls) == 3


def test_search_drops_a_post_with_no_parseable_publish_date() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://example.com/post/1", "snippet")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body=_post_html(published=None)),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []


def test_fetch_uses_the_parse_cached_during_search_without_another_request() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://example.com/post/1", "snippet")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body=_post_html()),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )

    results = asyncio.run(collector.search(search_query()))
    calls_after_search = len(transport.calls)
    document = asyncio.run(collector.fetch(results[0]))

    assert len(transport.calls) == calls_after_search  # fetch() made no new request
    assert document.metadata["document_type"] == "article"
    assert "sufficiently long post body" in document.body


def test_fetch_refetches_through_the_same_gates_on_a_cache_miss() -> None:
    transport = MockTransport([_robots_allow_all(), HttpResponse(status_code=200, headers={}, body=_post_html())])
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"testsite": _policy()}
    )
    result = SearchResult(
        source="testsite",
        channel=ChannelType.COMMUNITY,
        title="Test Title",
        url="https://example.com/post/1",
        published_at=datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
        query="대전",
    )

    document = asyncio.run(collector.fetch(result))

    assert document.body != ""
    assert len(transport.calls) == 2  # robots.txt + page fetch, even without a prior search()


def test_fetch_raises_when_site_is_not_enabled() -> None:
    collector = CommunityCollector(
        client_id="id",
        client_secret="secret",
        transport=MockTransport([]),
        policies={"testsite": _policy(enabled=False)},
    )
    result = SearchResult(
        source="testsite",
        channel=ChannelType.COMMUNITY,
        title="Test Title",
        url="https://example.com/post/1",
        published_at=datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc),
        query="대전",
    )

    with pytest.raises(CollectorError):
        asyncio.run(collector.fetch(result))


def test_constructor_requires_credentials() -> None:
    with pytest.raises(ValueError):
        CommunityCollector(client_id="", client_secret="secret")
    with pytest.raises(ValueError):
        CommunityCollector(client_id="id", client_secret="")


def _fmkorea_policy(**overrides) -> SitePolicy:
    return _policy(
        name="fmkorea",
        domains=("fmkorea.com", "www.fmkorea.com"),
        search_hints=("펨코",),
        **overrides,
    )


def test_fmkorea_resolves_a_bare_post_id_to_its_verified_board_prefix() -> None:
    board_html = {
        "best": '<a href="/best/99999999">a</a>',
        "best2": "<html></html>",
        "humor": '<a href="/10358221471">humor post</a>',
    }
    transport = MockTransport(
        [
            _webkr_response([("https://www.fmkorea.com/10358221471", "snippet")]),
            _robots_allow_all(),  # robots.txt, cached for the whole fmkorea.com domain
            HttpResponse(status_code=200, headers={}, body=board_html["best"]),
            HttpResponse(status_code=200, headers={}, body=board_html["best2"]),
            HttpResponse(status_code=200, headers={}, body=board_html["humor"]),
            HttpResponse(status_code=200, headers={}, body=_post_html(title="humor post")),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"fmkorea": _fmkorea_policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert results[0].url == "https://www.fmkorea.com/humor/10358221471"
    assert results[0].source == "fmkorea"
    # discovery(1) + robots.txt(1) + 3 board listings + the resolved post fetch = 6
    assert len(transport.calls) == 6


def test_fmkorea_drops_a_post_id_not_found_on_any_allowed_board_listing() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://www.fmkorea.com/99999999999", "snippet")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body="<html></html>"),  # best: no match
            HttpResponse(status_code=200, headers={}, body="<html></html>"),  # best2: no match
            HttpResponse(status_code=200, headers={}, body="<html></html>"),  # humor: no match
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"fmkorea": _fmkorea_policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert results == []
    # No post fetch should have been attempted for an unverified id.
    assert len(transport.calls) == 5


def test_fmkorea_ignores_whatever_prefix_naver_already_indexed_and_reverifies() -> None:
    # Even if Naver's own index already shows a "/best/<id>" style URL, the
    # id is re-resolved against the live board listings rather than trusted
    # -- here it's only genuinely found under /humor.
    transport = MockTransport(
        [
            _webkr_response([("https://www.fmkorea.com/best/10358221471", "snippet")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body="<html></html>"),  # best: no match
            HttpResponse(status_code=200, headers={}, body="<html></html>"),  # best2: no match
            HttpResponse(status_code=200, headers={}, body='<a href="/10358221471">x</a>'),  # humor: match
            HttpResponse(status_code=200, headers={}, body=_post_html()),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"fmkorea": _fmkorea_policy()}
    )

    results = asyncio.run(collector.search(search_query()))

    assert len(results) == 1
    assert results[0].url == "https://www.fmkorea.com/humor/10358221471"


def test_fmkorea_board_membership_is_cached_across_multiple_search_calls() -> None:
    transport = MockTransport(
        [
            _webkr_response([("https://www.fmkorea.com/10358221471", "snippet")]),
            _robots_allow_all(),
            HttpResponse(status_code=200, headers={}, body="<html></html>"),
            HttpResponse(status_code=200, headers={}, body="<html></html>"),
            HttpResponse(status_code=200, headers={}, body='<a href="/10358221471">x</a>'),
            HttpResponse(status_code=200, headers={}, body=_post_html()),
            # Second search() call for a different keyword: no new board
            # listing or robots.txt fetches, only discovery + the post fetch.
            _webkr_response([("https://www.fmkorea.com/10358221471", "snippet")]),
            HttpResponse(status_code=200, headers={}, body=_post_html()),
        ]
    )
    collector = CommunityCollector(
        client_id="id", client_secret="secret", transport=transport, policies={"fmkorea": _fmkorea_policy()}
    )

    asyncio.run(collector.search(search_query()))
    calls_after_first_search = len(transport.calls)
    asyncio.run(collector.search(SearchQuery(query="다른 키워드", channels=[ChannelType.COMMUNITY])))

    assert len(transport.calls) == calls_after_first_search + 2
