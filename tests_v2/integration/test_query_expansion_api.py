from fastapi.testclient import TestClient

from app.research import api
from app.schemas.research import QueryExpansionResult


def test_swagger_endpoint_accepts_issue_and_returns_research_plan(monkeypatch) -> None:
    payload = {
        "issue": "삼성디스플레이 67조 투자",
        "protected_entities": ["삼성디스플레이"],
        "research_questions": [
            {"id": "q1", "type": "FACT", "question": "투자 계획은 무엇인가?"}
        ],
        "queries": [
            {
                "research_question_id": "q1",
                "type": "FACT",
                "query": "삼성디스플레이 67조 투자",
                "purpose": "투자 계획 확인",
            }
        ],
    }

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
