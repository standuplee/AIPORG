import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.research import runner
from app.research.corpus import load_corpus
from app.research.review import load_session
from app.schemas.research import IssueInput, QueryType, SearchPurpose
from app.search.documents import FactResearchResult, FetchedDocument, FetchStatus, KeyFact, TimelineItem
from app.search.opinion import DiscussionPost, OpinionCandidates
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult, SourceType

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="석탄화력 특별법")
AT = datetime(2026, 8, 3, tzinfo=timezone.utc)


def _hit(n, channel=C.NEWS):
    return SearchResult(provider=SearchProvider.NAVER, channel=channel, query="q", sort="accuracy", title=f"제목{n}", snippet=f"요약{n}",
                        url=f"https://news.example.com/{n}", published_at=AT, rank=1)


def _q(rq, text, purpose=SearchPurpose.FACT_RESEARCH):
    return SimpleNamespace(research_question_id=rq, query=text, search_purpose=purpose)


@pytest.fixture
def wired(monkeypatch):
    a, b, c = _hit(1), _hit(2), _hit(3)
    calls = SimpleNamespace(analyzed=[], fetched=[])
    plan = SimpleNamespace(
        research_questions=[SimpleNamespace(id=f"RQ0{i}", type=QueryType.BACKGROUND, question=f"질문{i}") for i in (1, 2, 3)],
        queries=[_q("RQ01", "q1"), _q("RQ01", "q1b", SearchPurpose.FRAME_DISCOVERY), _q("RQ02", "q2"), _q("RQ03", "반응용", SearchPurpose.OPINION_CORPUS)],
        decomposition=SimpleNamespace(actions=[]), protected_terms=["석탄화력", "특별법"])

    class Qwen:
        async def expand(self, issue):
            return plan

    class Search:
        async def search_fact(self, query, limit=10):
            return {"q1": [a], "q1b": [a, b], "q2": [b, c]}[query]

    async def analyze_results(qwen, issue, decomposition, question, results):
        calls.analyzed.append((question.id, [r.result_id for r in results]))
        return SimpleNamespace(rq=question.id, results=results)

    monkeypatch.setattr(runner, "analyze_results", analyze_results)
    # relevant = everything except hit c
    monkeypatch.setattr(runner, "select_for_fetch", lambda analysis: [SimpleNamespace(result=r) for r in analysis.results if r.title != "제목3"])

    async def fetch_documents(results, rq_id, concurrency=4):
        calls.fetched.append((rq_id, [r.result_id for r in results]))
        return [FetchedDocument(result_id=r.result_id, research_question_id=rq_id, requested_url=r.url, fetch_status=FetchStatus.OK,
                                source_type=SourceType.NEWS, text=f"본문 {r.title}") for r in results]

    async def synthesize_facts(qwen, issue, questions, docs):
        calls.synth_docs = [d.result_id for d in docs]
        return FactResearchResult(summary="s", key_facts=[KeyFact(fact="f", source_result_ids=[a.result_id])], organizations=[], persons=[], locations=[],
                                  current_status=None, timeline=[TimelineItem(date="8월", event="e", source_result_ids=[b.result_id])],
                                  uncertainties=[], missing_information=[])

    post = _hit(9, C.BLOG)

    async def collect_corpus_adaptive(search, issue, queries, terms, *, qwen=None, fact=None):
        calls.corpus_terms = terms
        return [post], {"no_issue_term": 1}, [{"round": 0, "query": "반응 질의", "raw": 1, "kept": 1}]

    async def find_reaction_candidates(qwen, issue, queries, corpus, filtered_out, exclude):
        calls.exclude = exclude
        return OpinionCandidates(issue=issue.issue, queries=queries, corpus_size=1, relevant_count=1, filtered_out=filtered_out, exclude_keywords=exclude,
                                 candidates=[], discussion_posts=[DiscussionPost(result_id=post.result_id, channel="BLOG", title="글", url=post.url,
                                                                                  snippet="s", content_type="NEWS_REPOST", published_at=AT)])

    monkeypatch.setattr(runner, "fetch_documents", fetch_documents)
    monkeypatch.setattr(runner, "synthesize_facts", synthesize_facts)
    monkeypatch.setattr(runner, "collect_corpus_adaptive", collect_corpus_adaptive)
    monkeypatch.setattr(runner, "find_reaction_candidates", find_reaction_candidates)
    monkeypatch.setattr(runner, "build_queries", lambda issue, fact: ["반응 질의"])
    monkeypatch.setattr(runner, "key_terms", lambda issue, decomposition: ["석탄화력"])
    return SimpleNamespace(qwen=Qwen(), search=Search(), calls=calls, hits=(a, b, c), post=post)


def test_runner_saves_session_and_a_corpus_of_the_relevant_hits_only(wired, tmp_path):
    session, corpus = asyncio.run(runner.run_issue(wired.qwen, wired.search, ISSUE, "coal", tmp_path))
    a, b, c = wired.hits
    assert load_session(tmp_path / "session_coal.json").issue == ISSUE
    saved = load_corpus(tmp_path / "corpus_coal.json")
    assert saved == corpus
    ids = {i.result_id: i for i in corpus.items}
    assert set(ids) == {a.result_id, b.result_id, wired.post.result_id}       # c was judged not relevant; a found by two queries appears once
    assert ids[a.result_id].kind == "FACT" and ids[a.result_id].body == "본문 제목1" and ids[wired.post.result_id].kind == "OPINION"
    assert corpus.search_log == [{"round": 0, "query": "반응 질의", "raw": 1, "kept": 1}]
    assert session.fact_sources == {a.result_id: ["제목1", a.url], b.result_id: ["제목2", b.url]}


def test_questions_without_fact_queries_are_skipped_and_max_questions_limits_the_run(wired, tmp_path):
    asyncio.run(runner.run_issue(wired.qwen, wired.search, ISSUE, "coal", tmp_path))
    assert [q for q, _ in wired.calls.analyzed] == ["RQ01", "RQ02"]            # RQ03 has only an opinion query
    wired.calls.analyzed.clear()
    asyncio.run(runner.run_issue(wired.qwen, wired.search, ISSUE, "coal2", tmp_path, max_questions=1))
    assert [q for q, _ in wired.calls.analyzed] == ["RQ01"]


def test_opinion_stage_gets_the_issue_terms_and_protected_terms_as_excluded_keywords(wired, tmp_path):
    asyncio.run(runner.run_issue(wired.qwen, wired.search, ISSUE, "coal", tmp_path))
    assert wired.calls.corpus_terms == ["석탄화력"] and wired.calls.exclude == ["석탄화력", "특별법"]


def test_nothing_is_written_when_no_document_can_be_read(wired, monkeypatch, tmp_path):
    async def no_docs(*a, **k):
        raise ValueError("no readable documents to synthesize")

    monkeypatch.setattr(runner, "synthesize_facts", no_docs)
    with pytest.raises(ValueError, match="no readable"):
        asyncio.run(runner.run_issue(wired.qwen, wired.search, ISSUE, "coal", tmp_path))
    assert list(tmp_path.iterdir()) == []
