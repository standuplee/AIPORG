"""AI 요약 (Gemini 최종 요약 전용).

Gemini 에는 대표 영상 제목·대표 댓글·키워드·감성 통계만 전달한다.
영상/댓글 원문 전체는 전달하지 않는다. 키/모델 미가용 시 규칙 기반 요약으로 폴백.
문체는 유튜브 채널 한정 공공기관 보고서체.
"""
from __future__ import annotations

import logging
import os

from ..schema import (ChannelSentiment, Comment, IssueStat, KeywordStat, Video)

log = logging.getLogger(__name__)

_SYSTEM = (
    "당신은 공공기관 여론분석 보고서를 집필하는 애널리스트다. 입력으로 유튜브 "
    "영상·댓글에서 산출된 '대표 데이터(제목·대표댓글·키워드·감성통계)'만 받는다. "
    "다음 규칙을 지켜 3~4문장으로 요약하라.\n"
    "1) 개조식 음슴체(~로 나타남/~로 분석됨/~로 집계됨/~가 필요한 것으로 판단됨).\n"
    "2) 유튜브는 전체 여론이 아니라 하나의 채널임을 전제로, '유튜브 이용자 중심으로', "
    "'영상 댓글에서는', '유튜브 채널 내에서는' 표현을 사용한다.\n"
    "3) '충남 도민은' 처럼 전체 여론으로 일반화하지 않는다.\n"
    "4) 제공된 수치·항목만 사용하고 임의 수치를 만들지 않는다."
)


def _payload(videos: list[Video], comments: list[Comment],
             keywords: list[KeywordStat], sentiment: ChannelSentiment,
             issues: list[IssueStat]) -> str:
    import json
    data = {
        "대표_영상_제목": [v.title for v in videos[:8]],
        "대표_댓글": [c.text[:120] for c in comments[:8]],
        "상위_키워드": [k.keyword for k in keywords[:12]],
        "감성_통계": {"긍정": sentiment.positive, "중립": sentiment.neutral,
                   "부정": sentiment.negative, "혼재": sentiment.mixed,
                   "분석수": sentiment.total_analyzed},
        "핵심_이슈": [{"키워드": i.keyword, "감성": i.sentiment,
                    "조회수합": i.view_sum} for i in issues[:5]],
    }
    return "```DATA\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"


def summarize(videos: list[Video], comments: list[Comment],
              keywords: list[KeywordStat], sentiment: ChannelSentiment,
              issues: list[IssueStat], model: str = "gemini-2.5-flash") -> str:
    if os.environ.get("GEMINI_API_KEY"):
        try:
            from ...llm.providers import GeminiClient
            client = GeminiClient(model)
            return client.generate(_SYSTEM, _payload(videos, comments, keywords,
                                                     sentiment, issues))
        except Exception as exc:  # noqa: BLE001
            log.warning("Gemini 요약 실패 → 규칙 기반 폴백: %s", str(exc)[:80])
    return _fallback(keywords, sentiment, issues)


def _fallback(keywords: list[KeywordStat], sentiment: ChannelSentiment,
              issues: list[IssueStat]) -> str:
    kw = ", ".join(k.keyword for k in keywords[:5]) or "해당 없음"
    top = issues[0].keyword if issues else "해당 없음"
    return (
        f"유튜브 채널 내에서는 {kw} 등의 키워드가 주요하게 나타남. "
        f"영상 댓글에서는 긍정 {sentiment.positive}%, 부정 {sentiment.negative}%, "
        f"중립 {sentiment.neutral}%로 집계됨. "
        f"유튜브 이용자 중심으로 '{top}' 관련 관심이 확대된 것으로 분석되며, "
        f"지속적인 모니터링이 필요한 것으로 판단됨."
    )
