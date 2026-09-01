"""Evidence persistence model."""

from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Evidence(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    excerpt: Mapped[str] = mapped_column(String, nullable=False)


class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "evidence_id"],
            ["evidence.project_id", "evidence.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "document_id"],
            ["documents.project_id", "documents.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
