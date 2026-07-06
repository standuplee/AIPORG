"""사이트별 요청 제한기.

호스트별 최소 요청 간격(min_interval) 및 실행당 최대 요청 수
(max_requests_per_run)를 강제한다. 과도한 요청을 구조적으로 방지.
"""
from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, min_interval_sec: float, max_requests_per_run: int):
        self.min_interval = min_interval_sec
        self.max_requests = max_requests_per_run
        self._count = 0
        self._last = 0.0

    def can_request(self) -> bool:
        return self._count < self.max_requests

    def acquire(self) -> bool:
        """요청 직전 호출. 한도 초과면 False, 아니면 간격을 지키고 True."""
        if self._count >= self.max_requests:
            return False
        now = time.monotonic()
        wait = self.min_interval - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self._count += 1
        return True

    @property
    def used(self) -> int:
        return self._count
