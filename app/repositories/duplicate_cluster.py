"""Duplicate-cluster repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.document import (
    DuplicateClusterId,
    DuplicateClusterRead,
    DuplicateClusterSchema,
)


class DuplicateClusterRepository(SessionScopedRepository, Protocol):
    """Persist and retrieve project-scoped duplicate clusters."""

    def create(
        self, project_id: ProjectId, cluster: DuplicateClusterSchema
    ) -> DuplicateClusterRead:
        """Persist a duplicate cluster and its document membership."""

    def get(
        self, project_id: ProjectId, cluster_id: DuplicateClusterId
    ) -> DuplicateClusterRead | None:
        """Return a duplicate cluster when it exists for the project."""
