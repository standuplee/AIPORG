from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from app.search.base import SearchProviderBase, clean_text
from app.search.schemas import SearchChannel, SearchProvider, SearchResult

_KST = timezone(timedelta(hours=9))
_ENDPOINTS = {SearchChannel.NEWS: "news", SearchChannel.WEB: "webkr", SearchChannel.BLOG: "blog"}


class NaverSearchProvider(SearchProviderBase):
    channels = frozenset(_ENDPOINTS)

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }

    def _request(self, query, channel, limit, sort):
        params = {"query": query, "display": limit}
        if channel is not SearchChannel.WEB:  # webkr has no sort option
            params["sort"] = "sim" if sort == "accuracy" else "date"
        body = self._get(
            f"https://openapi.naver.com/v1/search/{_ENDPOINTS[channel]}.json",
            headers=self.headers,
            params=params,
        )
        results = []
        for rank, item in enumerate(body.get("items", []), 1):
            try:
                if item.get("pubDate"):
                    published_at = parsedate_to_datetime(item["pubDate"])
                elif item.get("postdate"):  # blog results: "YYYYMMDD", no time
                    published_at = datetime.strptime(item["postdate"], "%Y%m%d").replace(tzinfo=_KST)
                else:
                    published_at = None
            except (TypeError, ValueError):
                published_at = None
            results.append(
                SearchResult(
                    provider=SearchProvider.NAVER,
                    channel=channel,
                    query=query,
                    sort=sort if "sort" in params else "accuracy",
                    title=clean_text(item.get("title")),
                    snippet=clean_text(item.get("description")),
                    url=item.get("link", ""),
                    original_url=item.get("originallink") or None,
                    published_at=published_at,
                    rank=rank,
                )
            )
        return results
