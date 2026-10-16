"""Create the AIPORG 2.0 Phase 0 persistence schema.

Revision ID: 20260814_000001
Revises:
Create Date: 2026-08-14 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260814_000001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid()
JSON = sa.JSON()
DATETIME = sa.DateTime(timezone=True)
WORKFLOW = sa.Enum(
    "CREATED", "QUERIES_READY", "COLLECTION_RUNNING", "COLLECTION_COMPLETED",
    "CLEANING_COMPLETED", "EVIDENCE_COMPLETED", "ISSUES_COMPLETED",
    "ANALYTICS_COMPLETED", "NARRATIVE_COMPLETED", "VISUALS_COMPLETED",
    "REPORT_COMPLETED", name="workflow_state",
)
CHANNEL = sa.Enum("NEWS", "BLOG", "COMMUNITY", "SOCIAL", "VIDEO", name="channel_type")
RUN_STATUS = sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="collection_run_status")
GRADE = sa.Enum("A", "B", "C", "D", name="confidence_grade")
FACT_STATUS = sa.Enum("VERIFIED", "SUPPORTED", "UNCERTAIN", "REJECTED", name="fact_status")
SENTIMENT = sa.Enum("POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED", name="sentiment_label")


def _timestamps(table: list[sa.Column]) -> list[sa.Column]:
    return table + [
        sa.Column("id", UUID, nullable=False),
        sa.Column("created_at", DATETIME, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "projects", *_timestamps([
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("target", JSON, nullable=False),
            sa.Column("analysis_period", JSON, nullable=False),
            sa.Column("comparison_period", JSON, nullable=False),
            sa.Column("channels", JSON, nullable=False),
            sa.Column("workflow_state", WORKFLOW, nullable=False),
        ]), sa.PrimaryKeyConstraint("id")
    )
    op.create_table(
        "query_sets", *_timestamps([sa.Column("project_id", UUID, nullable=False)]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "queries", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("query_set_id", UUID, nullable=False),
            sa.Column("query", sa.String(1024), nullable=False), sa.Column("channels", JSON, nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id", "query_set_id"], ["query_sets.project_id", "query_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "collection_runs", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("query_id", UUID, nullable=False),
            sa.Column("channel", CHANNEL, nullable=False), sa.Column("query", sa.String(1024), nullable=False),
            sa.Column("started_at", DATETIME, nullable=False), sa.Column("completed_at", DATETIME),
            sa.Column("status", RUN_STATUS, nullable=False), sa.Column("documents_found", sa.Integer(), nullable=False),
            sa.Column("documents_saved", sa.Integer(), nullable=False), sa.Column("error_count", sa.Integer(), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "query_id"], ["queries.project_id", "queries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "documents", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("collection_run_id", UUID),
            sa.Column("source", sa.String(255), nullable=False), sa.Column("channel", CHANNEL, nullable=False),
            sa.Column("platform", sa.String(255), nullable=False), sa.Column("title", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=False), sa.Column("canonical_url", sa.String(), nullable=False),
            sa.Column("url_hash", sa.String(64), nullable=False), sa.Column("body", sa.String(), nullable=False),
            sa.Column("metadata", JSON, nullable=False), sa.Column("published_at", DATETIME, nullable=False),
            sa.Column("collected_at", DATETIME, nullable=False), sa.Column("cleaned_at", DATETIME),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "collection_run_id"], ["collection_runs.project_id", "collection_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id"),
        sa.UniqueConstraint("project_id", "canonical_url"), sa.UniqueConstraint("project_id", "url_hash")
    )
    op.create_table(
        "duplicate_clusters", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("canonical_document_id", UUID, nullable=False),
            sa.Column("unique_sources", JSON, nullable=False), sa.Column("distribution_count", sa.Integer(), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "canonical_document_id"], ["documents.project_id", "documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "document_duplicates", sa.Column("project_id", UUID, nullable=False),
        sa.Column("cluster_id", UUID, nullable=False), sa.Column("document_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["project_id", "cluster_id"], ["duplicate_clusters.project_id", "duplicate_clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "document_id"], ["documents.project_id", "documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "cluster_id", "document_id")
    )
    op.create_table(
        "evidence", *_timestamps([sa.Column("project_id", UUID, nullable=False), sa.Column("excerpt", sa.String(), nullable=False)]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "evidence_documents", sa.Column("project_id", UUID, nullable=False), sa.Column("evidence_id", UUID, nullable=False), sa.Column("document_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["project_id", "evidence_id"], ["evidence.project_id", "evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "document_id"], ["documents.project_id", "documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "evidence_id", "document_id")
    )
    op.create_table(
        "facts", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("claim", sa.String(), nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False), sa.Column("entities", JSON, nullable=False),
            sa.Column("evidence_document_ids", JSON, nullable=False), sa.Column("source_count", sa.Integer(), nullable=False),
            sa.Column("confidence", GRADE, nullable=False), sa.Column("status", FACT_STATUS, nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "numeric_facts", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("fact_id", UUID, nullable=False),
            sa.Column("metric", sa.String(255), nullable=False), sa.Column("value", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(64), nullable=False), sa.Column("source", sa.String(255), nullable=False),
            sa.Column("confidence", GRADE, nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id", "fact_id"], ["facts.project_id", "facts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "numeric_fact_evidence", sa.Column("project_id", UUID, nullable=False), sa.Column("numeric_fact_id", UUID, nullable=False), sa.Column("evidence_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["project_id", "numeric_fact_id"], ["numeric_facts.project_id", "numeric_facts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "evidence_id"], ["evidence.project_id", "evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "numeric_fact_id", "evidence_id")
    )
    op.create_table(
        "issues", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("label", sa.String(255), nullable=False),
            sa.Column("document_count", sa.Integer(), nullable=False), sa.Column("source_count", sa.Integer(), nullable=False),
            sa.Column("channel_count", sa.Integer(), nullable=False), sa.Column("sentiment", SENTIMENT, nullable=True),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "issue_facts", sa.Column("project_id", UUID, nullable=False), sa.Column("issue_id", UUID, nullable=False), sa.Column("fact_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(["project_id", "issue_id"], ["issues.project_id", "issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "fact_id"], ["facts.project_id", "facts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "issue_id", "fact_id")
    )
    op.create_table(
        "issue_subissues", sa.Column("project_id", UUID, nullable=False), sa.Column("issue_id", UUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("label", sa.String(255), nullable=False),
        sa.Column("policy", sa.String(), nullable=False), sa.Column("summary", sa.String(), nullable=False), sa.Column("sentiment", SENTIMENT, nullable=False),
        sa.ForeignKeyConstraint(["project_id", "issue_id"], ["issues.project_id", "issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("issue_id", "position")
    )
    op.create_table(
        "analytics_snapshots", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("metrics", JSON, nullable=False),
            sa.Column("run_id", UUID, nullable=False), sa.Column("input_version", sa.String(64), nullable=False), sa.Column("output_version", sa.String(64), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id")
    )
    op.create_table(
        "visualizations", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("kind", sa.String(255), nullable=False), sa.Column("title", sa.String(255), nullable=False),
            sa.Column("payload", JSON, nullable=False), sa.Column("run_id", UUID, nullable=False), sa.Column("input_version", sa.String(64), nullable=False), sa.Column("output_version", sa.String(64), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "reports", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("context", JSON, nullable=False), sa.Column("run_id", UUID, nullable=False),
            sa.Column("input_version", sa.String(64), nullable=False), sa.Column("output_version", sa.String(64), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id", "id")
    )
    op.create_table(
        "narratives", *_timestamps([
            sa.Column("project_id", UUID, nullable=False), sa.Column("issue_id", UUID), sa.Column("context", JSON, nullable=False),
            sa.Column("run_id", UUID, nullable=False), sa.Column("input_version", sa.String(64), nullable=False), sa.Column("output_version", sa.String(64), nullable=False),
        ]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "issue_id"], ["issues.project_id", "issues.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id")
    )
    op.create_table(
        "report_visualizations", sa.Column("project_id", UUID, nullable=False), sa.Column("report_id", UUID, nullable=False), sa.Column("visualization_id", UUID, nullable=False), sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id", "report_id"], ["reports.project_id", "reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id", "visualization_id"], ["visualizations.project_id", "visualizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("report_id", "visualization_id"), sa.UniqueConstraint("report_id", "position")
    )


def downgrade() -> None:
    for table_name in (
        "report_visualizations", "narratives", "reports", "visualizations", "analytics_snapshots",
        "issue_subissues", "issue_facts", "issues", "numeric_fact_evidence", "numeric_facts", "facts",
        "evidence_documents", "evidence", "document_duplicates", "duplicate_clusters", "documents",
        "collection_runs", "queries", "query_sets", "projects",
    ):
        op.drop_table(table_name)

    bind = op.get_bind()
    for enum_type in (SENTIMENT, FACT_STATUS, GRADE, RUN_STATUS, CHANNEL, WORKFLOW):
        enum_type.drop(bind, checkfirst=True)
