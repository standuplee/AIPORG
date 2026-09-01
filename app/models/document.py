"""Document and duplicate-cluster persistence models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ChannelType
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "canonical_url"),
        UniqueConstraint("project_id", "url_hash"),
        ForeignKeyConstraint(
            ["project_id", "collection_run_id"],
            ["collection_runs.project_id", "collection_runs.id"],
            ondelete="RESTRICT",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    collection_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DuplicateCluster(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "duplicate_clusters"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        ForeignKeyConstraint(
            ["project_id", "canonical_document_id"],
            ["documents.project_id", "documents.id"],
            ondelete="RESTRICT",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    canonical_document_id: Mapped[UUID] = mapped_column(nullable=False)
    unique_sources: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    distribution_count: Mapped[int] = mapped_column(Integer, nullable=False)


class DocumentDuplicate(Base):
    __tablename__ = "document_duplicates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "cluster_id"],
            ["duplicate_clusters.project_id", "duplicate_clusters.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "document_id"],
            ["documents.project_id", "documents.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    cluster_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
