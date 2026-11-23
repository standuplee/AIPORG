import asyncio
from datetime import datetime, timezone

from app.collectors.community.policy import SitePolicy
from app.collectors.replay import map_channel
from app.core.enums import ChannelType
from app.research.corpus import CorpusItem
from app.search.community import CommunitySearch
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult
from app.search.service import SearchService
from app.search.signals import SourceType, source_type


def _policy(name, domains, hint, enabled=True, exclude=()):
    return SitePolicy(name=name, enabled=enabled, domains=tuple(domains), search_hints=(hint,), user_agent="u", min_interval_sec=1.0,
                      max_requests_per_run=5, request_timeout_sec=5, respect_robots=True, exclude_patterns=tuple(exclude))


def _web(url, title="석탄화력 특별법 이야기"):
    return SearchResult(provider=SearchProvider.NAVER, channel=C.WEB, query="q", sort="accuracy", title=title, snippet="s", url=url,
                        published_at=datetime(2026, 8, 5, tzinfo=timezone.utc), rank=1)


class FakeNaver:
    """Answers per query text; records (query, channel, page)."""

    def __init__(self, by_hint):
        self.by_hint, self.calls = by_hint, []

    async def search(self, query, channel, limit=10, sort="accuracy", page=1):
        self.calls.append((query, channel, page))
        for hint, hits in self.by_hint.items():
            if hint in query:
                return hits
        return []


POLICIES = {
    "clien": _policy("clien", ["clien.net"], "클리앙", exclude=["/member"]),
    "dcinside": _policy("dcinside", ["dcinside.com"], "디시인사이드"),
    "theqoo": _policy("theqoo", ["theqoo.net"], "더쿠", enabled=False),
}


def test_only_enabled_sites_are_searched_and_hits_are_filtered_to_their_domains():
    naver = FakeNaver({
        "클리앙": [_web("https://www.clien.net/service/board/park/1"), _web("https://other.com/x"), _web("https://www.clien.net/member/9")],
        "디시인사이드": [_web("https://gall.dcinside.com/board/view/?id=a&no=2")],
    })
    out = asyncio.run(CommunitySearch(naver, POLICIES).search("석탄화력 특별법", 10))
    assert sorted(r.url for r in out) == ["https://gall.dcinside.com/board/view/?id=a&no=2", "https://www.clien.net/service/board/park/1"]
    assert all(r.channel is C.COMMUNITY for r in out)
    assert not any("더쿠" in q for q, _, _ in naver.calls)           # disabled site is never queried
    assert all(ch is C.WEB for _, ch, _ in naver.calls) and {q for q, _, _ in naver.calls} == {"석탄화력 특별법 클리앙", "석탄화력 특별법 디시인사이드"}


def test_one_failing_site_does_not_drop_the_others():
    class Flaky(FakeNaver):
        async def search(self, query, channel, limit=10, sort="accuracy", page=1):
            if "클리앙" in query:
                raise RuntimeError("down")
            return await super().search(query, channel, limit, sort, page)

    naver = Flaky({"디시인사이드": [_web("https://gall.dcinside.com/a")]})
    assert [r.url for r in asyncio.run(CommunitySearch(naver, POLICIES).search("q", 5))] == ["https://gall.dcinside.com/a"]


def test_opinion_search_includes_community_hits_only_when_policies_are_given():
    class Empty:
        async def search(self, query, channel, limit, sort, page=1):
            return []

    naver = FakeNaver({"클리앙": [_web("https://www.clien.net/service/board/park/1")]})
    plain = asyncio.run(SearchService(naver=naver, daum=Empty()).search_opinion("q"))
    assert plain == []
    with_community = asyncio.run(SearchService(naver=naver, daum=Empty(), community_policies=POLICIES).search_opinion("q"))
    assert [r.channel for r in with_community] == [C.COMMUNITY]


def test_community_channel_is_a_community_source_and_ingestible():
    r = _web("https://unknown-board.example/1").model_copy(update={"channel": C.COMMUNITY})
    assert source_type(r) is SourceType.COMMUNITY
    item = CorpusItem(result_id="x", channel="COMMUNITY", title="t", url="u", snippet="s", kind="OPINION", source_type="COMMUNITY")
    assert map_channel(item) is ChannelType.COMMUNITY
