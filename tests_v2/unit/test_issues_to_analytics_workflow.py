from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.analytics.service import AnalyticsService
from app.core.enums import WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import VersionedRunSchema
from app.workflows.issues_to_analytics import IssuesToAnalyticsWorkflow


def setup_workflow(state=WorkflowState.ISSUES_COMPLETED):
    project = Mock()
    project.get_workflow.return_value = SimpleNamespace(workflow_state=state)
    document, fact, issue, analytics = Mock(), Mock(), Mock(), Mock()
    document.list_canonical.return_value = []
    issue.list_by_project.return_value = []
    service = Mock(spec=AnalyticsService)
    workflow = IssuesToAnalyticsWorkflow(
        project_repository=project, document_repository=document,
        fact_repository=fact, issue_repository=issue,
        analytics_repository=analytics, analytics_service=service,
    )
    run = VersionedRunSchema(
        run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    return workflow, uuid4(), run


@pytest.mark.parametrize("state", [state for state in WorkflowState if state != WorkflowState.ISSUES_COMPLETED])
def test_rejects_any_state_other_than_completed_issues(state):
    workflow, project_id, run = setup_workflow(state)
    with pytest.raises(InvalidStateTransitionError, match="issues_completed"):
        workflow.run(project_id, run)
    workflow.document_repository.list_canonical.assert_not_called()
    workflow.analytics_repository.create.assert_not_called()


@pytest.mark.parametrize("missing", ["get_workflow", "get"])
def test_unknown_project_stops_before_reading_inputs(missing):
    workflow, project_id, run = setup_workflow()
    getattr(workflow.project_repository, missing).return_value = None
    with pytest.raises(ValueError, match="project does not exist"):
        workflow.run(project_id, run)
    workflow.document_repository.list_canonical.assert_not_called()


def test_success_persists_before_advancing_and_passes_only_canonical_inputs():
    workflow, project_id, run = setup_workflow()
    calls = Mock()
    calls.attach_mock(workflow.analytics_repository.create, "save")
    calls.attach_mock(workflow.project_repository.advance_workflow, "advance")
    result = workflow.run(project_id, run)
    assert result is workflow.analytics_repository.create.return_value
    workflow.document_repository.list_canonical.assert_called_once_with(project_id)
    workflow.analytics_service.build.assert_called_once_with(
        project_id, run, [],
        analysis_period=workflow.project_repository.get.return_value.analysis_period,
        comparison_period=workflow.project_repository.get.return_value.comparison_period,
        issues=[], facts_by_id={},
    )
    assert [call[0] for call in calls.mock_calls] == ["save", "advance"]
    workflow.project_repository.advance_workflow.assert_called_once_with(project_id, WorkflowState.ANALYTICS_COMPLETED)


@pytest.mark.parametrize("failure_stage", ["build", "save", "missing_fact"])
def test_failure_does_not_advance_workflow(failure_stage):
    workflow, project_id, run = setup_workflow()
    if failure_stage == "build":
        workflow.analytics_service.build.side_effect = ValueError("invalid inputs")
    elif failure_stage == "save":
        workflow.analytics_repository.create.side_effect = ValueError("write failed")
    else:
        workflow.issue_repository.list_by_project.return_value = [SimpleNamespace(fact_ids=[uuid4()])]
        workflow.fact_repository.get.return_value = None
    with pytest.raises(ValueError):
        workflow.run(project_id, run)
    workflow.project_repository.advance_workflow.assert_not_called()


def test_comments_are_excluded_from_analytics_and_counted_separately():
    workflow, project_id, run = setup_workflow()
    article = SimpleNamespace(document_id=uuid4(), metadata={})
    comment = SimpleNamespace(document_id=uuid4(), metadata={"document_type": "comment"})
    workflow.document_repository.list_canonical.return_value = [article, comment]
    workflow.analytics_service.build.return_value = AnalyticsSnapshotSchema(
        project_id=project_id, run=run, metrics={"unique_documents": 1},
    )
    workflow.analytics_repository.create.side_effect = lambda snapshot: snapshot

    result = workflow.run(project_id, run)

    workflow.analytics_service.build.assert_called_once_with(
        project_id, run, [article],
        analysis_period=workflow.project_repository.get.return_value.analysis_period,
        comparison_period=workflow.project_repository.get.return_value.comparison_period,
        issues=[], facts_by_id={},
    )
    assert result.metrics["unique_documents"] == 1
    assert result.metrics["comment_count"] == 1
    assert result.metrics["comment_document_ids"] == [str(comment.document_id)]


def test_no_comments_leaves_metrics_untouched():
    workflow, project_id, run = setup_workflow()
    article = SimpleNamespace(document_id=uuid4(), metadata={})
    workflow.document_repository.list_canonical.return_value = [article]
    workflow.analytics_repository.create.side_effect = lambda snapshot: snapshot

    workflow.run(project_id, run)

    workflow.analytics_service.build.assert_called_once_with(
        project_id, run, [article],
        analysis_period=workflow.project_repository.get.return_value.analysis_period,
        comparison_period=workflow.project_repository.get.return_value.comparison_period,
        issues=[], facts_by_id={},
    )
    # build()'s own return value is persisted as-is -- no model_copy when there
    # are no comments to report.
    workflow.analytics_repository.create.assert_called_once_with(
        workflow.analytics_service.build.return_value
    )


def test_shared_fact_is_loaded_once_with_project_scope():
    workflow, project_id, run = setup_workflow()
    fact_id = uuid4()
    workflow.issue_repository.list_by_project.return_value = [
        SimpleNamespace(fact_ids=[fact_id]), SimpleNamespace(fact_ids=[fact_id]),
    ]
    workflow.run(project_id, run)
    workflow.fact_repository.get.assert_called_once_with(project_id, fact_id)
