"""Collected and cleaned document contracts for AIPORG 2.0."""

from typing import TypeAlias
from uuid import UUID

from app.core.enums import ChannelType
from app.schemas.common import SchemaBase
from pydantic import AwareDatetime, Field


DocumentId: TypeAlias = UUID
DuplicateClusterId: TypeAlias = UUID


class SearchResult(SchemaBase):
    source: str
    channel: ChannelType
    title: str
    url: str
    published_at: AwareDatetime
    query: str


class RawDocument(SearchResult):
    document_id: DocumentId
    platform: str
    body: str
    metadata: dict[str, object]
    collected_at: AwareDatetime


class CleanDocument(SchemaBase):
    document_id: DocumentId
    title: str
    body: str
    canonical_url: str
    cleaned_at: AwareDatetime
    source: str | None = None
    channel: ChannelType | None = None
    platform: str | None = None
    published_at: AwareDatetime | None = None
    query: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class DuplicateClusterSchema(SchemaBase):
    cluster_id: DuplicateClusterId
    canonical_document: DocumentId
    duplicates: list[DocumentId]
    unique_sources: list[str]
    distribution_count: int


DocumentRead = RawDocument | CleanDocument
DuplicateClusterRead = DuplicateClusterSchema
