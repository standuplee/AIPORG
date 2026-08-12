from __future__ import annotations

from collections import Counter

from ..models import Document, ReportMeta, Sentiment
from ..models_keyword_report import KeywordReportModel, KeywordReportSummary
from .channels import build_channel_trends
from .issues import rank_issues
from .keywords import top_ranked_keywords
from .methodology import default_methodology
from .recommendations import build_recommendations
from .sentiment import build_sentiment_drivers
from .sources import build_source_references


class KeywordAnalysisPipeline:
    def run(
        self,
        current_docs: list[Document],
        previous_docs: list[Document],
        meta: ReportMeta,
        issue_keywords: dict[str, list[str]] | None = None,
    ) -> KeywordReportModel:
        issues = rank_issues(current_docs, issue_keywords=issue_keywords or {}, top_n=4)
        channels = build_channel_trends(current_docs, previous_docs)
        keywords = top_ranked_keywords(current_docs, top_n=20)
        positive_drivers, negative_drivers = build_sentiment_drivers(current_docs)
        implications, channel_recommendations = build_recommendations(
            issues,
            positive_drivers,
            negative_drivers,
        )

        return KeywordReportModel(
            summary=KeywordReportSummary(
                analysis_period=f"{meta.period_start:%Y.%m.%d}~{meta.period_end:%Y.%m.%d}",
                channel_count=len({doc.channel.value for doc in current_docs}),
                primary_keyword=meta.leader_name,
                positive_ratio=_positive_ratio(current_docs),
                month_over_month=_month_over_month(current_docs, previous_docs),
            ),
            issues=issues,
            channel_overview=channels,
            top_keywords=keywords,
            sentiment_overview=_sentiment_overview(current_docs),
            positive_drivers=positive_drivers,
            negative_drivers=negative_drivers,
            implications=implications,
            channel_recommendations=channel_recommendations,
            sources=build_source_references(current_docs),
            methodology=default_methodology(),
        )


def _positive_ratio(docs: list[Document]) -> float:
    labeled = [doc for doc in docs if doc.sentiment]
    if not labeled:
        return 0.0
    positives = sum(1 for doc in labeled if doc.sentiment == Sentiment.POSITIVE)
    return round((positives / len(labeled)) * 100, 2)


def _month_over_month(current_docs: list[Document], previous_docs: list[Document]) -> str:
    if not previous_docs:
        return "비교 불가"
    change = ((len(current_docs) - len(previous_docs)) / len(previous_docs)) * 100
    sign = "▲" if change > 0 else "▼" if change < 0 else "—"
    return f"{sign}{abs(round(change, 1))}%"


def _sentiment_overview(docs: list[Document]) -> dict[str, float]:
    labeled = [doc.sentiment.value for doc in docs if doc.sentiment]
    if not labeled:
        return {}
    counts = Counter(labeled)
    total = len(labeled)
    return {label: round((count / total) * 100, 2) for label, count in counts.items()}
