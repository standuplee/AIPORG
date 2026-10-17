"""Persist a versioned analytics snapshot after issue completion.

Use repositories sharing the caller's session_scope transaction so snapshot
creation and state advancement commit or roll back together.

Comments (``metadata["document_type"] == "comment"``, see
``app/collectors/youtube.py``) are excluded from ``AnalyticsService.build()``'s
article-oriented counts and reported separately (``comment_count``,
``comment_document_ids`` in the resulting snapshot's metrics) -- the
2026-10-17 decision that comment and article mentions need separate names and
denominators (requirements doc §4.2), done here rather than inside
``AnalyticsService`` so its already-tested counting logic is untouched.
"""

from app.analytics.service import AnalyticsService
from app.core.enums import WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.repositories.analytics import AnalyticsRepository
from app.repositories.document import DocumentRepository
from app.repositories.fact import FactRepository
from app.repositories.issue import IssueRepository
from app.repositories.project import ProjectRepository
from app.schemas.analytics import AnalyticsSnapshotRead
from app.schemas.common import ProjectId, VersionedRunSchema


class IssuesToAnalyticsWorkflow:
    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        document_repository: DocumentRepository,
        fact_repository: FactRepository,
        issue_repository: IssueRepository,
        analytics_repository: AnalyticsRepository,
        analytics_service: AnalyticsService,
    ) -> None:
        self.project_repository = project_repository
        self.document_repository = document_repository
        self.fact_repository = fact_repository
        self.issue_repository = issue_repository
        self.analytics_repository = analytics_repository
        self.analytics_service = analytics_service

    def run(self, project_id: ProjectId, run: VersionedRunSchema) -> AnalyticsSnapshotRead:
        workflow = self.project_repository.get_workflow(project_id)
        if workflow is None:
            raise ValueError("project does not exist")
        if workflow.workflow_state is not WorkflowState.ISSUES_COMPLETED:
            raise InvalidStateTransitionError("analytics requires the issues_completed workflow state")
        project = self.project_repository.get(project_id)
        if project is None:
            raise ValueError("project does not exist")
        documents = self.document_repository.list_canonical(project_id)
        articles = [
            document for document in documents
            if document.metadata.get("document_type") != "comment"
        ]
        comments = [
            document for document in documents
            if document.metadata.get("document_type") == "comment"
        ]
        issues = self.issue_repository.list_by_project(project_id)
        facts = {}
        for fact_id in sorted({fact_id for issue in issues for fact_id in issue.fact_ids}, key=str):
            fact = self.fact_repository.get(project_id, fact_id)
            if fact is None:
                raise ValueError("issue references an unknown project fact")
            facts[fact_id] = fact
        snapshot = self.analytics_service.build(
            project_id,
            run,
            articles,
            analysis_period=project.analysis_period,
            comparison_period=project.comparison_period,
            issues=issues,
            facts_by_id=facts,
        )
        if comments:
            snapshot = snapshot.model_copy(update={
                "metrics": {
                    **snapshot.metrics,
                    "comment_count": len(comments),
                    "comment_document_ids": sorted(
                        str(document.document_id) for document in comments
                    ),
                },
            })
        saved = self.analytics_repository.create(snapshot)
        self.project_repository.advance_workflow(project_id, WorkflowState.ANALYTICS_COMPLETED)
        return saved
