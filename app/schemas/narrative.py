"""Narrative input and output contracts for AIPORG 2.0.

The output contracts below (``NarrativeSentenceSchema``, ``NarrativeGenerationSchema``,
``NarrativeOutputSchema``) implement the design decided in
``docs/aiporg2/narrative-design.md`` (2026-09-23 recommendation, adopted
2026-10-16): a sentence-level, source-mapped narrative output that an LLM
draft or the deterministic template renderer can both produce. They are
additive -- ``NarrativeContext`` and its field names are unchanged, and
``ReportSchema.context`` (app/schemas/report.py) still takes a
``NarrativeContext``, not this output shape.

``NarrativeOutputSchema.approved``/``approved_at`` (added 2026-10-18, see
``docs/aiporg2/visualization-design.md``) are additive fields for the same
reason -- they default to unapproved so every existing caller/payload stays
valid.
"""

from datetime import datetime

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.core.enums import SentimentLabel
from app.schemas.common import ProjectId, RunId, SchemaBase, VersionedRunSchema
from app.schemas.document import DocumentId
from app.schemas.evidence import EvidenceId
from app.schemas.fact import FactId, FactSchema
from app.schemas.issue import IssueSchema


class NarrativeContext(SchemaBase):
    issue: IssueSchema
    facts: list[FactSchema]
    sentiment: SentimentLabel
    keywords: list[str]
    positive_reasons: list[str]
    negative_reasons: list[str]


NarrativeRead = NarrativeContext


class NarrativeSentenceSchema(SchemaBase):
    """One narrative sentence and the evidence it is grounded in.

    A sentence with no reference at all cannot be checked against source
    data, so at least one of these four must be populated -- matching the
    requirement that generated or user-edited text must trace back to a
    fact, document, evidence excerpt, or an AnalyticsSnapshot path.
    """

    text: str
    fact_ids: list[FactId] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    document_ids: list[DocumentId] = Field(default_factory=list)
    analytics_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_grounded(self) -> "NarrativeSentenceSchema":
        if not self.text.strip():
            raise ValueError("sentence text cannot be empty")
        if not (
            self.fact_ids or self.evidence_ids or self.document_ids or self.analytics_paths
        ):
            raise ValueError(
                "sentence must reference at least one fact, evidence, document, "
                "or analytics path"
            )
        return self


class NarrativeGenerationSchema(SchemaBase):
    """Provenance of one LLM call. Absent on template-rendered output."""

    provider: str
    model: str
    prompt_version: str
    input_snapshot_sha256: str
    generated_at: datetime
    usage: dict[str, int] = Field(default_factory=dict)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


class NarrativeOutputSchema(SchemaBase):
    """A sentence-level narrative version: an LLM draft, a user edit, or a
    template render. Every edit is a new version (a new ``run``); none of
    them overwrite a prior one, so approval can be rolled back to any
    version regardless of what produced it."""

    project_id: ProjectId
    run: VersionedRunSchema
    analytics_run_id: RunId | None = None
    generation: NarrativeGenerationSchema | None = None
    sentences: list[NarrativeSentenceSchema]
    approved: bool = False
    approved_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_approval_timestamp(self) -> "NarrativeOutputSchema":
        if self.approved and self.approved_at is None:
            raise ValueError("approved output must carry approved_at")
        if not self.approved and self.approved_at is not None:
            raise ValueError("unapproved output must not carry approved_at")
        return self


NarrativeOutputRead = NarrativeOutputSchema
