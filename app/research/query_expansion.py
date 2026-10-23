"""Qwen-backed research-question and search-query generation."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any, Protocol

import requests

from app.research.query.prompts import SYSTEM_PROMPT
from app.schemas.research import IssueInput, QueryExpansionResult

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

    async def expand(self, issue: IssueInput) -> QueryExpansionResult:
        response = await self.transport.post(
            f"{self.base_url}/api/chat",
            json_body={
                "model": self.model,
                "stream": False,
                "think": False,
                "format": QueryExpansionResult.model_json_schema(),
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": issue.model_dump_json()},
                ],
            },
        )
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Qwen response returned HTTP {response.status_code}")
        try:
            content = response.json()["message"]["content"]
            result = QueryExpansionResult.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"Qwen response did not match QueryExpansionResult: {exc}") from exc
        if result.issue != issue.issue:
            raise ValueError("Qwen response issue does not match the requested issue")
        return result
