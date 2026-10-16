"""Project repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.core.enums import WorkflowState
from app.schemas.project import ProjectCreate, ProjectRead, ProjectWorkflowSnapshot


class ProjectRepository(SessionScopedRepository, Protocol):
    """Persist and retrieve projects."""

    def create(self, project: ProjectCreate) -> ProjectRead:
        """Persist a new project."""

    def get(self, project_id: ProjectId) -> ProjectRead | None:
        """Return a project when it exists."""

    def get_workflow(self, project_id: ProjectId) -> ProjectWorkflowSnapshot | None:
        """Return the current project workflow state."""

    def advance_workflow(
        self,
        project_id: ProjectId,
        target: WorkflowState,
    ) -> ProjectWorkflowSnapshot:
        """Advance the project by exactly one valid workflow state."""
