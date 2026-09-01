"""Project repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.project import ProjectCreate, ProjectRead


class ProjectRepository(SessionScopedRepository, Protocol):
    """Persist and retrieve projects."""

    def create(self, project: ProjectCreate) -> ProjectRead:
        """Persist a new project."""

    def get(self, project_id: ProjectId) -> ProjectRead | None:
        """Return a project when it exists."""
