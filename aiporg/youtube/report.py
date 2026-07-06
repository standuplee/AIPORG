"""Report Generator — YouTubeReport(JSON) 생성.

문체 규칙: 공공기관 개조식 음슴체 + 유튜브 채널 한정 표현. 유튜브를 전체 여론으로
일반화하지 않으며 '충남 도민은' 같은 표현을 쓰지 않는다.
"""
from __future__ import annotations

from .analyzer import sentiment as S
from .config import YouTubeConfig
from .schema import (ChannelSentiment, Comment, GovernorEvaluation, IssueStat,
                     KeywordStat, NotableTrend, TopicStat, Video, YouTubeOverview,
                     YouTubeReport)


def _overview_narrative(cfg: YouTubeConfig, videos: list[Video],
                        comments: list[Comment], sent: ChannelSentiment) -> str:
    total_views = sum(v.view_count for v in videos)
    top_kw = ", ".join(sorted({k for v in videos for k in v.matched_keywords})[:5])
    return (
        f"{cfg.period_start.year}년 {cfg.period_start.month}월 {cfg.subject_name} 관련 "
        f"유튜브 영상은 {len(videos)}건, 댓글은 {len(comments)}건이 수집됨. "
        f"해당 영상의 누적 조회수는 {total_views:,}회로 집계되며, 유튜브 채널 내에서 "
        f"{top_kw} 등에 대한 관심이 확대된 것으로 나타남. "
        f"영상 댓글에서는 긍정 {sent.positive}%, 부정 {sent.negative}%, "
        f"중립 {sent.neutral}%의 감성 분포가 확인됨."
    )


def _dedup_title(subject: str, title: str) -> str:
    """'충청남도'+'도지사' → '충청남도지사' (중복 음절 제거)."""
    if subject and title and subject[-1] == title[0]:
        return subject + title[1:]
    return subject + title


def _governor_eval(cfg: YouTubeConfig, videos: list[Video],
                   comments: list[Comment]) -> GovernorEvaluation:
    name = cfg.leader_name
    v_hit = [v for v in videos if name in f"{v.title} {v.description}"]
    hit_ids = {v.video_id for v in v_hit}
    # 도지사 관련 영상의 댓글까지 포함해 반응을 집계(제목만 보지 않음)
    c_hit = [c for c in comments if c.video_id in hit_ids or name in c.text]
    labels = [v.sentiment or S.classify(v.title) for v in v_hit] \
        + [c.sentiment or S.classify(c.text) for c in c_hit]
    agg = S.aggregate(labels)
    pos_pts, neg_pts = [], []
    if agg.positive > 0:
        pos_pts.append("정책·현장 행보 관련 긍정적 반응이 상대적으로 높게 나타남")
    if agg.negative > 0:
        neg_pts.append("일부 정책·현안에 대한 비판적 반응이 확인됨")
    return GovernorEvaluation(
        subject=f"{name} {_dedup_title(cfg.subject_name, cfg.leader_title)}",
        positive_pct=agg.positive, negative_pct=agg.negative, neutral_pct=agg.neutral,
        positive_points=pos_pts, negative_points=neg_pts,
        note=("본 평가는 유튜브 채널 내 영상·댓글에 한정된 반응으로, 전체 여론을 "
              "대표하지 않음. 유튜브 이용자 중심의 반응으로 해석함"),
    )


def _recommendations(issues: list[IssueStat], sent: ChannelSentiment) -> list[str]:
    recs: list[str] = []
    if issues:
        recs.append(f"유튜브 채널 내 관심이 집중된 '{issues[0].keyword}' 관련 "
                    f"정확한 정보 제공 콘텐츠 확대가 필요한 것으로 판단됨")
    neg = [i for i in issues if i.sentiment == "부정"]
    if neg:
        recs.append(f"영상 댓글에서 부정 여론이 형성된 '{neg[0].keyword}' 관련 "
                    f"오해 해소 및 소통 강화가 필요한 것으로 판단됨")
    if sent.negative >= 30:
        recs.append("유튜브 이용자 중심의 부정 여론에 대한 사실관계 설명 콘텐츠 "
                    "제작이 필요한 것으로 판단됨")
    recs.append("유튜브 채널을 하나의 여론 창구로 활용한 정기 모니터링 지속이 "
                "필요한 것으로 판단됨")
    return recs[:4]


def build_report(cfg: YouTubeConfig, videos: list[Video], comments: list[Comment],
                 keywords: list[KeywordStat], topics: list[TopicStat],
                 issues: list[IssueStat], trends: list[NotableTrend],
                 channel_sentiment: ChannelSentiment, ai_summary: str) -> YouTubeReport:
    top_videos = sorted(videos, key=lambda v: v.view_count, reverse=True)[:10]
    top_comments = sorted(comments, key=lambda c: c.like_count, reverse=True)[:10]
    overview = YouTubeOverview(
        subject_name=cfg.subject_name, leader_name=cfg.leader_name,
        period_start=cfg.period_start.isoformat(), period_end=cfg.period_end.isoformat(),
        video_count=len(videos), comment_count=len(comments),
        total_views=sum(v.view_count for v in videos),
        total_likes=sum(v.like_count for v in videos),
        positive_ratio=channel_sentiment.positive,
        narrative=_overview_narrative(cfg, videos, comments, channel_sentiment),
    )
    return YouTubeReport(
        youtube_overview=overview,
        channel_sentiment=channel_sentiment,
        top_keywords=keywords[:20],
        top_topics=topics,
        top_videos=top_videos,
        top_comments=top_comments,
        notable_trends=trends,
        governor_evaluation=_governor_eval(cfg, videos, comments),
        recommendations=_recommendations(issues, channel_sentiment),
        ai_summary=ai_summary,
    )
