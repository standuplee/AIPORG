"""Give undated community search hits a publish date by reading the post, under 2.0's community rules.

Web search returns no date for community posts, so they cannot be counted by month. CommunityCollector.fetch_post
applies robots.txt, the per-site request interval and the per-run request cap; a post it refuses stays undated
(still usable as qualitative reaction, held by the monthly ingest). Posts dated outside the period are dropped.
"""

import asyncio
import logging
from collections import defaultdict
from urllib.parse import urlsplit

from app.schemas.research import IssueInput
from app.search.schemas import PeriodStatus, SearchChannel, SearchResult
from app.search.period import classify_period

logger = logging.getLogger(__name__)


async def _site(collector, posts: list[SearchResult]) -> dict[str, object]:
    """Posts of one site, one at a time: the collector's rate limiter spaces the requests."""
    found = {}
    for r in posts:
        try:
            content = await collector.fetch_post(r.url)
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the rest
            logger.warning("community date fetch failed: %s", type(exc).__name__)
            continue
        if content is not None:
            found[r.url] = content.posted_at
    return found


async def resolve_community_dates(collector, posts: list[SearchResult], issue: IssueInput) -> tuple[list[SearchResult], dict[str, int]]:
    """Returns (posts with dates filled and out-of-period community posts removed, counts)."""
    todo = [r for r in posts if r.channel is SearchChannel.COMMUNITY and r.published_at is None]
    by_site = defaultdict(list)
    for r in todo:
        by_site[urlsplit(r.url).netloc.removeprefix("www.").removeprefix("m.")].append(r)
    dates: dict[str, object] = {}
    for found in await asyncio.gather(*(_site(collector, rs) for rs in by_site.values())):
        dates.update(found)

    kept, out = [], 0
    for r in posts:
        if r.url in dates:
            r = r.model_copy(update={"published_at": dates[r.url]})
            if classify_period(r, issue.start_date, issue.end_date) is PeriodStatus.OUT_OF_PERIOD:
                out += 1
                continue
        kept.append(r)
    return kept, {"community": len(todo), "dated": len(dates) - out, "out_of_period": out, "undated": len(todo) - len(dates)}
