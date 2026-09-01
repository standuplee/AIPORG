"""Fact and numeric-fact persistence models."""

from datetime import date
from uuid import UUID

from sqlalchemy import (
    Date,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ConfidenceGrade, FactStatus
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Fact(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "facts"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    claim: Mapped[str] = mapped_column(String, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    entities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[ConfidenceGrade] = mapped_column(
        Enum(ConfidenceGrade, name="confidence_grade"), nullable=False
    )
    status: Mapped[FactStatus] = mapped_column(
        Enum(FactStatus, name="fact_status"), nullable=False
    )


class NumericFact(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "numeric_facts"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        ForeignKeyConstraint(
            ["project_id", "fact_id"],
            ["facts.project_id", "facts.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    fact_id: Mapped[UUID] = mapped_column(nullable=False)
    metric: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[ConfidenceGrade] = mapped_column(
        Enum(ConfidenceGrade, name="confidence_grade"), nullable=False
    )


class NumericFactEvidence(Base):
    __tablename__ = "numeric_fact_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "numeric_fact_id"],
            ["numeric_facts.project_id", "numeric_facts.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "evidence_id"],
            ["evidence.project_id", "evidence.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    numeric_fact_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
