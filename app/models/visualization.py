"""Visualization persistence model."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, VersionedRunMixin


class Visualization(UUIDPrimaryKeyMixin, CreatedAtMixin, VersionedRunMixin, Base):
    __tablename__ = "visualizations"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
