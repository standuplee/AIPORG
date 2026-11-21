import asyncio
from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.collectors.replay import ReplayCollector, map_channel, partition
from app.core.enums import ChannelType
from app.research.corpus import CorpusItem, IssueCorpus
from app.schemas.query import SearchQuery

AT = datetime(2026, 8, 3, tzinfo=timezone.utc)


def _item(rid, channel="BLOG", published=AT, source_type="BLOG", body=None, kind="OPINION"):
    return CorpusItem(result_id=rid, channel=channel, title=f"제목{rid}", url=f"https://www.example.com/{rid}", snippet=f"요약{rid}",
                      published_at=published, kind=kind, source_type=source_type, body=body)


def _corpus(*items):
    return IssueCorpus(issue="석탄화력 특별법", region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), items=list(items))


def test_channel_mapping():
    assert map_channel(_item("a", "NEWS", source_type="NEWS")) is ChannelType.NEWS
    assert map_channel(_item("a", "BLOG")) is ChannelType.BLOG
    assert map_channel(_item("a", "CAFE", source_type="COMMUNITY")) is ChannelType.COMMUNITY
    assert map_channel(_item("a", "WEB", source_type="NEWS")) is ChannelType.NEWS
    assert map_channel(_item("a", "WEB", source_type="OTHER")) is None


def test_undated_and_unmapped_items_are_held_not_returned():
    ok = _item("ok")
    undated = _item("undated", published=None)
    unmapped = _item("unmapped", "WEB", source_type="OTHER")
    undated_unmapped = _item("both", "WEB", published=None, source_type="OTHER")
    usable, held = partition(_corpus(ok, undated, unmapped, undated_unmapped))
    assert [i.result_id for i, _ in usable] == ["ok"]
    assert held == {"undated": "undated", "unmapped": "unmapped_channel", "both": "undated"}  # undated wins
    found = asyncio.run(ReplayCollector(_corpus(ok, undated, unmapped)).search(SearchQuery(query="석탄화력 특별법", channels=[ChannelType.BLOG])))
    assert [r.title for r in found] == ["제목ok"]


def test_search_only_returns_matching_issue_and_channel():
    corpus = _corpus(_item("b1"), _item("n1", "NEWS", source_type="NEWS"))
    c = ReplayCollector(corpus)
    assert asyncio.run(c.search(SearchQuery(query="다른 이슈", channels=[ChannelType.BLOG]))) == []
    blog = asyncio.run(c.search(SearchQuery(query="석탄화력 특별법", channels=[ChannelType.BLOG])))
    assert [r.channel for r in blog] == [ChannelType.BLOG] and blog[0].source == "example.com"


def test_fetch_builds_raw_document_with_body_flag():
    full = _item("full", "NEWS", source_type="NEWS", body="기사 본문", kind="FACT")
    snippet_only = _item("snip")
    c = ReplayCollector(_corpus(full, snippet_only))
    results = asyncio.run(c.search(SearchQuery(query="석탄화력 특별법", channels=[ChannelType.NEWS, ChannelType.BLOG])))
    docs = {d.title: d for d in (asyncio.run(c.fetch(r)) for r in results)}
    a, b = docs["제목full"], docs["제목snip"]
    assert a.body == "기사 본문" and a.metadata["body_available"] is True and a.metadata["kind"] == "FACT" and a.metadata["source_type"] == "NEWS"
    assert b.body == "요약snip" and b.metadata["body_available"] is False
    assert a.document_id == uuid5(NAMESPACE_URL, "full") and b.document_id == uuid5(NAMESPACE_URL, "snip")  # stable across runs
    assert a.platform == "news" and a.channel is ChannelType.NEWS and a.query == "석탄화력 특별법"
