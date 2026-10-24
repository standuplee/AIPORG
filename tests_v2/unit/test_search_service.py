import asyncio

from app.search import base
from app.search.daum import DaumSearchProvider
from app.search.deduplicator import deduplicate
from app.search.naver import NaverSearchProvider
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult
from app.search.service import SearchService


def _r(url, title="t", original=None, provider=SearchProvider.NAVER):
    return SearchResult(provider=provider, channel=C.NEWS, query="q", sort="accuracy",
                        title=title, snippet="", url=url, original_url=original, rank=1)


def test_dedup_by_press_url_and_title_ignoring_tracking_params():
    hits = [
        _r("https://n.news.naver.com/1", "삼성 67조 투자!", original="https://www.a.com/news?idxno=1&utm_source=x"),
        _r("https://v.daum.net/9", "삼성 67조 투자", provider=SearchProvider.DAUM),  # same title
        _r("https://a.com/news?idxno=1", "다른 제목"),  # same press URL
        _r("https://a.com/news?idxno=2", "다른 기사"),
    ]
    assert [h.title for h in deduplicate(hits)] == ["삼성 67조 투자!", "다른 기사"]


def test_providers_map_sort_and_keep_original_url(monkeypatch):
    calls = []

    def get(url, **kw):
        calls.append((url, kw["params"]))
        if "naver" in url:
            return {"items": [{"title": "<b>A</b>", "description": "d", "link": "l",
                               "originallink": "o", "pubDate": "Tue, 01 Sep 2026 17:34:00 +0900"}]}
        return {"documents": [{"title": "T", "contents": "c", "url": "u", "datetime": ""}]}

    monkeypatch.setattr(base.SearchProviderBase, "_get", staticmethod(get))
    n = asyncio.run(NaverSearchProvider("i", "s").search("q", C.NEWS, 5, "recency"))[0]
    assert (n.title, n.url, n.original_url, n.published_at.year) == ("A", "l", "o", 2026)
    d = asyncio.run(DaumSearchProvider("k").search("q", C.CAFE, 5, "recency"))[0]
    assert d.published_at is None
    assert calls[0][1]["sort"] == "date" and calls[1][1]["sort"] == "recency"


def test_service_survives_one_failing_engine():
    class Ok:
        async def search(self, query, channel, limit, sort):
            return [_r(f"https://x.com/{channel.value}/{sort}", f"{channel.value}{sort}")]

    class Boom:
        async def search(self, *a):
            raise RuntimeError("down")

    fact = asyncio.run(SearchService(naver=Boom(), daum=Ok()).search_fact("q"))
    assert len(fact) == 2  # daum web accuracy + recency
    opinion = asyncio.run(SearchService(naver=Boom(), daum=Ok()).search_opinion("q"))
    assert len(opinion) == 2  # daum blog + cafe


def test_period_gate_keeps_unknown_dates():
    from datetime import date, datetime, timezone

    from app.search.period import classify_period
    from app.search.schemas import PeriodStatus as P

    def at(dt):
        r = _r("https://a.com/1")
        return r.model_copy(update={"published_at": dt})

    s, e = date(2026, 9, 1), date(2026, 9, 30)
    utc = timezone.utc
    assert classify_period(at(None), s, e) is P.UNKNOWN
    assert classify_period(at(datetime(2026, 8, 31, 16, tzinfo=utc)), s, e) is P.IN_PERIOD  # 9/1 KST
    assert classify_period(at(datetime(2026, 10, 2, tzinfo=utc)), s, e) is P.OUT_OF_PERIOD
    assert classify_period(at(datetime(2025, 5, 1, tzinfo=utc)), s, e, allow_historical=True) is P.HISTORICAL_ALLOWED


def _decomp():
    from app.schemas.research import IssueDecomposition

    return IssueDecomposition(subjects=[], actions=["법안 처리"], amounts=[], locations=[], organizations=[],
                              policies=[], explicit_in_input=["특별법"], unknowns=[], laws=["석탄화력폐지지역 특별법"])


def _question(kind="FACT"):
    from app.schemas.research import ResearchQuestion

    return ResearchQuestion(id="RQ01", type=kind, question="법안이 통과되었는가?")


def _issue():
    from datetime import date

    from app.schemas.research import IssueInput

    return IssueInput(region="충청남도", start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), issue="석탄화력폐지지역 특별법")


class _FakeQwen:
    """Scores every hit 3 and echoes input terms as 'discovered' to test code-side cleaning."""

    def __init__(self, skip_first_call=False):
        self.calls = 0
        self.skip = skip_first_call
        self.sent = []

    async def chat(self, system, user, schema):
        import json

        from app.search.schemas import AssessmentBatch, SearchResultAssessment

        self.calls += 1
        ids = [x["result_id"] for x in json.loads(user)["results"]]
        self.sent += ids
        if self.skip and self.calls == 1:
            ids = ids[:1]
        return AssessmentBatch(assessments=[
            SearchResultAssessment(result_id=i, research_question_id="?", relevance_score=3, reason="r",
                                   matched_terms=["특별법", "없는말"],
                                   discovered_entities=["석탄화력폐지지역 특별법", "석탄화력 폐지지역 특별법", "충남", "산업통상부", "지어낸기관"])
            for i in ids
        ])


def test_analyzer_scores_per_question_and_cleans_llm_output():
    from datetime import datetime, timezone

    from app.search.analyzer import analyze_results, select_for_fetch

    live = _r("https://a.com/news/1", "특별법 산업통상부 충남 협의").model_copy(
        update={"snippet": "특별법 논의", "published_at": datetime(2026, 9, 1, tzinfo=timezone.utc)})
    unknown = _r("https://a.com/news/2", "특별법 소식")
    old = _r("https://a.com/news/3", "특별법 지난 소식").model_copy(
        update={"published_at": datetime(2026, 10, 20, tzinfo=timezone.utc)})
    listing = _r("https://a.com/news/list?page=1", "특별법 목록")
    qwen = _FakeQwen()

    analysis = asyncio.run(analyze_results(qwen, _issue(), _decomp(), _question(), [live, unknown, old, listing]))

    assert listing.result_id not in qwen.sent  # structural noise never reaches Qwen
    assert analysis.results[3].assessment is None and analysis.results[3].metadata.structural_noise
    a = analysis.results[0].assessment
    assert a.research_question_id == "RQ01"
    assert a.matched_terms == ["특별법"]  # "없는말" is not in the hit
    assert a.discovered_entities == ["산업통상부"]  # echoed input term and unseen entity dropped
    assert analysis.discovered_entities == ["산업통상부"]
    assert [x.result.result_id for x in select_for_fetch(analysis)] == [live.result_id, unknown.result_id]


def test_background_question_allows_historical_documents():
    from datetime import datetime, timezone

    from app.search.analyzer import analyze_results, select_for_fetch

    old = _r("https://a.com/news/9", "특별법 배경").model_copy(update={"published_at": datetime(2025, 5, 1, tzinfo=timezone.utc)})
    analysis = asyncio.run(analyze_results(_FakeQwen(), _issue(), _decomp(), _question("BACKGROUND"), [old]))
    assert analysis.results[0].metadata.period_status.value == "HISTORICAL_ALLOWED"
    assert len(select_for_fetch(analysis)) == 1


def test_analyzer_retries_ids_qwen_skipped():
    qwen = _FakeQwen(skip_first_call=True)
    from app.search.analyzer import analyze_results

    out = asyncio.run(analyze_results(qwen, _issue(), _decomp(), _question(),
                                      [_r("https://a.com/news/1", "a"), _r("https://a.com/news/2", "b")]))
    assert all(r.assessment for r in out.results) and qwen.calls == 2


def test_signals_are_issue_independent():
    from app.search.schemas import SourceType as S
    from app.search.signals import numeric_mentions, source_type

    kinds = {(m.type, m.raw) for m in numeric_mentions("무더위쉼터 6,813곳, 67조 원, 8월 20일 본회의, 지원율 12.5%")}
    assert {("COUNT", "6,813곳"), ("MONEY", "67조 원"), ("DATE", "8월 20일"), ("PERCENT", "12.5%")} <= kinds

    def src(url, channel=C.WEB):
        return source_type(_r(url).model_copy(update={"channel": channel}))

    assert src("https://www.chungnam.go.kr/x") is S.GOVERNMENT
    assert src("https://search.assembly.go.kr/x") is S.LEGISLATURE  # longest registry match beats go.kr
    assert src("https://gall.dcinside.com/x") is S.COMMUNITY
    assert src("https://x.com/y", C.BLOG) is S.BLOG
    assert src("https://press.com/articleView.html?idxno=1") is S.NEWS
    assert src("https://unknown.example/") is S.OTHER
