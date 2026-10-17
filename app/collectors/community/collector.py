"""Community discovery-collection via Naver web search + site-specific HTML parsing.

Ported from the 1.0 ``aiporg/collect/community/`` module (``adapter.py`` +
``discovery.py`` + ``fetch.py`` + ``policy.py`` + ``ratelimit.py`` +
``robots.py`` + ``sites/*.py``) to the 2.0 ``BaseCollector`` protocol
(``search()``/``fetch()``). The pipeline is unchanged: there is no official
API for any of clien/dcinside/fmkorea/ruliweb/theqoo, so candidate post URLs
are discovered through Naver's general web-document search (``webkr.json``)
filtered to each enabled site's domains, then each candidate is gated
through robots.txt + a per-site rate limit + exclude patterns before its
public HTML is fetched and parsed by a site-specific parser
(``app/collectors/community/parsers.py``).

Safety gate preserved from 1.0, unchanged: every site in
``config/community.yaml`` defaults to ``enabled: false`` until an operator
has reviewed that site's robots.txt/terms of service and flipped it on.
This collector does not modify that file and collects nothing (an empty
result, not an error) while every site stays disabled.

Real gaps found and fixed while porting (live-verified, see
``parsers.py`` docstrings for the per-site evidence):
  - 1.0's parsers never populated ``posted_at`` in practice. 2.0's
    ``SearchResult.published_at`` is required, so every parser here adds
    real date extraction and a post with no parseable date is dropped
    (same "게시 시각을 확인할 수 없는 자료는 보류" policy
    ``app/collectors/google_search.py`` already applies).
  - fmkorea's and theqoo's title selectors were stale (confirmed against
    real posts) and have been fixed.
  - theqoo's "views" selector was actually reading the post's date text.
  - 1.0 filtered discovered URLs by domain only; a per-site URL-shape check
    (``parsers.POST_URL_PATTERNS``) now skips board/gallery/category
    listing pages before spending rate-limit budget fetching them.

Architectural difference from 1.0 (not a bug fix, a consequence of fitting
the 2.0 ``search()``/``fetch()`` split): 1.0's adapter did discovery, fetch,
and parse in one pass. Here, ``search()`` does discovery *and* the
fetch+parse (it needs the parsed date for the required ``published_at``
field before it can even construct a ``SearchResult``), caching the parsed
``PostContent`` in memory keyed by URL; ``fetch()`` then returns the cached
result without a second HTTP request. This only works because
``CollectionService.collect()`` always calls ``search()`` once and then
``fetch()`` on each of its own results sequentially on the same collector
instance (``app/collection/service.py``) -- if ``fetch()`` is ever called
on a URL this instance did not just discover (cache miss), it falls back to
re-fetching live rather than failing outright.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from typing import Protocol
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from app.collectors.base import BaseCollector
from app.collectors.community.parsers import (
    FMKOREA_BOARDS,
    PostContent,
    POST_URL_PATTERNS,
    extract_fmkorea_board_post_ids,
    get_parser,
)
from app.collectors.community.policy import SitePolicy, load_policies
from app.collectors.community.ratelimit import RateLimiter
from app.collectors.community.robots import RobotsGate
from app.collectors.errors import CollectorError
from app.collectors.transport import HttpResponse, RequestsTransport
from app.core.enums import ChannelType
from app.schemas.document import RawDocument, SearchResult
from app.schemas.query import SearchQuery


NAVER_WEBKR_URL = "https://openapi.naver.com/v1/search/webkr.json"


class _Transport(Protocol):
    async def get(
        self, url: str, *, params: dict[str, object] | None = None, headers: dict[str, str] | None = None
    ) -> HttpResponse: ...


def _clean_snippet(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", "", value))).strip()


class CommunityCollector(BaseCollector):
    """Discover and fetch community posts across the sites enabled in config/community.yaml."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: _Transport | None = None,
        policies: dict[str, SitePolicy] | None = None,
        config_path: str | None = None,
        discovery_display: int = 50,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Naver API credentials are required for community discovery")
        if not 1 <= discovery_display <= 100:
            raise ValueError("discovery_display must be between 1 and 100")
        self.client_id = client_id
        self.client_secret = client_secret
        self.transport = transport or RequestsTransport()
        self.policies = policies if policies is not None else load_policies(config_path)
        self.discovery_display = discovery_display
        self._robots_gates = {
            name: RobotsGate(self.transport, user_agent=policy.user_agent)
            for name, policy in self.policies.items()
        }
        # One RateLimiter per site, created lazily and kept for this
        # collector instance's whole lifetime -- which is one Streamlit
        # collection run (build_collectors() builds one instance reused
        # across every keyword), matching 1.0's "budget per adapter.run()
        # call" semantics rather than resetting per keyword.
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._parsed_cache: dict[str, PostContent] = {}
        # post id -> board ("best"/"best2"/"humor"), built once per instance
        # from each board's own listing page (see _fmkorea_board_membership).
        self._fmkorea_membership: dict[str, str] | None = None

    def _enabled_policies(self) -> dict[str, SitePolicy]:
        return {name: policy for name, policy in self.policies.items() if policy.enabled}

    def _rate_limiter(self, site: str, policy: SitePolicy) -> RateLimiter:
        if site not in self._rate_limiters:
            self._rate_limiters[site] = RateLimiter(policy.min_interval_sec, policy.max_requests_per_run)
        return self._rate_limiters[site]

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        enabled = self._enabled_policies()
        if not enabled:
            # Every site disabled is the default, safe state (see module
            # docstring) -- an empty result, not a failure.
            return []

        candidates = await self._discover(query.query, enabled)
        results: list[SearchResult] = []
        for site, url, snippet_title in candidates:
            policy = enabled[site]
            if site == "fmkorea":
                resolved_url = await self._resolve_fmkorea_url(url, policy)
                if resolved_url is None:
                    continue
                url = resolved_url
            if policy.is_excluded(url):
                continue
            pattern = POST_URL_PATTERNS.get(site)
            if pattern is not None:
                parsed_url = urlparse(url)
                if not pattern.search(parsed_url.path + "?" + parsed_url.query):
                    continue
            limiter = self._rate_limiter(site, policy)
            if not limiter.can_request():
                continue
            if policy.respect_robots and not await self._robots_gates[site].allowed(url):
                continue
            if not await limiter.acquire():
                continue
            content = await self._fetch_and_parse(url, policy, site)
            if content is None or not content.ok:
                continue
            self._parsed_cache[url] = content
            results.append(
                SearchResult(
                    source=site,
                    channel=ChannelType.COMMUNITY,
                    title=content.title or snippet_title,
                    url=url,
                    published_at=content.posted_at,
                    query=query.query,
                )
            )
        return results

    async def fetch(self, result: SearchResult) -> RawDocument:
        content = self._parsed_cache.pop(result.url, None)
        if content is None:
            # Cache miss: search() did not just discover this URL on this
            # instance (should not happen via CollectionService's normal
            # search-then-fetch sequence, see module docstring). Still route
            # through the same robots/rate-limit gates as search() rather
            # than ever fetching ungated -- a cache miss is a reason to be
            # defensive, not a reason to skip the site's own policy.
            policy = self.policies.get(result.source)
            if policy is None or not policy.enabled:
                raise CollectorError(
                    code="malformed_response",
                    message=f"Community site '{result.source}' is not enabled",
                    details={"provider": "community", "site": result.source, "url": result.url},
                )
            limiter = self._rate_limiter(result.source, policy)
            if policy.respect_robots and not await self._robots_gates[result.source].allowed(result.url):
                raise CollectorError(
                    code="malformed_response",
                    message="Community post disallowed by robots.txt on re-fetch",
                    details={"provider": "community", "site": result.source, "url": result.url},
                )
            if not await limiter.acquire():
                raise CollectorError(
                    code="malformed_response",
                    message="Community site rate-limit budget exhausted on re-fetch",
                    details={"provider": "community", "site": result.source, "url": result.url},
                )
            content = await self._fetch_and_parse(result.url, policy, result.source)
            if content is None or not content.ok:
                raise CollectorError(
                    code="malformed_response",
                    message="Community post body could not be parsed on re-fetch",
                    details={"provider": "community", "site": result.source, "url": result.url},
                )
        return RawDocument(
            document_id=uuid5(NAMESPACE_URL, result.url),
            source=result.source,
            channel=result.channel,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            query=result.query,
            platform=result.source,
            body=content.body,
            metadata={
                "document_type": "article",
                "views": content.views,
                "likes": content.likes,
                "comment_count": content.comment_count,
            },
            collected_at=datetime.now(timezone.utc),
        )

    async def _discover(
        self, keyword: str, enabled: dict[str, SitePolicy]
    ) -> list[tuple[str, str, str]]:
        seen: set[str] = set()
        candidates: list[tuple[str, str, str]] = []
        for site, policy in enabled.items():
            for hint in policy.search_hints[:2]:
                try:
                    response = await self.transport.get(
                        NAVER_WEBKR_URL,
                        params={"query": f"{keyword} {hint}", "display": self.discovery_display},
                        headers={
                            "X-Naver-Client-Id": self.client_id,
                            "X-Naver-Client-Secret": self.client_secret,
                        },
                    )
                except CollectorError:
                    # One failed (site, hint) discovery call must not fail
                    # discovery for the other sites/hints -- same per-site
                    # isolation 1.0's discovery.py used (log and continue).
                    continue
                if not 200 <= response.status_code < 300:
                    # A discovery call failing for one site/hint should not
                    # fail the whole community search -- same per-site
                    # isolation as naver_news.py's comment fetch.
                    continue
                try:
                    payload = response.json()
                except (TypeError, ValueError):
                    continue
                items = payload.get("items") if isinstance(payload, dict) else None
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    link = item.get("link")
                    if not isinstance(link, str) or link in seen:
                        continue
                    host = urlparse(link).netloc.lower()
                    if not policy.matches_domain(host):
                        continue
                    seen.add(link)
                    candidates.append((site, link, _clean_snippet(item.get("title"))))
        return candidates

    async def _fetch_and_parse(self, url: str, policy: SitePolicy, site: str) -> PostContent | None:
        try:
            response = await self.transport.get(
                url, headers={"User-Agent": policy.user_agent, "Accept-Language": "ko-KR,ko;q=0.9"}
            )
        except CollectorError:
            return None
        if not 200 <= response.status_code < 300:
            return None
        return get_parser(site).parse(response.body)

    async def _resolve_fmkorea_url(self, url: str, policy: SitePolicy) -> str | None:
        """Rewrite a discovered fmkorea URL to its robots.txt-allowed form, or drop it.

        fmkorea's robots.txt (confirmed live) only allows generic bots on
        "/", "/best", "/best2", "/humor" -- an individual post's bare
        numeric URL (what Naver's index actually returns) is never allowed
        regardless of which board it's in. The same post is reachable at
        "/<board>/<id>" when <board> is one of those three (confirmed
        live), but only a post genuinely linked from that board's own
        listing page is treated as belonging to it -- see
        parsers.extract_fmkorea_board_post_ids's docstring for why an
        unverified prefix stamp is not an option. This also re-derives the
        id from whatever path Naver indexed (bare or already prefixed)
        rather than trusting Naver's own prefix, if any.
        """
        last_segment = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        if not last_segment.isdigit():
            return None
        membership = await self._fmkorea_board_membership(policy)
        board = membership.get(last_segment)
        if board is None:
            return None
        return f"https://www.fmkorea.com/{board}/{last_segment}"

    async def _fmkorea_board_membership(self, policy: SitePolicy) -> dict[str, str]:
        if self._fmkorea_membership is not None:
            return self._fmkorea_membership
        membership: dict[str, str] = {}
        limiter = self._rate_limiter("fmkorea", policy)
        for board in FMKOREA_BOARDS:
            board_url = f"https://www.fmkorea.com/{board}"
            if policy.respect_robots and not await self._robots_gates["fmkorea"].allowed(board_url):
                # Shouldn't happen for these three paths given fmkorea's
                # actual robots.txt, but stay defensive rather than assume.
                continue
            if not await limiter.acquire():
                break  # this site's per-run request budget is used up
            try:
                response = await self.transport.get(
                    board_url,
                    headers={"User-Agent": policy.user_agent, "Accept-Language": "ko-KR,ko;q=0.9"},
                )
            except CollectorError:
                continue
            if not 200 <= response.status_code < 300:
                continue
            for post_id in extract_fmkorea_board_post_ids(response.body, board):
                membership.setdefault(post_id, board)
        self._fmkorea_membership = membership
        return membership
