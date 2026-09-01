"""Report repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.common import ProjectId
from app.schemas.report import ReportRead, ReportSchema


class ReportRepository(SessionScopedRepository, Protocol):
    """Persist assembled reports."""

    def create(self, report: ReportSchema) -> ReportRead:
        """Persist an assembled report."""

    def get_latest(self, project_id: ProjectId) -> ReportRead | None:
        """Return the latest report for a project."""
