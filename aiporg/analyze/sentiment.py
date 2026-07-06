"""감성 분석 (PRD 7-⑤): 긍정/부정/중립/혼재.

한국어 감성 사전 기반 스코어링. LLM 감성분류기로 교체 가능하도록
classify() 시그니처를 단순하게 유지한다.
"""
from __future__ import annotations

from ..models import Sentiment
from .text import tokenize

POSITIVE = {
    "유치", "성과", "기대", "확대", "호재", "긍정", "개선", "성공", "발전",
    "지원", "혜택", "최대", "역대", "추진력", "강화", "활성화", "우수", "선도",
    "돌봄", "투자", "일자리", "증설", "확충",
}
NEGATIVE = {
    "반대", "우려", "논란", "갈등", "부족", "불발", "무산", "비판", "지적",
    "부정", "불확실", "미흡", "졸속", "폐지", "축소", "지연", "위기", "상승",
    "불출마", "혼란", "실패",
}


def score_text(text: str) -> float:
    toks = set(tokenize(text))
    pos = len(toks & POSITIVE)
    neg = len(toks & NEGATIVE)
    if pos == neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def classify(text: str) -> Sentiment:
    toks = set(tokenize(text))
    pos = len(toks & POSITIVE)
    neg = len(toks & NEGATIVE)
    if pos == 0 and neg == 0:
        return Sentiment.NEUTRAL
    if pos > 0 and neg > 0 and abs(pos - neg) <= 1:
        return Sentiment.MIXED
    if pos > neg:
        return Sentiment.POSITIVE
    if neg > pos:
        return Sentiment.NEGATIVE
    return Sentiment.NEUTRAL


def aggregate(sentiments: list[Sentiment]) -> dict[str, float]:
    """긍정/중립/부정 비율(%). 혼재는 중립에 합산."""
    if not sentiments:
        return {"긍정": 0.0, "중립": 0.0, "부정": 0.0}
    n = len(sentiments)
    pos = sum(1 for s in sentiments if s == Sentiment.POSITIVE)
    neg = sum(1 for s in sentiments if s == Sentiment.NEGATIVE)
    neu = n - pos - neg
    return {
        "긍정": round(pos / n * 100, 1),
        "중립": round(neu / n * 100, 1),
        "부정": round(neg / n * 100, 1),
    }
