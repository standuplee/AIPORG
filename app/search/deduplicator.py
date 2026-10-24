import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from app.search.schemas import SearchResult

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref$|outurl$)", re.I)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)))
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}" + (f"?{query}" if query else "")


def normalize_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title).casefold()


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    """Keep the first hit per press URL and per normalized title."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique = []
    for result in results:
        url = normalize_url(result.original_url or result.url)
        title = normalize_title(result.title)
        if not url or url in seen_urls or (title and title in seen_titles):
            continue
        seen_urls.add(url)
        seen_titles.add(title)
        unique.append(result)
    return unique
