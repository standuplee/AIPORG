from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.narrative import (
    NarrativeGenerationSchema,
    NarrativeOutputSchema,
    NarrativeSentenceSchema,
)
from app.schemas.common import VersionedRunSchema


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_sentence_requires_at_least_one_grounding_reference() -> None:
    with pytest.raises(ValidationError):
        NarrativeSentenceSchema(text="근거 없는 문장이다.")


def test_sentence_accepts_any_single_grounding_reference() -> None:
    NarrativeSentenceSchema(text="사실 근거.", fact_ids=[uuid4()])
    NarrativeSentenceSchema(text="증거 근거.", evidence_ids=[uuid4()])
    NarrativeSentenceSchema(text="문서 근거.", document_ids=[uuid4()])
    NarrativeSentenceSchema(text="집계 근거.", analytics_paths=["metrics.unique_documents"])


def test_sentence_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        NarrativeSentenceSchema(text="   ", fact_ids=[uuid4()])


def test_generation_requires_timezone_aware_generated_at() -> None:
    with pytest.raises(ValidationError):
        NarrativeGenerationSchema(
            provider="gemini",
            model="gemini-2.0-flash",
            prompt_version="narrative-v1",
            input_snapshot_sha256="a" * 64,
            generated_at=datetime(2026, 9, 1),
        )


def test_output_allows_a_null_generation_for_template_fallback() -> None:
    output = NarrativeOutputSchema(
        project_id=uuid4(),
        run=VersionedRunSchema(
            run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW
        ),
        sentences=[NarrativeSentenceSchema(text="템플릿 문장.", fact_ids=[uuid4()])],
    )
    assert output.generation is None


def test_output_carries_generation_provenance_when_llm_produced_it() -> None:
    output = NarrativeOutputSchema(
        project_id=uuid4(),
        run=VersionedRunSchema(
            run_id=uuid4(), input_version="v1", output_version="v2", created_at=NOW
        ),
        analytics_run_id=uuid4(),
        generation=NarrativeGenerationSchema(
            provider="gemini",
            model="gemini-2.0-flash",
            prompt_version="narrative-v1",
            input_snapshot_sha256="a" * 64,
            generated_at=NOW,
            usage={"input_tokens": 500, "output_tokens": 120},
        ),
        sentences=[NarrativeSentenceSchema(text="LLM 문장.", fact_ids=[uuid4()])],
    )
    assert output.generation.provider == "gemini"
    assert output.generation.usage["output_tokens"] == 120


def test_output_defaults_to_unapproved() -> None:
    output = NarrativeOutputSchema(
        project_id=uuid4(),
        run=VersionedRunSchema(
            run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW
        ),
        sentences=[NarrativeSentenceSchema(text="템플릿 문장.", fact_ids=[uuid4()])],
    )
    assert output.approved is False
    assert output.approved_at is None


def test_output_approved_requires_timestamp() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        NarrativeOutputSchema(
            project_id=uuid4(),
            run=VersionedRunSchema(
                run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW
            ),
            sentences=[NarrativeSentenceSchema(text="템플릿 문장.", fact_ids=[uuid4()])],
            approved=True,
        )


def test_output_unapproved_rejects_timestamp() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        NarrativeOutputSchema(
            project_id=uuid4(),
            run=VersionedRunSchema(
                run_id=uuid4(), input_version="v1", output_version="v1", created_at=NOW
            ),
            sentences=[NarrativeSentenceSchema(text="템플릿 문장.", fact_ids=[uuid4()])],
            approved=False,
            approved_at=NOW,
        )
