"""감성 분석 (무료 모델 우선순위: KcELECTRA → KoELECTRA → 사전 폴백).

transformers 미설치 또는 모델 로드 실패 시 한국어 감성 사전으로 degrade.
Gemini 는 여기서 사용하지 않는다(최종 요약 전용).
"""
from __future__ import annotations

import logging

from ..schema import ChannelSentiment

log = logging.getLogger(__name__)

_POS = {
    "좋다", "좋은", "잘", "응원", "기대", "최고", "감사", "훌륭", "칭찬", "성과",
    "발전", "희망", "긍정", "지지", "찬성", "멋지", "대단", "박수", "화이팅",
}
_NEG = {
    "나쁘", "최악", "실망", "화나", "비판", "반대", "우려", "문제", "논란", "불만",
    "부정", "거짓", "무능", "혈세", "낭비", "짜증", "답답", "포기", "의혹", "갈등",
}

_MODEL_TRIED = False
_pipe = None
_LABELS = {"긍정": "긍정", "부정": "부정", "중립": "중립",
           "positive": "긍정", "negative": "부정", "neutral": "중립",
           "LABEL_0": "부정", "LABEL_1": "긍정"}


def _load_model():
    """KcELECTRA/KoELECTRA 감성 파이프라인 로드 시도(무거우면 자동 폴백)."""
    global _MODEL_TRIED, _pipe
    if _MODEL_TRIED:
        return _pipe
    _MODEL_TRIED = True
    for name in ("beomi/KcELECTRA-base-v2022", "monologg/koelectra-base-finetuned-nsmc"):
        try:
            from transformers import pipeline
            _pipe = pipeline("sentiment-analysis", model=name, truncation=True)
            log.info("감성 모델 로드: %s", name)
            return _pipe
        except Exception:
            continue
    _pipe = None
    return None


def _lexicon(text: str) -> str:
    t = text or ""
    pos = sum(1 for w in _POS if w in t)
    neg = sum(1 for w in _NEG if w in t)
    if pos == 0 and neg == 0:
        return "중립"
    if pos and neg and abs(pos - neg) <= 1:
        return "혼재"
    return "긍정" if pos > neg else "부정"


def classify(text: str) -> str:
    pipe = _load_model()
    if pipe is not None:
        try:
            out = pipe(text[:256])[0]
            return _LABELS.get(out.get("label", ""), _lexicon(text))
        except Exception:
            pass
    return _lexicon(text)


def classify_many(texts: list[str]) -> list[str]:
    return [classify(t) for t in texts]


def aggregate(labels: list[str]) -> ChannelSentiment:
    n = len(labels)
    if n == 0:
        return ChannelSentiment()
    c = {k: labels.count(k) for k in ("긍정", "부정", "중립", "혼재")}
    return ChannelSentiment(
        positive=round(c["긍정"] / n * 100, 1),
        negative=round(c["부정"] / n * 100, 1),
        neutral=round(c["중립"] / n * 100, 1),
        mixed=round(c["혼재"] / n * 100, 1),
        total_analyzed=n,
    )


def intensity(labels: list[str]) -> float:
    """감성 강도: 긍/부정 비율(비중립 비율)."""
    if not labels:
        return 0.0
    strong = sum(1 for x in labels if x in ("긍정", "부정"))
    return round(strong / len(labels), 4)
