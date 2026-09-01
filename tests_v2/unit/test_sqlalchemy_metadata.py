from uuid import UUID

from sqlalchemy import Enum, ForeignKeyConstraint, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped

from app.core.enums import ChannelType
from app.models import Base
from app.models.document import Document
from app.models.narrative import Narrative
from app.models.project import Project


REQUIRED_TABLES = {
    "projects",
    "query_sets",
    "queries",
    "collection_runs",
    "documents",
    "duplicate_clusters",
    "document_duplicates",
    "evidence",
    "evidence_documents",
    "facts",
    "numeric_facts",
    "numeric_fact_evidence",
    "issues",
    "issue_facts",
    "issue_subissues",
    "analytics_snapshots",
    "narratives",
    "visualizations",
    "reports",
    "report_visualizations",
}


def test_metadata_contains_required_tables() -> None:
    assert REQUIRED_TABLES <= set(Base.metadata.tables)


def test_documents_unique_constraint_uses_project_id_and_canonical_url() -> None:
    documents = Base.metadata.tables["documents"]
    unique_constraints = [
        constraint
        for constraint in documents.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        tuple(column.name for column in constraint.columns)
        == ("project_id", "canonical_url")
        for constraint in unique_constraints
    )


def test_projects_id_is_uuid_primary_key_and_reports_reference_it() -> None:
    projects = Base.metadata.tables["projects"]
    reports = Base.metadata.tables["reports"]

    assert projects.c.id.primary_key is True
    assert isinstance(projects.c.id.type, Uuid)
    assert {foreign_key.target_fullname for foreign_key in reports.c.project_id.foreign_keys} == {
        "projects.id"
    }


def test_normalized_associations_and_subissues_have_enforceable_foreign_keys() -> None:
    evidence = Base.metadata.tables["evidence"]
    evidence_documents = Base.metadata.tables["evidence_documents"]
    numeric_facts = Base.metadata.tables["numeric_facts"]
    numeric_fact_evidence = Base.metadata.tables["numeric_fact_evidence"]
    issue_subissues = Base.metadata.tables["issue_subissues"]
    report_visualizations = Base.metadata.tables["report_visualizations"]

    assert "document_id" not in evidence.c
    assert {foreign_key.target_fullname for foreign_key in evidence_documents.c.evidence_id.foreign_keys} == {
        "evidence.id"
    }
    assert {foreign_key.target_fullname for foreign_key in evidence_documents.c.document_id.foreign_keys} == {
        "documents.id"
    }
    assert "evidence_ids" not in numeric_facts.c
    assert {
        foreign_key.target_fullname
        for foreign_key in numeric_fact_evidence.c.numeric_fact_id.foreign_keys
    } == {"numeric_facts.id"}
    assert {foreign_key.target_fullname for foreign_key in numeric_fact_evidence.c.evidence_id.foreign_keys} == {
        "evidence.id"
    }
    assert {foreign_key.target_fullname for foreign_key in issue_subissues.c.issue_id.foreign_keys} == {
        "issues.id"
    }
    assert {"label", "policy", "summary", "sentiment", "position"} <= set(
        issue_subissues.c.keys()
    )
    assert {foreign_key.target_fullname for foreign_key in report_visualizations.c.report_id.foreign_keys} == {
        "reports.id"
    }
    assert {
        foreign_key.target_fullname
        for foreign_key in report_visualizations.c.visualization_id.foreign_keys
    } == {"visualizations.id"}
    assert "position" in report_visualizations.c


def test_dependent_links_use_project_scoped_composite_foreign_keys() -> None:
    def composite_foreign_keys(table_name: str) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
        table = Base.metadata.tables[table_name]
        return {
            (
                tuple(element.parent.name for element in constraint.elements),
                tuple(element.target_fullname for element in constraint.elements),
            )
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint) and len(constraint.elements) == 2
        }

    def has_project_scoped_identity(table_name: str) -> bool:
        return any(
            tuple(column.name for column in constraint.columns) == ("project_id", "id")
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, UniqueConstraint)
        )

    expected_foreign_keys = {
        "queries": {
            (("project_id", "query_set_id"), ("query_sets.project_id", "query_sets.id")),
        },
        "collection_runs": {
            (("project_id", "query_id"), ("queries.project_id", "queries.id")),
        },
        "documents": {
            (("project_id", "collection_run_id"), ("collection_runs.project_id", "collection_runs.id")),
        },
        "duplicate_clusters": {
            (("project_id", "canonical_document_id"), ("documents.project_id", "documents.id")),
        },
        "document_duplicates": {
            (("project_id", "cluster_id"), ("duplicate_clusters.project_id", "duplicate_clusters.id")),
            (("project_id", "document_id"), ("documents.project_id", "documents.id")),
        },
        "evidence_documents": {
            (("project_id", "evidence_id"), ("evidence.project_id", "evidence.id")),
            (("project_id", "document_id"), ("documents.project_id", "documents.id")),
        },
        "numeric_facts": {
            (("project_id", "fact_id"), ("facts.project_id", "facts.id")),
        },
        "numeric_fact_evidence": {
            (("project_id", "numeric_fact_id"), ("numeric_facts.project_id", "numeric_facts.id")),
            (("project_id", "evidence_id"), ("evidence.project_id", "evidence.id")),
        },
        "issue_facts": {
            (("project_id", "issue_id"), ("issues.project_id", "issues.id")),
            (("project_id", "fact_id"), ("facts.project_id", "facts.id")),
        },
        "issue_subissues": {
            (("project_id", "issue_id"), ("issues.project_id", "issues.id")),
        },
        "narratives": {
            (("project_id", "issue_id"), ("issues.project_id", "issues.id")),
        },
        "report_visualizations": {
            (("project_id", "report_id"), ("reports.project_id", "reports.id")),
            (("project_id", "visualization_id"), ("visualizations.project_id", "visualizations.id")),
        },
    }

    for table_name, expected in expected_foreign_keys.items():
        assert expected <= composite_foreign_keys(table_name)

    for table_name in {
        "query_sets",
        "queries",
        "collection_runs",
        "documents",
        "duplicate_clusters",
        "evidence",
        "facts",
        "numeric_facts",
        "issues",
        "reports",
        "visualizations",
    }:
        assert has_project_scoped_identity(table_name)


def test_enum_columns_exist_on_collection_runs_and_facts() -> None:
    collection_status = Base.metadata.tables["collection_runs"].c.status
    fact_status = Base.metadata.tables["facts"].c.status

    assert isinstance(collection_status.type, Enum)
    assert isinstance(fact_status.type, Enum)


def test_model_annotations_match_channel_and_nullable_columns() -> None:
    assert Project.__annotations__["channels"] == Mapped[list[ChannelType]]
    assert Document.__annotations__["collection_run_id"] == Mapped[UUID | None]
    assert Narrative.__annotations__["issue_id"] == Mapped[UUID | None]
