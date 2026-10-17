"""Per-site request throttle, ported from ``aiporg/collect/community/ratelimit.py``.

Same two limits as 1.0: a minimum delay between requests to the same site,
and a hard cap on total requests per run. The only change is
``time.sleep`` -> ``asyncio.sleep`` so the wait doesn't block the event loop
``app/collectors/transport.py`` and every other 2.0 collector run on.
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    def __init__(self, min_interval_sec: float, max_requests_per_run: int) -> None:
        self.min_interval_sec = min_interval_sec
        self.max_requests_per_run = max_requests_per_run
        self._count = 0
        self._last = 0.0

    def can_request(self) -> bool:
        return self._count < self.max_requests_per_run

    async def acquire(self) -> bool:
        """Call immediately before a request. False if the run's budget is used up."""
        if self._count >= self.max_requests_per_run:
            return False
        now = time.monotonic()
        wait = self.min_interval_sec - (now - self._last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()
        self._count += 1
        return True

    @property
    def used(self) -> int:
        return self._count
