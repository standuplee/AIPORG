"""Project and query persistence models."""

from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ChannelType, WorkflowState
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    analysis_period: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    comparison_period: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    channels: Mapped[list[ChannelType]] = mapped_column(JSON, nullable=False)
    workflow_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state"), nullable=False
    )


class QuerySet(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "query_sets"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )


class Query(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "queries"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        ForeignKeyConstraint(
            ["project_id", "query_set_id"],
            ["query_sets.project_id", "query_sets.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    query_set_id: Mapped[UUID] = mapped_column(
        nullable=False
    )
    query: Mapped[str] = mapped_column(String(1024), nullable=False)
    channels: Mapped[list[ChannelType]] = mapped_column(JSON, nullable=False)
