import asyncio
import json
from datetime import datetime, timedelta, timezone

from app.schemas.research import IssueInput, ResearchQuestion
from app.search import fetcher
from app.search.documents import FactResearchResult, FetchedDocument, FetchStatus, KeyFact, PublishedAtSource as P
from app.search.html_meta import extract_metadata, parse_date
from app.search.schemas import SearchChannel, SearchProvider, SearchResult, SourceType

BODY = "충남도는 9월 1일 삼성디스플레이와 투자협약을 체결했다고 밝혔다. " * 12


def _page(head="", body=BODY):
    return f"<html><head><title>t</title>{head}</head><body><article><p>{body}</p></article></body></html>"


def _hit(url="https://press.com/news/1", published=None):
    return SearchResult(provider=SearchProvider.NAVER, channel=SearchChannel.NEWS, query="q", sort="accuracy",
                        title="t", snippet="s", url=url, published_at=published, rank=1)


class _Resp:
    def __init__(self, html, status=200, ctype="text/html; charset=utf-8", url="https://press.com/final"):
        self.content, self.status_code, self.url = html.encode(), status, url
        self.headers = {"content-type": ctype}
        self.text = html


def test_date_priority_and_source_are_recorded():
    head = (
        '<script type="application/ld+json">{"@graph":[{"datePublished":"2026-09-01T17:34:00+09:00",'
        '"author":{"name":"홍길동"}}]}</script>'
        '<meta property="article:published_time" content="2026-09-02T00:00:00+09:00">'
    )
    m = extract_metadata(_page(head))
    assert (m["published_at_source"], m["author"]) == (P.JSON_LD, "홍길동")
    assert m["published_at"].day == 1
    m = extract_metadata(_page('<meta property="article:published_time" content="2026-09-02T00:00:00">'))
    assert m["published_at_source"] is P.ARTICLE_META and m["published_at"].utcoffset() == timedelta(hours=9)
    assert extract_metadata(_page('<meta property="og:article:published_time" content="2026.09.03 10:00">'))["published_at_source"] is P.OPEN_GRAPH
    assert extract_metadata(_page("", "<time datetime='2026-09-04'>x</time>"))["published_at_source"] is P.TIME_TAG
    m = extract_metadata(_page(), "입력 2026.09.05 09:30 기자 ...")
    assert m["published_at_source"] is P.TEXT_PATTERN
    assert extract_metadata(_page())["published_at_source"] is P.UNKNOWN
    assert parse_date("not a date") is None and parse_date("2026-13-45") is None


def test_fetch_ok_recovers_date_from_html_not_search_api(monkeypatch):
    html = _page('<meta property="article:published_time" content="2026-09-01T10:00:00+09:00">')
    monkeypatch.setattr(fetcher, "_get", lambda url: _Resp(html))
    doc = asyncio.run(fetcher.fetch_document(_hit(published=datetime(2026, 10, 1, tzinfo=timezone.utc)), "RQ01"))
    assert doc.fetch_status is FetchStatus.OK and doc.final_url == "https://press.com/final"
    assert doc.published_at_source is P.ARTICLE_META and doc.published_at.month == 9
    assert doc.source_type is SourceType.NEWS and doc.text_length == len(doc.text) >= 200


def test_fetch_failure_modes_are_recorded_not_raised(monkeypatch):
    import requests

    cases = [
        (lambda url: _Resp("x", 404), FetchStatus.HTTP_ERROR),
        (lambda url: _Resp("%PDF", ctype="application/pdf"), FetchStatus.UNSUPPORTED_TYPE),
        (lambda url: _Resp(_page(body="짧음")), FetchStatus.EMPTY_TEXT),
    ]
    for fn, status in cases:
        monkeypatch.setattr(fetcher, "_get", fn)
        assert asyncio.run(fetcher.fetch_document(_hit(), "RQ01")).fetch_status is status

    def boom(url):
        raise requests.ConnectionError("secret-host")

    monkeypatch.setattr(fetcher, "_get", boom)
    doc = asyncio.run(fetcher.fetch_document(_hit(), "RQ01"))
    assert doc.fetch_status is FetchStatus.NETWORK_ERROR and doc.error == "ConnectionError"


def _doc(i, source=SourceType.NEWS, status=FetchStatus.OK):
    return FetchedDocument(result_id=i, research_question_id="RQ01", requested_url="u", fetch_status=status,
                           source_type=source, text=BODY if status is FetchStatus.OK else None, text_length=len(BODY))


def test_synthesizer_prefers_official_sources_and_drops_unsourced_facts():
    from app.search.synthesizer import NUM_CTX, select_documents, synthesize_facts

    docs = [_doc("n1"), _doc("n2"), _doc("g1", SourceType.GOVERNMENT), _doc("bad", status=FetchStatus.HTTP_ERROR)]
    assert [d.result_id for d in select_documents(docs)] == ["g1", "n1", "n2"]
    assert len(select_documents([_doc(f"n{i}") for i in range(30)])) == 8

    seen = {}

    class FakeQwen:
        async def chat(self, system, user, schema, *, num_ctx=None):
            seen.update(user=json.loads(user), num_ctx=num_ctx)
            return FactResearchResult(
                summary="s", organizations=["충남도"], persons=[], locations=[], current_status="MOU 체결",
                key_facts=[KeyFact(fact="ok", source_result_ids=["n2", "ghost", "g1", "n1"]), KeyFact(fact="no source", source_result_ids=["ghost"])],
                timeline=[], uncertainties=[], missing_information=[],
            )

    issue = IssueInput(region="충청남도", start_date=datetime(2026, 9, 1).date(), end_date=datetime(2026, 9, 30).date(), issue="x")
    q = ResearchQuestion(id="RQ01", type="FACT", question="?")
    out = asyncio.run(synthesize_facts(FakeQwen(), issue, [q], docs))
    assert [(f.fact, f.source_result_ids) for f in out.key_facts] == [("ok", ["g1", "n1"])]  # official first, capped at 2, unseen ids dropped
    assert seen["num_ctx"] == NUM_CTX and [d["result_id"] for d in seen["user"]["documents"]] == ["g1", "n1", "n2"]
    assert len(seen["user"]["documents"][0]["excerpt"]) <= 3000
