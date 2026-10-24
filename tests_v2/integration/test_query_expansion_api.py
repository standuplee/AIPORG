from fastapi.testclient import TestClient

from app.research import api
from app.schemas.research import QueryExpansionResult


def test_swagger_endpoint_accepts_issue_and_returns_research_plan(monkeypatch) -> None:
    payload = {
        "issue": "삼성디스플레이 67조 투자",
        "decomposition": {
            "subjects": ["삼성디스플레이"],
            "actions": ["투자"],
            "amounts": ["67조"],
            "locations": [],
            "organizations": ["삼성디스플레이"],
            "policies": [],
            "explicit_in_input": ["삼성디스플레이", "67조", "투자"],
            "unknowns": ["투자 대상 지역"],
        },
        "protected_terms": ["충청남도", "삼성디스플레이", "67조", "투자"],
        "research_questions": [],
        "queries": [],
    }
    question_types = [
        "FACT", "FACT", "DETAIL", "DETAIL", "BACKGROUND", "IMPACT", "IMPACT",
        "CONCERN", "CONCERN", "REACTION", "FOLLOWUP",
    ]
    payload["research_questions"] = [
        {"id": f"q{index}", "type": kind, "question": f"질문 {index}?"}
        for index, kind in enumerate(question_types, start=1)
    ]
    payload["queries"] = [
        {
            "research_question_id": question["id"],
            "type": question["type"],
            "query": f"삼성디스플레이 충청남도 조사 {index}",
            "search_purpose": "FACT_RESEARCH",
        }
        for index, question in enumerate(payload["research_questions"], start=1)
    ]

    async def expand(issue):
        assert issue.region == "충청남도"
        return QueryExpansionResult.model_validate(payload)

    monkeypatch.setattr(api.query_expansion_service, "expand", expand)
    client = TestClient(api.app)

    response = client.post(
        "/query-expansion",
        json={
            "region": "충청남도",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "issue": "삼성디스플레이 67조 투자",
        },
    )

    assert response.status_code == 200
    assert response.json() == payload
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/query-expansion"]["post"]
    example = operation["requestBody"]["content"]["application/json"]["examples"]["issue"]
    assert example["value"] == {
        "region": "충청남도",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "issue": "삼성디스플레이 67조 투자",
    }
