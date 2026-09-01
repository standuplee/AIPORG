"""Create evidence excerpts without inventing facts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.schemas.common import ProjectId
from app.schemas.document import CleanDocument
from app.schemas.evidence import EvidenceSchema


class EvidenceService:
    """Build deterministic, document-backed evidence records."""

    def __init__(
        self,
        *,
        max_excerpt_length: int = 500,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if max_excerpt_length <= 0:
            raise ValueError("max_excerpt_length must be positive")
        self.max_excerpt_length = max_excerpt_length
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def build(self, project_id: ProjectId, document: CleanDocument) -> EvidenceSchema:
        excerpt = document.body.strip()[: self.max_excerpt_length]
        if not excerpt:
            raise ValueError("evidence excerpt cannot be empty")
        evidence_id = uuid5(
            NAMESPACE_URL,
            f"{project_id}:{document.document_id}:{excerpt}",
        )
        return EvidenceSchema(
            evidence_id=evidence_id,
            project_id=project_id,
            document_id=document.document_id,
            excerpt=excerpt,
            created_at=self.now_fn(),
        )
