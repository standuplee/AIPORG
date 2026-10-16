from uuid import uuid4

import pytest

from app.core.enums import WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.schemas.project import ProjectWorkflowSnapshot
from app.workflows.evidence_to_issues import EvidenceToIssuesWorkflow


class _ProjectRepository:
    def __init__(self, project_id):
        self.project_id = project_id

    def get_workflow(self, project_id):
        return ProjectWorkflowSnapshot(
            project_id=project_id,
            workflow_state=WorkflowState.CLEANING_COMPLETED,
        )


def test_workflow_rejects_analysis_before_evidence_completion() -> None:
    project_id = uuid4()
    workflow = EvidenceToIssuesWorkflow(
        project_repository=_ProjectRepository(project_id),
        document_repository=object(),
        evidence_repository=object(),
        fact_repository=object(),
        issue_repository=object(),
        fact_extraction_service=object(),
        fact_validation_service=object(),
        issue_discovery_service=object(),
        issue_finalization_service=object(),
    )

    with pytest.raises(InvalidStateTransitionError, match="evidence_completed"):
        workflow.run(project_id)
