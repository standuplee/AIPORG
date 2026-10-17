"""robots.txt compliance gate, ported from ``aiporg/collect/community/robots.py``.

Fetches and caches each domain's robots.txt once (through the collector's own
transport, so it goes through the same retry/timeout behavior as every other
request) and answers whether a given URL may be fetched for the configured
user agent. Unreadable or unparseable robots.txt fails closed -- deny, not
allow -- the same "준법 우선" choice 1.0 made; a network hiccup on
robots.txt must never silently grant access that a real robots.txt would
have denied.

Uses ``protego`` (Scrapy's RFC 9309-compliant parser), not the standard
library's ``urllib.robotparser``. Confirmed live against
``fmkorea.com/robots.txt`` (2026-10-17): that file, like many real sites,
lists ``Disallow: /`` *before* more specific ``Allow: /best`` /
``Allow: /humor`` lines in the same ``User-agent: *`` group. RFC 9309 says
the *longest matching path* wins regardless of order (so ``/humor`` should
be allowed), but ``urllib.robotparser`` instead applies the first matching
rule in file order -- so it incorrectly denied *everything* on that site,
including paths the site's own robots.txt explicitly allows. ``protego``
implements the longest-match rule correctly (verified against this exact
file); switching fixed a real compliance bug in this gate, not just a
fmkorea-specific one.
"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from protego import Protego

from app.collectors.transport import HttpResponse


class _Transport(Protocol):
    async def get(
        self, url: str, *, params: dict[str, object] | None = None, headers: dict[str, str] | None = None
    ) -> HttpResponse: ...


class RobotsGate:
    def __init__(self, transport: _Transport, *, user_agent: str) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self._cache: dict[str, Protego | None] = {}

    async def _parser(self, url: str) -> Protego | None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._cache:
            return self._cache[base]
        try:
            response = await self.transport.get(
                base + "/robots.txt", headers={"User-Agent": self.user_agent}
            )
        except Exception:  # noqa: BLE001 -- any transport failure fails closed below
            self._cache[base] = None
            return None
        if response.status_code >= 400:
            # No robots.txt is, per the standard, full allow.
            parser = Protego.parse("")
        else:
            parser = Protego.parse(response.body)
        self._cache[base] = parser
        return parser

    async def allowed(self, url: str) -> bool:
        parser = await self._parser(url)
        if parser is None:
            return False  # fail closed: robots.txt was unreadable
        try:
            return parser.can_fetch(url, self.user_agent)
        except Exception:  # noqa: BLE001
            return False
