from datetime import date, datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest

from app.analytics.service import AnalyticsService
from app.core.enums import ChannelType, WorkflowState
from app.db.session import create_session_factory, session_scope
from app.facts.extraction import FactExtractionService
from app.facts.validation import FactValidationService
from app.issues.discovery import IssueDiscoveryService
from app.issues.finalization import IssueFinalizationService
from app.repositories.sqlalchemy import (
    SqlAlchemyAnalyticsRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDuplicateClusterRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFactRepository,
    SqlAlchemyIssueRepository,
    SqlAlchemyProjectRepository,
)
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema, VersionedRunSchema
from app.schemas.document import CleanDocument, DuplicateClusterSchema, RawDocument
from app.schemas.evidence import EvidenceSchema
from app.schemas.project import ProjectCreate
from app.workflows.evidence_to_issues import EvidenceToIssuesWorkflow
from app.workflows.issues_to_analytics import IssuesToAnalyticsWorkflow


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def factory(tmp_path):
    url = f"sqlite:///{tmp_path / 'analytics.db'}"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    factory = create_session_factory(url)
    yield factory
    factory.kw["bind"].dispose()


def seed(session):
    projects = SqlAlchemyProjectRepository(session)
    project = projects.create(ProjectCreate(
        name="analytics fixture",
        target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
        analysis_period=AnalysisPeriodSchema(start=date(2026, 9, 1), end=date(2026, 9, 30)),
        comparison_period=ComparisonPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
        channels=[ChannelType.NEWS, ChannelType.BLOG],
    ))
    for state in (
        WorkflowState.QUERIES_READY, WorkflowState.COLLECTION_RUNNING,
        WorkflowState.COLLECTION_COMPLETED, WorkflowState.CLEANING_COMPLETED,
        WorkflowState.EVIDENCE_COMPLETED,
    ):
        projects.advance_workflow(project.project_id, state)
    documents = SqlAlchemyDocumentRepository(session)
    evidence = SqlAlchemyEvidenceRepository(session)
    ids = []
    for index in range(4):
        published = NOW if index < 3 else datetime(2026, 8, 1, tzinfo=timezone.utc)
        raw = RawDocument(
            document_id=uuid4(), source=f"source-{index}",
            channel=ChannelType.BLOG if index == 1 else ChannelType.NEWS,
            platform="fixture", title="정책 발표", url=f"https://example.test/{index}",
            published_at=published, collected_at=NOW, query="충남 정책",
            body="충청남도가 정책을 발표했다.",
            metadata={"sentiment": "positive"} if index == 0 else {},
        )
        ids.append(raw.document_id)
        documents.upsert_raw(project.project_id, raw)
        documents.upsert_clean(project.project_id, CleanDocument(
            document_id=raw.document_id, title=raw.title, body=raw.body,
            canonical_url=raw.url, cleaned_at=NOW, metadata=raw.metadata,
        ))
        if index < 2:
            evidence.create(EvidenceSchema(
                evidence_id=uuid4(), project_id=project.project_id,
                document_id=raw.document_id, excerpt=raw.body, created_at=NOW,
            ))
    SqlAlchemyDuplicateClusterRepository(session).create(project.project_id, DuplicateClusterSchema(
        cluster_id=uuid4(), canonical_document=ids[0], duplicates=[ids[2]],
        unique_sources=["source-0", "source-2"], distribution_count=2,
    ))
    EvidenceToIssuesWorkflow(
        project_repository=projects, document_repository=documents,
        evidence_repository=evidence, fact_repository=SqlAlchemyFactRepository(session),
        issue_repository=SqlAlchemyIssueRepository(session),
        fact_extraction_service=FactExtractionService(), fact_validation_service=FactValidationService(),
        issue_discovery_service=IssueDiscoveryService(), issue_finalization_service=IssueFinalizationService(),
    ).run(project.project_id)
    return project.project_id, ids


def workflow(session, project_repository=None):
    return IssuesToAnalyticsWorkflow(
        project_repository=project_repository or SqlAlchemyProjectRepository(session),
        document_repository=SqlAlchemyDocumentRepository(session),
        fact_repository=SqlAlchemyFactRepository(session),
        issue_repository=SqlAlchemyIssueRepository(session),
        analytics_repository=SqlAlchemyAnalyticsRepository(session),
        analytics_service=AnalyticsService(),
    )


def run_info():
    return VersionedRunSchema(
        run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1", created_at=NOW,
    )


def test_evidence_issues_analytics_commit_to_migrated_database(factory):
    with session_scope(factory) as session:
        project_id, ids = seed(session)
    run = run_info()
    with session_scope(factory) as session:
        result = workflow(session).run(project_id, run)
        assert result.metrics["unique_documents"] == 2
        assert result.metrics["document_ids"] == sorted(str(value) for value in ids[:2])
        assert str(ids[2]) not in result.metrics["input_document_ids"]
        assert result.metrics["channel_mentions"] == {"blog": 1, "news": 1}
        assert result.metrics["sentiment_distribution"]["positive"] == 1
        assert result.metrics["sentiment_distribution"]["unclassified"] == 1
        assert result.metrics["daily_mentions"]["2026-09-01"] == 2
        assert result.metrics["comparison"]["unique_documents"] == 1
        assert result.metrics["comparison"]["change_percent"] == 100
        assert result.metrics["issues"][0]["document_count"] == 2
        assert result.metrics["issues"][0]["source_count"] == 2
        # Every counted issue document still resolves to evidence and a stored document.
        evidence_ids = {str(item.document_id) for item in SqlAlchemyEvidenceRepository(session).list_by_project(project_id)}
        assert set(result.metrics["issues"][0]["document_ids"]) <= evidence_ids
    with session_scope(factory) as session:
        assert SqlAlchemyAnalyticsRepository(session).get_latest(project_id) == result
        assert SqlAlchemyAnalyticsRepository(session).get_latest(uuid4()) is None
        assert result.run == run
        assert SqlAlchemyProjectRepository(session).get_workflow(project_id).workflow_state is WorkflowState.ANALYTICS_COMPLETED


def test_state_transition_failure_rolls_back_snapshot_and_allows_retry(factory):
    with session_scope(factory) as session:
        project_id, _ = seed(session)

    class FailingProjectRepository(SqlAlchemyProjectRepository):
        def advance_workflow(self, project_id, state):
            super().advance_workflow(project_id, state)
            raise RuntimeError("fixture state write failure")

    with pytest.raises(RuntimeError, match="state write failure"):
        with session_scope(factory) as session:
            workflow(session, FailingProjectRepository(session)).run(project_id, run_info())
    with session_scope(factory) as session:
        assert SqlAlchemyAnalyticsRepository(session).get_latest(project_id) is None
        assert SqlAlchemyProjectRepository(session).get_workflow(project_id).workflow_state is WorkflowState.ISSUES_COMPLETED
        workflow(session).run(project_id, run_info())
    with session_scope(factory) as session:
        assert SqlAlchemyProjectRepository(session).get_workflow(project_id).workflow_state is WorkflowState.ANALYTICS_COMPLETED
