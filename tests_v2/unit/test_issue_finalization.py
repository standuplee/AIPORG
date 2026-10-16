from datetime import date
from uuid import uuid4

import pytest

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel
from app.issues.finalization import IssueFinalizationService
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueCandidateSchema


def test_issue_details_repeat_validated_claim_without_new_wording() -> None:
    fact = FactSchema(
        fact_id=uuid4(), claim="충청남도가 정책을 발표했다.",
        event_date=date(2026, 9, 1), entities=["충청남도"],
        evidence_document_ids=[uuid4()], source_count=1,
        confidence=ConfidenceGrade.B, status=FactStatus.SUPPORTED,
    )
    candidate = IssueCandidateSchema(
        issue_id=uuid4(), label="충청남도", fact_ids=[fact.fact_id],
        document_count=1, source_count=1, channel_count=1,
    )

    issue = IssueFinalizationService().finalize(
        [candidate], facts_by_id={fact.fact_id: fact}
    )[0]

    assert issue.subissues[0].policy == fact.claim
    assert issue.subissues[0].summary == fact.claim
    assert issue.subissues[0].sentiment is SentimentLabel.NEUTRAL


def test_issue_finalization_rejects_unknown_fact() -> None:
    candidate = IssueCandidateSchema(
        issue_id=uuid4(), label="충청남도", fact_ids=[uuid4()],
        document_count=1, source_count=1, channel_count=1,
    )
    with pytest.raises(ValueError, match="unknown fact"):
        IssueFinalizationService().finalize([candidate], facts_by_id={})
