from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport


@dataclass
class _FakeRequestsResponse:
    status_code: int
    headers: dict
    content: bytes
    text: str


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


def test_default_request_recovers_utf8_body_missing_from_http_headers() -> None:
    # No charset in the HTTP header and no <meta charset> either --
    # response.text would default to ISO-8859-1 here (the real-data bug,
    # 2026-10-19) and mangle the Korean text. UnicodeDammit's encoding
    # detection should still recover it.
    html = "<html><body>충청남도가 발표했다</body></html>"
    fake_response = _FakeRequestsResponse(
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=html.encode("utf-8"),
        text=html.encode("utf-8").decode("latin-1"),  # what requests.text would give here
    )
    transport = RequestsTransport()
    with patch("requests.request", return_value=fake_response):
        response = asyncio.run(transport.get("https://example.test"))

    assert response.body == html


def test_default_request_honors_html_meta_charset_declaration() -> None:
    html = '<html><head><meta charset="euc-kr"></head><body>충청남도가 발표했다</body></html>'
    encoded = html.encode("euc-kr")
    fake_response = _FakeRequestsResponse(
        status_code=200,
        headers={"Content-Type": "text/html"},  # no charset param -- only the meta tag has it
        content=encoded,
        text=encoded.decode("latin-1"),
    )
    transport = RequestsTransport()
    with patch("requests.request", return_value=fake_response):
        response = asyncio.run(transport.get("https://example.test"))

    assert "충청남도가 발표했다" in response.body


def test_default_request_still_parses_json_bodies() -> None:
    body = '{"query": "충청남도"}'
    fake_response = _FakeRequestsResponse(
        status_code=200,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        content=body.encode("utf-8"),
        text=body,
    )
    transport = RequestsTransport()
    with patch("requests.request", return_value=fake_response):
        response = asyncio.run(transport.get("https://example.test"))

    assert response.json() == {"query": "충청남도"}
