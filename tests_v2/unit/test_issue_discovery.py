from datetime import date
from uuid import uuid4

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


def test_issue_discovery_groups_facts_by_existing_entities_and_counts_context() -> None:
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
    )

    assert candidates[0].label == "AI·충남"
    assert set(candidates[0].fact_ids) == {first.fact_id, second.fact_id}
    assert candidates[0].document_count == 3
    assert candidates[0].source_count == 2
    assert candidates[0].channel_count == 2
    assert candidates[1].label == "문화"


def test_issue_discovery_does_not_create_candidate_without_entities() -> None:
    fact = make_fact("근거 없는 라벨", [], [uuid4()])

    assert IssueDiscoveryService().discover([fact], source_by_document={}, channel_by_document={}) == []
