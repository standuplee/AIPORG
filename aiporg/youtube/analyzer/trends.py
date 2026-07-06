"""특이 동향 분석 (유튜브 채널 한정).

- 조회수/댓글 급증 이슈, 부정 여론 집중 이슈, 긍정 확산 이슈를 도출한다.
- 문체는 유튜브 채널 한정 표현을 사용한다("영상 댓글에서는", "유튜브 이용자 중심으로").
"""
from __future__ import annotations

from .issues import IssueStat
from ..schema import Comment, NotableTrend, Video


def detect(videos: list[Video], comments: list[Comment],
           issues: list[IssueStat]) -> list[NotableTrend]:
    trends: list[NotableTrend] = []
    if not videos:
        return trends

    # 1) 최다 조회 이슈
    if issues:
        top = issues[0]
        trends.append(NotableTrend(
            title=f"'{top.keyword}' 관련 영상 관심 집중",
            detail=(f"유튜브 채널 내에서 '{top.keyword}' 관련 영상 {top.video_count}건이 "
                    f"조회수 {top.view_sum:,}회로 집계되며 이용자 관심이 확대됨")))

    # 2) 부정 여론 집중 이슈
    neg = [i for i in issues if i.sentiment == "부정"]
    if neg:
        n = neg[0]
        trends.append(NotableTrend(
            title=f"'{n.keyword}' 관련 부정 여론 형성",
            detail=(f"영상 댓글에서는 '{n.keyword}' 관련 부정적 반응이 상대적으로 높게 "
                    f"나타나 유튜브 이용자 중심의 우려 여론이 형성됨")))

    # 3) 긍정 확산 이슈
    pos = [i for i in issues if i.sentiment == "긍정"]
    if pos:
        p = pos[0]
        trends.append(NotableTrend(
            title=f"'{p.keyword}' 관련 긍정 반응 확산",
            detail=(f"유튜브 이용자 중심으로 '{p.keyword}' 관련 긍정적 반응이 확산되는 "
                    f"것으로 분석됨")))

    # 4) 댓글 참여 활발 영상
    hot = max(videos, key=lambda v: v.comment_count, default=None)
    if hot and hot.comment_count > 0:
        trends.append(NotableTrend(
            title="댓글 참여 집중 영상 확인",
            detail=(f"「{hot.title[:40]}」 영상에 댓글 {hot.comment_count:,}건이 집계되어 "
                    f"유튜브 채널 내 활발한 의견 개진이 확인됨")))
    return trends[:4]
