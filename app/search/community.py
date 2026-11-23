"""Community discovery for the opinion corpus: Naver web search per enabled site, reusing 2.0's config/community.yaml.

Only search-result titles and snippets are used; no community page is fetched, so robots.txt and the
per-site request limits of the 2.0 crawler do not apply. The enabled flag, domains and exclude patterns do.
"""

import asyncio
import logging
from urllib.parse import urlsplit

from app.collectors.community.policy import SitePolicy
from app.search.base import SearchProviderBase
from app.search.schemas import SearchChannel, SearchResult

logger = logging.getLogger(__name__)


class CommunitySearch:
    def __init__(self, naver: SearchProviderBase, policies: dict[str, SitePolicy]) -> None:
        self.naver = naver
        self.policies = [p for p in policies.values() if p.enabled and p.search_hints]

    async def _site(self, policy: SitePolicy, query: str, limit: int, page: int) -> list[SearchResult]:
        kwargs = {"page": page} if page > 1 else {}
        hits = await self.naver.search(f"{query} {policy.search_hints[0]}", SearchChannel.WEB, limit, "accuracy", **kwargs)
        return [
            r.model_copy(update={"channel": SearchChannel.COMMUNITY})
            for r in hits
            if policy.matches_domain(urlsplit(r.url).netloc) and not policy.is_excluded(r.url)
        ]

    async def search(self, query: str, limit: int = 10, page: int = 1) -> list[SearchResult]:
        groups = await asyncio.gather(*(self._site(p, query, limit, page) for p in self.policies), return_exceptions=True)
        results = []
        for policy, group in zip(self.policies, groups):
            if isinstance(group, Exception):
                logger.warning("community search failed: %s: %s", policy.name, type(group).__name__)
            else:
                results += group
        return results
