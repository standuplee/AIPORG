import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.cleaning.service import CleaningService
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
from app.workflows.multi_query_collection_to_evidence import (
    CollectionRequest,
    MultiQueryCollectionToEvidenceWorkflow,
)


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _KeywordCollector:
    """Returns a fixed article plus a shared cross-keyword article."""

    def __init__(self, own_url: str, own_title: str) -> None:
        self.own_url = own_url
        self.own_title = own_title

    async def search(self, query):
        return [
            SearchResult(
                source="naver",
                channel=ChannelType.NEWS,
                title="충남 2차 공공기관 이전 발표",
                url="https://example.com/shared-across-keywords",
                published_at=NOW,
                query=query.query,
            ),
            SearchResult(
                source="daum",
                channel=ChannelType.NEWS,
                title=self.own_title,
                url=self.own_url,
                published_at=NOW,
                query=query.query,
            ),
        ]

    async def fetch(self, result):
        body = "충남으로 공공기관이 이전한다." if "shared" in result.url else f"{result.title} 상세 내용."
        return RawDocument(
            **result.model_dump(),
            document_id=uuid4(),
            platform="fixture",
            body=body,
            metadata={},
            collected_at=NOW,
        )


class _FailingCollector:
    async def search(self, query):
        del query
        raise CollectorError(code="fixture_failure", message="fixture search failed")

    async def fetch(self, result):
        raise AssertionError(f"fetch must not run: {result}")


def _project_create() -> ProjectCreate:
    return ProjectCreate(
        name="충남 9월 다중 키워드",
        target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
        analysis_period=AnalysisPeriodSchema(start=date(2026, 9, 1), end=date(2026, 9, 30)),
        comparison_period=ComparisonPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
        channels=[ChannelType.NEWS],
    )


def test_same_article_found_under_two_keywords_counts_once() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory.begin() as session:
        project_repository = SqlAlchemyProjectRepository(session)
        project = project_repository.create(_project_create())

        keyword_a = SearchQuery(query="충남 재정전략회의", channels=[ChannelType.NEWS])
        keyword_b = SearchQuery(query="삼성 디스플레이 투자유치", channels=[ChannelType.NEWS])
        keyword_c = SearchQuery(query="실패하는 키워드", channels=[ChannelType.NEWS])
        SqlAlchemyQuerySetRepository(session).create(
            project.project_id, [keyword_a, keyword_b, keyword_c]
        )
        project_repository.advance_workflow(project.project_id, WorkflowState.QUERIES_READY)

        query_id_by_text = dict(
            session.execute(
                select(Query.query, Query.id).where(Query.project_id == project.project_id)
            ).all()
        )

        document_repository = SqlAlchemyDocumentRepository(session)
        workflow = MultiQueryCollectionToEvidenceWorkflow(
            collection_run_repository=SqlAlchemyCollectionRunRepository(session),
            cleaning_service=CleaningService(),
            deduplication_service=DeduplicationService(),
            evidence_service=EvidenceService(now_fn=lambda: NOW),
            project_repository=project_repository,
            document_repository=document_repository,
            duplicate_cluster_repository=SqlAlchemyDuplicateClusterRepository(session),
            evidence_repository=SqlAlchemyEvidenceRepository(session),
            now_fn=lambda: NOW,
        )

        requests = [
            CollectionRequest(
                collector=_KeywordCollector(
                    "https://example.com/only-keyword-a", "충남 재정전략회의 개최"
                ),
                query_id=query_id_by_text[keyword_a.query],
                run_id=uuid4(),
                query=keyword_a,
            ),
            CollectionRequest(
                collector=_KeywordCollector(
                    "https://example.com/only-keyword-b", "삼성 디스플레이 67조 투자"
                ),
                query_id=query_id_by_text[keyword_b.query],
                run_id=uuid4(),
                query=keyword_b,
            ),
            CollectionRequest(
                collector=_FailingCollector(),
                query_id=query_id_by_text[keyword_c.query],
                run_id=uuid4(),
                query=keyword_c,
            ),
        ]

        results = asyncio.run(workflow.run(project_id=project.project_id, requests=requests))

        assert [r.status for r in results] == [
            CollectionRunStatus.COMPLETED,
            CollectionRunStatus.COMPLETED,
            CollectionRunStatus.FAILED,
        ]
        assert project_repository.get_workflow(project.project_id).workflow_state is (
            WorkflowState.EVIDENCE_COMPLETED
        )

        # 3 unique canonical URLs total: the shared article (found twice) plus
        # each keyword's own article -- the shared article must not be stored
        # twice just because two keywords found it.
        assert session.scalar(select(func.count()).select_from(Document)) == 3
        assert session.scalar(
            select(func.count()).select_from(Document).where(Document.cleaned_at.is_not(None))
        ) == 3
        assert session.scalar(select(func.count()).select_from(DuplicateCluster)) == 0
        assert session.scalar(select(func.count()).select_from(Evidence)) == 3
