from __future__ import annotations

import asyncio

import pytest

from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport


def test_transport_returns_response_without_retry() -> None:
    calls: list[int] = []

    def request(**kwargs):
        calls.append(1)
        return HttpResponse(status_code=200, headers={}, body='{"ok": true}')

    transport = RequestsTransport(request_fn=request, timeout_seconds=3, max_retries=2)

    response = asyncio.run(transport.get("https://example.test"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(calls) == 1


def test_transport_retries_retryable_status_then_succeeds() -> None:
    responses = iter([
        HttpResponse(status_code=429, headers={}, body="busy"),
        HttpResponse(status_code=200, headers={}, body="ok"),
    ])

    transport = RequestsTransport(
        request_fn=lambda **kwargs: next(responses),
        max_retries=1,
        backoff_seconds=0,
    )

    response = asyncio.run(transport.get("https://example.test"))

    assert response.status_code == 200


def test_transport_raises_structured_error_after_retry_exhaustion() -> None:
    transport = RequestsTransport(
        request_fn=lambda **kwargs: HttpResponse(status_code=503, headers={}, body="down"),
        max_retries=1,
        backoff_seconds=0,
    )

    with pytest.raises(CollectorError) as raised:
        asyncio.run(transport.get("https://example.test"))

    assert raised.value.code == "http_status"
    assert raised.value.retryable is True
    assert raised.value.details["status_code"] == 503


def test_transport_wraps_request_exception() -> None:
    def request(**kwargs):
        raise TimeoutError("timed out")

    transport = RequestsTransport(request_fn=request, max_retries=0)

    with pytest.raises(CollectorError) as raised:
        asyncio.run(transport.get("https://example.test"))

    assert raised.value.code == "network_error"
    assert raised.value.retryable is True
