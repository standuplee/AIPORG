"""HTTP transport boundary shared by AIPORG 2.0 collectors."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.collectors.errors import CollectorError


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: str

    def json(self) -> Any:
        return json.loads(self.body)


RequestFunction = Callable[..., HttpResponse]


class RequestsTransport:
    """Async facade over requests with bounded retry behavior."""

    def __init__(
        self,
        *,
        request_fn: RequestFunction | None = None,
        timeout_seconds: float = 10,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._request_fn = request_fn or self._default_request

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        for attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    self._request_fn,
                    method="GET",
                    url=url,
                    params=dict(params or {}),
                    headers=dict(headers or {}),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise CollectorError(
                        code="network_error",
                        message=f"HTTP request failed: {exc}",
                        retryable=True,
                        details={"url": url, "attempts": attempt + 1},
                    ) from exc
                await self._backoff(attempt)
                continue

            if response.status_code not in {429, *range(500, 600)}:
                return response
            if attempt >= self.max_retries:
                raise CollectorError(
                    code="http_status",
                    message=f"HTTP request returned status {response.status_code}",
                    retryable=True,
                    details={
                        "url": url,
                        "status_code": response.status_code,
                        "attempts": attempt + 1,
                    },
                )
            await self._backoff(attempt)

        raise AssertionError("retry loop must return or raise")

    async def _backoff(self, attempt: int) -> None:
        delay = self.backoff_seconds * (2**attempt)
        if delay:
            await asyncio.sleep(delay)

    @staticmethod
    def _default_request(**kwargs: Any) -> HttpResponse:
        import requests

        response = requests.request(**kwargs)
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.text,
        )
