"""Document repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId, RunId
from app.schemas.document import CleanDocument, DocumentId, DocumentRead, RawDocument


class DocumentRepository(SessionScopedRepository, Protocol):
    """Persist collected documents and locate cleaned canonical documents."""

    def list_canonical(self, project_id: ProjectId) -> list[CleanDocument]:
        """Return cleaned project documents excluding persisted duplicate members."""

    def count_canonical(self, project_id: ProjectId) -> int:
        """Return the canonical document count without loading any rows."""

    def list_canonical_page(
        self, project_id: ProjectId, *, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, object]]:
        """Return a bounded, display-only page of canonical documents (no
        body/metadata, every string field length-capped) -- see
        SqlAlchemyDocumentRepository.list_canonical_page for why."""

    def upsert_raw(
        self,
        project_id: ProjectId,
        document: RawDocument,
        *,
        collection_run_id: RunId | None = None,
    ) -> DocumentRead:
        """Insert or update a raw document within a project scope."""

    def upsert_clean(
        self, project_id: ProjectId, document: CleanDocument
    ) -> DocumentRead:
        """Insert or update cleaner output within a project scope."""

    def get_by_canonical_url(
        self, project_id: ProjectId, canonical_url: str
    ) -> DocumentRead | None:
        """Return a persisted document by its project-scoped canonical URL."""

    def list_raw_by_collection_run(
        self,
        project_id: ProjectId,
        collection_run_id: RunId,
    ) -> list[RawDocument]:
        """Return raw documents persisted by one collection run."""

    def get(self, project_id: ProjectId, document_id: DocumentId) -> DocumentRead | None:
        """Return a project-scoped document by ID."""
