"""4차: FastAPI 내부 API.

분석 모듈이 커뮤니티 정규화 데이터를 조회하고, 수집을 트리거할 수 있는
내부 엔드포인트를 제공한다. (외부 공개용이 아닌 내부 서비스 계층)

실행: ./.venv/bin/uvicorn aiporg.api.main:app --port 8800
문서: http://localhost:8800/docs
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from fastapi import FastAPI, Query
    from pydantic import BaseModel
except Exception as e:  # noqa: BLE001
    raise RuntimeError("FastAPI/pydantic 필요: pip install fastapi uvicorn") from e

from ..collect.community.adapter import CommunityAdapter
from ..collect.community.policy import load_policies
from ..collect.community.store import CommunityStore

app = FastAPI(title="AIPORG Internal API", version="1.0.0")


def _db_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "data", "community.db")


class PostOut(BaseModel):
    site: str
    url: str
    title: str
    body: str
    posted_at: Optional[str] = None
    views: int = 0
    likes: int = 0
    comment_count: int = 0
    keyword: str = ""


class CollectIn(BaseModel):
    keywords: list[str]
    start: Optional[str] = None
    end: Optional[str] = None


@app.get("/health")
def health():
    store = CommunityStore(_db_path())
    return {"status": "ok", "stored_posts": store.count()}


@app.get("/sites")
def sites():
    """사이트별 정책·활성화 상태."""
    pol = load_policies()
    return {n: {"enabled": p.enabled, "domains": p.domains,
                "min_interval_sec": p.min_interval_sec,
                "max_requests_per_run": p.max_requests_per_run,
                "respect_robots": p.respect_robots} for n, p in pol.items()}


@app.get("/posts", response_model=list[PostOut])
def posts(keyword: Optional[str] = None, site: Optional[str] = None,
          start: Optional[str] = None, end: Optional[str] = None,
          limit: int = Query(200, le=2000)):
    store = CommunityStore(_db_path())
    rows = store.query(keyword=keyword, site=site, start=start, end=end, limit=limit)
    return [PostOut(**r.__dict__) for r in rows]


@app.post("/collect")
def collect(body: CollectIn):
    """커뮤니티 수집 트리거 (활성 사이트만; 비활성이면 no-op)."""
    from datetime import date
    adapter = CommunityAdapter(_db_path())
    s = date.fromisoformat(body.start) if body.start else None
    e = date.fromisoformat(body.end) if body.end else None
    stats = adapter.run(body.keywords, s, e)
    return {"discovered": stats.discovered, "fetched": stats.fetched,
            "parsed": stats.parsed, "stored": stats.stored, "skipped": stats.skipped}
