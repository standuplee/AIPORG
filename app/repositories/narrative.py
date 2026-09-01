"""Narrative repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.narrative import NarrativeContext, NarrativeRead


class NarrativeRepository(SessionScopedRepository, Protocol):
    """Persist narrative contexts without generating new facts."""

    def save(self, project_id: ProjectId, context: NarrativeContext) -> NarrativeRead:
        """Persist an already-derived narrative context."""

    def get_latest(self, project_id: ProjectId) -> NarrativeRead | None:
        """Return the latest narrative context for a project."""
