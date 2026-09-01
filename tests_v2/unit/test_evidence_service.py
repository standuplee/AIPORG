from datetime import datetime, timezone
from uuid import uuid4

from app.evidence.service import EvidenceService
from app.schemas.document import CleanDocument


def test_evidence_builder_returns_traceable_deterministic_excerpt() -> None:
    project_id = uuid4()
    document_id = uuid4()
    document = CleanDocument(
        document_id=document_id,
        title="충남 AI",
        body="충남의 정책 추진 내용과 현장 반응을 확인할 수 있는 본문이다.",
        canonical_url="https://example.test/1",
        cleaned_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    service = EvidenceService(now_fn=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc))

    first = service.build(project_id, document)
    second = service.build(project_id, document)

    assert first == second
    assert first.project_id == project_id
    assert first.document_id == document_id
    assert first.excerpt == document.body
    assert first.created_at.tzinfo is not None


def test_evidence_builder_limits_excerpt_and_rejects_empty_body() -> None:
    project_id = uuid4()
    document = CleanDocument(
        document_id=uuid4(),
        title="제목",
        body="가" * 20,
        canonical_url="https://example.test/1",
        cleaned_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    service = EvidenceService(max_excerpt_length=10)

    assert len(service.build(project_id, document).excerpt) == 10

    empty = document.model_copy(update={"body": ""})
    try:
        service.build(project_id, empty)
    except ValueError as exc:
        assert "excerpt" in str(exc)
    else:
        raise AssertionError("empty evidence body must be rejected")
