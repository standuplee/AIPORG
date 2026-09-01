"""Collection run persistence models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ChannelType, CollectionRunStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class CollectionRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        ForeignKeyConstraint(
            ["project_id", "query_id"],
            ["queries.project_id", "queries.id"],
            ondelete="RESTRICT",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    query_id: Mapped[UUID] = mapped_column(nullable=False)
    channel: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"), nullable=False
    )
    query: Mapped[str] = mapped_column(String(1024), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[CollectionRunStatus] = mapped_column(
        Enum(CollectionRunStatus, name="collection_run_status"), nullable=False
    )
    documents_found: Mapped[int] = mapped_column(Integer, nullable=False)
    documents_saved: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
