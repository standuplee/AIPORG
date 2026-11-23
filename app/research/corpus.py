"""Everything one issue's research collected, stored so the monthly report can count it in one place."""

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from app.schemas.common import SchemaBase
from app.schemas.research import IssueInput
from app.search.documents import FetchedDocument
from app.search.opinion import DiscussionPost
from app.search.schemas import SearchResult
from app.search.signals import source_type

_OPINION_SOURCE = {"BLOG": "BLOG", "CAFE": "COMMUNITY"}


class CorpusItem(SchemaBase):
    result_id: str
    channel: str  # NEWS | BLOG | CAFE | WEB, as the search engine reported it
    title: str
    url: str
    snippet: str
    published_at: AwareDatetime | None = None
    kind: Literal["FACT", "OPINION"]
    source_type: str
    body: str | None = None  # only when the article was actually fetched


class IssueCorpus(SchemaBase):
    issue: str
    region: str
    start_date: date
    end_date: date
    items: list[CorpusItem]
    search_log: list[dict] = []  # per-query yield of the opinion search (raw hits, kept, fit, discarded)


def build_corpus(
    issue: IssueInput, fact_hits: list[SearchResult], fetched: dict[str, FetchedDocument], opinion_posts: list[DiscussionPost]
) -> IssueCorpus:
    """One item per result_id; a post found by both searches stays a FACT item."""
    items: dict[str, CorpusItem] = {}
    for r in fact_hits:
        doc = fetched.get(r.result_id)
        items.setdefault(r.result_id, CorpusItem(
            result_id=r.result_id, channel=r.channel.value, title=r.title, url=r.original_url or r.url, snippet=r.snippet,
            published_at=r.published_at, kind="FACT", source_type=(doc.source_type if doc else source_type(r)).value,
            body=doc.text if doc else None))
    for p in opinion_posts:
        items.setdefault(p.result_id, CorpusItem(
            result_id=p.result_id, channel=p.channel, title=p.title, url=p.url, snippet=p.snippet,
            published_at=p.published_at, kind="OPINION", source_type=_OPINION_SOURCE.get(p.channel, "OTHER")))
    return IssueCorpus(issue=issue.issue, region=issue.region, start_date=issue.start_date, end_date=issue.end_date,
                       items=list(items.values()))


def save_corpus(path: Path, corpus: IssueCorpus) -> None:
    path.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")


def load_corpus(path: Path) -> IssueCorpus:
    return IssueCorpus.model_validate_json(path.read_text(encoding="utf-8"))
