import asyncio
import html
import re
from abc import ABC, abstractmethod

import requests

from app.search.schemas import SearchChannel, SearchResult


def clean_text(text: object) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(text or ""))).strip()


class SearchProviderBase(ABC):
    channels: frozenset[SearchChannel]

    @abstractmethod
    def _request(self, query: str, channel: SearchChannel, limit: int, sort: str) -> list[SearchResult]:
        """Blocking call; sort is "accuracy" or "recency"."""

    async def search(
        self, query: str, channel: SearchChannel, limit: int = 10, sort: str = "accuracy"
    ) -> list[SearchResult]:
        if channel not in self.channels:
            raise ValueError(f"{type(self).__name__} does not support {channel.value}")
        if sort not in ("accuracy", "recency"):
            raise ValueError("sort must be 'accuracy' or 'recency'")
        return await asyncio.to_thread(self._request, query, channel, limit, sort)

    @staticmethod
    def _get(url: str, **kwargs) -> dict:
        response = requests.get(url, timeout=15, **kwargs)
        response.raise_for_status()
        return response.json()
