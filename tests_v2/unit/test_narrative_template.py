from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.enums import ConfidenceGrade, FactStatus, SentimentLabel
from app.narrative.template import TemplateNarrativeService
from app.schemas.analytics import AnalyticsSnapshotSchema
from app.schemas.common import VersionedRunSchema
from app.schemas.evidence import EvidenceSchema
from app.schemas.fact import FactSchema
from app.schemas.issue import IssueSchema
from app.schemas.narrative import NarrativeContext


def inputs():
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    project_id, document_id = uuid4(), uuid4()
    fact = FactSchema(
        fact_id=uuid4(), claim="충남에서 예산 30억원을 발표했다.", event_date=now.date(),
        entities=["충남"], evidence_document_ids=[document_id], source_count=1,
        confidence=ConfidenceGrade.A, status=FactStatus.SUPPORTED,
    )
    context = NarrativeContext(
        issue=IssueSchema(issue_id=uuid4(), label="충남", fact_ids=[fact.fact_id],
                          document_count=1, source_count=1, channel_count=1, subissues=[]),
        facts=[fact], sentiment=SentimentLabel.NEUTRAL, keywords=[],
        positive_reasons=[], negative_reasons=[],
    )
    analytics = AnalyticsSnapshotSchema(
        project_id=project_id,
        run=VersionedRunSchema(run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1", created_at=now),
        metrics={"unique_documents": 1, "document_ids": [str(document_id)]},
    )
    evidence = EvidenceSchema(evidence_id=uuid4(), project_id=project_id,
                              document_id=document_id, excerpt=fact.claim, created_at=now)
    return context, analytics, evidence


def test_template_quotes_only_supported_claims_and_snapshot_count():
    context, analytics, evidence = inputs()
    service = TemplateNarrativeService()
    text = service.render([context], analytics, [evidence])
    assert text == (
        "저장된 문서 기준 분석기간 언급량은 1건으로 집계됨.\n"
        "근거 문서에서 다음 내용이 확인됨: 「충남에서 예산 30억원을 발표했다.」"
    )
    assert service.render([context, context], analytics, [evidence]) == text
    service.validate(text, [context], analytics, [evidence])


@pytest.mark.parametrize("original,replacement", [
    ("30억원", "300억원"), ("충남", "서울"), ("발표했다.", "발표하지 않았다."),
])
def test_post_validation_blocks_changed_numbers_names_and_meaning(original, replacement):
    context, analytics, evidence = inputs()
    service = TemplateNarrativeService()
    text = service.render([context], analytics, [evidence])
    with pytest.raises(ValueError, match="template"):
        service.validate(text.replace(original, replacement), [context], analytics, [evidence])


@pytest.mark.parametrize("status", [FactStatus.UNCERTAIN, FactStatus.REJECTED])
def test_untrusted_facts_and_unverified_reasons_are_not_narrated(status):
    context, analytics, evidence = inputs()
    context.facts[0].status = status
    context.positive_reasons = ["지지율 99%"]
    text = TemplateNarrativeService().render([context], analytics, [evidence])
    assert "30" not in text and "99" not in text


@pytest.mark.parametrize("change", ["claim", "project", "document"])
def test_fact_requires_matching_project_document_and_evidence_text(change):
    context, analytics, evidence = inputs()
    if change == "claim":
        context.facts[0].claim = "충남에서 예산 300억원을 발표했다."
    elif change == "project":
        evidence.project_id = uuid4()
    else:
        evidence.document_id = uuid4()
    with pytest.raises(ValueError, match="evidence"):
        TemplateNarrativeService().render([context], analytics, [evidence])


@pytest.mark.parametrize("count", [True, -1, 1.5, "1", 2])
def test_numeric_counts_require_integer_and_matching_provenance(count):
    _, analytics, _ = inputs()
    analytics.metrics["unique_documents"] = count
    with pytest.raises(ValueError):
        TemplateNarrativeService().render([], analytics, [])


def test_empty_context_and_snapshot_produce_no_invented_statement():
    _, analytics, _ = inputs()
    analytics.metrics = {}
    assert TemplateNarrativeService().render([], analytics, []) == ""


def test_fact_outside_issue_is_rejected():
    context, analytics, evidence = inputs()
    context.issue.fact_ids = [uuid4()]
    with pytest.raises(ValueError, match="linked"):
        TemplateNarrativeService().render([context], analytics, [evidence])


@pytest.mark.parametrize("claim,excerpt", [
    ("30억원을 발표했다.", "130억원을 발표했다."),
    ("충남에서 발표했다.", "비충남에서 발표했다."),
])
def test_partial_sentence_match_cannot_support_a_different_number_or_name(claim, excerpt):
    context, analytics, evidence = inputs()
    context.facts[0].claim = claim
    evidence.excerpt = excerpt
    with pytest.raises(ValueError, match="evidence"):
        TemplateNarrativeService().render([context], analytics, [evidence])


def test_missing_evidence_links_are_rejected_even_for_mutated_input():
    context, analytics, evidence = inputs()
    context.facts[0].evidence_document_ids = []
    with pytest.raises(ValueError, match="evidence"):
        TemplateNarrativeService().render([context], analytics, [evidence])


def test_whole_sentence_is_supported_within_a_longer_excerpt():
    context, analytics, evidence = inputs()
    evidence.excerpt = "선행 설명이다. " + evidence.excerpt + " 후속 설명이다."
    assert context.facts[0].claim in TemplateNarrativeService().render([context], analytics, [evidence])
