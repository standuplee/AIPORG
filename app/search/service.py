import asyncio
import logging

from app.search.base import SearchProviderBase
from app.search.deduplicator import deduplicate
from app.search.schemas import SearchChannel as C
from app.search.schemas import SearchResult

logger = logging.getLogger(__name__)

# (provider attribute, channel, sort). Fact and opinion corpora are kept apart so
# opinion hits never leak into factual evidence (and vice versa).
FACT_PLAN = [
    ("naver", C.NEWS, "accuracy"), ("naver", C.NEWS, "recency"), ("naver", C.WEB, "accuracy"),
    ("daum", C.WEB, "accuracy"), ("daum", C.WEB, "recency"),
]
OPINION_PLAN = [("daum", C.BLOG, "accuracy"), ("daum", C.CAFE, "accuracy"), ("naver", C.BLOG, "accuracy")]


class SearchService:
    def __init__(self, naver: SearchProviderBase, daum: SearchProviderBase) -> None:
        self.providers = {"naver": naver, "daum": daum}

    async def _run(self, plan, query: str, limit: int) -> list[SearchResult]:
        groups = await asyncio.gather(
            *(self.providers[p].search(query, ch, limit, sort) for p, ch, sort in plan),
            return_exceptions=True,
        )
        results = []
        for (provider, channel, sort), group in zip(plan, groups):
            if isinstance(group, Exception):
                # One failing engine must not drop the others, but it must be visible.
                logger.warning("search failed: %s %s %s: %s", provider, channel.value, sort, type(group).__name__)
            else:
                results += group
        return deduplicate(results)

    async def search_fact(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await self._run(FACT_PLAN, query, limit)

    async def search_opinion(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await self._run(OPINION_PLAN, query, limit)
