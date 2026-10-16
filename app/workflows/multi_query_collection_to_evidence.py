"""Fan out collection across a project's whole keyword list, then build evidence once.

``CollectionToEvidenceWorkflow`` advances a project's workflow state exactly
once per call and accepts exactly one ``(query_id, run_id, query)`` triple.
That is correct for a single query, but a monthly project collects many
keywords across multiple channels in one sitting, and the project workflow
state machine (``app/core/state_machine.py``) only allows each state to be
entered once. Looping the single-query workflow per keyword would advance
``QUERIES_READY -> COLLECTION_RUNNING`` on the first keyword and then reject
every subsequent keyword with ``InvalidStateTransitionError``.

This workflow runs every requested ``(collector, query_id, run_id, query)``
collection first, advances the project through ``COLLECTION_RUNNING`` and
``COLLECTION_COMPLETED`` exactly once, then cleans, deduplicates, and builds
evidence from the union of raw documents collected across *all* of those
runs together -- which is also what makes cross-keyword duplicate detection
(the same article found under two different keywords) work at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.cleaning.service import CleaningService
from app.collection.service import CollectionService
from app.collectors.base import BaseCollector
from app.core.enums import CollectionRunStatus, WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.dedup.service import DeduplicationService
from app.evidence.service import EvidenceService
from app.repositories.document import DocumentRepository
from app.repositories.duplicate_cluster import DuplicateClusterRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.project import ProjectRepository
from app.schemas.collection import CollectionRun
from app.schemas.common import ProjectId, RunId
from app.schemas.document import DocumentId, RawDocument
from app.schemas.query import QueryId, SearchQuery


class _CollectionRunRepository(Protocol):
    def start(self, project_id, query_id, run): ...

    def complete(self, project_id, run_id, run): ...


@dataclass(frozen=True)
class CollectionRequest:
    """One collector run to perform for the project: a keyword against one channel adapter."""

    collector: BaseCollector
    query_id: QueryId
    run_id: RunId
    query: SearchQuery


class MultiQueryCollectionToEvidenceWorkflow:
    """Persist a project's whole keyword list as cleaned, deduplicated evidence."""

    def __init__(
        self,
        *,
        collection_run_repository: _CollectionRunRepository,
        cleaning_service: CleaningService,
        deduplication_service: DeduplicationService,
        evidence_service: EvidenceService,
        project_repository: ProjectRepository,
        document_repository: DocumentRepository,
        duplicate_cluster_repository: DuplicateClusterRepository,
        evidence_repository: EvidenceRepository,
        now_fn=None,
    ) -> None:
        self.collection_run_repository = collection_run_repository
        self.cleaning_service = cleaning_service
        self.deduplication_service = deduplication_service
        self.evidence_service = evidence_service
        self.project_repository = project_repository
        self.document_repository = document_repository
        self.duplicate_cluster_repository = duplicate_cluster_repository
        self.evidence_repository = evidence_repository
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    async def run(
        self,
        *,
        project_id: ProjectId,
        requests: list[CollectionRequest],
    ) -> list[CollectionRun]:
        if not requests:
            raise ValueError("at least one collection request is required")

        workflow = self.project_repository.get_workflow(project_id)
        if workflow is None:
            raise ValueError("project does not exist")
        if workflow.workflow_state is not WorkflowState.QUERIES_READY:
            raise InvalidStateTransitionError(
                "collection requires the queries_ready workflow state"
            )

        self.project_repository.advance_workflow(
            project_id, WorkflowState.COLLECTION_RUNNING
        )

        collection_runs: list[CollectionRun] = []
        for request in requests:
            service = CollectionService(
                collector=request.collector,
                document_repository=self.document_repository,
                collection_run_repository=self.collection_run_repository,
                now_fn=self.now_fn,
            )
            collection_runs.append(
                await service.collect(
                    project_id=project_id,
                    query_id=request.query_id,
                    run_id=request.run_id,
                    query=request.query,
                )
            )

        # Every requested collection is attempted and recorded even if some
        # fail -- a run per keyword/channel, not one run for the whole
        # project -- so one failed keyword must not block the others from
        # reaching evidence. Only COMPLETED runs contribute raw documents.
        self.project_repository.advance_workflow(
            project_id, WorkflowState.COLLECTION_COMPLETED
        )

        raw_documents: dict[DocumentId, RawDocument] = {}
        for collection_run in collection_runs:
            if collection_run.status is not CollectionRunStatus.COMPLETED:
                continue
            for document in self.document_repository.list_raw_by_collection_run(
                project_id, collection_run.id
            ):
                # The same article found under two keywords/channels upserts
                # to the same canonical_url row (app/repositories/sqlalchemy.py),
                # so keying this union by document_id already collapses it to
                # one entry -- this is the cross-query dedup the module
                # docstring describes.
                raw_documents[document.document_id] = document

        clean_documents = [
            self.cleaning_service.clean(document) for document in raw_documents.values()
        ]
        for document in clean_documents:
            self.document_repository.upsert_clean(project_id, document)
        self.project_repository.advance_workflow(
            project_id, WorkflowState.CLEANING_COMPLETED
        )

        sources = {
            document.document_id: document.source or ""
            for document in clean_documents
        }
        clusters = self.deduplication_service.cluster(
            clean_documents,
            source_by_document=sources,
        )
        duplicate_ids: set[DocumentId] = set()
        for cluster in clusters:
            self.duplicate_cluster_repository.create(project_id, cluster)
            duplicate_ids.update(cluster.duplicates)

        for document in clean_documents:
            if document.document_id in duplicate_ids:
                continue
            evidence = self.evidence_service.build(project_id, document)
            self.evidence_repository.create(evidence)
        self.project_repository.advance_workflow(
            project_id, WorkflowState.EVIDENCE_COMPLETED
        )
        return collection_runs
