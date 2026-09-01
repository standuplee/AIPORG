import pytest

from app.core.enums import WorkflowState
from app.core.state_machine import (
    InvalidStateTransitionError,
    WorkflowStateMachine,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkflowState.CREATED, WorkflowState.QUERIES_READY),
        (WorkflowState.QUERIES_READY, WorkflowState.COLLECTION_RUNNING),
        (WorkflowState.COLLECTION_RUNNING, WorkflowState.COLLECTION_COMPLETED),
        (WorkflowState.COLLECTION_COMPLETED, WorkflowState.CLEANING_COMPLETED),
        (WorkflowState.CLEANING_COMPLETED, WorkflowState.EVIDENCE_COMPLETED),
        (WorkflowState.EVIDENCE_COMPLETED, WorkflowState.ISSUES_COMPLETED),
        (WorkflowState.ISSUES_COMPLETED, WorkflowState.ANALYTICS_COMPLETED),
        (WorkflowState.ANALYTICS_COMPLETED, WorkflowState.NARRATIVE_COMPLETED),
        (WorkflowState.NARRATIVE_COMPLETED, WorkflowState.VISUALS_COMPLETED),
        (WorkflowState.VISUALS_COMPLETED, WorkflowState.REPORT_COMPLETED),
    ],
)
def test_all_adjacent_workflow_transitions_are_allowed(
    current: WorkflowState,
    target: WorkflowState,
) -> None:
    state_machine = WorkflowStateMachine()

    assert state_machine.can_transition(current, target)


def test_backward_transition_is_rejected() -> None:
    state_machine = WorkflowStateMachine()

    assert not state_machine.can_transition(
        WorkflowState.COLLECTION_RUNNING,
        WorkflowState.QUERIES_READY,
    )


def test_skip_transition_is_rejected() -> None:
    state_machine = WorkflowStateMachine()

    assert not state_machine.can_transition(
        WorkflowState.QUERIES_READY,
        WorkflowState.COLLECTION_COMPLETED,
    )


def test_report_completed_has_no_forward_transition() -> None:
    state_machine = WorkflowStateMachine()

    assert all(
        not state_machine.can_transition(WorkflowState.REPORT_COMPLETED, target)
        for target in WorkflowState
    )


def test_invalid_transition_raises_error() -> None:
    state_machine = WorkflowStateMachine()

    with pytest.raises(InvalidStateTransitionError):
        state_machine.require_transition(
            WorkflowState.CREATED,
            WorkflowState.COLLECTION_RUNNING,
        )
