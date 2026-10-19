from datetime import date
from uuid import uuid4

import pytest

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel, StanceLabel
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
    assert issue.subissues[0].stance is StanceLabel.NOT_APPLICABLE


def test_issue_finalization_classifies_real_sentiment_and_stance_per_fact() -> None:
    # previously every subissue was hardcoded NEUTRAL/NOT_APPLICABLE --
    # finalize() must now classify each fact's own claim text (see
    # app/sentiment/service.py), not fabricate a label independent of it.
    positive_fact = FactSchema(
        fact_id=uuid4(), claim="일자리 확대와 투자 유치 성과를 냈다.",
        event_date=date(2026, 9, 1), entities=["충청남도"],
        evidence_document_ids=[uuid4()], source_count=1,
        confidence=ConfidenceGrade.B, status=FactStatus.SUPPORTED,
    )
    opposed_fact = FactSchema(
        fact_id=uuid4(), claim="주민들이 행정통합에 반대 의사를 밝혔다.",
        event_date=date(2026, 9, 2), entities=["충청남도"],
        evidence_document_ids=[uuid4()], source_count=1,
        confidence=ConfidenceGrade.B, status=FactStatus.SUPPORTED,
    )
    candidate = IssueCandidateSchema(
        issue_id=uuid4(), label="충청남도",
        fact_ids=[positive_fact.fact_id, opposed_fact.fact_id],
        document_count=2, source_count=2, channel_count=1,
    )

    issue = IssueFinalizationService().finalize(
        [candidate],
        facts_by_id={positive_fact.fact_id: positive_fact, opposed_fact.fact_id: opposed_fact},
    )[0]

    by_policy = {detail.policy: detail for detail in issue.subissues}
    assert by_policy[positive_fact.claim].sentiment is SentimentLabel.POSITIVE
    assert by_policy[positive_fact.claim].stance is StanceLabel.NOT_APPLICABLE
    assert by_policy[opposed_fact.claim].stance is StanceLabel.OPPOSE


def test_issue_finalization_rejects_unknown_fact() -> None:
    candidate = IssueCandidateSchema(
        issue_id=uuid4(), label="충청남도", fact_ids=[uuid4()],
        document_count=1, source_count=1, channel_count=1,
    )
    with pytest.raises(ValueError, match="unknown fact"):
        IssueFinalizationService().finalize([candidate], facts_by_id={})
