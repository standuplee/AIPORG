"""AI 요약 (PRD 7-⑨): 이슈별 3/5/10줄 자동 요약.

기본은 TextRank 기반 추출 요약. LLM provider 가 주입되면 추상 요약으로 대체.
"""
from __future__ import annotations

import re

from ..models import Document


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?다음됨함임])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 10]


def extractive_summary(docs: list[Document], n_lines: int = 3) -> list[str]:
    """문서 집합에서 상위 n개 대표 문장 추출."""
    try:
        import networkx as nx
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:
        nx = None

    sents: list[str] = []
    for d in docs:
        sents.extend(_sentences(d.body or d.title))
    sents = list(dict.fromkeys(sents))   # 중복 제거, 순서 보존
    if len(sents) <= n_lines:
        return sents
    if nx is None:
        return sents[:n_lines]

    tfidf = TfidfVectorizer().fit_transform(sents)
    sim = cosine_similarity(tfidf)
    g = nx.from_numpy_array(sim)
    scores = nx.pagerank(g)
    ranked = sorted(((scores[i], s) for i, s in enumerate(sents)), reverse=True)
    return [s for _, s in ranked[:n_lines]]
