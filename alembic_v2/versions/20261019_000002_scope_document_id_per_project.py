"""Scope documents.id uniqueness to (project_id, id) instead of globally.

Revision ID: 20261019_000002
Revises: 20260814_000001
Create Date: 2026-10-19 00:00:02

Every reference to documents.id already goes through the compound FK
(project_id, id) -- app/models/document.py's DuplicateCluster/
DocumentDuplicate and app/models/evidence.py's Evidence all declare
ForeignKeyConstraint(["project_id", "..."], ["documents.project_id",
"documents.id"]). Nothing relies on documents.id being globally unique by
itself. But the original migration made "id" the table's sole primary key,
so it WAS globally unique -- and document_id is a deterministic hash of the
URL alone (uuid5(NAMESPACE_URL, url), computed in each collector's fetch()),
with no project_id in the hash input. Two different monthly projects whose
keyword searches happen to find the same real-world URL therefore collided
on a UNIQUE constraint violation (confirmed live, 2026-10-19 -- see
HANDOFF.md). This migration makes (project_id, id) the primary key so the
same URL can be collected again under a different project.

SQLite can't ALTER a primary key in place, and Alembic's batch mode can't
target the original (unnamed) PrimaryKeyConstraint by name here -- so this
rebuilds the table directly: rename aside, create fresh with the new PK,
copy rows over, drop the renamed original.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261019_000002"
down_revision: Union[str, Sequence[str], None] = "20260814_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid()
JSON = sa.JSON()
DATETIME = sa.DateTime(timezone=True)
CHANNEL = sa.Enum("NEWS", "BLOG", "COMMUNITY", "SOCIAL", "VIDEO", name="channel_type")

_COLUMNS = [
    "project_id", "collection_run_id", "source", "channel", "platform", "title",
    "url", "canonical_url", "url_hash", "body", "metadata", "published_at",
    "collected_at", "cleaned_at", "id", "created_at",
]


def _create_documents_table(primary_key: tuple[str, ...]) -> None:
    op.create_table(
        "documents",
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("collection_run_id", UUID),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("channel", CHANNEL, nullable=False),
        sa.Column("platform", sa.String(255), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("canonical_url", sa.String(), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column("published_at", DATETIME, nullable=False),
        sa.Column("collected_at", DATETIME, nullable=False),
        sa.Column("cleaned_at", DATETIME),
        sa.Column("id", UUID, nullable=False),
        sa.Column("created_at", DATETIME, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id", "collection_run_id"],
            ["collection_runs.project_id", "collection_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(*primary_key),
        sa.UniqueConstraint("project_id", "canonical_url"),
        sa.UniqueConstraint("project_id", "url_hash"),
    )


def _rebuild(primary_key: tuple[str, ...]) -> None:
    # legacy_alter_table=ON stops SQLite from rewriting *other* tables' FK
    # clauses to follow the rename below (its modern default "helpfully"
    # repoints them at "documents_pre_v2", which then dangles once that
    # table is dropped -- confirmed by testing this migration without it).
    op.execute("PRAGMA foreign_keys=OFF")
    op.execute("PRAGMA legacy_alter_table=ON")
    op.rename_table("documents", "documents_pre_v2")
    _create_documents_table(primary_key)
    columns = ", ".join(_COLUMNS)
    op.execute(f"INSERT INTO documents ({columns}) SELECT {columns} FROM documents_pre_v2")
    op.drop_table("documents_pre_v2")
    op.execute("PRAGMA legacy_alter_table=OFF")
    op.execute("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    _rebuild(("project_id", "id"))


def downgrade() -> None:
    _rebuild(("id",))
