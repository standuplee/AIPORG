"""Local API for trying the research planner in Swagger UI."""

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
import requests

from app.research.query_expansion import QwenQueryExpansionService
from app.core.config import get_settings
from app.schemas.research import IssueInput, QueryExpansionResult
from app.search.daum import DaumSearchProvider
from app.search.naver import NaverSearchProvider
from app.search.schemas import SearchResult
from app.search.service import SearchService

load_dotenv()
_settings = get_settings()

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


search_service = SearchService(
    naver=NaverSearchProvider(_settings.naver_client_id or "", _settings.naver_client_secret or ""),
    daum=DaumSearchProvider(_settings.kakao_rest_api_key or ""),
)


@app.get("/search/fact", response_model=list[SearchResult])
async def search_fact(query: str) -> list[SearchResult]:
    return await search_service.search_fact(query)


@app.get("/search/opinion", response_model=list[SearchResult])
async def search_opinion(query: str) -> list[SearchResult]:
    return await search_service.search_opinion(query)
