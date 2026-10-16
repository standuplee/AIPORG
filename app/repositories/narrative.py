"""Narrative repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.narrative import (
    NarrativeContext,
    NarrativeOutputRead,
    NarrativeOutputSchema,
    NarrativeRead,
)


class NarrativeRepository(SessionScopedRepository, Protocol):
    """Persist narrative contexts without generating new facts."""

    def save(self, project_id: ProjectId, context: NarrativeContext) -> NarrativeRead:
        """Persist an already-derived narrative context."""

    def get_latest(self, project_id: ProjectId) -> NarrativeRead | None:
        """Return the latest narrative *input context* for a project.

        Never returns a row saved through ``save_output`` -- those are a
        different shape (``NarrativeOutputSchema``) stored in the same table.
        """

    def save_output(
        self, project_id: ProjectId, output: NarrativeOutputSchema
    ) -> NarrativeOutputRead:
        """Persist one narrative output version (LLM draft, edit, or template
        render). Each call adds a new version; none are overwritten."""

    def get_latest_output(self, project_id: ProjectId) -> NarrativeOutputRead | None:
        """Return the most recently saved narrative output version, if any."""
