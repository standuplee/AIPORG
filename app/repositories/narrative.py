"""Narrative repository protocol."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

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

    def list_outputs(self, project_id: ProjectId) -> list[NarrativeOutputRead]:
        """Return every saved narrative output version, newest first.

        Supports version comparison and restoring/viewing an older draft --
        ``save_output`` never overwrites a prior version, so the full history
        is always available here.
        """

    def approve_output(
        self,
        project_id: ProjectId,
        run_id: UUID,
        approved: bool,
        approved_at: datetime | None,
    ) -> NarrativeOutputRead:
        """Set the approval flag on an existing output version in place.

        This does not create a new version -- approval is metadata about a
        version, not a content change (see docs/aiporg2/visualization-design.md).
        """
