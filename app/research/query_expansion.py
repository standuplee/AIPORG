"""Qwen-backed research-question and search-query generation."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any, Protocol

import requests
from pydantic import BaseModel

from app.research.query.prompts import (
    QUERY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_query_prompt,
    build_user_prompt,
)
from app.research.query.regions import BIAS_TERMS, REGION_ALIASES
from app.schemas.research import (
    IssueInput,
    QueryDraftSet,
    QueryExpansionResult,
    QueryType,
    ResearchPlan,
    SearchPurpose,
    SearchQuery,
)

QWEN_BASE_URL = "http://localhost:11434"


class _Response(Protocol):
    status_code: int

    def json(self) -> Any: ...


class _Transport(Protocol):
    async def post(
        self, url: str, *, json_body: Mapping[str, object]
    ) -> _Response: ...


class _RequestsTransport:
    async def post(
        self, url: str, *, json_body: Mapping[str, object]
    ) -> requests.Response:
        return await asyncio.to_thread(
            requests.post,
            url,
            json=dict(json_body),
            # Local 8B structured generation can exceed a normal web API timeout.
            timeout=120,
        )


class QwenQueryExpansionService:
    def __init__(
        self,
        *,
        model: str = "qwen3:8b",
        base_url: str = QWEN_BASE_URL,
        transport: _Transport | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _RequestsTransport()

    async def chat(self, system: str, user: str, schema: type[BaseModel]) -> Any:
        response = await self.transport.post(
            f"{self.base_url}/api/chat",
            json_body={
                "model": self.model,
                "stream": False,
                "think": False,
                "format": schema.model_json_schema(),
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Qwen response returned HTTP {response.status_code}")
        try:
            return schema.model_validate_json(response.json()["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"Qwen response did not match {schema.__name__}: {exc}") from exc

    async def expand(self, issue: IssueInput) -> QueryExpansionResult:
        # Qwen #1: research questions only.
        plan = await self.chat(
            SYSTEM_PROMPT,
            build_user_prompt(
                issue.region,
                issue.start_date.isoformat(),
                issue.end_date.isoformat(),
                issue.issue,
            ),
            ResearchPlan,
        )
        input_text = f"{issue.region} {issue.issue}"
        decomposition = plan.decomposition.model_copy(
            update={
                field: [t.strip() for t in getattr(plan.decomposition, field) if t.strip() in input_text and t.strip()]
                for field in (
                    "subjects", "actions", "amounts", "locations",
                    "organizations", "policies", "explicit_in_input",
                )
            }
        )
        # Qwen #2: lexical query variants per question. REACTION gets neutral
        # corpus queries from code so the query itself cannot steer sentiment.
        asked = [q for q in plan.research_questions if q.type is not QueryType.REACTION]
        drafts = await self.chat(
            QUERY_SYSTEM_PROMPT,
            build_query_prompt(
                issue.region,
                issue.issue,
                json.dumps([q.model_dump(mode="json") for q in asked], ensure_ascii=False),
            ),
            QueryDraftSet,
        )
        by_id = {d.research_question_id: d.queries for d in drafts.drafts}
        aliases = REGION_ALIASES.get(issue.region, [issue.region])
        queries: list[SearchQuery] = []
        seen: set[str] = set()
        for question in plan.research_questions:
            if question.type is QueryType.REACTION:
                raw, purpose = [issue.issue, f"{issue.region} {issue.issue}"], SearchPurpose.OPINION_CORPUS
            else:
                if question.id not in by_id:
                    raise ValueError(f"Qwen produced no queries for {question.id}")
                raw = by_id[question.id]
                purpose = (
                    SearchPurpose.FRAME_DISCOVERY
                    if question.type is QueryType.CONCERN
                    else SearchPurpose.FACT_RESEARCH
                )
                if purpose is SearchPurpose.FACT_RESEARCH:
                    raw = [" ".join(t for t in r.split() if t not in BIAS_TERMS) for r in raw]
            for text in raw:
                for alias in aliases:
                    variant = " ".join(text.replace(issue.region, alias).split())
                    if variant and variant.casefold() not in seen:
                        seen.add(variant.casefold())
                        queries.append(
                            SearchQuery(
                                research_question_id=question.id,
                                type=question.type,
                                query=variant,
                                search_purpose=purpose,
                            )
                        )
        return QueryExpansionResult(
            issue=issue.issue,
            decomposition=decomposition,
            # Code-owned: the user's own wording must survive every later rewrite.
            protected_terms=list(dict.fromkeys(issue.issue.split())),
            research_questions=plan.research_questions,
            queries=queries,
        )
