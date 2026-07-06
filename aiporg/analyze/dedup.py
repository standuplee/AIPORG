"""중복 제거 (PRD 7-①): 동일/유사/재배포 기사 제거.

1) 정확 중복: 제목+본문 해시
2) 유사 중복: TF-IDF 코사인 유사도 임계값 초과 시 병합
"""
from __future__ import annotations

import hashlib

from ..models import Document


def _hash(doc: Document) -> str:
    return hashlib.md5((doc.title + doc.body[:200]).encode("utf-8")).hexdigest()


def dedup(docs: list[Document], sim_threshold: float = 0.9) -> list[Document]:
    # 1) 정확 중복
    seen: dict[str, Document] = {}
    for d in docs:
        h = _hash(d)
        if h not in seen:
            seen[h] = d
    unique = list(seen.values())

    if len(unique) < 2:
        return unique

    # 2) 유사 중복 (TF-IDF 코사인)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [(d.title + " " + d.body) for d in unique]
        tfidf = TfidfVectorizer(min_df=1).fit_transform(corpus)
        sim = cosine_similarity(tfidf)
        keep = [True] * len(unique)
        for i in range(len(unique)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(unique)):
                if keep[j] and sim[i, j] >= sim_threshold:
                    keep[j] = False   # 재배포/유사본 제거
        return [d for d, k in zip(unique, keep) if k]
    except Exception:
        return unique
