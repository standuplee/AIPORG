"""Search query contracts for AIPORG 2.0."""

from typing import TypeAlias
from uuid import UUID

from app.core.enums import ChannelType
from app.schemas.common import SchemaBase


QueryId: TypeAlias = UUID


class SearchQuery(SchemaBase):
    query: str
    channels: list[ChannelType]
