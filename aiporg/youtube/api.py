"""FastAPI 라우터 — YouTube 여론 분석 API.

실행: ./.venv/bin/uvicorn aiporg.youtube.api:app --port 8810
문서: http://localhost:8810/docs
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .config import YouTubeConfig
from .repository import YouTubeRepository
from .schema import YouTubeReport
from .service import YouTubeService

app = FastAPI(title="AIPORG YouTube API", version="1.0.0")


class AnalyzeRequest(BaseModel):
    keywords: Optional[list[str]] = None
    period_start: str = "2026-06-01"
    period_end: str = "2026-06-30"
    subject_name: str = "충청남도"
    leader_name: str = "박수현"
    force: bool = False
    use_mock: bool = False               # API 키 없이 시연 시 True


def _config(req: AnalyzeRequest) -> YouTubeConfig:
    cfg = YouTubeConfig(
        period_start=date.fromisoformat(req.period_start),
        period_end=date.fromisoformat(req.period_end),
        subject_name=req.subject_name, leader_name=req.leader_name, force=req.force)
    if req.keywords:
        cfg.keywords = req.keywords
    return cfg


@app.get("/health")
def health() -> dict:
    repo = YouTubeRepository(YouTubeConfig().db_path)
    return {"status": "ok", **repo.counts()}


@app.post("/analyze", response_model=YouTubeReport)
def analyze(req: AnalyzeRequest) -> YouTubeReport:
    cfg = _config(req)
    client = None
    if req.use_mock:
        from .mock_data import MockApiClient
        client = MockApiClient()
    service = YouTubeService(cfg, client=client)
    return service.run()
