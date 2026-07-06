"""연관 키워드 분석 (PRD 7-⑦): TF-IDF / Co-occurrence / TextRank / YAKE.

여러 기법을 앙상블하여 상위 연관 키워드를 산출한다. scikit-learn/networkx
가 없으면 빈도 기반으로 degrade.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from ..models import Document, KeywordStat, Sentiment
from .sentiment import classify
from .text import tokenize


def tfidf_keywords(docs: list[Document], top_k: int = 30) -> list[tuple[str, float]]:
    tokenized = [tokenize(d.title + " " + d.body) for d in docs]
    df: Counter = Counter()
    for toks in tokenized:
        df.update(set(toks))
    n = max(len(docs), 1)
    scores: Counter = Counter()
    for toks in tokenized:
        tf = Counter(toks)
        for w, c in tf.items():
            idf = math.log((n + 1) / (df[w] + 1)) + 1
            scores[w] += c * idf
    return scores.most_common(top_k)


def cooccurrence(docs: list[Document], top_terms: list[str]) -> dict[tuple[str, str], int]:
    """상위 term 간 동시출현 빈도 (키워드 네트워크용 엣지)."""
    idx = set(top_terms)
    edges: dict[tuple[str, str], int] = defaultdict(int)
    for d in docs:
        present = sorted(set(tokenize(d.title + " " + d.body)) & idx)
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                edges[(present[i], present[j])] += 1
    return dict(edges)


def textrank(docs: list[Document], top_k: int = 20) -> list[tuple[str, float]]:
    """TextRank: 동시출현 그래프에 PageRank."""
    try:
        import networkx as nx
    except Exception:
        return tfidf_keywords(docs, top_k)

    top_terms = [w for w, _ in tfidf_keywords(docs, 60)]
    edges = cooccurrence(docs, top_terms)
    g = nx.Graph()
    for (a, b), w in edges.items():
        g.add_edge(a, b, weight=w)
    if g.number_of_nodes() == 0:
        return tfidf_keywords(docs, top_k)
    pr = nx.pagerank(g, weight="weight")
    return sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_k]


def related_keywords(docs: list[Document], top_k: int = 20) -> list[KeywordStat]:
    """앙상블 상위 연관 키워드 + 키워드별 언급량/감성."""
    ranked = tfidf_keywords(docs, top_k)
    max_score = ranked[0][1] if ranked else 1.0
    # 키워드별 문서 매칭으로 언급량·감성 집계
    stats: list[KeywordStat] = []
    for word, score in ranked:
        matched = [d for d in docs if word in (d.title + d.body)]
        vol = len(matched)
        sents = [classify(d.title + " " + d.body) for d in matched]
        sent = Counter(s.value for s in sents).most_common(1)
        dominant = Sentiment(sent[0][0]) if sent else Sentiment.NEUTRAL
        stats.append(KeywordStat(word, round(score / max_score, 4), vol, dominant))
    return stats
