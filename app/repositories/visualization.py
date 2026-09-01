"""Visualization repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.visualization import VisualizationAssetRead, VisualizationAssetSchema


class VisualizationRepository(SessionScopedRepository, Protocol):
    """Persist generated visualization assets."""

    def create(self, asset: VisualizationAssetSchema) -> VisualizationAssetRead:
        """Persist a visualization asset."""

    def list_by_project(self, project_id: ProjectId) -> list[VisualizationAssetRead]:
        """Return visualization assets for a project."""
