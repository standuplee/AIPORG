from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.enums import (
    ChannelType,
    CollectionRunStatus,
    ConfidenceGrade,
    FactStatus,
    SentimentLabel,
    WorkflowState,
)
from app.core.state_machine import InvalidStateTransitionError
from app.db.session import session_scope
from app.models import Base
from app.models.project import Query
from app.repositories.sqlalchemy import (
    SqlAlchemyAnalyticsRepository,
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFactRepository,
    SqlAlchemyIssueRepository,
    SqlAlchemyNarrativeRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQuerySetRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyVisualizationRepository,
)
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.collection import CollectionRun
from app.schemas.common import (
    AnalysisPeriodSchema,
    ComparisonPeriodSchema,
    TargetSchema,
    VersionedRunSchema,
)
from app.schemas.document import CleanDocument, RawDocument

from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema, NumericFactSchema
from app.schemas.issue import IssueDetailSchema, IssueSchema
from app.schemas.narrative import NarrativeContext
from app.schemas.project import ProjectCreate
from app.schemas.query import SearchQuery
from app.schemas.report import ReportSchema
from app.schemas.visualization import VisualizationAssetSchema


def _factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _project():
    return ProjectCreate(
        name="충남 여론",
        target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
        analysis_period=AnalysisPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
        comparison_period=ComparisonPeriodSchema(start=date(2026, 7, 1), end=date(2026, 7, 31)),
        channels=[ChannelType.NEWS],
    )


def test_project_and_query_repositories_are_project_scoped() -> None:
    factory = _factory()
    with session_scope(factory) as session:
        project_repo = SqlAlchemyProjectRepository(session)
        first = project_repo.create(_project())
        second = project_repo.create(_project().model_copy(update={"name": "다른 프로젝트"}))
        query_repo = SqlAlchemyQuerySetRepository(session)
        query_repo.create(first.project_id, [SearchQuery(query="충남", channels=[ChannelType.NEWS])])

        assert project_repo.get(first.project_id) == first
        assert query_repo.get(first.project_id)[0].query == "충남"
        assert query_repo.get(second.project_id) == []

        snapshot = project_repo.advance_workflow(
            first.project_id, WorkflowState.QUERIES_READY
        )
        assert snapshot.workflow_state is WorkflowState.QUERIES_READY
        assert project_repo.get_workflow(first.project_id) == snapshot
        with pytest.raises(InvalidStateTransitionError):
            project_repo.advance_workflow(
                first.project_id, WorkflowState.COLLECTION_COMPLETED
            )


def test_collection_run_and_document_upsert_round_trip() -> None:
    factory = _factory()
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).create(_project())
        SqlAlchemyQuerySetRepository(session).create(
            project.project_id, [SearchQuery(query="충남", channels=[ChannelType.NEWS])]
        )
        query_id = session.scalar(select(Query.id).where(Query.project_id == project.project_id))
        assert query_id is not None
        run = CollectionRun(
            id=uuid4(), project_id=project.project_id, channel=ChannelType.NEWS,
            query="충남", started_at=now, status=CollectionRunStatus.RUNNING,
            documents_found=0, documents_saved=0, error_count=0,
        )
        run_repo = SqlAlchemyCollectionRunRepository(session)
        assert run_repo.start(project.project_id, query_id, run) == run

        raw = RawDocument(
            document_id=uuid4(), source="연합뉴스", channel=ChannelType.NEWS,
            platform="naver", title="충남 소식", url="https://example.com/news/1",
            published_at=now, query="충남", body="본문", metadata={}, collected_at=now,
        )
        document_repo = SqlAlchemyDocumentRepository(session)
        persisted = document_repo.upsert_raw(project.project_id, raw)
        assert persisted.document_id == raw.document_id
        assert persisted.query == "충남"
        changed = raw.model_copy(update={"title": "수정된 제목"})
        assert document_repo.upsert_raw(project.project_id, changed).title == "수정된 제목"
        clean = CleanDocument(
            document_id=raw.document_id, title="정제 제목", body="정제 본문",
            canonical_url=raw.url, cleaned_at=now,
        )
        assert document_repo.upsert_clean(project.project_id, clean).body == "정제 본문"
        assert document_repo.get_by_canonical_url(project.project_id, raw.url) is not None


def test_downstream_repositories_round_trip_fixed_contracts() -> None:
    factory = _factory()
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).create(_project())
        document = RawDocument(
            document_id=uuid4(), source="연합뉴스", channel=ChannelType.NEWS,
            platform="naver", title="정책 발표", url="https://example.com/policy",
            published_at=now, query="정책", body="정책 근거 본문", metadata={}, collected_at=now,
        )
        SqlAlchemyDocumentRepository(session).upsert_raw(project.project_id, document)
        evidence = EvidenceSchema(
            evidence_id=uuid4(), project_id=project.project_id,
            document_id=document.document_id, excerpt=document.body, created_at=now,
        )
        evidence_repo = SqlAlchemyEvidenceRepository(session)
        evidence_repo.create(evidence)
        assert evidence_repo.get(project.project_id, evidence.evidence_id) == evidence
        assert evidence_repo.list_by_project(project.project_id) == [evidence]
        assert SqlAlchemyDocumentRepository(session).get(
            project.project_id, document.document_id
        ).document_id == document.document_id

        fact = FactSchema(
            fact_id=uuid4(), claim="정책 발표", event_date=date(2026, 8, 1),
            entities=["충청남도"], evidence_document_ids=[document.document_id],
            source_count=1, confidence=ConfidenceGrade.B, status=FactStatus.SUPPORTED,
        )
        fact_repo = SqlAlchemyFactRepository(session)
        fact_repo.save_batch(project.project_id, [fact])
        fact_repo.save_numeric(project.project_id, fact.fact_id, NumericFactSchema(
            metric="근거 수치", value=1, unit="건", source="연합뉴스",
            evidence_ids=[evidence.evidence_id], confidence=ConfidenceGrade.B,
        ))
        assert fact_repo.get(project.project_id, fact.fact_id) == fact

        issue = IssueSchema(
            issue_id=uuid4(), label="충청남도", fact_ids=[fact.fact_id],
            document_count=1, source_count=1, channel_count=1,
            subissues=[IssueDetailSchema(
                label="정책", policy="정책 발표", summary="근거 본문 요약",
                sentiment=SentimentLabel.NEUTRAL,
            )],
        )
        issue_repo = SqlAlchemyIssueRepository(session)
        issue_repo.save_batch(project.project_id, [issue])
        assert issue_repo.get(project.project_id, issue.issue_id) == issue

        run = VersionedRunSchema(
            run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1",
            created_at=now,
        )
        snapshot = AnalyticsSnapshotSchema(
            project_id=project.project_id, run=run, metrics={"unique_documents": 1},
        )
        analytics_repo = SqlAlchemyAnalyticsRepository(session)
        analytics_repo.create(snapshot)
        assert analytics_repo.get_latest(project.project_id) == snapshot

        context = NarrativeContext(
            issue=issue, facts=[fact], sentiment=SentimentLabel.NEUTRAL,
            keywords=["정책"], positive_reasons=[], negative_reasons=[],
        )
        narrative_repo = SqlAlchemyNarrativeRepository(session)
        narrative_repo.save(project.project_id, context)
        assert narrative_repo.get_latest(project.project_id) == context

        asset = VisualizationAssetSchema(
            visualization_id=uuid4(), project_id=project.project_id,
            kind="bar", title="채널별 언급량", created_at=now,
        )
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        visualization_repo.create(asset)
        assert visualization_repo.list_by_project(project.project_id) == [asset]

        report = ReportSchema(
            report_id=uuid4(), project_id=project.project_id, run=run,
            context=context, visualizations=[asset],
        )
        report_repo = SqlAlchemyReportRepository(session)
        report_repo.create(report)
        assert report_repo.get_latest(project.project_id) == report


def test_canonical_document_selection_excludes_duplicates_unclean_and_other_projects():
    from app.db.session import create_session_factory
    from app.repositories.sqlalchemy import SqlAlchemyDuplicateClusterRepository
    from app.schemas.document import DuplicateClusterSchema

    factory = create_session_factory("sqlite://")
    Base.metadata.create_all(factory.kw["bind"])
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    with session_scope(factory) as session:
        projects = SqlAlchemyProjectRepository(session)
        first, other = projects.create(_project()), projects.create(_project())
        documents = SqlAlchemyDocumentRepository(session)
        ids = []
        for index, project_id in enumerate([first.project_id] * 3 + [other.project_id]):
            raw = RawDocument(
                document_id=uuid4(), title="정책", body="본문", source="source",
                channel=ChannelType.NEWS, platform="fixture", url=f"https://example.test/{index}",
                published_at=now, collected_at=now, query="정책", metadata={},
            )
            documents.upsert_raw(project_id, raw)
            ids.append(raw.document_id)
            if index != 2:
                documents.upsert_clean(project_id, CleanDocument(
                    document_id=raw.document_id, title=raw.title, body=raw.body,
                    canonical_url=raw.url, cleaned_at=now,
                ))
        SqlAlchemyDuplicateClusterRepository(session).create(first.project_id, DuplicateClusterSchema(
            cluster_id=uuid4(), canonical_document=ids[0], duplicates=[ids[1]],
            unique_sources=["source"], distribution_count=2,
        ))
        assert [item.document_id for item in documents.list_canonical(first.project_id)] == [ids[0]]
        assert [item.document_id for item in documents.list_canonical(other.project_id)] == [ids[3]]
        assert documents.list_canonical(uuid4()) == []


def test_issue_listing_is_project_scoped_and_round_trips_existing_contract():
    factory = _factory()
    with session_scope(factory) as session:
        projects = SqlAlchemyProjectRepository(session)
        first, other = projects.create(_project()), projects.create(_project())
        fact = FactSchema(
            fact_id=uuid4(), claim="정책", event_date=date(2026, 9, 1), entities=["정책"],
            evidence_document_ids=[uuid4()], source_count=1,
            confidence=ConfidenceGrade.A, status=FactStatus.VERIFIED,
        )
        SqlAlchemyFactRepository(session).save_batch(first.project_id, [fact])
        issues = [IssueSchema(
            issue_id=uuid4(), label=label, fact_ids=[fact.fact_id],
            document_count=1, source_count=1, channel_count=1, subissues=[],
        ) for label in ["정책", "지원"]]
        repository = SqlAlchemyIssueRepository(session)
        repository.save_batch(first.project_id, issues)
        assert repository.list_by_project(first.project_id) == sorted(issues, key=lambda item: str(item.issue_id))
        assert repository.list_by_project(other.project_id) == []
