"""Article Fetcher: HTTP GET -> HTML -> main text + metadata. No browser rendering."""

import asyncio

import requests

from app.collectors.content_extraction import extract_article_text
from app.collectors.transport import _decode_response_body
from app.search.documents import FetchedDocument, FetchStatus, PublishedAtSource
from app.search.html_meta import extract_metadata
from app.search.schemas import SearchResult
from app.search.signals import source_type

MIN_TEXT_LENGTH = 200
MAX_TEXT_LENGTH = 200_000
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIPORG-Research/1.0)"}


def _get(url: str) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=15)


async def fetch_document(result: SearchResult, research_question_id: str) -> FetchedDocument:
    url = result.original_url or result.url
    base = dict(
        result_id=result.result_id, research_question_id=research_question_id,
        requested_url=url, source_type=source_type(result),
    )
    try:
        response = await asyncio.to_thread(_get, url)
    except requests.RequestException as exc:
        return FetchedDocument(**base, fetch_status=FetchStatus.NETWORK_ERROR, error=type(exc).__name__)
    common = dict(**base, final_url=response.url, http_status=response.status_code)
    if response.status_code >= 400:
        return FetchedDocument(**common, fetch_status=FetchStatus.HTTP_ERROR, error=f"HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type:
        return FetchedDocument(**common, fetch_status=FetchStatus.UNSUPPORTED_TYPE, error=content_type or "unknown")

    html = _decode_response_body(response)
    text = extract_article_text(html)[:MAX_TEXT_LENGTH]
    meta = extract_metadata(html, text)
    if meta["published_at"] is None and result.published_at is not None:
        meta["published_at"], meta["published_at_source"] = result.published_at, PublishedAtSource.SEARCH_API
    status = FetchStatus.OK if len(text) >= MIN_TEXT_LENGTH else FetchStatus.EMPTY_TEXT
    return FetchedDocument(
        **common, fetch_status=status, **meta,
        text=text or None, text_length=len(text), extraction_method="trafilatura",
        error=None if status is FetchStatus.OK else f"text shorter than {MIN_TEXT_LENGTH} chars",
    )


async def fetch_documents(
    results: list[SearchResult], research_question_id: str, concurrency: int = 4
) -> list[FetchedDocument]:
    gate = asyncio.Semaphore(concurrency)

    async def one(result):
        async with gate:
            return await fetch_document(result, research_question_id)

    return await asyncio.gather(*(one(r) for r in results))
