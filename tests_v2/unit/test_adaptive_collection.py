import asyncio
from datetime import date, datetime, timezone

from app.schemas.research import IssueInput
from app.search import base
from app.search.daum import DaumSearchProvider
from app.search.documents import FactResearchResult
from app.search.naver import NaverSearchProvider
from app.search.opinion import LifeTerms, collect_corpus, collect_corpus_adaptive
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="석탄화력 특별법")
IN_PERIOD = datetime(2026, 8, 10, tzinfo=timezone.utc)
OLD = datetime(2026, 1, 10, tzinfo=timezone.utc)


def _hit(key, good=True):
    return SearchResult(provider=SearchProvider.DAUM, channel=C.BLOG, query="q", sort="accuracy",
                        title=f"석탄화력 특별법 글 {key}" if good else f"무관한 글 {key}", snippet="", url=f"https://blog.example/{key}",
                        published_at=IN_PERIOD if good else OLD, rank=1)


class FakeSearch:
    """script: {(query, page): [hits]}; unknown keys return nothing. Records every call."""

    def __init__(self, script):
        self.script, self.calls = script, []

    async def search_opinion(self, query, limit=10, page=1):
        self.calls.append((query, page))
        return self.script.get((query, page), [])


class FakeQwen:
    model = "fake"

    def __init__(self, terms=None, fail=False):
        self.terms, self.fail, self.calls = terms or [], fail, 0

    async def chat(self, system, user, schema, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError("ollama down")
        return LifeTerms(terms=self.terms)


def _run(search, queries=("석탄화력 특별법",), qwen=None, fact=None, target=5):
    return asyncio.run(collect_corpus_adaptive(search, ISSUE, list(queries), ["석탄화력"], qwen=qwen, fact=fact, target=target))


def test_no_expansion_when_base_queries_reach_the_target():
    search = FakeSearch({("석탄화력 특별법", 1): [_hit(i) for i in range(5)]})
    kept, _, log = _run(search)
    assert len(kept) == 5 and search.calls == [("석탄화력 특별법", 1)]
    assert [row["round"] for row in log] == [0]


def test_low_yield_triggers_deeper_pages_and_period_queries():
    search = FakeSearch({
        ("석탄화력 특별법", 1): [_hit(0), _hit(1)],
        ("석탄화력 특별법", 2): [_hit(2), _hit(1)],  # a repeat must not be counted twice
        ("석탄화력 특별법 2026년 8월", 1): [_hit(3), _hit(4)],
    })
    kept, _, log = _run(search)
    assert sorted(r.title for r in kept) == [f"석탄화력 특별법 글 {i}" for i in range(5)]
    assert ("석탄화력 특별법", 2) in search.calls and ("석탄화력 특별법", 3) in search.calls
    assert any(row["query"] == "석탄화력 특별법 2026년 8월" and row["round"] == 1 for row in log)


def test_expansion_stops_as_soon_as_the_target_is_reached():
    search = FakeSearch({("석탄화력 특별법", 1): [_hit(0)], ("석탄화력 특별법", 2): [_hit(i) for i in range(1, 5)]})
    qwen = FakeQwen(["일자리"])
    kept, _, _ = _run(search, qwen=qwen)
    assert len(kept) == 5 and qwen.calls == 0  # round 2 (Qwen) never needed


def test_round_two_uses_validated_life_terms_and_policy_terms():
    fact = FactResearchResult(summary="", key_facts=[], organizations=["한국서부발전"], persons=[], locations=["태안군"],
                              timeline=[], uncertainties=[], missing_information=[])
    search = FakeSearch({
        ("석탄화력 특별법 일자리", 1): [_hit(10), _hit(11)],
        ("석탄화력 특별법 한국서부발전", 1): [_hit(12)],
    })
    qwen = FakeQwen(["일자리", "기대감", "석탄화력", "  "])  # bias word, issue word, blank are rejected
    kept, _, log = _run(search, qwen=qwen, fact=fact, target=50)
    queries = {row["query"] for row in log if row["round"] == 2}
    assert "석탄화력 특별법 일자리" in queries and "석탄화력 특별법 한국서부발전" in queries and "석탄화력 특별법 태안군" in queries
    assert not any("기대감" in q or q.endswith("석탄화력") for q in queries)
    assert len(kept) == 3


def test_low_fit_derived_query_is_discarded_with_its_hits():
    bad = [_hit(f"b{i}", good=False) for i in range(5)] + [_hit("keep")]  # fit 1/6 < 0.3
    search = FakeSearch({("석탄화력 특별법 일자리", 1): bad})
    kept, _, log = _run(search, qwen=FakeQwen(["일자리"]), target=50)
    row = next(r for r in log if r["query"] == "석탄화력 특별법 일자리")
    assert row["discarded"] is True and kept == []


def test_qwen_failure_skips_round_two_and_target_is_not_lowered():
    search = FakeSearch({("석탄화력 특별법", 1): [_hit(0)]})
    kept, _, log = _run(search, qwen=FakeQwen(fail=True), target=50)
    assert len(kept) == 1  # reported short, not padded
    assert not any(row["round"] == 2 for row in log)


def test_collect_corpus_behaviour_is_unchanged():
    search = FakeSearch({("a", 1): [_hit(1), _hit(2), _hit(1)]})
    kept, dropped = asyncio.run(collect_corpus(search, ISSUE, ["a", "b"], ["석탄화력"]))
    assert len(kept) == 2 and dropped == {}


def test_providers_send_the_page(monkeypatch):
    calls = []

    def get(url, **kw):
        calls.append((url, kw["params"]))
        return {"items": [], "documents": []}

    monkeypatch.setattr(base.SearchProviderBase, "_get", staticmethod(get))
    asyncio.run(NaverSearchProvider("i", "s").search("q", C.BLOG, 15, "accuracy", page=3))
    asyncio.run(DaumSearchProvider("k").search("q", C.CAFE, 15, "accuracy", page=3))
    assert calls[0][1]["start"] == 31 and calls[1][1]["page"] == 3


def test_fit_measures_relevance_not_period_so_old_but_on_topic_hits_do_not_discard_a_query():
    old_on_topic = [_hit(f"o{i}", good=True).model_copy(update={"published_at": OLD}) for i in range(6)]  # on topic, out of period
    search = FakeSearch({("석탄화력 특별법 일자리", 1): old_on_topic})
    kept, _, log = _run(search, qwen=FakeQwen(["일자리"]), target=50)
    row = next(r for r in log if r["query"] == "석탄화력 특별법 일자리")
    assert row["discarded"] is False and row["fit"] == 1.0 and kept == []


def test_deeper_pages_are_fetched_for_base_queries_even_when_few_hits_are_in_period():
    search = FakeSearch({("석탄화력 특별법", 1): [_hit("a")] + [_hit(f"x{i}").model_copy(update={"published_at": OLD}) for i in range(8)]})
    _run(search)
    assert [p for q, p in search.calls if q == "석탄화력 특별법"] == [1, 2, 3, 4, 5]
