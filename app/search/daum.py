from app.search.base import SearchProviderBase, clean_text
from app.search.schemas import SearchChannel, SearchProvider, SearchResult

_ENDPOINTS = {SearchChannel.WEB: "web", SearchChannel.BLOG: "blog", SearchChannel.CAFE: "cafe"}


class DaumSearchProvider(SearchProviderBase):
    channels = frozenset(_ENDPOINTS)

    def __init__(self, api_key: str) -> None:
        self.headers = {"Authorization": f"KakaoAK {api_key}"}

    def _request(self, query, channel, limit, sort):
        body = self._get(
            f"https://dapi.kakao.com/v2/search/{_ENDPOINTS[channel]}",
            headers=self.headers,
            params={"query": query, "size": limit, "sort": sort},
        )
        return [
            SearchResult(
                provider=SearchProvider.DAUM,
                channel=channel,
                query=query,
                sort=sort,
                title=clean_text(doc.get("title")),
                snippet=clean_text(doc.get("contents")),
                url=doc.get("url", ""),
                published_at=doc.get("datetime") or None,
                rank=rank,
            )
            for rank, doc in enumerate(body.get("documents", []), 1)
        ]
