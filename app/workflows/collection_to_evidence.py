"""Collection through evidence orchestration using repository boundaries only."""

from __future__ import annotations

from app.cleaning.service import CleaningService
from app.collection.service import CollectionService
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
from app.schemas.query import QueryId, SearchQuery


class CollectionToEvidenceWorkflow:
    """Persist a successful collection as cleaned, deduplicated evidence."""

    def __init__(
        self,
        *,
        collection_service: CollectionService,
        cleaning_service: CleaningService,
        deduplication_service: DeduplicationService,
        evidence_service: EvidenceService,
        project_repository: ProjectRepository,
        document_repository: DocumentRepository,
        duplicate_cluster_repository: DuplicateClusterRepository,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self.collection_service = collection_service
        self.cleaning_service = cleaning_service
        self.deduplication_service = deduplication_service
        self.evidence_service = evidence_service
        self.project_repository = project_repository
        self.document_repository = document_repository
        self.duplicate_cluster_repository = duplicate_cluster_repository
        self.evidence_repository = evidence_repository

    async def run(
        self,
        *,
        project_id: ProjectId,
        query_id: QueryId,
        run_id: RunId,
        query: SearchQuery,
    ) -> CollectionRun:
        workflow = self.project_repository.get_workflow(project_id)
        if workflow is None:
            raise ValueError("project does not exist")
        if workflow.workflow_state is not WorkflowState.QUERIES_READY:
            raise InvalidStateTransitionError(
                "collection requires the queries_ready workflow state"
            )

        collection_run = await self.collection_service.collect(
            project_id=project_id,
            query_id=query_id,
            run_id=run_id,
            query=query,
        )
        if collection_run.status is CollectionRunStatus.FAILED:
            return collection_run

        self.project_repository.advance_workflow(
            project_id, WorkflowState.COLLECTION_RUNNING
        )
        self.project_repository.advance_workflow(
            project_id, WorkflowState.COLLECTION_COMPLETED
        )

        raw_documents = self.document_repository.list_raw_by_collection_run(
            project_id, run_id
        )
        clean_documents = [
            self.cleaning_service.clean(document) for document in raw_documents
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
        duplicate_ids = set()
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
        return collection_run
