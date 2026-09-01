"""Query-set and collection-run repository protocols."""

from typing import Protocol

from app.repositories.base import SessionScopedRepository
from app.schemas.collection import CollectionRun, CollectionRunRead
from app.schemas.common import ProjectId, RunId
from app.schemas.query import QueryId, SearchQuery


class QuerySetRepository(SessionScopedRepository, Protocol):
    """Persist a project's generated search queries."""

    def create(self, project_id: ProjectId, queries: list[SearchQuery]) -> list[SearchQuery]:
        """Store the complete query set for a project."""

    def get(self, project_id: ProjectId) -> list[SearchQuery]:
        """Return the current query set for a project."""


class CollectionRunRepository(SessionScopedRepository, Protocol):
    """Persist collection-run lifecycle records."""

    def start(
        self, project_id: ProjectId, query_id: QueryId, run: CollectionRun
    ) -> CollectionRunRead:
        """Store a collection run at the start of its lifecycle."""

    def complete(
        self, project_id: ProjectId, run_id: RunId, run: CollectionRun
    ) -> CollectionRunRead:
        """Persist a terminal collection run with completion counters."""

    def get(self, project_id: ProjectId, run_id: RunId) -> CollectionRunRead | None:
        """Return a collection run when it exists for the project."""
