"""Provider-neutral search hit. Distinct from app.schemas.document.SearchResult."""

from enum import Enum

import hashlib

from pydantic import AwareDatetime, Field, computed_field

from app.schemas.common import SchemaBase


class SearchProvider(str, Enum):
    NAVER = "NAVER"
    DAUM = "DAUM"


class SearchChannel(str, Enum):
    NEWS = "NEWS"
    WEB = "WEB"
    BLOG = "BLOG"
    CAFE = "CAFE"


class SearchResult(SchemaBase):
    provider: SearchProvider
    channel: SearchChannel
    query: str
    sort: str
    title: str
    snippet: str
    url: str
    original_url: str | None = None  # press-site URL when `url` is a portal relay
    published_at: AwareDatetime | None = None
    rank: int

    @computed_field
    @property
    def result_id(self) -> str:
        """Stable across runs: the same press URL always gets the same id."""
        from app.search.deduplicator import normalize_url

        return hashlib.sha1(normalize_url(self.original_url or self.url).encode()).hexdigest()[:12]


class PeriodStatus(str, Enum):
    IN_PERIOD = "IN_PERIOD"
    OUT_OF_PERIOD = "OUT_OF_PERIOD"
    UNKNOWN = "UNKNOWN"  # never dropped: the date is recovered from the article body
    HISTORICAL_ALLOWED = "HISTORICAL_ALLOWED"


class SourceType(str, Enum):
    GOVERNMENT = "GOVERNMENT"
    PUBLIC_AGENCY = "PUBLIC_AGENCY"
    LEGISLATURE = "LEGISLATURE"
    COMPANY = "COMPANY"
    NEWS = "NEWS"
    BLOG = "BLOG"
    COMMUNITY = "COMMUNITY"
    OTHER = "OTHER"


class NumericMention(SchemaBase):
    raw: str
    type: str  # MONEY / COUNT / PERCENT / DATE
    context: str


class SearchResultMetadata(SchemaBase):
    """Deterministic facts about a hit; no LLM involved."""

    source_type: SourceType
    period_status: PeriodStatus
    numeric_mentions: list[NumericMention]
    date_mentions: list[str]
    noise_flags: list[str]

    @property
    def structural_noise(self) -> bool:
        return bool(self.noise_flags)


class SearchResultAssessment(SchemaBase):
    """Qwen's judgement of one hit against one research question."""

    result_id: str
    research_question_id: str
    relevance_score: int = Field(ge=0, le=3)  # 0 irrelevant, 1 weak, 2 useful, 3 directly useful
    reason: str
    matched_terms: list[str]
    discovered_entities: list[str]


class AssessmentBatch(SchemaBase):
    assessments: list[SearchResultAssessment]


class AssessedResult(SchemaBase):
    result: SearchResult
    metadata: SearchResultMetadata
    assessment: SearchResultAssessment | None  # None: skipped as structural noise


class SearchAnalysisResult(SchemaBase):
    research_question_id: str
    results: list[AssessedResult]
    discovered_entities: list[str]
