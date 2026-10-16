import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.enums import ChannelType, CollectionRunStatus, WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.schemas.project import ProjectWorkflowSnapshot
from app.schemas.query import SearchQuery
from app.workflows.multi_query_collection_to_evidence import (
    CollectionRequest,
    MultiQueryCollectionToEvidenceWorkflow,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _FixtureCollector:
    def __init__(self, results):
        self._results = results

    async def search(self, query):
        del query
        return self._results

    async def fetch(self, result):
        raise AssertionError("fetch must go through CollectionService, not be called directly")


class _ProjectRepository:
    def __init__(self, project_id, initial_state=WorkflowState.QUERIES_READY):
        self.snapshot = ProjectWorkflowSnapshot(project_id=project_id, workflow_state=initial_state)
        self.advances: list[WorkflowState] = []

    def get_workflow(self, project_id):
        assert project_id == self.snapshot.project_id
        return self.snapshot

    def advance_workflow(self, project_id, target):
        assert project_id == self.snapshot.project_id
        self.snapshot = ProjectWorkflowSnapshot(project_id=project_id, workflow_state=target)
        self.advances.append(target)
        return self.snapshot


class _DuplicateClusterRepository:
    def __init__(self):
        self.created = []

    def create(self, project_id, cluster):
        del project_id
        self.created.append(cluster)
        return cluster


class _EvidenceRepository:
    def __init__(self):
        self.created = []

    def create(self, evidence):
        self.created.append(evidence)
        return evidence


def _query(text: str) -> SearchQuery:
    return SearchQuery(query=text, channels=[ChannelType.NEWS])


class _NoOpCollectionRunRepository:
    """CollectionService only needs start/complete to accept and echo back the run."""

    def start(self, project_id, query_id, run):
        del project_id, query_id
        return run

    def complete(self, project_id, run_id, run):
        del project_id, run_id
        return run


def test_rejects_an_empty_request_list() -> None:
    project_id = uuid4()
    workflow = MultiQueryCollectionToEvidenceWorkflow(
        collection_run_repository=object(),
        cleaning_service=object(),
        deduplication_service=object(),
        evidence_service=object(),
        project_repository=_ProjectRepository(project_id),
        document_repository=object(),
        duplicate_cluster_repository=object(),
        evidence_repository=object(),
    )

    with pytest.raises(ValueError):
        asyncio.run(workflow.run(project_id=project_id, requests=[]))


def test_rejects_a_project_outside_queries_ready() -> None:
    project_id = uuid4()
    project_repository = _ProjectRepository(project_id, initial_state=WorkflowState.CREATED)
    workflow = MultiQueryCollectionToEvidenceWorkflow(
        collection_run_repository=object(),
        cleaning_service=object(),
        deduplication_service=object(),
        evidence_service=object(),
        project_repository=project_repository,
        document_repository=object(),
        duplicate_cluster_repository=object(),
        evidence_repository=object(),
    )
    request = CollectionRequest(
        collector=_FixtureCollector([]),
        query_id=uuid4(),
        run_id=uuid4(),
        query=_query("충남"),
    )

    with pytest.raises(InvalidStateTransitionError):
        asyncio.run(workflow.run(project_id=project_id, requests=[request]))

    assert project_repository.advances == []


def test_one_failed_keyword_does_not_block_the_others_from_reaching_evidence() -> None:
    from app.cleaning.service import CleaningService
    from app.dedup.service import DeduplicationService
    from app.evidence.service import EvidenceService
    from app.collectors.errors import CollectorError
    from app.schemas.document import RawDocument, SearchResult

    project_id = uuid4()

    class _FailingCollector:
        async def search(self, query):
            del query
            raise CollectorError(code="fixture_failure", message="boom")

        async def fetch(self, result):
            raise AssertionError("fetch must not run after a failed search")

    ok_result = SearchResult(
        source="naver",
        channel=ChannelType.NEWS,
        title="삼성 디스플레이 투자",
        url="https://press.example/a",
        published_at=NOW,
        query="삼성 디스플레이",
    )

    class _OkCollector:
        async def search(self, query):
            del query
            return [ok_result]

        async def fetch(self, result):
            return RawDocument(
                **result.model_dump(),
                document_id=uuid4(),
                platform="fixture",
                body="삼성이 디스플레이에 투자했다.",
                metadata={},
                collected_at=NOW,
            )

    document_repository = _TrackingDocumentRepository()
    collection_run_repository = _NoOpCollectionRunRepository()
    project_repository = _ProjectRepository(project_id)
    workflow = MultiQueryCollectionToEvidenceWorkflow(
        collection_run_repository=collection_run_repository,
        cleaning_service=CleaningService(),
        deduplication_service=DeduplicationService(),
        evidence_service=EvidenceService(now_fn=lambda: NOW),
        project_repository=project_repository,
        document_repository=document_repository,
        duplicate_cluster_repository=_DuplicateClusterRepository(),
        evidence_repository=_EvidenceRepository(),
        now_fn=lambda: NOW,
    )

    failing_request = CollectionRequest(
        collector=_FailingCollector(),
        query_id=uuid4(),
        run_id=uuid4(),
        query=_query("충남 재정전략회의"),
    )
    ok_request = CollectionRequest(
        collector=_OkCollector(),
        query_id=uuid4(),
        run_id=uuid4(),
        query=_query("삼성 디스플레이"),
    )

    results = asyncio.run(
        workflow.run(project_id=project_id, requests=[failing_request, ok_request])
    )

    assert {run.status for run in results} == {
        CollectionRunStatus.FAILED,
        CollectionRunStatus.COMPLETED,
    }
    assert project_repository.advances == [
        WorkflowState.COLLECTION_RUNNING,
        WorkflowState.COLLECTION_COMPLETED,
        WorkflowState.CLEANING_COMPLETED,
        WorkflowState.EVIDENCE_COMPLETED,
    ]
    assert len(document_repository.cleaned) == 1
    assert document_repository.cleaned[0].title == "삼성 디스플레이 투자"


class _TrackingDocumentRepository:
    """Real raw-document storage (keyed by url) plus clean-document tracking."""

    def __init__(self):
        self._raw_by_url: dict[str, object] = {}
        self._raw_by_run: dict[object, list] = {}
        self.cleaned = []

    def upsert_raw(self, project_id, document, *, collection_run_id=None):
        del project_id
        self._raw_by_url[document.url] = document
        if collection_run_id is not None:
            self._raw_by_run.setdefault(collection_run_id, []).append(document)
        return document

    def list_raw_by_collection_run(self, project_id, collection_run_id):
        del project_id
        return list(self._raw_by_run.get(collection_run_id, []))

    def upsert_clean(self, project_id, document):
        del project_id
        self.cleaned.append(document)
        return document
