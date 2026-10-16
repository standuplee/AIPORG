import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.core.enums import ChannelType, CollectionRunStatus, WorkflowState
from app.schemas.collection import CollectionRun
from app.schemas.project import ProjectWorkflowSnapshot
from app.schemas.query import SearchQuery
from app.workflows.collection_to_evidence import CollectionToEvidenceWorkflow


class _FailedCollectionService:
    async def collect(self, *, project_id, query_id, run_id, query):
        del query_id, query
        return CollectionRun(
            id=run_id,
            project_id=project_id,
            channel=ChannelType.NEWS,
            query="충남",
            started_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            status=CollectionRunStatus.FAILED,
            documents_found=0,
            documents_saved=0,
            error_count=1,
        )


class _ProjectRepository:
    def __init__(self, project_id):
        self.snapshot = ProjectWorkflowSnapshot(
            project_id=project_id,
            workflow_state=WorkflowState.QUERIES_READY,
        )
        self.advances = []

    def get_workflow(self, project_id):
        assert project_id == self.snapshot.project_id
        return self.snapshot

    def advance_workflow(self, project_id, target):
        self.advances.append((project_id, target))


def test_failed_collection_preserves_last_successful_project_state() -> None:
    project_id = uuid4()
    project_repository = _ProjectRepository(project_id)
    workflow = CollectionToEvidenceWorkflow(
        collection_service=_FailedCollectionService(),
        cleaning_service=object(),
        deduplication_service=object(),
        evidence_service=object(),
        project_repository=project_repository,
        document_repository=object(),
        duplicate_cluster_repository=object(),
        evidence_repository=object(),
    )

    result = asyncio.run(workflow.run(
        project_id=project_id,
        query_id=uuid4(),
        run_id=uuid4(),
        query=SearchQuery(query="충남", channels=[ChannelType.NEWS]),
    ))

    assert result.status is CollectionRunStatus.FAILED
    assert project_repository.advances == []
    assert project_repository.snapshot.workflow_state is WorkflowState.QUERIES_READY

