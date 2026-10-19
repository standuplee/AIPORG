"""Issue contracts for AIPORG 2.0."""

from typing import Annotated, TypeAlias
from uuid import UUID

from app.core.enums import SentimentLabel, StanceLabel
from app.schemas.common import SchemaBase
from app.schemas.fact import FactId
from pydantic import Field


IssueId: TypeAlias = UUID


class IssueCandidateSchema(SchemaBase):
    issue_id: IssueId
    label: str
    fact_ids: Annotated[list[FactId], Field(min_length=1)]
    document_count: Annotated[int, Field(ge=0)]
    source_count: Annotated[int, Field(ge=0)]
    channel_count: Annotated[int, Field(ge=0)]


class IssueDetailSchema(SchemaBase):
    label: str
    policy: str
    summary: str
    sentiment: SentimentLabel
    stance: StanceLabel


class IssueSchema(IssueCandidateSchema):
    subissues: list[IssueDetailSchema]


IssueRead = IssueSchema
