from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import SentimentLabel, StanceLabel
from app.schemas.issue import IssueCandidateSchema, IssueSchema


def issue_candidate_payload() -> dict[str, object]:
    return {
        "issue_id": str(uuid4()),
        "label": "Economic concerns",
        "fact_ids": [str(uuid4())],
        "document_count": 12,
        "source_count": 6,
        "channel_count": 3,
    }


def issue_detail_payload() -> dict[str, object]:
    return {
        "label": "Household cost pressure",
        "policy": "Strengthen cost-of-living support.",
        "summary": "Residents cited higher household expenses.",
        "sentiment": "negative",
        "stance": "not_applicable",
    }


def test_issue_candidate_schema_uses_exact_prd_anchor_fields() -> None:
    assert set(IssueCandidateSchema.model_fields) == {
        "issue_id",
        "label",
        "fact_ids",
        "document_count",
        "source_count",
        "channel_count",
    }

    candidate = IssueCandidateSchema.model_validate(issue_candidate_payload())

    assert candidate.document_count == 12
    assert candidate.source_count == 6
    assert candidate.channel_count == 3


def test_issue_schema_uses_strict_issue_detail_subissues() -> None:
    assert set(IssueSchema.model_fields) == {
        "issue_id",
        "label",
        "fact_ids",
        "document_count",
        "source_count",
        "channel_count",
        "subissues",
    }

    issue = IssueSchema.model_validate(
        {
            **issue_candidate_payload(),
            "subissues": [issue_detail_payload() for _ in range(5)],
        }
    )

    assert len(issue.subissues) == 5
    assert issue.subissues[0].sentiment is SentimentLabel.NEGATIVE
    assert issue.subissues[0].stance is StanceLabel.NOT_APPLICABLE
    assert set(type(issue.subissues[0]).model_fields) == {
        "label",
        "policy",
        "summary",
        "sentiment",
        "stance",
    }


@pytest.mark.parametrize("field", ["document_count", "source_count", "channel_count"])
def test_issue_candidate_schema_rejects_negative_counts(field: str) -> None:
    with pytest.raises(ValidationError):
        IssueCandidateSchema.model_validate({**issue_candidate_payload(), field: -1})


def test_issue_candidate_schema_requires_at_least_one_fact_link() -> None:
    with pytest.raises(ValidationError):
        IssueCandidateSchema.model_validate({**issue_candidate_payload(), "fact_ids": []})


@pytest.mark.parametrize(
    "schema,payload",
    [
        (IssueCandidateSchema, issue_candidate_payload()),
        (
            IssueSchema,
            {
                **issue_candidate_payload(),
                "subissues": [],
            },
        ),
    ],
)
def test_issue_contract_schemas_reject_extra_fields(
    schema: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        schema.model_validate({**payload, "unexpected": "value"})  # type: ignore[attr-defined]
