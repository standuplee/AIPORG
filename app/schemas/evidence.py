"""Evidence contracts for AIPORG 2.0."""

from typing import TypeAlias
from uuid import UUID

from pydantic import AwareDatetime

from app.schemas.common import ProjectId, SchemaBase
from app.schemas.document import DocumentId


EvidenceId: TypeAlias = UUID


class EvidenceSchema(SchemaBase):
    evidence_id: EvidenceId
    project_id: ProjectId
    document_id: DocumentId
    excerpt: str
    created_at: AwareDatetime


EvidenceRead = EvidenceSchema
