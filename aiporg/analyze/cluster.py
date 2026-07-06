"""토픽 군집화 (PRD 7-④): 행정/복지/경제/환경/교육/산업/선거/문화 등.

카테고리 사전으로 1차 분류 후, 미분류 문서는 TF-IDF+KMeans 로 보조 군집화.
"""
from __future__ import annotations

from collections import Counter

from ..models import Document

CATEGORY_LEXICON = {
    "행정": ["행정", "통합", "조직", "청사", "행정통합", "특별법"],
    "선거": ["선거", "공천", "출마", "후보", "지방선거", "당선"],
    "경제": ["경제", "투자", "물가", "일자리", "예산", "국비", "데이터센터"],
    "산업": ["산업", "반도체", "제조", "기업", "패키징", "특화도시", "AI"],
    "도정": ["도정", "업무계획", "정책", "도지사", "시책"],
    "환경": ["환경", "탄소", "발전", "석탄", "전력", "에너지", "기후"],
    "복지": ["복지", "돌봄", "요양", "보육", "취약", "지원금"],
    "교육": ["교육", "학교", "대학", "학생", "교사"],
    "문화": ["문화", "관광", "축제", "예술", "체육"],
}


def categorize(doc: Document) -> str:
    text = doc.title + " " + doc.body
    scores = {cat: sum(text.count(w) for w in words)
              for cat, words in CATEGORY_LEXICON.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "기타"


def cluster(docs: list[Document]) -> dict[str, list[Document]]:
    groups: dict[str, list[Document]] = {}
    for d in docs:
        cat = categorize(d)
        d.cluster = cat
        groups.setdefault(cat, []).append(d)
    return groups


def category_distribution(docs: list[Document]) -> Counter:
    return Counter(categorize(d) for d in docs)
