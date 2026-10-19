from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import ChannelType, ConfidenceGrade, FactStatus, SentimentLabel, StanceLabel
from app.db.session import session_scope
from app.models import Base
from app.report.approval import ReportApprovalError, ReportApprovalService
from app.repositories.sqlalchemy import (
    SqlAlchemyNarrativeRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyVisualizationRepository,
)
from app.schemas.common import (
    AnalysisPeriodSchema,
    ComparisonPeriodSchema,
    TargetSchema,
    VersionedRunSchema,
)
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueDetailSchema, IssueSchema
from app.schemas.narrative import NarrativeContext, NarrativeOutputSchema, NarrativeSentenceSchema
from app.schemas.project import ProjectCreate
from app.schemas.visualization import VisualizationItemSchema, VisualizationOutputSchema

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


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


def _fact() -> FactSchema:
    return FactSchema(
        fact_id=uuid4(), claim="사실 근거.", event_date=date(2026, 8, 14),
        entities=["충청남도"], evidence_document_ids=[uuid4()],
        source_count=1, confidence=ConfidenceGrade.B, status=FactStatus.SUPPORTED,
    )


def _issue(fact_id) -> IssueSchema:
    return IssueSchema(
        issue_id=uuid4(), label="충청남도", fact_ids=[fact_id],
        document_count=0, source_count=0, channel_count=0,
        subissues=[IssueDetailSchema(
            label="정책", policy="정책 발표", summary="근거 본문 요약",
            sentiment=SentimentLabel.NEUTRAL, stance=StanceLabel.NOT_APPLICABLE,
        )],
    )


def _visualization_output(slot_key: str) -> VisualizationOutputSchema:
    return VisualizationOutputSchema(
        project_id=uuid4(),  # overwritten by caller before saving
        run=VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW),
        analytics_run_id=uuid4(),
        slot_key=slot_key,
        kind="chart",
        title="시각 자료",
        items=[VisualizationItemSchema(
            label="뉴스", value=1, analytics_path="metrics.channel_mentions.NEWS", order=0,
        )],
    )


def test_approve_requires_narrative_and_all_visualization_slots() -> None:
    factory = _factory()
    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).create(_project())
        narrative_repo = SqlAlchemyNarrativeRepository(session)
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        report_repo = SqlAlchemyReportRepository(session)
        service = ReportApprovalService(narrative_repo, visualization_repo, report_repo)

        with pytest.raises(ReportApprovalError) as excinfo:
            service.approve(project.project_id, now=NOW)
        assert set(excinfo.value.missing) == {"narrative", "channel_donut", "top10_keywords"}
        assert report_repo.get_latest(project.project_id) is None


def test_approve_creates_report_once_everything_is_approved() -> None:
    factory = _factory()
    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).create(_project())
        narrative_repo = SqlAlchemyNarrativeRepository(session)
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        report_repo = SqlAlchemyReportRepository(session)
        service = ReportApprovalService(narrative_repo, visualization_repo, report_repo)

        fact = _fact()
        context = NarrativeContext(
            issue=_issue(fact.fact_id), facts=[fact], sentiment=SentimentLabel.NEUTRAL,
            keywords=["정책"], positive_reasons=[], negative_reasons=[],
        )
        narrative_repo.save(project.project_id, context)
        output = NarrativeOutputSchema(
            project_id=project.project_id,
            run=VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW),
            sentences=[NarrativeSentenceSchema(text="문장.", analytics_paths=["metrics.unique_documents"])],
        )
        narrative_repo.save_output(project.project_id, output)
        narrative_repo.approve_output(project.project_id, output.run.run_id, True, NOW)

        for slot_key in ("channel_donut", "top10_keywords"):
            viz_output = _visualization_output(slot_key).model_copy(update={"project_id": project.project_id})
            visualization_repo.save_output(project.project_id, viz_output)
            visualization_repo.approve_output(project.project_id, viz_output.run.run_id, True, NOW)

        report = service.approve(project.project_id, now=NOW)

        assert report_repo.get_latest(project.project_id) == report
        assert report.context == context
        assert {asset.kind for asset in report.visualizations} == {"chart"}
        assert len(report.visualizations) == 2


def test_approve_blocks_when_visualization_was_edited_after_approval() -> None:
    factory = _factory()
    with session_scope(factory) as session:
        project = SqlAlchemyProjectRepository(session).create(_project())
        narrative_repo = SqlAlchemyNarrativeRepository(session)
        visualization_repo = SqlAlchemyVisualizationRepository(session)
        report_repo = SqlAlchemyReportRepository(session)
        service = ReportApprovalService(narrative_repo, visualization_repo, report_repo)

        fact = _fact()
        context = NarrativeContext(
            issue=_issue(fact.fact_id), facts=[fact], sentiment=SentimentLabel.NEUTRAL,
            keywords=["정책"], positive_reasons=[], negative_reasons=[],
        )
        narrative_repo.save(project.project_id, context)
        output = NarrativeOutputSchema(
            project_id=project.project_id,
            run=VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW),
            sentences=[NarrativeSentenceSchema(text="문장.", analytics_paths=["metrics.unique_documents"])],
        )
        narrative_repo.save_output(project.project_id, output)
        narrative_repo.approve_output(project.project_id, output.run.run_id, True, NOW)

        donut_v1 = _visualization_output("channel_donut").model_copy(update={"project_id": project.project_id})
        visualization_repo.save_output(project.project_id, donut_v1)
        visualization_repo.approve_output(project.project_id, donut_v1.run.run_id, True, NOW)
        cards_v1 = _visualization_output("top10_keywords").model_copy(update={"project_id": project.project_id})
        visualization_repo.save_output(project.project_id, cards_v1)
        visualization_repo.approve_output(project.project_id, cards_v1.run.run_id, True, NOW)

        # re-render the donut (e.g. user edited a label) -- new version starts unapproved
        donut_v2 = donut_v1.model_copy(update={
            "run": VersionedRunSchema(
                run_id=uuid4(), input_version="v1", output_version="v2",
                created_at=NOW.replace(microsecond=1),
            ),
            "approved": False,
            "approved_at": None,
        })
        visualization_repo.save_output(project.project_id, donut_v2)

        with pytest.raises(ReportApprovalError) as excinfo:
            service.approve(project.project_id, now=NOW)
        assert excinfo.value.missing == ["channel_donut"]
