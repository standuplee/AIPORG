"""정중한 HTTP fetch (robots + rate-limit + 제외규칙 게이트).

로그인/우회/차단회피를 하지 않는다. 표준 User-Agent 를 밝히고, robots 불허
또는 제외 패턴이면 수집하지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .policy import SitePolicy
from .ratelimit import RateLimiter
from .robots import RobotsGate

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int = 0
    html: str = ""
    skipped_reason: str = ""


class PoliteFetcher:
    def __init__(self, policy: SitePolicy):
        self.p = policy
        self.robots = RobotsGate(policy.user_agent, policy.request_timeout_sec,
                                 fail_closed=policy.respect_robots)
        # robots crawl-delay 가 정책보다 크면 그 값을 존중
        self.limiter = RateLimiter(policy.min_interval_sec, policy.max_requests_per_run)

    def fetch(self, url: str) -> FetchResult:
        if self.p.is_excluded(url):
            return FetchResult(url, False, skipped_reason="제외 패턴")
        if self.p.respect_robots and not self.robots.allowed(url):
            log.info("[%s] robots 불허 → 건너뜀: %s", self.p.name, url)
            return FetchResult(url, False, skipped_reason="robots 불허")
        delay = self.robots.crawl_delay(url)
        if delay and delay > self.limiter.min_interval:
            self.limiter.min_interval = delay
        if not self.limiter.acquire():
            return FetchResult(url, False, skipped_reason="요청 한도 초과")
        try:
            import requests
            r = requests.get(url, timeout=self.p.request_timeout_sec,
                             headers={"User-Agent": self.p.user_agent,
                                      "Accept-Language": "ko-KR,ko;q=0.9"})
            return FetchResult(url, r.status_code < 400, r.status_code, r.text)
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] fetch 실패: %s", self.p.name, e)
            return FetchResult(url, False, skipped_reason=str(e)[:80])
