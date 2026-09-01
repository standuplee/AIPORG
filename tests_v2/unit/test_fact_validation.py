from datetime import date
from uuid import uuid4

import pytest

from app.facts.validation import FactValidationService
from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.fact import FactSchema


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
