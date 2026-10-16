from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.facts.validation import FactValidationService
from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.fact import FactSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import NumericFactSchema


def fact(*document_ids) -> FactSchema:
    return FactSchema(
        fact_id=uuid4(),
        claim="충남 정책이 발표되었다.",
        event_date=date(2026, 7, 20),
        entities=["충남"],
        evidence_document_ids=list(document_ids),
        source_count=len(document_ids),
        confidence=ConfidenceGrade.C,
        status=FactStatus.UNCERTAIN,
    )


def test_fact_is_verified_by_official_evidence_or_two_sources() -> None:
    official = FactValidationService().validate(fact(uuid4()), official_source=True)
    independent = FactValidationService().validate(fact(uuid4(), uuid4()))

    assert official.status is FactStatus.VERIFIED
    assert independent.status is FactStatus.VERIFIED
    assert official.confidence is ConfidenceGrade.A
    assert independent.confidence is ConfidenceGrade.C


def test_single_non_official_source_is_supported_only() -> None:
    result = FactValidationService().validate(fact(uuid4()))

    assert result.status is FactStatus.SUPPORTED
    assert result.confidence is ConfidenceGrade.C


def test_fact_without_evidence_is_rejected() -> None:
    invalid = FactSchema.model_construct(
        fact_id=uuid4(),
        claim="주장",
        event_date=date(2026, 7, 20),
        entities=["충남"],
        evidence_document_ids=[],
        source_count=0,
        confidence=ConfidenceGrade.D,
        status=FactStatus.UNCERTAIN,
    )
    with pytest.raises(ValueError, match="evidence"):
        FactValidationService().validate(invalid, official_source=False)


def test_numeric_fact_requires_value_in_linked_evidence() -> None:
    evidence_id = uuid4()
    evidence = EvidenceSchema(
        evidence_id=evidence_id,
        project_id=uuid4(),
        document_id=uuid4(),
        excerpt="사업비는 총 1,250.5억 원이다.",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    numeric = NumericFactSchema(
        metric="사업비",
        value=1250.5,
        unit="억 원",
        source="공식자료",
        evidence_ids=[evidence_id],
        confidence=ConfidenceGrade.A,
    )

    assert FactValidationService().validate_numeric(
        numeric, evidence_by_id={evidence_id: evidence}
    ) == numeric
    with pytest.raises(ValueError, match="not present"):
        FactValidationService().validate_numeric(
            numeric.model_copy(update={"value": 1300}),
            evidence_by_id={evidence_id: evidence},
        )
