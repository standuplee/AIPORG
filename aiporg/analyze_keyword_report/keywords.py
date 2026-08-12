from __future__ import annotations

from collections import Counter, defaultdict

from ..analyze.text import tokenize
from ..models import Document
from ..models_keyword_report import RankedKeywordItem
from .dictionaries import STOPWORDS, categorize_keyword


def top_ranked_keywords(docs: list[Document], top_n: int = 20) -> list[RankedKeywordItem]:
    frequencies: Counter[str] = Counter()
    channels: dict[str, set[str]] = defaultdict(set)
    for doc in docs:
        seen_in_doc: set[str] = set()
        for token in tokenize(f"{doc.title} {doc.body}"):
            if token in STOPWORDS:
                continue
            frequencies[token] += 1
            if token not in seen_in_doc:
                channels[token].add(doc.channel.value)
                seen_in_doc.add(token)

    ranked_terms = sorted(
        frequencies,
        key=lambda term: (-frequencies[term], -len(channels[term]), term),
    )[:top_n]
    return [
        RankedKeywordItem(
            rank=index,
            keyword=term,
            category=categorize_keyword(term),
        )
        for index, term in enumerate(ranked_terms, start=1)
    ]
