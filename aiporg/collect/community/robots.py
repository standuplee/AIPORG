"""robots.txt 준수 게이트.

도메인별 robots.txt 를 1회 조회·캐시하고, 우리 User-Agent 기준으로 해당
URL 수집 허용 여부를 판단한다. robots 를 못 읽으면 '보수적으로 거부'한다
(fail-closed) — 준법 우선.
"""
from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse

log = logging.getLogger(__name__)


class RobotsGate:
    def __init__(self, user_agent: str, timeout: int = 10, fail_closed: bool = True):
        self.user_agent = user_agent
        self.timeout = timeout
        self.fail_closed = fail_closed
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _parser(self, url: str):
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._cache:
            return self._cache[base]
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            import requests
            r = requests.get(base + "/robots.txt", timeout=self.timeout,
                             headers={"User-Agent": self.user_agent})
            if r.status_code >= 400:
                # robots 없음(404) → 표준상 전체 허용으로 간주
                rp.parse([])
            else:
                rp.parse(r.text.splitlines())
            self._cache[base] = rp
        except Exception as e:  # noqa: BLE001
            log.warning("robots.txt 조회 실패(%s): %s", base, e)
            self._cache[base] = None
        return self._cache[base]

    def allowed(self, url: str) -> bool:
        rp = self._parser(url)
        if rp is None:
            return not self.fail_closed   # 조회 실패 시 보수적으로 거부
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return not self.fail_closed

    def crawl_delay(self, url: str) -> float | None:
        rp = self._parser(url)
        if rp is None:
            return None
        try:
            d = rp.crawl_delay(self.user_agent)
            return float(d) if d is not None else None
        except Exception:
            return None
