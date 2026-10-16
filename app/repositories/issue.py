"""Issue repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.issue import IssueId, IssueRead, IssueSchema


class IssueRepository(SessionScopedRepository, Protocol):
    """Persist issue aggregates and their fact links."""

    def list_by_project(self, project_id: ProjectId) -> list[IssueRead]:
        """Return project issues in deterministic ID order."""

    def save_batch(self, project_id: ProjectId, issues: list[IssueSchema]) -> list[IssueRead]:
        """Persist issue aggregates for a project."""

    def get(self, project_id: ProjectId, issue_id: IssueId) -> IssueRead | None:
        """Return an issue when it exists for the project."""
