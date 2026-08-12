"""키워드 조사 보고서 전용 데이터 모델."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


@dataclass
class KeywordReportSummary:
    analysis_period: str = ""
    channel_count: int = 0
    primary_keyword: str = ""
    positive_ratio: float = 0.0
    month_over_month: str = ""


@dataclass
class KeywordIssue:
    rank: int = 0
    title: str = ""
    subtitle: str = ""
    body: str = ""
    evidence: list[str] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    comparison_delta: str = ""
    representative_documents: list[str] = field(default_factory=list)


@dataclass
class ChannelTrendItem:
    channel: str = ""
    share_or_volume: float = 0.0
    change_direction: str = ""
    change_pct: float | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class RankedKeywordItem:
    rank: int = 0
    keyword: str = ""
    category: str = ""


@dataclass
class SentimentDriver:
    sentiment: str = ""
    title: str = ""
    detail: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass
class SourceReference:
    source_id: str = ""
    title: str = ""
    url: str = ""
    publisher: str = ""
    published_at: str = ""
    channel: str = ""


@dataclass
class KeywordReportModel:
    summary: KeywordReportSummary = field(default_factory=KeywordReportSummary)
    issues: list[KeywordIssue] = field(default_factory=list)
    channel_overview: list[ChannelTrendItem] = field(default_factory=list)
    top_keywords: list[RankedKeywordItem] = field(default_factory=list)
    sentiment_overview: dict[str, float] = field(default_factory=dict)
    positive_drivers: list[SentimentDriver] = field(default_factory=list)
    negative_drivers: list[SentimentDriver] = field(default_factory=list)
    implications: list[dict[str, str]] = field(default_factory=list)
    channel_recommendations: list[dict[str, str]] = field(default_factory=list)
    sources: list[SourceReference] = field(default_factory=list)
    methodology: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _encode(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "KeywordReportModel":
        return cls(
            summary=KeywordReportSummary(**raw.get("summary", {})),
            issues=[KeywordIssue(**item) for item in raw.get("issues", [])],
            channel_overview=[ChannelTrendItem(**item) for item in raw.get("channel_overview", [])],
            top_keywords=[RankedKeywordItem(**item) for item in raw.get("top_keywords", [])],
            sentiment_overview=raw.get("sentiment_overview", {}),
            positive_drivers=[SentimentDriver(**item) for item in raw.get("positive_drivers", [])],
            negative_drivers=[SentimentDriver(**item) for item in raw.get("negative_drivers", [])],
            implications=raw.get("implications", []),
            channel_recommendations=raw.get("channel_recommendations", []),
            sources=[SourceReference(**item) for item in raw.get("sources", [])],
            methodology=raw.get("methodology", []),
        )


def _encode(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _encode(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_encode(v) for v in obj]
    return obj
