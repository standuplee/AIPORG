"""Document repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.document import CleanDocument, DocumentRead, RawDocument


class DocumentRepository(SessionScopedRepository, Protocol):
    """Persist collected documents and locate cleaned canonical documents."""

    def upsert_raw(self, project_id: ProjectId, document: RawDocument) -> DocumentRead:
        """Insert or update a raw document within a project scope."""

    def upsert_clean(
        self, project_id: ProjectId, document: CleanDocument
    ) -> DocumentRead:
        """Insert or update cleaner output within a project scope."""

    def get_by_canonical_url(
        self, project_id: ProjectId, canonical_url: str
    ) -> DocumentRead | None:
        """Return a persisted document by its project-scoped canonical URL."""
