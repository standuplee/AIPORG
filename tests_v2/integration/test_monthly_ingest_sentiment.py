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
