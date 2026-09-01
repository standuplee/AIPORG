"""Fact contracts for AIPORG 2.0."""

from datetime import date
from typing import Annotated, TypeAlias
from uuid import UUID

from app.core.enums import ConfidenceGrade, FactStatus
from app.schemas.common import SchemaBase
from app.schemas.document import DocumentId
from app.schemas.evidence import EvidenceId
from pydantic import Field, FiniteFloat


FactId: TypeAlias = UUID


class FactSchema(SchemaBase):
    fact_id: FactId
    claim: str
    event_date: date
    entities: list[str]
    evidence_document_ids: Annotated[list[DocumentId], Field(min_length=1)]
    source_count: Annotated[int, Field(ge=0)]
    confidence: ConfidenceGrade
    status: FactStatus


class NumericFactSchema(SchemaBase):
    metric: str
    value: FiniteFloat
    unit: str
    source: str
    evidence_ids: Annotated[list[EvidenceId], Field(min_length=1)]
    confidence: ConfidenceGrade


FactRead = FactSchema
