from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.collection.service import CollectionService
from app.collectors.errors import CollectorError
from app.core.enums import ChannelType, CollectionRunStatus
from app.schemas.collection import CollectionRun
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)


def result(index: int) -> SearchResult:
    return SearchResult(
        source="test",
        channel=ChannelType.NEWS,
        title=f"title-{index}",
        url=f"https://example.test/{index}",
        published_at=NOW,
        query="박수현",
    )


def raw(result_value: SearchResult) -> RawDocument:
    return RawDocument(
        **result_value.model_dump(),
        document_id=uuid4(),
        platform="test",
        body="body",
        metadata={},
        collected_at=NOW,
    )


class FakeCollector:
    def __init__(self, results: list[SearchResult], failures: set[str] | None = None) -> None:
        self.results = results
        self.failures = failures or set()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        return self.results

    async def fetch(self, item: SearchResult) -> RawDocument:
        if item.url in self.failures:
            raise CollectorError(code="fetch_failed", message="fetch failed", retryable=False)
        return raw(item)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.saved: list[RawDocument] = []

    def upsert_raw(self, project_id, document):
        self.saved.append(document)
        return document


class FakeRunRepository:
    def __init__(self) -> None:
        self.started: CollectionRun | None = None
        self.completed: CollectionRun | None = None

    def start(self, project_id, query_id, run):
        self.started = run
        return run

    def complete(self, project_id, run_id, run):
        self.completed = run
        return run


def test_collection_service_persists_all_fetched_documents() -> None:
    doc_repo = FakeDocumentRepository()
    run_repo = FakeRunRepository()
    service = CollectionService(
        collector=FakeCollector([result(1), result(2)]),
        document_repository=doc_repo,
        collection_run_repository=run_repo,
        now_fn=lambda: NOW,
    )

    run = asyncio.run(
        service.collect(
            project_id=uuid4(),
            query_id=uuid4(),
            run_id=uuid4(),
            query=SearchQuery(query="박수현", channels=[ChannelType.NEWS]),
        )
    )

    assert run.status is CollectionRunStatus.COMPLETED
    assert run.documents_found == 2
    assert run.documents_saved == 2
    assert run.error_count == 0
    assert len(doc_repo.saved) == 2
    assert run_repo.started is not None
    assert run_repo.completed == run


def test_collection_service_records_partial_fetch_failures() -> None:
    doc_repo = FakeDocumentRepository()
    run_repo = FakeRunRepository()
    service = CollectionService(
        collector=FakeCollector([result(1), result(2)], failures={result(2).url}),
        document_repository=doc_repo,
        collection_run_repository=run_repo,
        now_fn=lambda: NOW,
    )

    run = asyncio.run(
        service.collect(
            project_id=uuid4(),
            query_id=uuid4(),
            run_id=uuid4(),
            query=SearchQuery(query="박수현", channels=[ChannelType.NEWS]),
        )
    )

    assert run.status is CollectionRunStatus.COMPLETED
    assert run.documents_found == 2
    assert run.documents_saved == 1
    assert run.error_count == 1


def test_collection_service_marks_failed_when_search_fails() -> None:
    class SearchFailureCollector(FakeCollector):
        async def search(self, query):
            raise CollectorError(code="search_failed", message="search failed")

    run_repo = FakeRunRepository()
    service = CollectionService(
        collector=SearchFailureCollector([]),
        document_repository=FakeDocumentRepository(),
        collection_run_repository=run_repo,
        now_fn=lambda: NOW,
    )

    run = asyncio.run(
        service.collect(
            project_id=uuid4(),
            query_id=uuid4(),
            run_id=uuid4(),
            query=SearchQuery(query="박수현", channels=[ChannelType.NEWS]),
        )
    )

    assert run.status is CollectionRunStatus.FAILED
    assert run.completed_at == NOW
    assert run_repo.completed == run


def test_collection_service_rejects_query_without_channel() -> None:
    service = CollectionService(
        collector=FakeCollector([]),
        document_repository=FakeDocumentRepository(),
        collection_run_repository=FakeRunRepository(),
        now_fn=lambda: NOW,
    )

    with pytest.raises(ValueError, match="at least one channel"):
        asyncio.run(
            service.collect(
                project_id=uuid4(),
                query_id=uuid4(),
                run_id=uuid4(),
                query=SearchQuery(query="박수현", channels=[]),
            )
        )
