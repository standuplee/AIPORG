from datetime import date, datetime, timezone

from app.research.corpus import IssueCorpus, build_corpus, load_corpus, save_corpus
from app.schemas.research import IssueInput
from app.search.documents import FetchedDocument, FetchStatus
from app.search.opinion import DiscussionPost
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchProvider, SearchResult, SourceType
from app.search.signals import source_type

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="석탄화력 특별법")


def _hit(i, channel=C.NEWS, url=None, published=datetime(2026, 8, 3, tzinfo=timezone.utc)):
    return SearchResult(provider=SearchProvider.NAVER, channel=channel, query="q", sort="accuracy", title=f"제목{i}",
                        snippet=f"요약{i}", url=url or f"https://news.example.com/{i}", published_at=published, rank=1)


def _fetched(hit, text="본문 전체", kind=SourceType.GOVERNMENT):
    return FetchedDocument(result_id=hit.result_id, research_question_id="RQ01", requested_url=hit.url,
                           fetch_status=FetchStatus.OK, source_type=kind, text=text)


def _post(result_id, channel="BLOG", published=None):
    return DiscussionPost(result_id=result_id, channel=channel, title="글", url=f"https://blog.example/{result_id}",
                          snippet="스니펫", content_type="NEWS_REPOST", published_at=published)


def test_build_corpus_merges_fact_and_opinion_and_keeps_one_item_per_result_id():
    a, b = _hit(1), _hit(2)
    corpus = build_corpus(ISSUE, [a, b], {a.result_id: _fetched(a)}, [_post(a.result_id), _post("op2")])
    assert len(corpus.items) == 3
    by_id = {i.result_id: i for i in corpus.items}
    assert by_id[a.result_id].kind == "FACT" and by_id[a.result_id].body == "본문 전체"
    assert by_id[b.result_id].body is None and by_id["op2"].kind == "OPINION"


def test_source_type_comes_from_fetched_document_then_registry_then_channel():
    a, b = _hit(1), _hit(2)
    corpus = build_corpus(ISSUE, [a, b], {a.result_id: _fetched(a, kind=SourceType.GOVERNMENT)},
                          [_post("op1", "BLOG"), _post("op2", "CAFE")])
    by_id = {i.result_id: i for i in corpus.items}
    assert by_id[a.result_id].source_type == "GOVERNMENT"
    assert by_id[b.result_id].source_type == source_type(b).value
    assert by_id["op1"].source_type == "BLOG" and by_id["op2"].source_type == "COMMUNITY"


def test_save_and_load_round_trip_keeps_missing_published_at_as_none(tmp_path):
    corpus = build_corpus(ISSUE, [_hit(1)], {}, [_post("op1", published=None)])
    path = tmp_path / "corpus.json"
    save_corpus(path, corpus)
    loaded = load_corpus(path)
    assert isinstance(loaded, IssueCorpus) and loaded == corpus
    assert {i.result_id: i.published_at for i in loaded.items}["op1"] is None
