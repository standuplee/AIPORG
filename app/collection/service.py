"""Orchestrate one collector run without leaking persistence into adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.collectors.base import BaseCollector
from app.collectors.errors import CollectorError
from app.core.enums import CollectionRunStatus
from app.repositories.collection import CollectionRunRepository
from app.repositories.document import DocumentRepository
from app.schemas.collection import CollectionRun
from app.schemas.common import ProjectId, RunId
from app.schemas.document import RawDocument
from app.schemas.query import QueryId, SearchQuery


class _DocumentRepository(Protocol):
    def upsert_raw(self, project_id: ProjectId, document: RawDocument): ...


class CollectionService:
    """Run search/fetch, then persist only through repository contracts."""

    def __init__(
        self,
        *,
        collector: BaseCollector,
        document_repository: DocumentRepository | _DocumentRepository,
        collection_run_repository: CollectionRunRepository,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.collector = collector
        self.document_repository = document_repository
        self.collection_run_repository = collection_run_repository
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    async def collect(
        self,
        *,
        project_id: ProjectId,
        query_id: QueryId,
        run_id: RunId,
        query: SearchQuery,
    ) -> CollectionRun:
        if not query.channels:
            raise ValueError("query must include at least one channel")
        started_at = self.now_fn()
        run = CollectionRun(
            id=run_id,
            project_id=project_id,
            channel=query.channels[0],
            query=query.query,
            started_at=started_at,
            status=CollectionRunStatus.RUNNING,
            documents_found=0,
            documents_saved=0,
            error_count=0,
        )
        self.collection_run_repository.start(project_id, query_id, run)

        try:
            results = await self.collector.search(query)
        except CollectorError:
            failed = run.model_copy(
                update={
                    "status": CollectionRunStatus.FAILED,
                    "completed_at": self.now_fn(),
                    "error_count": 1,
                }
            )
            return self.collection_run_repository.complete(project_id, run_id, failed)

        saved = 0
        errors = 0
        for result in results:
            try:
                document = await self.collector.fetch(result)
                self.document_repository.upsert_raw(project_id, document)
                saved += 1
            except CollectorError:
                errors += 1

        completed = run.model_copy(
            update={
                "status": CollectionRunStatus.COMPLETED,
                "completed_at": self.now_fn(),
                "documents_found": len(results),
                "documents_saved": saved,
                "error_count": errors,
            }
        )
        return self.collection_run_repository.complete(project_id, run_id, completed)
