from uuid import uuid4

from app.core.enums import SentimentLabel, StanceLabel
from app.narrative.reasons import aggregate_issue_sentiment, derive_narrative_reasons
from app.schemas.issue import IssueDetailSchema, IssueSchema


def _detail(summary: str, sentiment: SentimentLabel) -> IssueDetailSchema:
    return IssueDetailSchema(
        label="이슈", policy=summary, summary=summary,
        sentiment=sentiment, stance=StanceLabel.NOT_APPLICABLE,
    )


def _issue(details: list[IssueDetailSchema]) -> IssueSchema:
    return IssueSchema(
        issue_id=uuid4(), label="이슈", fact_ids=[uuid4()],
        document_count=len(details), source_count=len(details), channel_count=1,
        subissues=details,
    )


def test_derive_narrative_reasons_splits_by_sentiment_and_caps_at_five() -> None:
    details = (
        [_detail(f"긍정 사유 {i}", SentimentLabel.POSITIVE) for i in range(7)]
        + [_detail("부정 사유 1", SentimentLabel.NEGATIVE)]
        + [_detail("중립 사유", SentimentLabel.NEUTRAL)]
    )
    positive, negative = derive_narrative_reasons(_issue(details))

    assert len(positive) == 5  # capped, not padded to a fixed count
    assert negative == ["부정 사유 1"]
    assert "중립 사유" not in positive and "중립 사유" not in negative


def test_derive_narrative_reasons_does_not_pad_when_few_exist() -> None:
    # requirements doc §4.3: "근거가 2개 유형이면 2개만 작성"
    details = [_detail("긍정 사유 1", SentimentLabel.POSITIVE)]
    positive, negative = derive_narrative_reasons(_issue(details))
    assert positive == ["긍정 사유 1"]
    assert negative == []


def test_aggregate_issue_sentiment_returns_mixed_when_balanced() -> None:
    details = [
        _detail("긍정", SentimentLabel.POSITIVE),
        _detail("부정", SentimentLabel.NEGATIVE),
    ]
    assert aggregate_issue_sentiment(_issue(details)) is SentimentLabel.MIXED


def test_aggregate_issue_sentiment_picks_the_larger_polarity() -> None:
    details = [
        _detail("긍정1", SentimentLabel.POSITIVE),
        _detail("긍정2", SentimentLabel.POSITIVE),
        _detail("긍정3", SentimentLabel.POSITIVE),
        _detail("부정", SentimentLabel.NEGATIVE),
    ]
    assert aggregate_issue_sentiment(_issue(details)) is SentimentLabel.POSITIVE


def test_aggregate_issue_sentiment_defaults_to_neutral_without_subissues() -> None:
    issue = IssueSchema(
        issue_id=uuid4(), label="이슈", fact_ids=[uuid4()],
        document_count=0, source_count=0, channel_count=0, subissues=[],
    )
    assert aggregate_issue_sentiment(issue) is SentimentLabel.NEUTRAL
