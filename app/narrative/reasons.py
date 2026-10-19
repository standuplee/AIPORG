"""Derive narrative-context positive/negative reasons from an issue.

Each subissue's sentiment is already classified (app/sentiment/service.py,
called from IssueFinalizationService) -- this module only groups and caps
what's already there, generating no new wording (AGENTS.md rule 6). A
reason is the exact grounded claim text, picked up to ``max_reasons`` per
polarity and never padded to reach that count (requirements doc §4.3:
"숫자나 이유 개수를 채우기 위한 생성은 금지").
"""

from collections import Counter

from app.core.enums import SentimentLabel
from app.schemas.issue import IssueSchema

MAX_REASONS = 5


def derive_narrative_reasons(
    issue: IssueSchema, *, max_reasons: int = MAX_REASONS
) -> tuple[list[str], list[str]]:
    """Return (positive_reasons, negative_reasons) for NarrativeContext."""

    positive = [
        detail.summary for detail in issue.subissues
        if detail.sentiment is SentimentLabel.POSITIVE
    ][:max_reasons]
    negative = [
        detail.summary for detail in issue.subissues
        if detail.sentiment is SentimentLabel.NEGATIVE
    ][:max_reasons]
    return positive, negative


def aggregate_issue_sentiment(issue: IssueSchema) -> SentimentLabel:
    """A single representative sentiment for the whole issue: MIXED when
    positive/negative subissues are roughly balanced, otherwise whichever
    polarity has more subissues; falls back to the most common label when
    neither polarity is present at all (e.g. every subissue is NEUTRAL)."""

    if not issue.subissues:
        return SentimentLabel.NEUTRAL
    counts = Counter(detail.sentiment for detail in issue.subissues)
    positive = counts.get(SentimentLabel.POSITIVE, 0)
    negative = counts.get(SentimentLabel.NEGATIVE, 0)
    if positive and negative and abs(positive - negative) <= 1:
        return SentimentLabel.MIXED
    if positive > negative:
        return SentimentLabel.POSITIVE
    if negative > positive:
        return SentimentLabel.NEGATIVE
    return max(counts, key=lambda label: counts[label])
