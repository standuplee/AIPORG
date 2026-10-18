"""Protocol contract tests for AIPORG 2.0 repositories."""

from typing import Protocol, get_type_hints

from app.repositories.analytics import AnalyticsRepository
from app.repositories.base import SessionScopedRepository
from app.repositories.collection import CollectionRunRepository, QuerySetRepository
from app.repositories.document import DocumentRepository
from app.repositories.duplicate_cluster import DuplicateClusterRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.fact import FactRepository
from app.repositories.issue import IssueRepository
from app.repositories.narrative import NarrativeRepository
from app.repositories.project import ProjectRepository
from app.repositories.report import ReportRepository
from app.repositories.visualization import VisualizationRepository
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.collection import CollectionRun
from app.schemas.common import ProjectId, RunId
from app.schemas.document import (
    CleanDocument,
    DuplicateClusterRead,
    DuplicateClusterSchema,
    RawDocument,
)
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueSchema
from app.schemas.narrative import NarrativeContext
from app.schemas.project import ProjectCreate, ProjectRead, ProjectWorkflowSnapshot
from app.schemas.query import QueryId, SearchQuery
from app.schemas.report import ReportSchema
from app.schemas.collection import CollectionRunRead
from app.schemas.document import DocumentRead
from app.schemas.visualization import VisualizationAssetSchema


def test_repository_protocols_are_session_scoped() -> None:
    protocols = (
        ProjectRepository,
        QuerySetRepository,
        CollectionRunRepository,
        DocumentRepository,
        DuplicateClusterRepository,
        EvidenceRepository,
        FactRepository,
        IssueRepository,
        AnalyticsRepository,
        NarrativeRepository,
        VisualizationRepository,
        ReportRepository,
    )

    assert getattr(SessionScopedRepository, "_is_protocol", False)
    assert "session" not in SessionScopedRepository.__dict__
    assert all(SessionScopedRepository in protocol.__mro__ for protocol in protocols)


def test_project_repository_has_schema_typed_create_and_get() -> None:
    assert getattr(ProjectRepository, "_is_protocol", False)
    assert {"create", "get", "list", "get_workflow", "advance_workflow"} <= set(
        ProjectRepository.__dict__
    )

    create_hints = get_type_hints(ProjectRepository.create)
    get_hints = get_type_hints(ProjectRepository.get)

    assert create_hints["project"] is ProjectCreate
    assert create_hints["return"] is ProjectRead
    assert get_hints["return"] == ProjectRead | None
    assert get_type_hints(ProjectRepository.list)["return"] == list[ProjectRead]
    assert get_type_hints(ProjectRepository.get_workflow)["return"] == (
        ProjectWorkflowSnapshot | None
    )


def test_queryset_and_collection_run_repositories_use_existing_schemas() -> None:
    assert {"create", "get"} <= set(QuerySetRepository.__dict__)
    assert {"start", "complete", "get", "list_by_project"} <= set(
        CollectionRunRepository.__dict__
    )

    assert get_type_hints(QuerySetRepository.create)["queries"] == list[SearchQuery]
    assert get_type_hints(QuerySetRepository.create)["return"] == list[SearchQuery]
    start_hints = get_type_hints(CollectionRunRepository.start)
    complete_hints = get_type_hints(CollectionRunRepository.complete)

    assert start_hints["project_id"] is ProjectId
    assert start_hints["query_id"] is QueryId
    assert start_hints["run"] is CollectionRun
    assert start_hints["return"] is CollectionRunRead
    assert complete_hints["project_id"] is ProjectId
    assert complete_hints["run_id"] is RunId
    assert complete_hints["run"] is CollectionRun
    assert complete_hints["return"] is CollectionRunRead
    get_hints = get_type_hints(CollectionRunRepository.get)
    assert get_hints["return"] == CollectionRunRead | None
    assert get_type_hints(CollectionRunRepository.list_by_project)["return"] == list[
        CollectionRunRead
    ]


def test_document_repository_has_schema_typed_upsert_and_canonical_lookup() -> None:
    assert {
        "upsert_raw",
        "upsert_clean",
        "get_by_canonical_url",
        "list_raw_by_collection_run",
        "get",
    } <= set(
        DocumentRepository.__dict__
    )

    upsert_hints = get_type_hints(DocumentRepository.upsert_raw)
    upsert_clean_hints = get_type_hints(DocumentRepository.upsert_clean)
    lookup_hints = get_type_hints(DocumentRepository.get_by_canonical_url)

    assert upsert_hints["document"] is RawDocument
    assert upsert_hints["return"] is DocumentRead
    assert upsert_clean_hints["project_id"] is ProjectId
    assert upsert_clean_hints["document"] is CleanDocument
    assert upsert_clean_hints["return"] is DocumentRead
    assert lookup_hints["return"] == DocumentRead | None


def test_duplicate_cluster_repository_is_project_scoped_and_schema_typed() -> None:
    assert getattr(DuplicateClusterRepository, "_is_protocol", False)
    assert {"create", "get"} <= set(DuplicateClusterRepository.__dict__)

    create_hints = get_type_hints(DuplicateClusterRepository.create)
    get_hints = get_type_hints(DuplicateClusterRepository.get)

    assert create_hints["project_id"] is ProjectId
    assert create_hints["cluster"] is DuplicateClusterSchema
    assert create_hints["return"] is DuplicateClusterRead
    assert get_hints["project_id"] is ProjectId
    assert get_hints["return"] == DuplicateClusterRead | None


def test_remaining_repositories_expose_schema_typed_phase_zero_operations() -> None:
    expected_methods = {
        EvidenceRepository: {"create", "get", "list_by_project"},
        FactRepository: {"save_batch", "get"},
        IssueRepository: {"save_batch", "get"},
        AnalyticsRepository: {"create", "get_latest"},
        NarrativeRepository: {
            "save", "get_latest", "save_output", "get_latest_output", "list_outputs",
            "approve_output",
        },
        VisualizationRepository: {
            "create", "list_by_project", "save_output", "get_latest_output",
            "list_outputs", "approve_output",
        },
        ReportRepository: {"create", "get_latest"},
    }

    expected_annotations = {
        EvidenceRepository.create: EvidenceSchema,
        FactRepository.save_batch: list[FactSchema],
        IssueRepository.save_batch: list[IssueSchema],
        AnalyticsRepository.create: AnalyticsSnapshotSchema,
        NarrativeRepository.save: NarrativeContext,
        VisualizationRepository.create: VisualizationAssetSchema,
        ReportRepository.create: ReportSchema,
    }

    for protocol, methods in expected_methods.items():
        assert getattr(protocol, "_is_protocol", False)
        assert methods <= set(protocol.__dict__)

    for method, expected_input in expected_annotations.items():
        hints = get_type_hints(method)
        input_hints = [value for name, value in hints.items() if name not in {"return", "self"}]
        assert expected_input in input_hints


def test_repository_contracts_do_not_depend_on_sqlalchemy_models() -> None:
    protocols: tuple[type[Protocol], ...] = (
        ProjectRepository,
        QuerySetRepository,
        CollectionRunRepository,
        DocumentRepository,
        DuplicateClusterRepository,
        EvidenceRepository,
        FactRepository,
        IssueRepository,
        AnalyticsRepository,
        NarrativeRepository,
        VisualizationRepository,
        ReportRepository,
    )

    for protocol in protocols:
        annotations = str(get_type_hints(protocol))
        for method_name, method in protocol.__dict__.items():
            if callable(method):
                annotations += str(get_type_hints(method))
        assert "app.models" not in annotations


def test_analytics_inputs_use_existing_project_scoped_contracts() -> None:
    assert get_type_hints(DocumentRepository.list_canonical) == {
        "project_id": ProjectId, "return": list[CleanDocument],
    }
    assert get_type_hints(IssueRepository.list_by_project) == {
        "project_id": ProjectId, "return": list[IssueSchema],
    }
