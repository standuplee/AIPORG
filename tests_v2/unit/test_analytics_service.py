from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.analytics.service import AnalyticsService
from app.core.enums import ChannelType, ConfidenceGrade, FactStatus
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, VersionedRunSchema
from app.schemas.document import CleanDocument
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueSchema


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
PERIOD = AnalysisPeriodSchema(start=date(2026, 9, 1), end=date(2026, 9, 3))
PREVIOUS = ComparisonPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31))


def document(**updates):
    identity = uuid4()
    return CleanDocument(
        document_id=identity, title="정책", body="정책 지원 123",
        canonical_url=f"https://example.test/{identity}", cleaned_at=NOW,
        published_at=NOW, channel=ChannelType.NEWS, source="source-a",
    ).model_copy(update=updates)


def build(documents, **kwargs):
    return AnalyticsService().build(
        uuid4(),
        VersionedRunSchema(run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1", created_at=NOW),
        documents, analysis_period=PERIOD,
        comparison_period=kwargs.pop("comparison_period", PREVIOUS), **kwargs,
    ).metrics


def test_counts_trace_to_unique_documents_and_stored_labels():
    first = document(metadata={"sentiment": "positive"})
    second = document(channel=None, source=None)
    third = document(metadata={"sentiment": ["negative"]}, channel=ChannelType.BLOG)
    metrics = build([first, second, third, first])
    assert metrics["unique_documents"] == 3
    assert metrics["channel_mentions"] == {"news": 1, "blog": 1, "unclassified": 1}
    assert metrics["unclassified_documents"] == 1
    assert metrics["sentiment_distribution"] == {
        "positive": 1, "negative": 0, "neutral": 0, "mixed": 0, "unclassified": 2,
    }
    assert metrics["keyword_frequencies"] == {"정책": 6, "지원": 3}
    assert metrics["keyword_document_ids"]["정책"] == metrics["document_ids"]
    for name in ("channel", "source", "daily"):
        for key, count in metrics[f"{name}_mentions"].items():
            assert count == len(metrics[f"{name}_document_ids"][key])
    assert metrics["daily_mentions"] == {"2026-09-01": 3, "2026-09-02": 0, "2026-09-03": 0}


def test_period_boundaries_use_explicit_timezone_and_keep_undated_provenance():
    boundary = document(published_at=datetime(2026, 8, 31, 15, tzinfo=timezone.utc))
    previous = document(published_at=datetime(2026, 8, 31, 14, 59, tzinfo=timezone.utc))
    after = document(published_at=datetime(2026, 9, 3, 15, tzinfo=timezone.utc))
    undated = document(published_at=None)
    metrics = build([boundary, previous, after, undated])
    assert metrics["document_ids"] == [str(boundary.document_id)]
    assert metrics["undated_document_ids"] == [str(undated.document_id)]
    assert metrics["comparison"]["document_ids"] == [str(previous.document_id)]
    assert metrics["comparison"]["change"] == 0
    assert metrics["basis"]["timezone"] == "Asia/Seoul"


@pytest.mark.parametrize("period,status", [(None, "period_not_configured"), (PREVIOUS, "no_comparison_documents")])
def test_missing_comparison_never_invents_zero_or_growth(period, status):
    metrics = build([document()], comparison_period=period)
    assert metrics["comparison"]["status"] == status
    for field in ("unique_documents", "change", "change_percent"):
        assert metrics["comparison"][field] is None


def test_comparison_change_is_computed_from_observed_documents():
    previous = document(published_at=datetime(2026, 8, 4, tzinfo=timezone.utc))
    metrics = build([document(), document(), previous])
    assert metrics["comparison"]["unique_documents"] == 1
    assert metrics["comparison"]["change"] == 1
    assert metrics["comparison"]["change_percent"] == 100
    empty_current = build([previous])
    assert empty_current["comparison"]["change_percent"] == -100


def test_empty_input_has_zero_observed_counts_and_no_assumed_sentiment():
    metrics = build([])
    assert metrics["unique_documents"] == 0
    assert metrics["document_ids"] == []
    assert all(count == 0 for count in metrics["sentiment_distribution"].values())
    assert metrics["keyword_frequencies"] == {}
    assert metrics["issues"] == []


def test_issue_distribution_recalculates_counts_and_excludes_untrusted_facts():
    first, second = document(), document(source="source-b", channel=ChannelType.BLOG)
    trusted = FactSchema(
        fact_id=uuid4(), claim="정책", event_date=NOW.date(), entities=["정책"],
        evidence_document_ids=[first.document_id], source_count=99,
        confidence=ConfidenceGrade.A, status=FactStatus.VERIFIED,
    )
    uncertain = trusted.model_copy(update={
        "fact_id": uuid4(), "evidence_document_ids": [second.document_id], "status": FactStatus.UNCERTAIN,
    })
    issue = IssueSchema(
        issue_id=uuid4(), label="정책", fact_ids=[trusted.fact_id, uncertain.fact_id],
        document_count=99, source_count=99, channel_count=99, subissues=[],
    )
    metrics = build([first, second], issues=[issue], facts_by_id={fact.fact_id: fact for fact in [trusted, uncertain]})
    result = metrics["issues"][0]
    assert result["document_count"] == result["source_count"] == result["channel_count"] == 1
    assert result["document_ids"] == [str(first.document_id)]
    assert result["excluded_fact_ids"] == [str(uncertain.fact_id)]
    assert result["source_mentions"] == {"source-a": 1}
    with pytest.raises(ValueError, match="unknown"):
        build([first], issues=[issue])


def test_input_fingerprint_and_metrics_are_order_independent_and_sensitive_to_changes():
    first, second = document(), document()
    assert build([first, second]) == build([second, first, first])
    changed = second.model_copy(update={"body": "다른 본문"})
    assert build([first, second])["basis"]["input_sha256"] != build([first, changed])["basis"]["input_sha256"]


def test_ambiguous_document_identity_is_rejected():
    first = document()
    with pytest.raises(ValueError, match="conflicting"):
        build([first, first.model_copy(update={"body": "다른 본문"})])
    with pytest.raises(ValueError, match="canonical"):
        build([first, first.model_copy(update={"document_id": uuid4()})])


def test_keyword_extraction_drops_particles_verbs_and_leaked_script_tokens():
    # 2026-10-19 real-data finding: plain character-token frequency put
    # particles/verbs ("있다"/"위해"/"지난"/"함께") and leaked inline
    # JavaScript ("var") at the top of TOP10 -- none of these are ever
    # tagged NNG/NNP, so the noun-only filter must drop them all.
    noisy = document(
        title="소식",
        body=(
            "AI 농기계 보급 사업을 위해 충남도는 지난 폭염 대응 현장을 함께 "
            "점검했다고 밝혔다. var fixed = false 라는 코드도 섞여 있다."
        ),
    )
    metrics = build([noisy])
    keywords = metrics["keyword_frequencies"]
    for noise in ("있다", "위해", "지난", "함께", "var", "ai"):
        assert noise not in keywords
    for real_keyword in ("농기계", "보급", "사업", "폭염", "대응", "현장", "점검"):
        assert real_keyword in keywords


def test_keyword_extraction_falls_back_to_token_frequency_without_kiwipiepy(monkeypatch):
    from app.analytics import service as analytics_service

    monkeypatch.setattr(analytics_service, "_get_kiwi", lambda: None)
    doc = document(title="정책", body="정책 지원 123")
    metrics = build([doc])
    assert metrics["keyword_frequencies"] == {"정책": 2, "지원": 1}
    assert metrics["basis"]["keywords"] == "title_and_body_casefold_letter_tokens_min_length_2"
