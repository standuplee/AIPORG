"""Analytics snapshot persistence model."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, VersionedRunMixin


class AnalyticsSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, VersionedRunMixin, Base):
    __tablename__ = "analytics_snapshots"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
