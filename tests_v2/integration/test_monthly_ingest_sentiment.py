import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import ChannelType
from app.models import Base
from app.repositories.sqlalchemy import SqlAlchemyDocumentRepository, SqlAlchemyProjectRepository
from app.research.corpus import CorpusItem, IssueCorpus
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
from app.schemas.project import ProjectCreate
from app.workflows.ingest_issue_corpora import ingest_corpora

AT = datetime(2026, 8, 5, tzinfo=timezone.utc)


def _item(rid, url=None, channel="BLOG", published=AT, source_type="BLOG", kind="OPINION", body=None):
    return CorpusItem(result_id=rid, channel=channel, title=f"제목 {rid}", url=url or f"https://blog.example.com/{rid}",
                      snippet=f"스니펫 {rid} 석탄화력 특별법", published_at=published, kind=kind, source_type=source_type, body=body)


def _corpus(issue, *items):
    return IssueCorpus(issue=issue, region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), items=list(items))


def _factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _project(session):
    return SqlAlchemyProjectRepository(session).create(ProjectCreate(
        name="충남 8월", target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
        analysis_period=AnalysisPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
        comparison_period=ComparisonPeriodSchema(start=date(2026, 7, 1), end=date(2026, 7, 31)),
        channels=[ChannelType.BLOG, ChannelType.NEWS, ChannelType.COMMUNITY])).project_id


def test_ingest_counts_add_up_and_issue_becomes_query():
    factory = _factory()
    corpus = _corpus("석탄화력 특별법", _item("a"), _item("b", "https://news.example.com/b", "NEWS", source_type="NEWS", kind="FACT", body="기사 본문"),
                     _item("c", channel="CAFE", source_type="COMMUNITY"), _item("d", published=None), _item("e", channel="WEB", source_type="OTHER"))
    with factory.begin() as session:
        project_id = _project(session)
        summary = asyncio.run(ingest_corpora(session, project_id, [corpus]))
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
    s = summary["석탄화력 특별법"]
    assert s == {"total": 5, "ingestible": 3, "held_undated": 1, "held_unmapped_channel": 1}
    assert s["total"] == s["ingestible"] + s["held_undated"] + s["held_unmapped_channel"]
    assert len(docs) == 3 and {d.query for d in docs} == {"석탄화력 특별법"} and summary["__canonical_documents__"] == {"count": 3}
    assert {d.channel for d in docs} == {ChannelType.BLOG, ChannelType.NEWS, ChannelType.COMMUNITY}


def test_same_url_in_fact_and_opinion_is_one_document():
    factory = _factory()
    corpus = _corpus("석탄화력 특별법", _item("x1", "https://blog.example.com/same", kind="FACT"), _item("x2", "https://blog.example.com/same"))
    with factory.begin() as session:
        project_id = _project(session)
        summary = asyncio.run(ingest_corpora(session, project_id, [corpus]))
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
    assert summary["석탄화력 특별법"]["ingestible"] == 2 and len(docs) == 1


def test_all_undated_issue_ingests_nothing_without_error():
    factory = _factory()
    corpus = _corpus("석탄화력 특별법", _item("u1", published=None), _item("u2", published=None))
    with factory.begin() as session:
        project_id = _project(session)
        summary = asyncio.run(ingest_corpora(session, project_id, [corpus]))
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
    assert summary["석탄화력 특별법"] == {"total": 2, "ingestible": 0, "held_undated": 2, "held_unmapped_channel": 0}
    assert docs == [] and summary["__canonical_documents__"] == {"count": 0}


def test_two_issues_make_two_queries():
    factory = _factory()
    a = _corpus("석탄화력 특별법", _item("a1"))
    b = _corpus("폭염 대응", _item("b1"), _item("b2", channel="CAFE", source_type="COMMUNITY"))
    with factory.begin() as session:
        project_id = _project(session)
        asyncio.run(ingest_corpora(session, project_id, [a, b]))
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
    assert {d.query for d in docs} == {"석탄화력 특별법", "폭염 대응"} and len(docs) == 3


class _AnswerQwen:
    model = "fake-qwen"

    def __init__(self):
        self.titles_seen = []

    async def chat(self, system, user, schema, **kw):
        import json
        from app.sentiment.document_classifier import SentimentBatch, SentimentItem
        items = []
        for d in json.loads(user)["documents"]:
            self.titles_seen.append(d["title"])
            if d["title"].endswith(" a"):
                items.append(SentimentItem(document_id=d["document_id"], label="positive", evidence="석탄화력 특별법", reason="r"))
            elif d["title"].endswith(" c"):
                items.append(SentimentItem(document_id=d["document_id"], label="negative", evidence="없는 문장", reason="r"))
            else:
                items.append(SentimentItem(document_id=d["document_id"], label="neutral", reason="r"))
        return SentimentBatch(results=items)


def test_classify_project_writes_labels_the_analytics_reads():
    from app.sentiment.document_classifier import classify_project
    factory = _factory()
    corpus = _corpus("석탄화력 특별법", _item("a"), _item("b"), _item("c"))
    with factory.begin() as session:
        project_id = _project(session)
        asyncio.run(ingest_corpora(session, project_id, [corpus]))
        counts = asyncio.run(classify_project(_AnswerQwen(), session, project_id))
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
    assert counts == {"positive": 1, "negative": 0, "neutral": 1, "mixed": 0, "unclassified": 1, "skipped_reviewed": 0}
    assert sum(counts.values()) == len(docs) == 3
    by_title = {d.title: d for d in docs}
    assert by_title["제목 a"].metadata["sentiment"] == "positive" and by_title["제목 b"].metadata["sentiment"] == "neutral"
    assert "sentiment" not in by_title["제목 c"].metadata and by_title["제목 c"].metadata["sentiment_reason"] == "근거 구절 확인 실패"


def test_rerun_keeps_other_metadata_and_skips_reviewed_documents():
    from app.sentiment.document_classifier import classify_project
    factory = _factory()
    corpus = _corpus("석탄화력 특별법", _item("a"), _item("b"))
    with factory.begin() as session:
        project_id = _project(session)
        asyncio.run(ingest_corpora(session, project_id, [corpus]))
        asyncio.run(classify_project(_AnswerQwen(), session, project_id))
        repo = SqlAlchemyDocumentRepository(session)
        a = next(d for d in repo.list_canonical(project_id) if d.title == "제목 a")
        repo.upsert_clean(project_id, a.model_copy(update={"metadata": {**a.metadata, "sentiment": "negative", "sentiment_review": "CORRECTED"}}))
        qwen = _AnswerQwen()
        counts = asyncio.run(classify_project(qwen, session, project_id))
        docs = {d.title: d for d in repo.list_canonical(project_id)}
    assert counts["skipped_reviewed"] == 1 and qwen.titles_seen == ["제목 b"]
    assert docs["제목 a"].metadata["sentiment"] == "negative" and docs["제목 a"].metadata["body_available"] is False
    assert docs["제목 b"].metadata["kind"] == "OPINION" and docs["제목 b"].metadata["sentiment"] == "neutral"


class _KeyedQwen:
    """Label by the first letter of the result id in the title: p positive, n negative, u neutral, x bad evidence."""
    model = "fake-qwen"

    async def chat(self, system, user, schema, **kw):
        import json
        from app.sentiment.document_classifier import SentimentBatch, SentimentItem
        out = []
        for d in json.loads(user)["documents"]:
            kind = d["title"].split()[-1][0]
            label, evidence = {"p": ("positive", "석탄화력 특별법"), "n": ("negative", "석탄화력 특별법"), "u": ("neutral", ""), "x": ("negative", "원문에 없는 문장")}[kind]
            out.append(SentimentItem(document_id=d["document_id"], label=label, evidence=evidence, reason="r"))
        return SentimentBatch(results=out)


def test_corpus_to_sentiment_distribution():
    from datetime import date as _date

    from app.analytics.service import AnalyticsService
    from app.schemas.common import VersionedRunSchema
    from uuid import uuid4

    from app.sentiment.document_classifier import classify_project

    factory = _factory()
    corpora = [_corpus("석탄화력 특별법", _item("p1"), _item("p2"), _item("n1"), _item("d1", published=None)),
               _corpus("폭염 대응", _item("u1"), _item("x1"), _item("x2", channel="CAFE", source_type="COMMUNITY"))]

    def distribution(session, project_id):
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)
        run = VersionedRunSchema(run_id=uuid4(), input_version="docs:v1", output_version="analytics:v1", created_at=AT)
        snapshot = AnalyticsService().build(project_id, run, docs, analysis_period=AnalysisPeriodSchema(start=_date(2026, 8, 1), end=_date(2026, 8, 31)),
                                            comparison_period=None)
        return snapshot.metrics["sentiment_distribution"], snapshot.metrics["unique_documents"]

    with factory.begin() as session:
        project_id = _project(session)
        summary = asyncio.run(ingest_corpora(session, project_id, corpora))
        before, _ = distribution(session, project_id)
        asyncio.run(classify_project(_KeyedQwen(), session, project_id))
        after, unique = distribution(session, project_id)
    assert before["unclassified"] == 6 and before["positive"] == 0          # without classification nothing is counted
    assert after == {"mixed": 0, "negative": 1, "neutral": 1, "positive": 2, "unclassified": 2}
    assert sum(after.values()) == unique == summary["__canonical_documents__"]["count"] == 6
    assert summary["석탄화력 특별법"]["held_undated"] == 1                    # the held post is in no count


def test_two_corpora_with_the_same_issue_name_are_rejected_not_silently_merged():
    import pytest

    factory = _factory()
    with factory.begin() as session:
        project_id = _project(session)
        with pytest.raises(ValueError, match="석탄화력 특별법"):
            asyncio.run(ingest_corpora(session, project_id, [_corpus("석탄화력 특별법", _item("a")), _corpus("석탄화력 특별법", _item("b"))]))
        assert SqlAlchemyDocumentRepository(session).count_canonical(project_id) == 0


def test_ingest_corpus_files_reads_saved_corpora_into_the_project(tmp_path):
    from app.research.corpus import save_corpus
    from app.workflows.ingest_issue_corpora import ingest_corpus_files

    factory = _factory()
    with factory.begin() as session:
        project_id = _project(session)
    save_corpus(tmp_path / "corpus_a.json", _corpus("석탄화력 특별법", _item("a1"), _item("a2", published=None)))
    save_corpus(tmp_path / "corpus_b.json", _corpus("폭염 대응", _item("b1")))
    summary = ingest_corpus_files(factory, project_id, [tmp_path / "corpus_a.json", tmp_path / "corpus_b.json"])
    assert summary["석탄화력 특별법"]["held_undated"] == 1 and summary["__canonical_documents__"] == {"count": 2}
    with factory.begin() as session:
        assert {d.query for d in SqlAlchemyDocumentRepository(session).list_canonical(project_id)} == {"석탄화력 특별법", "폭염 대응"}
