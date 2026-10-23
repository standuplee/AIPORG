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


MAX_STARS = 5

# Requirements §4.4 leaves the reference report's star-rating formula
# undecided ("산식이 제시되어 있지 않다... 임의의 별점을 채우지 않는다").
# The user chose a fixed, documented sentiment-label->star conversion over
# a real mention-count ratio (2026-10-20): every subissue sharing a
# sentiment label gets exactly the same star count -- coarser than the
# reference image's half-star gradations, but never a fabricated per-row
# number, since subissues carry no fact/document count of their own to
# ratio against (see HANDOFF.md).
STAR_RATING_BY_SENTIMENT: dict[SentimentLabel, tuple[int, str]] = {
    SentimentLabel.POSITIVE: (5, "긍정"),
    SentimentLabel.NEUTRAL: (3, "중립"),
    SentimentLabel.MIXED: (3, "혼재"),
    SentimentLabel.NEGATIVE: (1, "부정"),
}


def sentiment_to_stars(label: SentimentLabel) -> tuple[int, str]:
    """Return (star_count, label_text) for one subissue's '온라인 반응' cell."""

    return STAR_RATING_BY_SENTIMENT[label]


def render_star_rating(count: int, *, max_stars: int = MAX_STARS) -> str:
    if not 0 <= count <= max_stars:
        raise ValueError("star count out of range")
    return "★" * count + "☆" * (max_stars - count)


def summarize_subissue_sentiment_counts(issue: IssueSchema) -> dict[SentimentLabel, int]:
    """Real counts of subissues by sentiment label -- the template (no-LLM)
    fallback's closing-sentence numbers are exactly these counts, never an
    estimate (AGENTS.md rule 7)."""

    counts = Counter(detail.sentiment for detail in issue.subissues)
    return {label: counts.get(label, 0) for label in SentimentLabel}
