from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.enums import ChannelType, FactStatus
from app.facts.extraction import FactExtractionService
from app.schemas.document import CleanDocument
from app.schemas.evidence import EvidenceSchema


def _document(document_id, source):
    return CleanDocument(
        document_id=document_id,
        title="정책 발표",
        body="충청남도가 정책을 발표했다. 후속 문장이다.",
        canonical_url=f"https://example.com/{document_id}",
        cleaned_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        source=source,
        channel=ChannelType.NEWS,
        platform="fixture",
        published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def test_extraction_uses_verbatim_sentence_and_actual_unique_sources() -> None:
    project_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    documents = {
        first_id: _document(first_id, "source-a"),
        second_id: _document(second_id, "source-b"),
    }
    evidence = [
        EvidenceSchema(
            evidence_id=uuid4(), project_id=project_id, document_id=document_id,
            excerpt="충청남도가 정책을 발표했다. 후속 문장이다.",
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        for document_id in (first_id, second_id)
    ]

    facts = FactExtractionService().extract(
        project_id,
        evidence,
        documents=documents,
        entity_terms=["충청남도", "없는 인물"],
    )

    assert len(facts) == 1
    assert facts[0].claim == "충청남도가 정책을 발표했다."
    assert facts[0].entities == ["충청남도"]
    assert facts[0].source_count == 2
    assert set(facts[0].evidence_document_ids) == {first_id, second_id}
    assert facts[0].status is FactStatus.UNCERTAIN


def test_extraction_rejects_missing_source_document() -> None:
    project_id = uuid4()
    evidence = EvidenceSchema(
        evidence_id=uuid4(), project_id=project_id, document_id=uuid4(),
        excerpt="충청남도 근거 문장.",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ValueError, match="source document"):
        FactExtractionService().extract(
            project_id, [evidence], documents={}, entity_terms=["충청남도"]
        )
