"""Narrative input contracts for AIPORG 2.0."""

from app.core.enums import SentimentLabel
from app.schemas.common import SchemaBase
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueSchema


class NarrativeContext(SchemaBase):
    issue: IssueSchema
    facts: list[FactSchema]
    sentiment: SentimentLabel
    keywords: list[str]
    positive_reasons: list[str]
    negative_reasons: list[str]


NarrativeRead = NarrativeContext
