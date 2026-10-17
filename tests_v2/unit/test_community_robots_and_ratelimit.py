import asyncio

from app.collectors.community.ratelimit import RateLimiter
from app.collectors.community.robots import RobotsGate
from app.collectors.transport import HttpResponse


class MockTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[str] = []

    async def get(self, url: str, *, params=None, headers=None) -> HttpResponse:
        self.calls.append(url)
        return next(self.responses)


def test_robots_gate_allows_when_robots_txt_permits() -> None:
    transport = MockTransport(
        [HttpResponse(status_code=200, headers={}, body="User-agent: *\nAllow: /")]
    )
    gate = RobotsGate(transport, user_agent="TestBot")

    allowed = asyncio.run(gate.allowed("https://example.com/post/1"))

    assert allowed is True


def test_robots_gate_applies_longest_match_not_file_order() -> None:
    # Regression test for a real bug found live against fmkorea.com's actual
    # robots.txt (2026-10-17): it lists "Disallow: /" *before* more specific
    # "Allow: /best" / "Allow: /humor" lines in the same User-agent: * group.
    # RFC 9309 says the longest matching path wins regardless of order, so
    # /humor should be allowed -- stdlib's urllib.robotparser instead applied
    # the first matching rule in file order and denied everything, including
    # paths the site explicitly allows. This is why robots.py uses protego.
    transport = MockTransport(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body="User-agent: *\nDisallow: /\nAllow: /$\nAllow: /best\nAllow: /humor",
            )
        ]
    )
    gate = RobotsGate(transport, user_agent="TestBot")

    assert asyncio.run(gate.allowed("https://example.com/humor/123")) is True
    assert asyncio.run(gate.allowed("https://example.com/best/456")) is True
    assert asyncio.run(gate.allowed("https://example.com/other/789")) is False


def test_robots_gate_denies_disallowed_paths() -> None:
    transport = MockTransport(
        [HttpResponse(status_code=200, headers={}, body="User-agent: *\nDisallow: /")]
    )
    gate = RobotsGate(transport, user_agent="TestBot")

    allowed = asyncio.run(gate.allowed("https://example.com/post/1"))

    assert allowed is False


def test_robots_gate_allows_when_robots_txt_is_missing() -> None:
    transport = MockTransport([HttpResponse(status_code=404, headers={}, body="")])
    gate = RobotsGate(transport, user_agent="TestBot")

    allowed = asyncio.run(gate.allowed("https://example.com/post/1"))

    assert allowed is True


def test_robots_gate_fails_closed_when_transport_raises() -> None:
    class RaisingTransport:
        async def get(self, url, *, params=None, headers=None):
            raise RuntimeError("network down")

    gate = RobotsGate(RaisingTransport(), user_agent="TestBot")

    allowed = asyncio.run(gate.allowed("https://example.com/post/1"))

    assert allowed is False


def test_robots_gate_caches_per_domain() -> None:
    transport = MockTransport(
        [HttpResponse(status_code=200, headers={}, body="User-agent: *\nAllow: /")]
    )
    gate = RobotsGate(transport, user_agent="TestBot")

    asyncio.run(gate.allowed("https://example.com/post/1"))
    asyncio.run(gate.allowed("https://example.com/post/2"))

    assert len(transport.calls) == 1


def test_rate_limiter_blocks_requests_beyond_the_run_budget() -> None:
    limiter = RateLimiter(min_interval_sec=0.0, max_requests_per_run=2)

    assert asyncio.run(limiter.acquire()) is True
    assert asyncio.run(limiter.acquire()) is True
    assert asyncio.run(limiter.acquire()) is False
    assert limiter.can_request() is False
    assert limiter.used == 2
