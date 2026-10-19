from datetime import date
from uuid import uuid4

import pytest

from app.core.enums import ChannelType, ConfidenceGrade, FactStatus
from app.issues.discovery import IssueDiscoveryService
from app.schemas.fact import FactSchema


def make_fact(claim: str, entities: list[str], document_ids: list) -> FactSchema:
    return FactSchema(
        fact_id=uuid4(),
        claim=claim,
        event_date=date(2026, 7, 20),
        entities=entities,
        evidence_document_ids=document_ids,
        source_count=len(document_ids),
        confidence=ConfidenceGrade.C,
        status=FactStatus.VERIFIED,
    )


def test_issue_discovery_groups_facts_by_originating_query_and_counts_context() -> None:
    document_a, document_b, document_c = uuid4(), uuid4(), uuid4()
    first = make_fact("AI 정책 발표", ["충남", "AI"], [document_a, document_b])
    second = make_fact("AI 현장 추진", ["AI", "충남"], [document_b, document_c])
    third = make_fact("문화 행사", ["문화"], [document_c])

    candidates = IssueDiscoveryService().discover(
        [first, second, third],
        source_by_document={document_a: "뉴스", document_b: "뉴스", document_c: "블로그"},
        channel_by_document={
            document_a: ChannelType.NEWS,
            document_b: ChannelType.NEWS,
            document_c: ChannelType.BLOG,
        },
        query_by_document={
            document_a: "AI 농기계",
            document_b: "AI 농기계",
            document_c: "문화 행사 키워드",
        },
    )

    by_label = {candidate.label: candidate for candidate in candidates}
    assert set(by_label) == {"AI 농기계", "문화 행사 키워드"}
    assert set(by_label["AI 농기계"].fact_ids) == {first.fact_id, second.fact_id}
    assert by_label["AI 농기계"].document_count == 3
    assert by_label["AI 농기계"].source_count == 2
    assert by_label["AI 농기계"].channel_count == 2
    assert by_label["문화 행사 키워드"].fact_ids == [third.fact_id]


def test_issue_discovery_assigns_a_fact_to_its_most_common_query_when_evidence_spans_two_queries() -> None:
    # same article found under two different monthly keywords -- rare, but
    # a fact must still land in exactly one issue, deterministically.
    document_a, document_b, document_c = uuid4(), uuid4(), uuid4()
    fact = make_fact("두 키워드에서 같은 기사가 발견됨", [], [document_a, document_b, document_c])

    candidates = IssueDiscoveryService().discover(
        [fact],
        source_by_document={document_a: "뉴스", document_b: "뉴스", document_c: "뉴스"},
        channel_by_document={
            document_a: ChannelType.NEWS, document_b: ChannelType.NEWS, document_c: ChannelType.NEWS,
        },
        query_by_document={document_a: "키워드B", document_b: "키워드A", document_c: "키워드A"},
    )

    assert len(candidates) == 1
    assert candidates[0].label == "키워드A"  # 2 of 3 documents found under 키워드A


def test_issue_discovery_requires_query_provenance_for_every_evidence_document() -> None:
    fact = make_fact("근거 문서에 조사어 정보가 없음", [], [uuid4()])

    with pytest.raises(ValueError, match="query provenance"):
        IssueDiscoveryService().discover(
            [fact], source_by_document={}, channel_by_document={}, query_by_document={},
        )


def test_issue_discovery_no_longer_requires_entities_to_form_an_issue() -> None:
    # previously a fact with no matching org/person/region term was silently
    # dropped from every issue -- query-based grouping has no such gap,
    # since every document has a query.
    document = uuid4()
    fact = make_fact("고정 용어가 전혀 없는 기사 내용", [], [document])

    candidates = IssueDiscoveryService().discover(
        [fact],
        source_by_document={document: "뉴스"},
        channel_by_document={document: ChannelType.NEWS},
        query_by_document={document: "석탄화력폐지지역 특별법"},
    )

    assert len(candidates) == 1
    assert candidates[0].label == "석탄화력폐지지역 특별법"
    assert candidates[0].fact_ids == [fact.fact_id]
