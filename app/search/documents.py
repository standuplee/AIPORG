"""Fetched article and its question-specific, evidence-grounded assessment."""

from enum import Enum

from pydantic import AwareDatetime, Field

from app.schemas.common import SchemaBase
from app.search.schemas import SourceType


class FetchStatus(str, Enum):
    OK = "OK"
    HTTP_ERROR = "HTTP_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"  # pdf/hwp/etc.; not parsed in this step
    EMPTY_TEXT = "EMPTY_TEXT"  # often JS-rendered pages


class PublishedAtSource(str, Enum):
    JSON_LD = "JSON_LD"
    ARTICLE_META = "ARTICLE_META"
    OPEN_GRAPH = "OPEN_GRAPH"
    TIME_TAG = "TIME_TAG"
    SEARCH_API = "SEARCH_API"
    TEXT_PATTERN = "TEXT_PATTERN"
    UNKNOWN = "UNKNOWN"


class FetchedDocument(SchemaBase):
    result_id: str
    research_question_id: str
    requested_url: str
    final_url: str | None = None
    fetch_status: FetchStatus
    http_status: int | None = None
    title: str | None = None
    author: str | None = None
    published_at: AwareDatetime | None = None
    published_at_source: PublishedAtSource = PublishedAtSource.UNKNOWN
    source_type: SourceType
    text: str | None = None
    text_length: int = 0
    extraction_method: str | None = None
    error: str | None = None


class KeyFact(SchemaBase):
    fact: str = Field(min_length=1)
    source_result_ids: list[str]


class TimelineItem(SchemaBase):
    date: str | None = None  # as written in the sources; not normalised or guessed
    event: str = Field(min_length=1)
    source_result_ids: list[str]


class FactResearchResult(SchemaBase):
    """Qwen's synthesis of the fetched documents; every fact points back to result ids."""

    summary: str
    key_facts: list[KeyFact]
    organizations: list[str]
    persons: list[str]
    locations: list[str]
    current_status: str | None = None
    timeline: list[TimelineItem]
    uncertainties: list[str]  # conflicting or unconfirmed points, marked "확인 필요"
    missing_information: list[str]  # only key gaps a report would clearly need
