from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.enums import ChannelType, FactStatus, WorkflowState
from app.facts.extraction import FactExtractionService
from app.facts.validation import FactValidationService
from app.issues.discovery import IssueDiscoveryService
from app.issues.finalization import IssueFinalizationService
from app.models import Base
from app.models.fact import Fact
from app.models.issue import Issue, IssueFact
from app.repositories.sqlalchemy import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFactRepository,
    SqlAlchemyIssueRepository,
    SqlAlchemyProjectRepository,
)
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
from app.schemas.document import CleanDocument, RawDocument
from app.schemas.evidence import EvidenceSchema
from app.schemas.project import ProjectCreate
from app.workflows.evidence_to_issues import EvidenceToIssuesWorkflow


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_evidence_becomes_verified_fact_and_traceable_issue() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory.begin() as session:
        project_repository = SqlAlchemyProjectRepository(session)
        project = project_repository.create(ProjectCreate(
            name="evidence fixture",
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
        for state in (
            WorkflowState.QUERIES_READY,
            WorkflowState.COLLECTION_RUNNING,
            WorkflowState.COLLECTION_COMPLETED,
            WorkflowState.CLEANING_COMPLETED,
            WorkflowState.EVIDENCE_COMPLETED,
        ):
            project_repository.advance_workflow(project.project_id, state)

        document_repository = SqlAlchemyDocumentRepository(session)
        evidence_repository = SqlAlchemyEvidenceRepository(session)
        document_ids = []
        for index, source in enumerate(("source-a", "source-b")):
            document_id = uuid4()
            document_ids.append(document_id)
            raw = RawDocument(
                document_id=document_id,
                source=source,
                channel=ChannelType.NEWS,
                platform="fixture",
                title="정책 발표",
                url=f"https://example.com/{index}",
                published_at=NOW,
                query="충청남도 정책",
                body="충청남도가 정책을 발표했다. 후속 설명이다.",
                metadata={},
                collected_at=NOW,
            )
            document_repository.upsert_raw(project.project_id, raw)
            document_repository.upsert_clean(project.project_id, CleanDocument(
                document_id=document_id,
                title=raw.title,
                body=raw.body,
                canonical_url=raw.url,
                cleaned_at=NOW,
                source=source,
                channel=ChannelType.NEWS,
                platform="fixture",
                published_at=NOW,
                query=raw.query,
            ))
            evidence_repository.create(EvidenceSchema(
                evidence_id=uuid4(),
                project_id=project.project_id,
                document_id=document_id,
                excerpt=raw.body,
                created_at=NOW,
            ))

        workflow = EvidenceToIssuesWorkflow(
            project_repository=project_repository,
            document_repository=document_repository,
            evidence_repository=evidence_repository,
            fact_repository=SqlAlchemyFactRepository(session),
            issue_repository=SqlAlchemyIssueRepository(session),
            fact_extraction_service=FactExtractionService(),
            fact_validation_service=FactValidationService(),
            issue_discovery_service=IssueDiscoveryService(),
            issue_finalization_service=IssueFinalizationService(),
        )
        issues = workflow.run(project.project_id)

        assert len(issues) == 1
        assert issues[0].document_count == 2
        assert issues[0].source_count == 2
        assert set(issues[0].fact_ids)
        assert issues[0].subissues[0].summary == "충청남도가 정책을 발표했다."
        assert project_repository.get_workflow(project.project_id).workflow_state is (
            WorkflowState.ISSUES_COMPLETED
        )
        fact = session.scalar(select(Fact))
        assert fact is not None
        assert fact.status is FactStatus.VERIFIED
        assert fact.source_count == 2
        assert set(fact.evidence_document_ids) == {str(value) for value in document_ids}
        assert session.scalar(select(func.count()).select_from(Issue)) == 1
        assert session.scalar(select(func.count()).select_from(IssueFact)) == 1
