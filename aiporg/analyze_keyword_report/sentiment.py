from __future__ import annotations

from ..models import Document, Sentiment
from ..models_keyword_report import SentimentDriver
from .keywords import top_ranked_keywords


def build_sentiment_drivers(docs: list[Document]) -> tuple[list[SentimentDriver], list[SentimentDriver]]:
    positive_docs = [doc for doc in docs if doc.sentiment == Sentiment.POSITIVE]
    negative_docs = [doc for doc in docs if doc.sentiment == Sentiment.NEGATIVE]
    return _build_for_group("긍정", positive_docs), _build_for_group("부정", negative_docs)


def _build_for_group(sentiment: str, docs: list[Document]) -> list[SentimentDriver]:
    if not docs:
        return []
    representative = max(docs, key=lambda doc: doc.views + doc.comments + doc.likes)
    keywords = [item.keyword for item in top_ranked_keywords(docs, top_n=3)]
    detail = representative.body or representative.title
    if keywords:
        detail = f"{', '.join(keywords)} 관련 언급. {detail}"
    return [
        SentimentDriver(
            sentiment=sentiment,
            title=representative.title,
            detail=detail,
            evidence=[representative.url],
        )
    ]
