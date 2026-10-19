from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema, NumericFactSchema
from app.schemas.issue import IssueSchema
from app.schemas.narrative import NarrativeContext
from app.schemas.report import ReportSchema
from app.schemas.visualization import VisualizationAssetSchema


def fact_payload() -> dict[str, object]:
    return {
        "fact_id": str(uuid4()),
        "claim": "Public concern increased during the analysis period.",
        "event_date": "2026-08-14",
        "entities": ["residents", "local economy"],
        "evidence_document_ids": [str(uuid4()), str(uuid4())],
        "source_count": 2,
        "confidence": "A",
        "status": "SUPPORTED",
    }


def evidence_payload() -> dict[str, object]:
    return {
        "evidence_id": str(uuid4()),
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "excerpt": "Household expenses rose during the analysis period.",
        "created_at": "2026-08-14T09:00:00Z",
    }


def numeric_fact_payload() -> dict[str, object]:
    return {
        "metric": "unemployment_rate",
        "value": 42.5,
        "unit": "percent",
        "source": "National Statistics Office",
        "evidence_ids": [str(uuid4())],
        "confidence": "B",
    }


def run_payload() -> dict[str, object]:
    return {
        "run_id": str(uuid4()),
        "input_version": "narrative-v1",
        "output_version": "report-v1",
        "created_at": "2026-08-14T09:00:00Z",
    }


def analytics_snapshot_payload() -> dict[str, object]:
    return {
        "project_id": str(uuid4()),
        "run": run_payload(),
        "metrics": {
            "document_count": 12,
            "sentiment": {"negative": 0.5, "positive": 0.3},
            "channels": ["news", "blog"],
            "has_comparison": True,
            "note": None,
        },
    }


def visualization_payload(project_id: str | None = None) -> dict[str, object]:
    return {
        "visualization_id": str(uuid4()),
        "project_id": project_id or str(uuid4()),
        "kind": "trend",
        "title": "Issue trend",
        "created_at": "2026-08-14T09:00:00Z",
    }


def issue_detail_payload() -> dict[str, object]:
    return {
        "label": "Household cost pressure",
        "policy": "Strengthen cost-of-living support.",
        "summary": "Residents cited higher household expenses.",
        "sentiment": "negative",
        "stance": "not_applicable",
    }


def issue_payload() -> dict[str, object]:
    return {
        "issue_id": str(uuid4()),
        "label": "Economic concerns",
        "fact_ids": [str(uuid4())],
        "document_count": 12,
        "source_count": 6,
        "channel_count": 3,
        "subissues": [issue_detail_payload()],
    }


def narrative_context_payload() -> dict[str, object]:
    return {
        "issue": issue_payload(),
        "facts": [fact_payload()],
        "sentiment": "negative",
        "keywords": ["economy", "cost of living"],
        "positive_reasons": ["Support measures are visible."],
        "negative_reasons": ["Household expenses remain high."],
    }


def test_fact_schema_uses_exact_prd_fields_and_uppercase_status_literals() -> None:
    assert set(FactSchema.model_fields) == {
        "fact_id",
        "claim",
        "event_date",
        "entities",
        "evidence_document_ids",
        "source_count",
        "confidence",
        "status",
    }
    assert {status.value for status in FactStatus} == {
        "VERIFIED",
        "SUPPORTED",
        "UNCERTAIN",
        "REJECTED",
    }

    fact = FactSchema.model_validate(fact_payload())

    assert fact.event_date == date(2026, 8, 14)
    assert fact.confidence is ConfidenceGrade.A
    assert fact.status is FactStatus.SUPPORTED


@pytest.mark.parametrize("status", FactStatus)
def test_fact_schema_accepts_each_prd_status(status: FactStatus) -> None:
    fact = FactSchema.model_validate({**fact_payload(), "status": status.value})

    assert fact.status is status


def test_fact_schema_rejects_lowercase_status_literal() -> None:
    with pytest.raises(ValidationError):
        FactSchema.model_validate({**fact_payload(), "status": "supported"})


def test_numeric_fact_schema_is_an_independent_prd_contract() -> None:
    assert set(NumericFactSchema.model_fields) == {
        "metric",
        "value",
        "unit",
        "source",
        "evidence_ids",
        "confidence",
    }

    numeric_fact = NumericFactSchema.model_validate(numeric_fact_payload())

    assert numeric_fact.confidence is ConfidenceGrade.B
    assert len(numeric_fact.evidence_ids) == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_numeric_fact_schema_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        NumericFactSchema.model_validate({**numeric_fact_payload(), "value": value})


@pytest.mark.parametrize(
    "schema,payload,field,value",
    [
        (FactSchema, fact_payload(), "source_count", -1),
        (FactSchema, fact_payload(), "evidence_document_ids", []),
        (NumericFactSchema, numeric_fact_payload(), "evidence_ids", []),
    ],
)
def test_fact_contract_schemas_reject_invalid_persistence_invariants(
    schema: type[object], payload: dict[str, object], field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate({**payload, field: value})  # type: ignore[attr-defined]


def test_evidence_schema_uses_exact_prd_fields_and_serializes_to_json() -> None:
    payload = evidence_payload()

    assert set(EvidenceSchema.model_fields) == {
        "evidence_id",
        "project_id",
        "document_id",
        "excerpt",
        "created_at",
    }
    assert EvidenceSchema.model_validate(payload).model_dump(mode="json") == payload


def test_evidence_schema_rejects_naive_created_at_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceSchema.model_validate(
            {**evidence_payload(), "created_at": "2026-08-14T09:00:00"}
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceSchema.model_validate({**evidence_payload(), "unexpected": "value"})


def test_analytics_snapshot_schema_serializes_recursive_json_metrics() -> None:
    payload = analytics_snapshot_payload()

    assert set(AnalyticsSnapshotSchema.model_fields) == {
        "project_id",
        "run",
        "metrics",
    }
    assert AnalyticsSnapshotSchema.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "metrics",
    [
        {"observed_at": datetime(2026, 8, 14, 9, tzinfo=timezone.utc)},
        {"channels": {"news", "blog"}},
        {"share": float("inf")},
    ],
)
def test_analytics_snapshot_schema_rejects_non_json_metric_values(
    metrics: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="JSON-compatible"):
        AnalyticsSnapshotSchema.model_validate(
            {**analytics_snapshot_payload(), "metrics": metrics}
        )


def test_analytics_snapshot_schema_rejects_naive_run_timestamp_and_extra_fields() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        AnalyticsSnapshotSchema.model_validate(
            {
                **analytics_snapshot_payload(),
                "run": {**run_payload(), "created_at": "2026-08-14T09:00:00"},
            }
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AnalyticsSnapshotSchema.model_validate(
            {**analytics_snapshot_payload(), "unexpected": "value"}
        )


def test_visualization_asset_schema_uses_exact_fields_and_serializes_to_json() -> None:
    payload = visualization_payload()

    assert set(VisualizationAssetSchema.model_fields) == {
        "visualization_id",
        "project_id",
        "kind",
        "title",
        "created_at",
    }
    assert VisualizationAssetSchema.model_validate(payload).model_dump(mode="json") == payload


def test_visualization_asset_schema_rejects_naive_created_at_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        VisualizationAssetSchema.model_validate(
            {**visualization_payload(), "created_at": "2026-08-14T09:00:00"}
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualizationAssetSchema.model_validate(
            {**visualization_payload(), "unexpected": "value"}
        )


@pytest.mark.parametrize(
    "schema,payload",
    [
        (FactSchema, fact_payload()),
        (
            NumericFactSchema,
            numeric_fact_payload(),
        ),
    ],
)
def test_fact_contract_schemas_reject_extra_fields(
    schema: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        schema.model_validate({**payload, "unexpected": "value"})  # type: ignore[attr-defined]


def test_narrative_context_and_report_are_strict_phase_zero_contracts() -> None:
    context = NarrativeContext.model_validate(narrative_context_payload())
    project_id = str(uuid4())
    visual = VisualizationAssetSchema.model_validate(visualization_payload(project_id))
    report = ReportSchema.model_validate(
        {
            "report_id": str(uuid4()),
            "project_id": project_id,
            "run": run_payload(),
            "context": context.model_dump(mode="json"),
            "visualizations": [visual.model_dump(mode="json")],
        }
    )

    assert set(NarrativeContext.model_fields) == {
        "issue",
        "facts",
        "sentiment",
        "keywords",
        "positive_reasons",
        "negative_reasons",
    }
    assert context.sentiment is SentimentLabel.NEGATIVE
    assert report.context == context
    assert report.visualizations == [visual]


def test_report_schema_rejects_visualization_from_another_project() -> None:
    report_project_id = str(uuid4())

    with pytest.raises(ValidationError, match="visualization project_id"):
        ReportSchema.model_validate(
            {
                "report_id": str(uuid4()),
                "project_id": report_project_id,
                "run": run_payload(),
                "context": narrative_context_payload(),
                "visualizations": [visualization_payload()],
            }
        )


@pytest.mark.parametrize(
    "schema,payload",
    [
        (NarrativeContext, narrative_context_payload()),
        (
            ReportSchema,
            {
                "report_id": str(uuid4()),
                "project_id": str(uuid4()),
                "run": run_payload(),
                "context": narrative_context_payload(),
                "visualizations": [],
            },
        ),
    ],
)
def test_downstream_aggregate_contracts_reject_extra_fields(
    schema: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        schema.model_validate({**payload, "unexpected": "value"})  # type: ignore[attr-defined]
