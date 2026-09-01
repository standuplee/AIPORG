"""Report persistence model."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, VersionedRunMixin


class Report(UUIDPrimaryKeyMixin, CreatedAtMixin, VersionedRunMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ReportVisualization(Base):
    __tablename__ = "report_visualizations"
    __table_args__ = (
        UniqueConstraint("report_id", "position"),
        ForeignKeyConstraint(
            ["project_id", "report_id"],
            ["reports.project_id", "reports.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "visualization_id"],
            ["visualizations.project_id", "visualizations.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    report_id: Mapped[UUID] = mapped_column(primary_key=True)
    visualization_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
