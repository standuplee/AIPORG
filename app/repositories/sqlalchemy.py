"""Concrete SQLAlchemy repositories for the fixed AIPORG 2.0 contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import WorkflowState
from app.core.state_machine import WorkflowStateMachine
from app.models.analytics import AnalyticsSnapshot
from app.models.collection import CollectionRun as CollectionRunModel
from app.models.document import Document, DocumentDuplicate, DuplicateCluster
from app.models.evidence import Evidence, EvidenceDocument
from app.models.fact import Fact, NumericFact, NumericFactEvidence
from app.models.issue import Issue, IssueFact, IssueSubissue
from app.models.narrative import Narrative
from app.models.project import Project, Query, QuerySet
from app.models.report import Report, ReportVisualization
from app.models.visualization import Visualization
from app.schemas.analytics import AnalyticsSnapshotRead, AnalyticsSnapshotSchema
from app.schemas.collection import CollectionRun, CollectionRunRead
from app.schemas.common import ProjectId, RunId, VersionedRunSchema
from app.schemas.document import (
    CleanDocument,
    DocumentRead,
    DuplicateClusterId,
    DuplicateClusterRead,
    DuplicateClusterSchema,
    RawDocument,
)
from app.schemas.evidence import EvidenceId, EvidenceRead, EvidenceSchema
from app.schemas.fact import FactId, FactRead, FactSchema, NumericFactSchema
from app.schemas.issue import IssueDetailSchema, IssueId, IssueRead, IssueSchema
from app.schemas.narrative import (
    NarrativeContext,
    NarrativeOutputRead,
    NarrativeOutputSchema,
    NarrativeRead,
)
from app.schemas.project import ProjectCreate, ProjectRead, ProjectWorkflowSnapshot
from app.schemas.query import QueryId, SearchQuery
from app.schemas.report import ReportRead, ReportSchema
from app.schemas.visualization import (
    VisualizationAssetRead,
    VisualizationAssetSchema,
    VisualizationOutputRead,
    VisualizationOutputSchema,
)


class RepositoryConflictError(ValueError):
    """Raised when persistence constraints reject a repository operation."""


class _Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _flush(self) -> None:
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(str(exc.orig)) from exc


class SqlAlchemyProjectRepository(_Repository):
    def create(self, project: ProjectCreate) -> ProjectRead:
        row = Project(
            name=project.name,
            target=project.target.model_dump(mode="json"),
            analysis_period=project.analysis_period.model_dump(mode="json"),
            comparison_period=project.comparison_period.model_dump(mode="json"),
            channels=[channel.value for channel in project.channels],
            workflow_state=WorkflowState.CREATED,
        )
        self.session.add(row)
        self._flush()
        return _project_read(row)

    def get(self, project_id: ProjectId) -> ProjectRead | None:
        row = self.session.get(Project, project_id)
        return _project_read(row) if row is not None else None

    def list(self) -> list[ProjectRead]:
        rows = self.session.scalars(
            select(Project).order_by(Project.created_at.desc(), Project.id.desc())
        ).all()
        return [_project_read(row) for row in rows]

    def get_workflow(self, project_id: ProjectId) -> ProjectWorkflowSnapshot | None:
        row = self.session.get(Project, project_id)
        if row is None:
            return None
        return ProjectWorkflowSnapshot(
            project_id=row.id,
            workflow_state=row.workflow_state,
        )

    def advance_workflow(
        self,
        project_id: ProjectId,
        target: WorkflowState,
    ) -> ProjectWorkflowSnapshot:
        row = self.session.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )
        if row is None:
            raise RepositoryConflictError("project does not exist")
        WorkflowStateMachine().require_transition(row.workflow_state, target)
        row.workflow_state = target
        self._flush()
        return ProjectWorkflowSnapshot(project_id=row.id, workflow_state=target)


class SqlAlchemyQuerySetRepository(_Repository):
    def create(self, project_id: ProjectId, queries: list[SearchQuery]) -> list[SearchQuery]:
        if self.session.get(Project, project_id) is None:
            raise RepositoryConflictError("project does not exist")
        self.session.execute(delete(Query).where(Query.project_id == project_id))
        old_sets = self.session.scalars(
            select(QuerySet).where(QuerySet.project_id == project_id)
        ).all()
        for old_set in old_sets:
            self.session.delete(old_set)
        self._flush()
        query_set = QuerySet(project_id=project_id)
        self.session.add(query_set)
        self._flush()
        for item in queries:
            self.session.add(
                Query(
                    project_id=project_id,
                    query_set_id=query_set.id,
                    query=item.query,
                    channels=[channel.value for channel in item.channels],
                )
            )
        self._flush()
        return list(queries)

    def get(self, project_id: ProjectId) -> list[SearchQuery]:
        rows = self.session.scalars(
            select(Query)
            .where(Query.project_id == project_id)
            .order_by(Query.created_at, Query.id)
        ).all()
        return [SearchQuery(query=row.query, channels=row.channels) for row in rows]


class SqlAlchemyCollectionRunRepository(_Repository):
    def start(
        self, project_id: ProjectId, query_id: QueryId, run: CollectionRun
    ) -> CollectionRunRead:
        if run.project_id != project_id:
            raise RepositoryConflictError("collection run project_id does not match")
        row = CollectionRunModel(
            id=run.id,
            project_id=project_id,
            query_id=query_id,
            channel=run.channel,
            query=run.query,
            started_at=run.started_at,
            completed_at=run.completed_at,
            status=run.status,
            documents_found=run.documents_found,
            documents_saved=run.documents_saved,
            error_count=run.error_count,
        )
        self.session.add(row)
        self._flush()
        return _collection_read(row)

    def complete(
        self, project_id: ProjectId, run_id: RunId, run: CollectionRun
    ) -> CollectionRunRead:
        row = self.session.scalar(
            select(CollectionRunModel).where(
                CollectionRunModel.project_id == project_id,
                CollectionRunModel.id == run_id,
            )
        )
        if row is None:
            raise RepositoryConflictError("collection run does not exist")
        if run.id != run_id or run.project_id != project_id:
            raise RepositoryConflictError("collection run identity does not match")
        row.completed_at = run.completed_at
        row.status = run.status
        row.documents_found = run.documents_found
        row.documents_saved = run.documents_saved
        row.error_count = run.error_count
        self._flush()
        return _collection_read(row)

    def get(self, project_id: ProjectId, run_id: RunId) -> CollectionRunRead | None:
        row = self.session.scalar(
            select(CollectionRunModel).where(
                CollectionRunModel.project_id == project_id,
                CollectionRunModel.id == run_id,
            )
        )
        return _collection_read(row) if row is not None else None

    def list_by_project(self, project_id: ProjectId) -> list[CollectionRunRead]:
        rows = self.session.scalars(
            select(CollectionRunModel)
            .where(CollectionRunModel.project_id == project_id)
            .order_by(CollectionRunModel.started_at, CollectionRunModel.id)
        ).all()
        return [_collection_read(row) for row in rows]


class SqlAlchemyDocumentRepository(_Repository):
    def list_canonical(self, project_id: ProjectId) -> list[CleanDocument]:
        duplicate = select(DocumentDuplicate.document_id).where(
            DocumentDuplicate.project_id == project_id,
            DocumentDuplicate.document_id == Document.id,
        ).exists()
        rows = self.session.scalars(select(Document).where(
            Document.project_id == project_id,
            Document.cleaned_at.is_not(None),
            ~duplicate,
        ).order_by(Document.id)).all()
        return [_clean_document(row) for row in rows]

    def upsert_raw(
        self,
        project_id: ProjectId,
        document: RawDocument,
        *,
        collection_run_id: RunId | None = None,
    ) -> DocumentRead:
        canonical_url = document.url.strip()
        row = self.session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.canonical_url == canonical_url,
            )
        )
        values = dict(
            collection_run_id=collection_run_id,
            source=document.source,
            channel=document.channel,
            platform=document.platform,
            title=document.title,
            url=document.url,
            canonical_url=canonical_url,
            url_hash=hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
            body=document.body,
            source_metadata={**document.metadata, "_aiporg_query": document.query},
            published_at=document.published_at,
            collected_at=document.collected_at,
        )
        if row is None:
            row = Document(id=document.document_id, project_id=project_id, **values)
            self.session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self._flush()
        return _raw_document(row)

    def upsert_clean(
        self, project_id: ProjectId, document: CleanDocument
    ) -> DocumentRead:
        row = self.session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.id == document.document_id,
            )
        )
        if row is None:
            raise RepositoryConflictError("raw document must exist before cleaning")
        row.title = document.title
        row.body = document.body
        row.canonical_url = document.canonical_url
        row.url_hash = hashlib.sha256(document.canonical_url.encode("utf-8")).hexdigest()
        row.cleaned_at = document.cleaned_at
        if document.source is not None:
            row.source = document.source
        if document.channel is not None:
            row.channel = document.channel
        if document.platform is not None:
            row.platform = document.platform
        if document.published_at is not None:
            row.published_at = document.published_at
        row.source_metadata = {
            **document.metadata,
            "_aiporg_query": document.query
            or row.source_metadata.get("_aiporg_query", ""),
        }
        self._flush()
        return _clean_document(row)

    def get_by_canonical_url(
        self, project_id: ProjectId, canonical_url: str
    ) -> DocumentRead | None:
        row = self.session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.canonical_url == canonical_url,
            )
        )
        if row is None:
            return None
        return _clean_document(row) if row.cleaned_at is not None else _raw_document(row)

    def list_raw_by_collection_run(
        self,
        project_id: ProjectId,
        collection_run_id: RunId,
    ) -> list[RawDocument]:
        rows = self.session.scalars(
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.collection_run_id == collection_run_id,
            )
            .order_by(Document.collected_at, Document.id)
        ).all()
        return [_raw_document(row) for row in rows]

    def get(self, project_id: ProjectId, document_id: UUID) -> DocumentRead | None:
        row = self.session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.id == document_id,
            )
        )
        if row is None:
            return None
        return _clean_document(row) if row.cleaned_at is not None else _raw_document(row)


class SqlAlchemyDuplicateClusterRepository(_Repository):
    def create(
        self, project_id: ProjectId, cluster: DuplicateClusterSchema
    ) -> DuplicateClusterRead:
        row = DuplicateCluster(
            id=cluster.cluster_id,
            project_id=project_id,
            canonical_document_id=cluster.canonical_document,
            unique_sources=cluster.unique_sources,
            distribution_count=cluster.distribution_count,
        )
        self.session.add(row)
        # No ORM relationship orders these inserts: persist the parent first.
        self._flush()
        for document_id in cluster.duplicates:
            self.session.add(
                DocumentDuplicate(
                    project_id=project_id,
                    cluster_id=cluster.cluster_id,
                    document_id=document_id,
                )
            )
        self._flush()
        return cluster

    def get(
        self, project_id: ProjectId, cluster_id: DuplicateClusterId
    ) -> DuplicateClusterRead | None:
        row = self.session.scalar(
            select(DuplicateCluster).where(
                DuplicateCluster.project_id == project_id,
                DuplicateCluster.id == cluster_id,
            )
        )
        if row is None:
            return None
        duplicate_ids = self.session.scalars(
            select(DocumentDuplicate.document_id).where(
                DocumentDuplicate.project_id == project_id,
                DocumentDuplicate.cluster_id == cluster_id,
            )
        ).all()
        return DuplicateClusterSchema(
            cluster_id=row.id,
            canonical_document=row.canonical_document_id,
            duplicates=list(duplicate_ids),
            unique_sources=row.unique_sources,
            distribution_count=row.distribution_count,
        )


class SqlAlchemyEvidenceRepository(_Repository):
    def create(self, evidence: EvidenceSchema) -> EvidenceRead:
        row = Evidence(
            id=evidence.evidence_id,
            project_id=evidence.project_id,
            excerpt=evidence.excerpt,
            created_at=evidence.created_at,
        )
        self.session.add(row)
        self.session.add(
            EvidenceDocument(
                project_id=evidence.project_id,
                evidence_id=evidence.evidence_id,
                document_id=evidence.document_id,
            )
        )
        self._flush()
        return evidence

    def get(self, project_id: ProjectId, evidence_id: EvidenceId) -> EvidenceRead | None:
        row = self.session.scalar(
            select(Evidence).where(Evidence.project_id == project_id, Evidence.id == evidence_id)
        )
        if row is None:
            return None
        document_id = self.session.scalar(
            select(EvidenceDocument.document_id).where(
                EvidenceDocument.project_id == project_id,
                EvidenceDocument.evidence_id == evidence_id,
            )
        )
        if document_id is None:
            raise RepositoryConflictError("evidence document link is missing")
        return EvidenceSchema(
            evidence_id=row.id,
            project_id=row.project_id,
            document_id=document_id,
            excerpt=row.excerpt,
            created_at=_aware(row.created_at),
        )

    def list_by_project(self, project_id: ProjectId) -> list[EvidenceRead]:
        rows = self.session.scalars(
            select(Evidence)
            .where(Evidence.project_id == project_id)
            .order_by(Evidence.created_at, Evidence.id)
        ).all()
        results = []
        for row in rows:
            document_id = self.session.scalar(
                select(EvidenceDocument.document_id).where(
                    EvidenceDocument.project_id == project_id,
                    EvidenceDocument.evidence_id == row.id,
                )
            )
            if document_id is None:
                raise RepositoryConflictError("evidence document link is missing")
            results.append(EvidenceSchema(
                evidence_id=row.id,
                project_id=row.project_id,
                document_id=document_id,
                excerpt=row.excerpt,
                created_at=_aware(row.created_at),
            ))
        return results


class SqlAlchemyFactRepository(_Repository):
    def save_batch(self, project_id: ProjectId, facts: list[FactSchema]) -> list[FactRead]:
        for fact in facts:
            row = self.session.scalar(
                select(Fact).where(Fact.project_id == project_id, Fact.id == fact.fact_id)
            )
            values = dict(
                claim=fact.claim,
                event_date=fact.event_date,
                entities=fact.entities,
                evidence_document_ids=[str(value) for value in fact.evidence_document_ids],
                source_count=fact.source_count,
                confidence=fact.confidence,
                status=fact.status,
            )
            if row is None:
                self.session.add(Fact(id=fact.fact_id, project_id=project_id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        self._flush()
        return list(facts)

    def save_numeric(
        self, project_id: ProjectId, fact_id: FactId, fact: NumericFactSchema
    ) -> NumericFactSchema:
        numeric_id = uuid5(
            NAMESPACE_URL,
            f"{project_id}:{fact_id}:{fact.metric}:{fact.value}:{fact.unit}",
        )
        self.session.add(
            NumericFact(
                id=numeric_id,
                project_id=project_id,
                fact_id=fact_id,
                metric=fact.metric,
                value=fact.value,
                unit=fact.unit,
                source=fact.source,
                confidence=fact.confidence,
            )
        )
        for evidence_id in fact.evidence_ids:
            self.session.add(
                NumericFactEvidence(
                    project_id=project_id,
                    numeric_fact_id=numeric_id,
                    evidence_id=evidence_id,
                )
            )
        self._flush()
        return fact

    def get(self, project_id: ProjectId, fact_id: FactId) -> FactRead | None:
        row = self.session.scalar(
            select(Fact).where(Fact.project_id == project_id, Fact.id == fact_id)
        )
        return _fact_read(row) if row is not None else None


class SqlAlchemyIssueRepository(_Repository):
    def list_by_project(self, project_id: ProjectId) -> list[IssueRead]:
        ids = self.session.scalars(select(Issue.id).where(
            Issue.project_id == project_id,
        ).order_by(Issue.id)).all()
        issues = []
        for issue_id in ids:
            issue = self.get(project_id, issue_id)
            if issue is None:
                raise RepositoryConflictError("issue disappeared during project listing")
            issues.append(issue)
        return issues

    def save_batch(self, project_id: ProjectId, issues: list[IssueSchema]) -> list[IssueRead]:
        for issue in issues:
            row = self.session.scalar(
                select(Issue).where(Issue.project_id == project_id, Issue.id == issue.issue_id)
            )
            if row is None:
                row = Issue(id=issue.issue_id, project_id=project_id)
                self.session.add(row)
            row.label = issue.label
            row.document_count = issue.document_count
            row.source_count = issue.source_count
            row.channel_count = issue.channel_count
            row.sentiment = None
            self.session.execute(
                delete(IssueFact).where(
                    IssueFact.project_id == project_id, IssueFact.issue_id == issue.issue_id
                )
            )
            self.session.execute(
                delete(IssueSubissue).where(
                    IssueSubissue.project_id == project_id,
                    IssueSubissue.issue_id == issue.issue_id,
                )
            )
            for fact_id in issue.fact_ids:
                self.session.add(IssueFact(project_id=project_id, issue_id=issue.issue_id, fact_id=fact_id))
            for position, detail in enumerate(issue.subissues):
                self.session.add(
                    IssueSubissue(
                        project_id=project_id,
                        issue_id=issue.issue_id,
                        position=position,
                        **detail.model_dump(),
                    )
                )
        self._flush()
        return list(issues)

    def get(self, project_id: ProjectId, issue_id: IssueId) -> IssueRead | None:
        row = self.session.scalar(
            select(Issue).where(Issue.project_id == project_id, Issue.id == issue_id)
        )
        if row is None:
            return None
        fact_ids = list(self.session.scalars(select(IssueFact.fact_id).where(
            IssueFact.project_id == project_id, IssueFact.issue_id == issue_id
        )).all())
        details = self.session.scalars(select(IssueSubissue).where(
            IssueSubissue.project_id == project_id, IssueSubissue.issue_id == issue_id
        ).order_by(IssueSubissue.position)).all()
        return IssueSchema(
            issue_id=row.id,
            label=row.label,
            fact_ids=fact_ids,
            document_count=row.document_count,
            source_count=row.source_count,
            channel_count=row.channel_count,
            subissues=[IssueDetailSchema(
                label=item.label,
                policy=item.policy,
                summary=item.summary,
                sentiment=item.sentiment,
                stance=item.stance,
            ) for item in details],
        )


class SqlAlchemyAnalyticsRepository(_Repository):
    def create(self, snapshot: AnalyticsSnapshotSchema) -> AnalyticsSnapshotRead:
        self.session.add(AnalyticsSnapshot(
            project_id=snapshot.project_id,
            run_id=snapshot.run.run_id,
            input_version=snapshot.run.input_version,
            output_version=snapshot.run.output_version,
            created_at=snapshot.run.created_at,
            metrics=snapshot.metrics,
        ))
        self._flush()
        return snapshot

    def get_latest(self, project_id: ProjectId) -> AnalyticsSnapshotRead | None:
        row = self.session.scalar(select(AnalyticsSnapshot).where(
            AnalyticsSnapshot.project_id == project_id
        ).order_by(AnalyticsSnapshot.created_at.desc(), AnalyticsSnapshot.id.desc()))
        if row is None:
            return None
        return AnalyticsSnapshotSchema(
            project_id=row.project_id,
            run=_versioned_run(row),
            metrics=row.metrics,
        )


class SqlAlchemyNarrativeRepository(_Repository):
    def save(self, project_id: ProjectId, context: NarrativeContext) -> NarrativeRead:
        identity = uuid5(NAMESPACE_URL, f"{project_id}:{context.model_dump_json()}")
        self.session.add(Narrative(
            id=identity,
            project_id=project_id,
            issue_id=context.issue.issue_id,
            context=context.model_dump(mode="json"),
            run_id=identity,
            input_version="narrative-context:v1",
            output_version="narrative-context:v1",
        ))
        self._flush()
        return context

    def get_latest(self, project_id: ProjectId) -> NarrativeRead | None:
        rows = self.session.scalars(select(Narrative).where(
            Narrative.project_id == project_id
        ).order_by(Narrative.created_at.desc(), Narrative.id.desc())).all()
        for row in rows:
            if not self._is_output_row(row.context):
                return NarrativeContext.model_validate(row.context)
        return None

    def save_output(
        self, project_id: ProjectId, output: NarrativeOutputSchema
    ) -> NarrativeOutputRead:
        if output.project_id != project_id:
            raise RepositoryConflictError("narrative output project_id does not match")
        self.session.add(Narrative(
            id=output.run.run_id,
            project_id=project_id,
            issue_id=None,
            context={"kind": "narrative_output", "data": output.model_dump(mode="json")},
            run_id=output.run.run_id,
            input_version=output.run.input_version,
            output_version=output.run.output_version,
        ))
        self._flush()
        return output

    def get_latest_output(self, project_id: ProjectId) -> NarrativeOutputRead | None:
        rows = self.session.scalars(select(Narrative).where(
            Narrative.project_id == project_id
        )).all()
        outputs = [
            NarrativeOutputSchema.model_validate(row.context["data"])
            for row in rows
            if self._is_output_row(row.context)
        ]
        if not outputs:
            return None
        # SQLite's CURRENT_TIMESTAMP (Narrative.created_at's server default)
        # only has 1-second resolution, so several versions saved within the
        # same second would tie under an SQL ORDER BY on it. Each output
        # carries its own higher-resolution run.created_at in the payload;
        # use that instead so "latest" is well-defined even when a user
        # regenerates a draft more than once within the same second.
        return max(outputs, key=lambda output: output.run.created_at)

    def list_outputs(self, project_id: ProjectId) -> list[NarrativeOutputRead]:
        rows = self.session.scalars(select(Narrative).where(
            Narrative.project_id == project_id
        )).all()
        outputs = [
            NarrativeOutputSchema.model_validate(row.context["data"])
            for row in rows
            if self._is_output_row(row.context)
        ]
        # Same reasoning as get_latest_output: order by each version's own
        # run.created_at, not the DB row's created_at (1-second resolution).
        outputs.sort(key=lambda output: output.run.created_at, reverse=True)
        return outputs

    def approve_output(
        self,
        project_id: ProjectId,
        run_id: UUID,
        approved: bool,
        approved_at: datetime | None,
    ) -> NarrativeOutputRead:
        row = self.session.scalar(select(Narrative).where(
            Narrative.project_id == project_id, Narrative.id == run_id
        ))
        if row is None or not self._is_output_row(row.context):
            raise RepositoryConflictError("narrative output does not exist")
        data = dict(row.context["data"])
        data["approved"] = approved
        data["approved_at"] = approved_at.isoformat() if approved_at is not None else None
        output = NarrativeOutputSchema.model_validate(data)
        row.context = {"kind": "narrative_output", "data": output.model_dump(mode="json")}
        self._flush()
        return output

    @staticmethod
    def _is_output_row(context: object) -> bool:
        return isinstance(context, dict) and context.get("kind") == "narrative_output"


class SqlAlchemyVisualizationRepository(_Repository):
    def create(self, asset: VisualizationAssetSchema) -> VisualizationAssetRead:
        self.session.add(Visualization(
            id=asset.visualization_id,
            project_id=asset.project_id,
            kind=asset.kind,
            title=asset.title,
            payload={},
            run_id=asset.visualization_id,
            input_version="visualization-asset:v1",
            output_version="visualization-asset:v1",
            created_at=asset.created_at,
        ))
        self._flush()
        return asset

    def list_by_project(self, project_id: ProjectId) -> list[VisualizationAssetRead]:
        rows = self.session.scalars(select(Visualization).where(
            Visualization.project_id == project_id
        ).order_by(Visualization.created_at, Visualization.id)).all()
        return [VisualizationAssetSchema(
            visualization_id=row.id,
            project_id=row.project_id,
            kind=row.kind,
            title=row.title,
            created_at=_aware(row.created_at),
        ) for row in rows if not self._is_output_row(row.payload)]

    def save_output(
        self, project_id: ProjectId, output: VisualizationOutputSchema
    ) -> VisualizationOutputRead:
        if output.project_id != project_id:
            raise RepositoryConflictError("visualization output project_id does not match")
        self.session.add(Visualization(
            id=output.run.run_id,
            project_id=project_id,
            kind=output.kind,
            title=output.title,
            payload={"kind": "visualization_output", "data": output.model_dump(mode="json")},
            run_id=output.run.run_id,
            input_version=output.run.input_version,
            output_version=output.run.output_version,
        ))
        self._flush()
        return output

    def get_latest_output(
        self, project_id: ProjectId, slot_key: str
    ) -> VisualizationOutputRead | None:
        outputs = self._outputs_for_slot(project_id, slot_key)
        if not outputs:
            return None
        return max(outputs, key=lambda output: output.run.created_at)

    def list_outputs(
        self, project_id: ProjectId, slot_key: str
    ) -> list[VisualizationOutputRead]:
        outputs = self._outputs_for_slot(project_id, slot_key)
        outputs.sort(key=lambda output: output.run.created_at, reverse=True)
        return outputs

    def approve_output(
        self,
        project_id: ProjectId,
        run_id: UUID,
        approved: bool,
        approved_at: datetime | None,
    ) -> VisualizationOutputRead:
        row = self.session.scalar(select(Visualization).where(
            Visualization.project_id == project_id, Visualization.id == run_id
        ))
        if row is None or not self._is_output_row(row.payload):
            raise RepositoryConflictError("visualization output does not exist")
        data = dict(row.payload["data"])
        data["approved"] = approved
        data["approved_at"] = approved_at.isoformat() if approved_at is not None else None
        output = VisualizationOutputSchema.model_validate(data)
        row.payload = {"kind": "visualization_output", "data": output.model_dump(mode="json")}
        self._flush()
        return output

    def _outputs_for_slot(
        self, project_id: ProjectId, slot_key: str
    ) -> list[VisualizationOutputSchema]:
        rows = self.session.scalars(select(Visualization).where(
            Visualization.project_id == project_id
        )).all()
        outputs = []
        for row in rows:
            if not self._is_output_row(row.payload):
                continue
            output = VisualizationOutputSchema.model_validate(row.payload["data"])
            if output.slot_key == slot_key:
                outputs.append(output)
        return outputs

    @staticmethod
    def _is_output_row(payload: object) -> bool:
        return isinstance(payload, dict) and payload.get("kind") == "visualization_output"


class SqlAlchemyReportRepository(_Repository):
    def create(self, report: ReportSchema) -> ReportRead:
        self.session.add(Report(
            id=report.report_id,
            project_id=report.project_id,
            context=report.context.model_dump(mode="json"),
            run_id=report.run.run_id,
            input_version=report.run.input_version,
            output_version=report.run.output_version,
            created_at=report.run.created_at,
        ))
        for position, asset in enumerate(report.visualizations):
            self.session.add(ReportVisualization(
                project_id=report.project_id,
                report_id=report.report_id,
                visualization_id=asset.visualization_id,
                position=position,
            ))
        self._flush()
        return report

    def get_latest(self, project_id: ProjectId) -> ReportRead | None:
        row = self.session.scalar(select(Report).where(
            Report.project_id == project_id
        ).order_by(Report.created_at.desc(), Report.id.desc()))
        if row is None:
            return None
        links = self.session.scalars(select(ReportVisualization).where(
            ReportVisualization.project_id == project_id,
            ReportVisualization.report_id == row.id,
        ).order_by(ReportVisualization.position)).all()
        assets = []
        for link in links:
            asset = self.session.get(Visualization, link.visualization_id)
            if asset is None:
                raise RepositoryConflictError("report visualization is missing")
            assets.append(VisualizationAssetSchema(
                visualization_id=asset.id,
                project_id=asset.project_id,
                kind=asset.kind,
                title=asset.title,
                created_at=_aware(asset.created_at),
            ))
        return ReportSchema(
            report_id=row.id,
            project_id=row.project_id,
            run=_versioned_run(row),
            context=NarrativeContext.model_validate(row.context),
            visualizations=assets,
        )


def _project_read(row: Project) -> ProjectRead:
    return ProjectRead(
        project_id=row.id,
        name=row.name,
        target=row.target,
        analysis_period=row.analysis_period,
        comparison_period=row.comparison_period,
        channels=row.channels,
    )


def _collection_read(row: CollectionRunModel) -> CollectionRunRead:
    return CollectionRun(
        id=row.id,
        project_id=row.project_id,
        channel=row.channel,
        query=row.query,
        started_at=_aware(row.started_at),
        completed_at=_aware(row.completed_at) if row.completed_at is not None else None,
        status=row.status,
        documents_found=row.documents_found,
        documents_saved=row.documents_saved,
        error_count=row.error_count,
    )


def _raw_document(row: Document) -> RawDocument:
    return RawDocument(
        document_id=row.id,
        source=row.source,
        channel=row.channel,
        platform=row.platform,
        title=row.title,
        url=row.url,
        published_at=_aware(row.published_at),
        query=row.source_metadata.get("_aiporg_query", ""),
        body=row.body,
        metadata={key: value for key, value in row.source_metadata.items() if key != "_aiporg_query"},
        collected_at=_aware(row.collected_at),
    )


def _clean_document(row: Document) -> CleanDocument:
    return CleanDocument(
        document_id=row.id,
        title=row.title,
        body=row.body,
        canonical_url=row.canonical_url,
        cleaned_at=_aware(row.cleaned_at or row.collected_at),
        source=row.source,
        channel=row.channel,
        platform=row.platform,
        published_at=_aware(row.published_at),
        query=row.source_metadata.get("_aiporg_query"),
        metadata={key: value for key, value in row.source_metadata.items() if key != "_aiporg_query"},
    )


def _fact_read(row: Fact) -> FactRead:
    return FactSchema(
        fact_id=row.id,
        claim=row.claim,
        event_date=row.event_date,
        entities=row.entities,
        evidence_document_ids=[UUID(value) for value in row.evidence_document_ids],
        source_count=row.source_count,
        confidence=row.confidence,
        status=row.status,
    )


def _versioned_run(row: AnalyticsSnapshot | Report) -> VersionedRunSchema:
    return VersionedRunSchema(
        run_id=row.run_id,
        input_version=row.input_version,
        output_version=row.output_version,
        created_at=_aware(row.created_at),
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
