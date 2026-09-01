from app.core.enums import WorkflowState


_VALID_TRANSITIONS: dict[WorkflowState, tuple[WorkflowState, ...]] = {
    WorkflowState.CREATED: (WorkflowState.QUERIES_READY,),
    WorkflowState.QUERIES_READY: (WorkflowState.COLLECTION_RUNNING,),
    WorkflowState.COLLECTION_RUNNING: (WorkflowState.COLLECTION_COMPLETED,),
    WorkflowState.COLLECTION_COMPLETED: (WorkflowState.CLEANING_COMPLETED,),
    WorkflowState.CLEANING_COMPLETED: (WorkflowState.EVIDENCE_COMPLETED,),
    WorkflowState.EVIDENCE_COMPLETED: (WorkflowState.ISSUES_COMPLETED,),
    WorkflowState.ISSUES_COMPLETED: (WorkflowState.ANALYTICS_COMPLETED,),
    WorkflowState.ANALYTICS_COMPLETED: (WorkflowState.NARRATIVE_COMPLETED,),
    WorkflowState.NARRATIVE_COMPLETED: (WorkflowState.VISUALS_COMPLETED,),
    WorkflowState.VISUALS_COMPLETED: (WorkflowState.REPORT_COMPLETED,),
    WorkflowState.REPORT_COMPLETED: (),
}


class InvalidStateTransitionError(ValueError):
    """Raised when a workflow state transition is not allowed."""


class WorkflowStateMachine:
    """Enforces Phase 0's forward-only workflow sequence."""

    def can_transition(self, current: WorkflowState, target: WorkflowState) -> bool:
        return target in _VALID_TRANSITIONS.get(current, ())

    def require_transition(self, current: WorkflowState, target: WorkflowState) -> None:
        if not self.can_transition(current, target):
            raise InvalidStateTransitionError(
                f"Cannot transition from {current.value} to {target.value}."
            )
