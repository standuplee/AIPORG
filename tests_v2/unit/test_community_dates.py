import asyncio
from datetime import date, datetime, timezone

from app.collectors.community.parsers import PostContent
from app.schemas.research import IssueInput
from app.search.community_dates import resolve_community_dates
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="석탄화력 특별법")


def _post(url, channel=C.COMMUNITY, at=None):
    return SearchResult(provider=SearchProvider.NAVER, channel=channel, query="q", sort="accuracy", title=url, snippet="s", url=url, published_at=at, rank=1)


class FakeCollector:
    def __init__(self, dates):
        self.dates, self.fetched = dates, []

    async def fetch_post(self, url):
        self.fetched.append(url)
        d = self.dates.get(url)
        return None if d is None else PostContent(title="t", body="b" * 30, posted_at=d)


def _at(day, month=8):
    return datetime(2026, month, day, tzinfo=timezone.utc)


def test_undated_community_posts_get_their_date_and_out_of_period_ones_are_dropped():
    a, b, c, d = _post("https://c.net/a"), _post("https://c.net/b"), _post("https://c.net/c"), _post("https://c.net/d")
    col = FakeCollector({a.url: _at(5), b.url: _at(5, 6), c.url: None})          # d unknown to the collector too
    kept, log = asyncio.run(resolve_community_dates(col, [a, b, c, d], ISSUE))
    assert {r.url: r.published_at for r in kept} == {a.url: _at(5), c.url: None, d.url: None}   # b is June -> dropped
    assert log == {"community": 4, "dated": 1, "out_of_period": 1, "undated": 2}


def test_only_undated_community_posts_are_fetched_other_posts_pass_through():
    blog, dated, undated = _post("https://b.net/1", C.BLOG), _post("https://c.net/2", at=_at(7)), _post("https://c.net/3")
    col = FakeCollector({undated.url: _at(9)})
    kept, _ = asyncio.run(resolve_community_dates(col, [blog, dated, undated], ISSUE))
    assert col.fetched == [undated.url] and [r.url for r in kept] == [blog.url, dated.url, undated.url]


def test_a_failing_fetch_leaves_the_post_undated_without_stopping_the_rest():
    class Boom(FakeCollector):
        async def fetch_post(self, url):
            if url.endswith("a"):
                raise RuntimeError("down")
            return await super().fetch_post(url)

    a, b = _post("https://c.net/a"), _post("https://c.net/b")
    kept, log = asyncio.run(resolve_community_dates(Boom({b.url: _at(3)}), [a, b], ISSUE))
    assert {r.url: r.published_at for r in kept} == {a.url: None, b.url: _at(3)} and log["undated"] == 1
