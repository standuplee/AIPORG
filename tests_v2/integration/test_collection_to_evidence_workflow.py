import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.cleaning.service import CleaningService
from app.collection.service import CollectionService
from app.collectors.errors import CollectorError
from app.core.enums import ChannelType, CollectionRunStatus, WorkflowState
from app.dedup.service import DeduplicationService
from app.evidence.service import EvidenceService
from app.models import Base
from app.models.document import Document, DuplicateCluster
from app.models.evidence import Evidence
from app.models.project import Query
from app.repositories.sqlalchemy import (
    SqlAlchemyCollectionRunRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQuerySetRepository,
)
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
from app.schemas.document import RawDocument, SearchResult
from app.schemas.project import ProjectCreate
from app.schemas.query import SearchQuery
from app.workflows.collection_to_evidence import CollectionToEvidenceWorkflow


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _FixtureCollector:
    async def search(self, query):
        return [
            SearchResult(
                source="source-a",
                channel=ChannelType.NEWS,
                title="같은 정책 발표",
                url="https://example.com/a",
                published_at=NOW,
                query=query.query,
            ),
            SearchResult(
                source="source-b",
                channel=ChannelType.NEWS,
                title="같은 정책 발표",
                url="https://example.com/b",
                published_at=NOW,
                query=query.query,
            ),
        ]

    async def fetch(self, result):
        return RawDocument(
            **result.model_dump(),
            document_id=uuid4(),
            platform="fixture",
            body="충청남도가 정책을 발표했다.",
            metadata={},
            collected_at=NOW,
        )


class _SearchFailureCollector:
    async def search(self, query):
        del query
        raise CollectorError(code="fixture_failure", message="fixture search failed")

    async def fetch(self, result):
        raise AssertionError(f"fetch must not run: {result}")


def test_fixture_reaches_evidence_completed_without_network() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory.begin() as session:
        project_repository = SqlAlchemyProjectRepository(session)
        project = project_repository.create(ProjectCreate(
            name="충남 9월",
            target=TargetSchema(
                organization="충청남도", primary_person="도지사", region="충남"
            ),
            analysis_period=AnalysisPeriodSchema(
                start=date(2026, 9, 1), end=date(2026, 9, 30)
            ),
            comparison_period=ComparisonPeriodSchema(
                start=date(2026, 8, 1), end=date(2026, 8, 31)
            ),
            channels=[ChannelType.NEWS],
        ))
        query = SearchQuery(query="충남 정책", channels=[ChannelType.NEWS])
        SqlAlchemyQuerySetRepository(session).create(project.project_id, [query])
        project_repository.advance_workflow(
            project.project_id, WorkflowState.QUERIES_READY
        )
        query_id = session.scalar(
            select(Query.id).where(Query.project_id == project.project_id)
        )
        assert query_id is not None

        document_repository = SqlAlchemyDocumentRepository(session)
        workflow = CollectionToEvidenceWorkflow(
            collection_service=CollectionService(
                collector=_FixtureCollector(),
                document_repository=document_repository,
                collection_run_repository=SqlAlchemyCollectionRunRepository(session),
                now_fn=lambda: NOW,
            ),
            cleaning_service=CleaningService(),
            deduplication_service=DeduplicationService(),
            evidence_service=EvidenceService(now_fn=lambda: NOW),
            project_repository=project_repository,
            document_repository=document_repository,
            duplicate_cluster_repository=SqlAlchemyDuplicateClusterRepository(session),
            evidence_repository=SqlAlchemyEvidenceRepository(session),
        )
        result = asyncio.run(workflow.run(
            project_id=project.project_id,
            query_id=query_id,
            run_id=uuid4(),
            query=query,
        ))

        assert result.status is CollectionRunStatus.COMPLETED
        assert result.documents_saved == 2
        assert project_repository.get_workflow(project.project_id).workflow_state is (
            WorkflowState.EVIDENCE_COMPLETED
        )
        assert session.scalar(select(func.count()).select_from(Document)) == 2
        assert session.scalar(
            select(func.count()).select_from(Document).where(Document.cleaned_at.is_not(None))
        ) == 2
        assert session.scalar(select(func.count()).select_from(DuplicateCluster)) == 1
        assert session.scalar(select(func.count()).select_from(Evidence)) == 1


def test_failed_collection_can_retry_from_last_successful_state() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory.begin() as session:
        project_repository = SqlAlchemyProjectRepository(session)
        project = project_repository.create(ProjectCreate(
            name="retry fixture",
            target=TargetSchema(
                organization="충청남도", primary_person="도지사", region="충남"
            ),
            analysis_period=AnalysisPeriodSchema(
                start=date(2026, 9, 1), end=date(2026, 9, 30)
            ),
            comparison_period=ComparisonPeriodSchema(
                start=date(2026, 8, 1), end=date(2026, 8, 31)
            ),
            channels=[ChannelType.NEWS],
        ))
        query = SearchQuery(query="충남 정책", channels=[ChannelType.NEWS])
        SqlAlchemyQuerySetRepository(session).create(project.project_id, [query])
        project_repository.advance_workflow(
            project.project_id, WorkflowState.QUERIES_READY
        )
        query_id = session.scalar(
            select(Query.id).where(Query.project_id == project.project_id)
        )
        assert query_id is not None
        document_repository = SqlAlchemyDocumentRepository(session)

        def build_workflow(collector):
            return CollectionToEvidenceWorkflow(
                collection_service=CollectionService(
                    collector=collector,
                    document_repository=document_repository,
                    collection_run_repository=SqlAlchemyCollectionRunRepository(session),
                    now_fn=lambda: NOW,
                ),
                cleaning_service=CleaningService(),
                deduplication_service=DeduplicationService(),
                evidence_service=EvidenceService(now_fn=lambda: NOW),
                project_repository=project_repository,
                document_repository=document_repository,
                duplicate_cluster_repository=SqlAlchemyDuplicateClusterRepository(session),
                evidence_repository=SqlAlchemyEvidenceRepository(session),
            )

        failed = asyncio.run(build_workflow(_SearchFailureCollector()).run(
            project_id=project.project_id,
            query_id=query_id,
            run_id=uuid4(),
            query=query,
        ))
        assert failed.status is CollectionRunStatus.FAILED
        assert project_repository.get_workflow(project.project_id).workflow_state is (
            WorkflowState.QUERIES_READY
        )

        retried = asyncio.run(build_workflow(_FixtureCollector()).run(
            project_id=project.project_id,
            query_id=query_id,
            run_id=uuid4(),
            query=query,
        ))
        assert retried.status is CollectionRunStatus.COMPLETED
        assert project_repository.get_workflow(project.project_id).workflow_state is (
            WorkflowState.EVIDENCE_COMPLETED
        )
