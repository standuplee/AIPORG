import asyncio
import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.research.query_expansion import QwenQueryExpansionService
from app.research.query.prompts import SYSTEM_PROMPT
from app.schemas.research import (
    IssueInput,
    QueryExpansionResult,
    QueryType,
)


def _result_payload() -> dict[str, object]:
    return {
        "issue": "삼성디스플레이 투자",
        "protected_entities": ["삼성디스플레이", "아산"],
        "research_questions": [
            {"id": "q1", "type": "FACT", "question": "투자 계획은 무엇인가?"},
            {"id": "q2", "type": "IMPACT", "question": "지역에 미치는 영향은 무엇인가?"},
        ],
        "queries": [
            {
                "research_question_id": "q1",
                "type": "FACT",
                "query": "삼성디스플레이 아산 투자 계획",
                "purpose": "투자 계획 확인",
            },
            {
                "research_question_id": "q2",
                "type": "IMPACT",
                "query": "삼성디스플레이 아산 지역경제 영향",
                "purpose": "지역 영향 확인",
            },
        ],
    }


class _Response:
    status_code = 200

    def __init__(self, body: dict[str, object]) -> None:
        self.body = json.dumps(body)

    def json(self):
        return json.loads(self.body)


class _Transport:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def post(self, url, *, json_body):
        self.calls.append({"url": url, "json_body": json_body})
        return self.response


def test_query_expansion_requires_valid_issue_and_matching_question_links() -> None:
    issue = IssueInput(
        region="충청남도",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        issue="삼성디스플레이 투자",
    )
    result = QueryExpansionResult.model_validate(_result_payload())

    assert issue.issue == result.issue
    assert result.queries[0].research_question_id == result.research_questions[0].id
    assert result.queries[0].type is QueryType.FACT

    payload = _result_payload()
    payload["queries"] = [
        {"research_question_id": "missing", "type": "FACT", "query": "query", "purpose": "purpose"}
    ]
    with pytest.raises(ValidationError):
        QueryExpansionResult.model_validate(payload)

    payload = _result_payload()
    payload["queries"] = payload["queries"][:1]
    with pytest.raises(ValidationError):
        QueryExpansionResult.model_validate(payload)

    payload = _result_payload()
    payload["research_questions"] = [
        {"id": f"q{index}", "type": "FACT", "question": f"question {index}"}
        for index in range(11)
    ]
    payload["queries"] = [
        {
            "research_question_id": f"q{index}",
            "type": "FACT",
            "query": f"query {index}",
            "purpose": "test",
        }
        for index in range(10)
    ]
    with pytest.raises(ValidationError):
        QueryExpansionResult.model_validate(payload)


def test_issue_input_rejects_reversed_period() -> None:
    with pytest.raises(ValidationError):
        IssueInput(
            region="충청남도",
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 1),
            issue="삼성디스플레이 투자",
        )


def test_qwen_generates_research_questions_before_search_queries() -> None:
    payload = _result_payload()
    transport = _Transport(
        _Response({"message": {"content": json.dumps(payload, ensure_ascii=False)}})
    )
    service = QwenQueryExpansionService(transport=transport)

    result = asyncio.run(
        service.expand(
            IssueInput(
                region="충청남도",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 30),
                issue="삼성디스플레이 투자",
            )
        )
    )

    assert result == QueryExpansionResult.model_validate(payload)
    request = transport.calls[0]
    body = request["json_body"]
    assert request["url"] == "http://localhost:11434/api/chat"
    assert body["model"] == "qwen3:8b"
    assert body["stream"] is False
    assert body["think"] is False
    assert body["format"] == QueryExpansionResult.model_json_schema()
    assert body["messages"][0]["content"] == SYSTEM_PROMPT


def test_qwen_rejects_malformed_structured_output() -> None:
    transport = _Transport(
        _Response({"message": {"content": "not json"}})
    )
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
