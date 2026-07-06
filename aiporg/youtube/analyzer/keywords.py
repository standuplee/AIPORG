"""키워드 추출 (무료 라이브러리만).

우선순위: Kiwi(명사 추출) → KeyBERT(가중) → TF-IDF/빈도 폴백.
설치되지 않은 라이브러리는 자동으로 건너뛴다.
"""
from __future__ import annotations

import re
from collections import Counter

from ..schema import KeywordStat

_STOP = {
    "충남", "충청남도", "영상", "유튜브", "구독", "채널", "오늘", "이번", "관련",
    "그리고", "하지만", "우리", "여러분", "정말", "너무", "사람", "생각", "경우",
    "때문", "정도", "이것", "저것", "그것", "니다", "습니다", "합니다",
    # 감성/일반 표현 (이슈 키워드로 부적합)
    "기대", "부족", "응원", "발전", "방향", "추진", "우려", "확대", "성과",
    "모습", "관심", "발표", "점검", "현장", "비전", "정도", "생각", "바랍니다",
}
_TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        try:
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
        except Exception:
            _kiwi = False
    return _kiwi


def extract_nouns(text: str) -> list[str]:
    kiwi = _get_kiwi()
    if kiwi:
        try:
            return [t.form for t in kiwi.tokenize(text)
                    if t.tag.startswith("NN") and len(t.form) > 1
                    and t.form not in _STOP]
        except Exception:
            pass
    return [w for w in _TOKEN.findall(text) if len(w) > 1 and w not in _STOP]


def top_keywords(texts: list[str], top_n: int = 20) -> list[KeywordStat]:
    """문서 집합 → 상위 키워드(빈도+TF-IDF 가중)."""
    tokenized = [extract_nouns(t) for t in texts]
    freq: Counter = Counter()
    for toks in tokenized:
        freq.update(toks)
    if not freq:
        return []
    weights = _tfidf_weights(tokenized, freq)
    max_w = max(weights.values()) if weights else 1.0
    stats = []
    for kw, cnt in freq.most_common(top_n):
        stats.append(KeywordStat(keyword=kw, frequency=cnt,
                                 weight=round(weights.get(kw, 0.0) / max_w, 4)))
    return stats


def _tfidf_weights(tokenized: list[list[str]], freq: Counter) -> dict[str, float]:
    import math

    n_docs = max(len(tokenized), 1)
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    return {w: c * (math.log((n_docs + 1) / (df[w] + 1)) + 1) for w, c in freq.items()}
