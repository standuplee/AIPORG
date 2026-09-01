"""Pure RawDocument to CleanDocument normalization."""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.schemas.document import CleanDocument, RawDocument


_TRACKING_PARAMS = frozenset({"fbclid", "gclid", "ref", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"})


class CleaningService:
    """Normalize text and URLs without network, LLM, or persistence access."""

    def clean(self, document: RawDocument) -> CleanDocument:
        title = self._text(document.title)
        body = self._text(document.body)
        if not title:
            raise ValueError("document title cannot be empty")
        if not body:
            raise ValueError("document body cannot be empty")
        return CleanDocument(
            document_id=document.document_id,
            title=title,
            body=body,
            canonical_url=self.canonicalize_url(document.url),
            cleaned_at=document.collected_at,
            source=document.source,
            channel=document.channel,
            platform=document.platform,
            published_at=document.published_at,
            query=document.query,
            metadata=document.metadata,
        )

    @staticmethod
    def canonicalize_url(url: str) -> str:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL must use http or https")

        hostname = parsed.hostname.lower()
        port = parsed.port
        netloc = hostname
        if port is not None and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
            netloc = f"{hostname}:{port}"
        path = parsed.path or "/"
        query = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower() not in _TRACKING_PARAMS and not key.lower().startswith("utm_")
            ]
        )
        return urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))

    @staticmethod
    def _text(value: str) -> str:
        normalized = unicodedata.normalize("NFC", html.unescape(value))
        normalized = re.sub(r"<[^>]+>", " ", normalized).replace("\u00a0", " ")
        return re.sub(r"\s+", " ", normalized).strip()
