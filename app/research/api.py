"""Local API for trying the research planner in Swagger UI."""

from fastapi import Body, FastAPI, HTTPException
import requests

from app.research.query_expansion import QwenQueryExpansionService
from app.schemas.research import IssueInput, QueryExpansionResult

app = FastAPI(title="Issue Research Engine", version="0.1.0")
query_expansion_service = QwenQueryExpansionService()


@app.post(
    "/query-expansion",
    response_model=QueryExpansionResult,
    responses={502: {"description": "Ollama query generation failed"}},
)
async def expand_query(
    issue: IssueInput = Body(
        openapi_examples={
            "issue": {
                "summary": "삼성디스플레이 투자 조사",
                "value": {
                    "region": "충청남도",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-30",
                    "issue": "삼성디스플레이 67조 투자",
                },
            }
        }
    ),
) -> QueryExpansionResult:
    try:
        return await query_expansion_service.expand(issue)
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
