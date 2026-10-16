"""Issue and issue-fact association persistence models."""

from uuid import UUID

from sqlalchemy import Enum, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SentimentLabel
from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Issue(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("project_id", "id"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sentiment: Mapped[SentimentLabel | None] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label"), nullable=True
    )


class IssueFact(Base):
    __tablename__ = "issue_facts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "issue_id"],
            ["issues.project_id", "issues.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "fact_id"],
            ["facts.project_id", "facts.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    issue_id: Mapped[UUID] = mapped_column(primary_key=True)
    fact_id: Mapped[UUID] = mapped_column(primary_key=True)


class IssueSubissue(Base):
    __tablename__ = "issue_subissues"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "issue_id"],
            ["issues.project_id", "issues.id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    issue_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    policy: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    sentiment: Mapped[SentimentLabel] = mapped_column(
        Enum(SentimentLabel, name="sentiment_label"), nullable=False
    )
