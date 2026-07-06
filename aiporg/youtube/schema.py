"""YouTube 서브시스템 데이터 스키마 (pydantic).

개인정보 미수집 원칙: 댓글 작성자 이름/채널 URL/프로필은 저장하지 않으며,
작성자 식별은 단방향 해시(author_hash)로만 보관한다.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from pydantic import BaseModel, Field


def author_hash(name: Optional[str]) -> str:
    """작성자 표시명 -> 단방향 해시(원문 미저장)."""
    if not name:
        return ""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


class Video(BaseModel):
    video_id: str
    title: str = ""
    description: str = ""
    channel_title: str = ""
    published_at: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    url: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    sentiment: Optional[str] = None       # 긍정/부정/중립/혼재
    topic: Optional[str] = None


class Comment(BaseModel):
    comment_id: str
    video_id: str
    text: str = ""
    published_at: Optional[str] = None
    like_count: int = 0
    author_hash: str = ""                 # 이름/URL/프로필 저장 금지
    sentiment: Optional[str] = None


class KeywordStat(BaseModel):
    keyword: str
    frequency: int = 0
    weight: float = 0.0
    sentiment: str = "중립"


class TopicStat(BaseModel):
    topic: str
    video_count: int = 0
    view_sum: int = 0
    ratio: float = 0.0


class IssueStat(BaseModel):
    rank: int
    keyword: str
    topic: str = "기타"
    score: float = 0.0
    view_sum: int = 0
    comment_sum: int = 0
    video_count: int = 0
    sentiment: str = "중립"


class ChannelSentiment(BaseModel):
    positive: float = 0.0
    neutral: float = 0.0
    negative: float = 0.0
    mixed: float = 0.0
    total_analyzed: int = 0


class NotableTrend(BaseModel):
    title: str
    detail: str


class GovernorEvaluation(BaseModel):
    subject: str
    positive_pct: float = 0.0
    negative_pct: float = 0.0
    neutral_pct: float = 0.0
    positive_points: list[str] = Field(default_factory=list)
    negative_points: list[str] = Field(default_factory=list)
    note: str = ""


class YouTubeOverview(BaseModel):
    subject_name: str
    leader_name: str
    period_start: str
    period_end: str
    video_count: int = 0
    comment_count: int = 0
    total_views: int = 0
    total_likes: int = 0
    positive_ratio: float = 0.0
    narrative: str = ""


class YouTubeReport(BaseModel):
    """Report Generator 가 그대로 사용하는 최종 산출물."""

    source: str = "youtube"
    youtube_overview: YouTubeOverview
    channel_sentiment: ChannelSentiment
    top_keywords: list[KeywordStat] = Field(default_factory=list)
    top_topics: list[TopicStat] = Field(default_factory=list)
    top_videos: list[Video] = Field(default_factory=list)
    top_comments: list[Comment] = Field(default_factory=list)
    notable_trends: list[NotableTrend] = Field(default_factory=list)
    governor_evaluation: GovernorEvaluation
    recommendations: list[str] = Field(default_factory=list)
    ai_summary: str = ""
