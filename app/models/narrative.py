"""Narrative persistence model."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, VersionedRunMixin


class Narrative(UUIDPrimaryKeyMixin, CreatedAtMixin, VersionedRunMixin, Base):
    __tablename__ = "narratives"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "issue_id"],
            ["issues.project_id", "issues.id"],
            ondelete="RESTRICT",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    issue_id: Mapped[UUID | None] = mapped_column(nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
