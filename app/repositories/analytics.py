"""Analytics repository protocol."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.analytics import AnalyticsSnapshotRead, AnalyticsSnapshotSchema
from app.schemas.common import ProjectId


class AnalyticsRepository(SessionScopedRepository, Protocol):
    """Persist versioned analytics snapshots."""

    def create(self, snapshot: AnalyticsSnapshotSchema) -> AnalyticsSnapshotRead:
        """Persist an analytics snapshot."""

    def get_latest(self, project_id: ProjectId) -> AnalyticsSnapshotRead | None:
        """Return the latest analytics snapshot for a project."""

    def get_latest_summary(self, project_id: ProjectId) -> dict[str, object] | None:
        """Return a bounded, UI-safe projection of the latest snapshot's
        metrics (no full keyword/provenance collections) -- see
        SqlAlchemyAnalyticsRepository.get_latest_summary for why."""
