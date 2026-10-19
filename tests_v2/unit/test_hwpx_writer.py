from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from hwpx import TextExtractor
from hwpx.tools.package_validator import validate_editor_open_safety
from hwpx.tools.validator import validate_document

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel
from app.report.hwpx_writer import HwpxPrototypeError, build_cover_toc_summary
from app.schemas.common import VersionedRunSchema
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueDetailSchema, IssueSchema
from app.schemas.narrative import NarrativeContext, NarrativeOutputSchema, NarrativeSentenceSchema
from app.schemas.report import ReportSchema
from app.schemas.visualization import VisualizationItemSchema, VisualizationOutputSchema

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def _run() -> VersionedRunSchema:
    return VersionedRunSchema(run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW)


def _narrative_context() -> NarrativeContext:
    fact = FactSchema(
        fact_id=uuid4(), claim="사실 근거 문장.", event_date=NOW.date(),
        entities=["충청남도"], evidence_document_ids=[uuid4()],
        source_count=1, confidence=ConfidenceGrade.A, status=FactStatus.VERIFIED,
    )
    issue = IssueSchema(
        issue_id=uuid4(), label="내포신도시 2차 이전", fact_ids=[fact.fact_id],
        document_count=1, source_count=1, channel_count=1,
        subissues=[IssueDetailSchema(
            label="정책", policy="이전 발표", summary="요약", sentiment=SentimentLabel.POSITIVE,
        )],
    )
    return NarrativeContext(
        issue=issue, facts=[fact], sentiment=SentimentLabel.POSITIVE,
        keywords=[issue.label], positive_reasons=[], negative_reasons=[],
    )


def _narrative_output(project_id) -> NarrativeOutputSchema:
    return NarrativeOutputSchema(
        project_id=project_id, run=_run(),
        sentences=[NarrativeSentenceSchema(
            text="내포신도시 2차 이전 발표 이후 언급량이 뚜렷하게 늘었다.",
            analytics_paths=["metrics.unique_documents"],
        )],
        approved=True, approved_at=NOW,
    )


def _visualization_output(project_id, slot_key: str, items: list[VisualizationItemSchema]) -> VisualizationOutputSchema:
    return VisualizationOutputSchema(
        project_id=project_id, run=_run(), analytics_run_id=uuid4(),
        slot_key=slot_key, kind="chart" if slot_key == "channel_donut" else "cards",
        title="채널 비중" if slot_key == "channel_donut" else "TOP10 키워드",
        items=items, approved=True, approved_at=NOW,
    )


def _report(project_id, context: NarrativeContext) -> ReportSchema:
    return ReportSchema(
        report_id=uuid4(), project_id=project_id, run=_run(),
        context=context, visualizations=[],
    )


def test_build_cover_toc_summary_round_trips_real_content() -> None:
    project_id = uuid4()
    context = _narrative_context()
    narrative_output = _narrative_output(project_id)
    visualization_outputs = {
        "channel_donut": _visualization_output(project_id, "channel_donut", [
            VisualizationItemSchema(
                label="NEWS", value=30, analytics_path="metrics.channel_mentions.NEWS", order=0,
            ),
            VisualizationItemSchema(
                label="VIDEO", value=12, analytics_path="metrics.channel_mentions.VIDEO", order=1,
            ),
        ]),
        "top10_keywords": _visualization_output(project_id, "top10_keywords", [
            VisualizationItemSchema(
                label="내포신도시", value=20,
                analytics_path="metrics.keyword_frequencies.내포신도시", order=0,
            ),
            VisualizationItemSchema(
                label="이전", value=15,
                analytics_path="metrics.keyword_frequencies.이전", order=1,
            ),
        ]),
    }
    report = _report(project_id, context)

    raw = build_cover_toc_summary(
        report, narrative_output, visualization_outputs,
        title="2026년 9월 충남 온라인여론 키워드조사 분석 보고서",
    )
    assert isinstance(raw, bytes)
    assert len(raw) > 0

    text = TextExtractor(BytesIO(raw)).extract_text()
    assert "2026년 9월 충남 온라인여론 키워드조사 분석 보고서" in text
    assert narrative_output.sentences[0].text in text
    # the donut chart's channel labels are pixels inside an embedded PNG --
    # not text-extractable -- so check the picture was actually embedded
    # instead of expecting "NEWS"/"VIDEO" as text.
    with ZipFile(BytesIO(raw)) as archive:
        assert any(name.startswith("BinData/") for name in archive.namelist())
    assert "내포신도시" in text and "이전" in text

    assert validate_document(raw).ok
    assert validate_editor_open_safety(raw).ok


def test_build_cover_toc_summary_requires_both_visualization_slots() -> None:
    project_id = uuid4()
    context = _narrative_context()
    narrative_output = _narrative_output(project_id)
    report = _report(project_id, context)

    with pytest.raises(HwpxPrototypeError):
        build_cover_toc_summary(report, narrative_output, {}, title="제목")


def test_build_cover_toc_summary_handles_empty_items_without_crashing() -> None:
    project_id = uuid4()
    context = _narrative_context()
    narrative_output = _narrative_output(project_id)
    visualization_outputs = {
        "channel_donut": _visualization_output(project_id, "channel_donut", []),
        "top10_keywords": _visualization_output(project_id, "top10_keywords", []),
    }
    report = _report(project_id, context)

    raw = build_cover_toc_summary(
        report, narrative_output, visualization_outputs, title="제목",
    )
    text = TextExtractor(BytesIO(raw)).extract_text()
    assert "표시할 채널 항목이 없다." in text
    assert "표시할 키워드 항목이 없다." in text
