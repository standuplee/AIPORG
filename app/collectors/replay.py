"""Hand an issue's already-collected corpus to the normal collection workflow; makes no network or LLM call."""

from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.core.enums import ChannelType
from app.research.corpus import CorpusItem, IssueCorpus
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


def map_channel(item: CorpusItem) -> ChannelType | None:
    """WEB counts only when it is a news source; anything else would need a channel 2.0 does not have."""
    if item.channel == "NEWS":
        return ChannelType.NEWS
    if item.channel == "BLOG":
        return ChannelType.BLOG
    if item.channel == "CAFE":
        return ChannelType.COMMUNITY
    if item.channel == "WEB" and item.source_type == "NEWS":
        return ChannelType.NEWS
    return None


def partition(corpus: IssueCorpus) -> tuple[list[tuple[CorpusItem, ChannelType]], dict[str, str]]:
    """Items 2.0 can ingest, and the held ones with why (2.0 documents need a publish date)."""
    usable, held = [], {}
    for item in corpus.items:
        channel = map_channel(item)
        if item.published_at is None:
            held[item.result_id] = "undated"
        elif channel is None:
            held[item.result_id] = "unmapped_channel"
        else:
            usable.append((item, channel))
    return usable, held


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


class ReplayCollector(BaseCollector):
    def __init__(self, corpus: IssueCorpus) -> None:
        self.corpus = corpus
        self.usable, self.held = partition(corpus)
        self._by_url = {item.url: item for item, _ in self.usable}

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        if query.query != self.corpus.issue:
            return []
        return [
            SearchResult(source=_host(item.url), channel=channel, title=item.title, url=item.url,
                         published_at=item.published_at, query=query.query)
            for item, channel in self.usable if channel in query.channels
        ]

    async def fetch(self, result: SearchResult) -> RawDocument:
        item = self._by_url[result.url]
        return RawDocument(
            **result.model_dump(), document_id=uuid5(NAMESPACE_URL, item.result_id), platform=result.channel.value,
            body=item.body or item.snippet or item.title,
            metadata={"body_available": item.body is not None, "kind": item.kind, "source_type": item.source_type},
            collected_at=datetime.now(timezone.utc),
        )
