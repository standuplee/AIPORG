"""핵심 데이터 모델.

수집 단계(Document)부터 분석 결과(AnalysisResult), 최종 보고서 모델
(ReportModel)까지 파이프라인 전 구간에서 공유하는 dataclass 정의.

품질 원칙(PRD 12항):
- 모든 통계는 실제 수집 데이터(Document)에 근거한다.
- 핵심 이슈/문장은 evidence(원문 링크)로 역추적 가능해야 한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# 열거형
# --------------------------------------------------------------------------- #
class Channel(str, Enum):
    NEWS = "뉴스기사"
    X = "X(트위터)"
    INSTAGRAM = "인스타그램"
    YOUTUBE = "유튜브"
    COMMUNITY = "커뮤니티"
    BLOG = "블로그"
    RSS = "공공RSS"

    @property
    def short(self) -> str:
        return {
            Channel.NEWS: "뉴스",
            Channel.X: "X",
            Channel.INSTAGRAM: "인스타",
            Channel.YOUTUBE: "유튜브",
            Channel.COMMUNITY: "커뮤니티",
            Channel.BLOG: "블로그",
            Channel.RSS: "RSS",
        }[self]


class Sentiment(str, Enum):
    POSITIVE = "긍정"
    NEGATIVE = "부정"
    NEUTRAL = "중립"
    MIXED = "혼재"


# --------------------------------------------------------------------------- #
# 수집 데이터
# --------------------------------------------------------------------------- #
@dataclass
class Document:
    """수집된 개별 게시물/기사 1건 (PRD 6항: 수집 데이터)."""

    doc_id: str
    channel: Channel
    title: str
    body: str
    url: str
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    views: int = 0
    comments: int = 0
    likes: int = 0
    matched_keywords: list[str] = field(default_factory=list)
    # 분석 단계에서 채워지는 필드
    sentiment: Optional[Sentiment] = None
    cluster: Optional[str] = None
    entities: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["channel"] = self.channel.value
        d["sentiment"] = self.sentiment.value if self.sentiment else None
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        d = dict(d)
        d["channel"] = Channel(d["channel"])
        if d.get("sentiment"):
            d["sentiment"] = Sentiment(d["sentiment"])
        if d.get("published_at"):
            d["published_at"] = datetime.fromisoformat(d["published_at"])
        return cls(**d)


# --------------------------------------------------------------------------- #
# 분석 결과 구성요소
# --------------------------------------------------------------------------- #
@dataclass
class Issue:
    """핵심 이슈 1건 (보고서 Ⅱ-2 TOP10)."""

    rank: int
    category: str          # 행정/선거/경제/산업/도정/환경/복지 ...
    title: str
    volume: int            # 언급량(건)
    change_pct: float      # 전월 대비 증감률
    sentiment: Sentiment
    evidence: list[str] = field(default_factory=list)   # 대표 기사 URL
    ai_comment: str = ""   # AI 해설


@dataclass
class KeywordStat:
    keyword: str
    weight: float          # TF-IDF / 빈도 기반 가중치
    volume: int
    sentiment: Sentiment = Sentiment.NEUTRAL


@dataclass
class ChannelSentiment:
    channel: Channel
    positive: float
    neutral: float
    negative: float
    feature_text: str = ""     # 채널별 여론 특징
    feature_volume: int = 0


@dataclass
class SpecialTrend:
    """특이 온라인 동향 (보고서 Ⅲ-2, 표 3-1)."""

    title: str
    detail: str


@dataclass
class CoreKeyword:
    """핵심 키워드 상세 분석 (보고서 Ⅳ, 그림 4-1 카드)."""

    name: str
    volume: int
    sentiment: Sentiment
    change_pct: float
    analysis: str
    evidence: list[str] = field(default_factory=list)
    summary: str = ""              # 카드 한 줄 요약
    positive_point: str = ""       # ▲ 긍정/찬성 논지
    negative_point: str = ""       # ▼ 부정/반대 논지
    keywords: list[str] = field(default_factory=list)   # 핵심어


@dataclass
class JobEvaluation:
    """직무수행 평가 (보고서 Ⅴ, 그림 5-1)."""

    subject: str           # 평가 대상 (예: 박수현 충남지사)
    positive_pct: float
    negative_pct: float
    positive_reasons: list[str] = field(default_factory=list)
    negative_reasons: list[str] = field(default_factory=list)
    neutral_pct: float = 0.0                       # 모름·무응답
    comparison: dict[str, float] = field(default_factory=dict)  # 광역단체장 긍정평가 비교(%)
    highlight_region: str = ""                     # 비교 그래프 강조 지역


@dataclass
class Implication:
    """시사점 및 대응 제언 (보고서 Ⅵ, 표 6-1)."""

    topic: str
    headline: str          # 시사점 요약
    body: str              # 상세 분석
    response: str          # 대응 제언


# --------------------------------------------------------------------------- #
# 통합 분석 결과
# --------------------------------------------------------------------------- #
@dataclass
class AnalysisResult:
    """파이프라인 산출물. 보고서 렌더링의 단일 입력원(single source)."""

    total_volume: int
    prev_change_pct: float
    subject_volumes: dict[str, int] = field(default_factory=dict)   # 충남도정/충남지사 등
    subject_changes: dict[str, float] = field(default_factory=dict)  # 대상별 전월 대비 증감률
    positive_ratio: float = 0.0
    channel_share: dict[str, float] = field(default_factory=dict)   # 채널별 언급 비중
    daily_volume: dict[str, int] = field(default_factory=dict)      # 일별 추이
    top_issues: list[Issue] = field(default_factory=list)
    channel_sentiments: list[ChannelSentiment] = field(default_factory=list)
    overall_sentiment: dict[str, float] = field(default_factory=dict)  # 긍/중/부
    related_keywords: list[KeywordStat] = field(default_factory=list)
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    special_trends: list[SpecialTrend] = field(default_factory=list)
    core_keywords: list[CoreKeyword] = field(default_factory=list)
    job_evaluation: Optional[JobEvaluation] = None
    implications: list[Implication] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)    # NER 집계

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_encode(self), fh, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# 보고서 상위 모델 (입력 메타 + 분석 결과)
# --------------------------------------------------------------------------- #
@dataclass
class ReportMeta:
    project_name: str
    subject_name: str          # 분석 대상 지자체/기관 (충청남도)
    leader_title: str          # 도지사 / 시장 / 장관 ...
    leader_name: str           # 박수현
    period_start: date
    period_end: date
    keywords: dict[str, list[str]]     # 키워드 수집 체계 (구분 -> 키워드들)
    report_title: str
    tool_name: str = "Lucy 2.0(RSN)"

    @property
    def period_days(self) -> int:
        return (self.period_end - self.period_start).days + 1

    @property
    def year(self) -> int:
        return self.period_start.year

    @property
    def month(self) -> int:
        return self.period_start.month


@dataclass
class ReportModel:
    meta: ReportMeta
    analysis: AnalysisResult


# --------------------------------------------------------------------------- #
# 직렬화 헬퍼
# --------------------------------------------------------------------------- #
def _encode(obj):
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
