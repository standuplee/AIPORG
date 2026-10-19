"""Evidence through issue orchestration using stored provenance only."""

from __future__ import annotations

from app.core.enums import WorkflowState
from app.core.state_machine import InvalidStateTransitionError
from app.facts.extraction import FactExtractionService
from app.facts.validation import FactValidationService
from app.issues.discovery import IssueDiscoveryService
from app.issues.finalization import IssueFinalizationService
from app.repositories.document import DocumentRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.fact import FactRepository
from app.repositories.issue import IssueRepository
from app.repositories.project import ProjectRepository
from app.schemas.common import ProjectId
from app.schemas.document import CleanDocument
from app.schemas.issue import IssueRead


class EvidenceToIssuesWorkflow:
    """Extract, validate, group, and persist facts and issues."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        document_repository: DocumentRepository,
        evidence_repository: EvidenceRepository,
        fact_repository: FactRepository,
        issue_repository: IssueRepository,
        fact_extraction_service: FactExtractionService,
        fact_validation_service: FactValidationService,
        issue_discovery_service: IssueDiscoveryService,
        issue_finalization_service: IssueFinalizationService,
        official_sources: set[str] | None = None,
    ) -> None:
        self.project_repository = project_repository
        self.document_repository = document_repository
        self.evidence_repository = evidence_repository
        self.fact_repository = fact_repository
        self.issue_repository = issue_repository
        self.fact_extraction_service = fact_extraction_service
        self.fact_validation_service = fact_validation_service
        self.issue_discovery_service = issue_discovery_service
        self.issue_finalization_service = issue_finalization_service
        self.official_sources = official_sources or set()

    def run(self, project_id: ProjectId) -> list[IssueRead]:
        workflow = self.project_repository.get_workflow(project_id)
        if workflow is None:
            raise ValueError("project does not exist")
        if workflow.workflow_state is not WorkflowState.EVIDENCE_COMPLETED:
            raise InvalidStateTransitionError(
                "fact and issue analysis requires the evidence_completed workflow state"
            )
        project = self.project_repository.get(project_id)
        if project is None:
            raise ValueError("project does not exist")

        evidence = self.evidence_repository.list_by_project(project_id)
        documents = {}
        for item in evidence:
            document = self.document_repository.get(project_id, item.document_id)
            if not isinstance(document, CleanDocument):
                raise ValueError("evidence requires a cleaned source document")
            documents[item.document_id] = document

        entity_terms = [
            project.target.organization,
            project.target.primary_person,
            project.target.region,
        ]
        extracted = self.fact_extraction_service.extract(
            project_id,
            evidence,
            documents=documents,
            entity_terms=entity_terms,
        )
        facts = [
            self.fact_validation_service.validate(
                fact,
                official_source=any(
                    documents[document_id].source in self.official_sources
                    for document_id in fact.evidence_document_ids
                ),
            )
            for fact in extracted
        ]
        self.fact_repository.save_batch(project_id, facts)

        source_by_document = {
            document_id: document.source or ""
            for document_id, document in documents.items()
        }
        channel_by_document = {
            document_id: document.channel
            for document_id, document in documents.items()
            if document.channel is not None
        }
        query_by_document = {
            document_id: document.query or "미분류"
            for document_id, document in documents.items()
        }
        candidates = self.issue_discovery_service.discover(
            facts,
            source_by_document=source_by_document,
            channel_by_document=channel_by_document,
            query_by_document=query_by_document,
        )
        issues = self.issue_finalization_service.finalize(
            candidates,
            facts_by_id={fact.fact_id: fact for fact in facts},
        )
        saved = self.issue_repository.save_batch(project_id, issues)
        self.project_repository.advance_workflow(
            project_id, WorkflowState.ISSUES_COMPLETED
        )
        return saved
