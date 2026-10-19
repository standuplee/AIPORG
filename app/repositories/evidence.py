"""Evidence repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.evidence import EvidenceId, EvidenceRead, EvidenceSchema


class EvidenceRepository(SessionScopedRepository, Protocol):
    """Persist and retrieve evidence records."""

    def create(self, evidence: EvidenceSchema) -> EvidenceRead:
        """Persist evidence and its linked document reference."""

    def get(self, project_id: ProjectId, evidence_id: EvidenceId) -> EvidenceRead | None:
        """Return evidence when it exists for the project."""

    def list_by_project(self, project_id: ProjectId) -> list[EvidenceRead]:
        """Return project evidence in deterministic creation order."""

    def count_by_project(self, project_id: ProjectId) -> int:
        """Return the evidence count without loading any evidence rows."""
