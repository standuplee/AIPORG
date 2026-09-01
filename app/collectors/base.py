"""Provider-independent collector contract."""

from abc import ABC, abstractmethod

from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


class BaseCollector(ABC):
    """Discover and fetch documents without persistence or analysis side effects."""

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Return search results for a query."""

    @abstractmethod
    async def fetch(self, result: SearchResult) -> RawDocument:
        """Fetch one result and normalize it into a raw document."""
