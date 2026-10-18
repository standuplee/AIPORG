"""Visualization repository protocol."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.visualization import (
    VisualizationAssetRead,
    VisualizationAssetSchema,
    VisualizationOutputRead,
    VisualizationOutputSchema,
)


class VisualizationRepository(SessionScopedRepository, Protocol):
    """Persist generated visualization assets."""

    def create(self, asset: VisualizationAssetSchema) -> VisualizationAssetRead:
        """Persist a visualization asset."""

    def list_by_project(self, project_id: ProjectId) -> list[VisualizationAssetRead]:
        """Return visualization assets for a project."""

    def save_output(
        self, project_id: ProjectId, output: VisualizationOutputSchema
    ) -> VisualizationOutputRead:
        """Persist one visualization output version for a slot (a render,
        an edit, or a regeneration). Each call adds a new version; none are
        overwritten."""

    def get_latest_output(
        self, project_id: ProjectId, slot_key: str
    ) -> VisualizationOutputRead | None:
        """Return the most recently saved output version for a slot, if any."""

    def list_outputs(
        self, project_id: ProjectId, slot_key: str
    ) -> list[VisualizationOutputRead]:
        """Return every saved output version for a slot, newest first."""

    def approve_output(
        self,
        project_id: ProjectId,
        run_id: UUID,
        approved: bool,
        approved_at: datetime | None,
    ) -> VisualizationOutputRead:
        """Set the approval flag on an existing output version in place."""
