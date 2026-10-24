import asyncio
import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.research.query_expansion import QwenQueryExpansionService
from app.research.query.prompts import SYSTEM_PROMPT
from app.schemas.research import (
    IssueInput,
    QueryDraftSet,
    QueryExpansionResult,
    QueryType,
    ResearchPlan,
    SearchPurpose,
)

QUESTION_TYPES = [
    "FACT", "FACT", "DETAIL", "DETAIL", "BACKGROUND", "IMPACT", "IMPACT",
    "CONCERN", "CONCERN", "REACTION", "FOLLOWUP",
]


def _plan_payload() -> dict[str, object]:
    return {
        "decomposition": {
            "subjects": ["삼성디스플레이"],
            "actions": ["투자"],
            "amounts": ["67조"],
            "locations": [],
            "organizations": ["삼성디스플레이", "아산디스플레이시티2"],
            "policies": [],
            "explicit_in_input": ["삼성디스플레이", "67조", "투자"],
            "unknowns": ["67조의 의미"],
        },
        "research_questions": [
            {"id": f"RQ{i:02d}", "type": kind, "question": f"{kind} 조사 질문 {i}?"}
            for i, kind in enumerate(QUESTION_TYPES, start=1)
        ],
    }


def _drafts_payload() -> dict[str, object]:
    return {
        "drafts": [
            {
                "research_question_id": f"RQ{i:02d}",
                "queries": [
                    f"삼성디스플레이 충청남도 투자 일정 {i}",
                    f"삼성디스플레이 투자 일자리 효과 {i}" if kind == "IMPACT" else f"삼성디스플레이 투자 개요 {i}",
                ],
            }
            for i, kind in enumerate(QUESTION_TYPES, start=1)
            if kind != "REACTION"
        ]
    }


def _result_payload(issue: str = "삼성디스플레이 67조 투자") -> dict[str, object]:
    questions = _plan_payload()["research_questions"]
    return {
        "issue": issue,
        "decomposition": _plan_payload()["decomposition"],
        "protected_terms": [],
        "research_questions": questions,
        "queries": [
            {
                "research_question_id": q["id"],
                "type": q["type"],
                "query": f"{issue} 조사 축 {i}",
                "search_purpose": "FACT_RESEARCH",
            }
            for i, q in enumerate(questions, start=1)
        ],
    }


class _Response:
    status_code = 200

    def __init__(self, body: dict[str, object]) -> None:
        self.body = json.dumps(body, ensure_ascii=False)

    def json(self):
        return json.loads(self.body)


class _Transport:
    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def post(self, url, *, json_body):
        self.calls.append({"url": url, "json_body": json_body})
        return self.responses.pop(0)


def _msg(payload) -> _Response:
    return _Response({"message": {"content": json.dumps(payload, ensure_ascii=False)}})


def test_query_expansion_requires_issue_decomposition_and_fixed_question_mix() -> None:
    payload = _result_payload()
    result = QueryExpansionResult.model_validate(payload)

    assert result.decomposition.explicit_in_input == ["삼성디스플레이", "67조", "투자"]
    assert len(result.research_questions) == 11
    assert result.queries[0].type is QueryType.FACT

    payload["research_questions"] = payload["research_questions"][:-1]
    with pytest.raises(ValidationError, match="at least 11 items"):
        QueryExpansionResult.model_validate(payload)


def test_query_expansion_rejects_duplicate_queries() -> None:
    payload = _result_payload()
    payload["queries"][1]["query"] = payload["queries"][0]["query"]
    with pytest.raises(ValidationError, match="duplicate search queries"):
        QueryExpansionResult.model_validate(payload)


def test_issue_input_rejects_reversed_period() -> None:
    with pytest.raises(ValidationError):
        IssueInput(
            region="충청남도",
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 1),
            issue="삼성디스플레이 투자",
        )


def test_two_stage_expansion_applies_aliases_purposes_and_bias_control() -> None:
    transport = _Transport(_msg(_plan_payload()), _msg(_drafts_payload()))
    issue = IssueInput(
        region="충청남도",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        issue="삼성디스플레이 67조 투자",
    )

    result = asyncio.run(QwenQueryExpansionService(transport=transport).expand(issue))

    assert result.protected_terms == ["삼성디스플레이", "67조", "투자"]
    assert len(transport.calls) == 2
    first, second = (c["json_body"] for c in transport.calls)
    assert first["format"] == ResearchPlan.model_json_schema()
    assert first["messages"][0]["content"] == SYSTEM_PROMPT
    assert second["format"] == QueryDraftSet.model_json_schema()
    assert "RQ10" not in second["messages"][1]["content"]  # REACTION is code-owned
    # synonym expansion: both region spellings are searched
    texts = [q.query for q in result.queries]
    assert "삼성디스플레이 충청남도 투자 일정 1" in texts
    assert "삼성디스플레이 충남 투자 일정 1" in texts
    # neutral opinion corpus for REACTION
    reaction = [q for q in result.queries if q.type is QueryType.REACTION]
    assert {q.query for q in reaction} == {
        "삼성디스플레이 67조 투자",
        "충청남도 삼성디스플레이 67조 투자",
        "충남 삼성디스플레이 67조 투자",
    }
    assert {q.search_purpose for q in reaction} == {SearchPurpose.OPINION_CORPUS}
    # bias words stripped from factual queries; CONCERN is frame discovery
    impact = [q.query for q in result.queries if q.type is QueryType.IMPACT]
    assert not any("효과" in q for q in impact)
    assert {q.search_purpose for q in result.queries if q.type is QueryType.CONCERN} == {
        SearchPurpose.FRAME_DISCOVERY
    }
    assert any(q.type is QueryType.FOLLOWUP for q in result.queries)


def test_qwen_rejects_malformed_structured_output() -> None:
    transport = _Transport(_Response({"message": {"content": "not json"}}))
    service = QwenQueryExpansionService(transport=transport)

    with pytest.raises(ValueError, match="Qwen response"):
        asyncio.run(
            service.expand(
                IssueInput(
                    region="충청남도",
                    start_date=date(2026, 9, 1),
                    end_date=date(2026, 9, 30),
                    issue="삼성디스플레이 투자",
                )
            )
        )
