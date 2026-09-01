"""Deterministic document deduplication levels 1 through 3."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.document import CleanDocument, DuplicateClusterSchema


class DeduplicationService:
    """Cluster exact canonical URL, title, and body duplicates in that order."""

    def cluster(
        self,
        documents: Iterable[CleanDocument],
        *,
        source_by_document: Mapping[UUID, str],
    ) -> list[DuplicateClusterSchema]:
        remaining = list(documents)
        document_ids = {document.document_id for document in remaining}
        missing_sources = document_ids - source_by_document.keys()
        if missing_sources:
            raise ValueError("source provenance is required for every document")
        clusters: list[DuplicateClusterSchema] = []
        for key_fn in (self._url_key, self._title_key, self._body_key):
            groups: dict[str, list[CleanDocument]] = {}
            for document in remaining:
                groups.setdefault(key_fn(document), []).append(document)
            consumed: set[UUID] = set()
            for key, group in groups.items():
                if not key or len(group) < 2:
                    continue
                group = sorted(group, key=lambda item: item.document_id.hex)
                canonical = group[0]
                duplicate_ids = [item.document_id for item in group[1:]]
                if not duplicate_ids:
                    continue
                sources = sorted(
                    {source_by_document[item.document_id] for item in group}
                )
                clusters.append(
                    DuplicateClusterSchema(
                        cluster_id=uuid5(NAMESPACE_URL, f"{canonical.document_id}:{key}"),
                        canonical_document=canonical.document_id,
                        duplicates=duplicate_ids,
                        unique_sources=sources,
                        distribution_count=len(group),
                    )
                )
                consumed.update(item.document_id for item in group)
            remaining = [item for item in remaining if item.document_id not in consumed]
        return clusters

    @staticmethod
    def _url_key(document: CleanDocument) -> str:
        return document.canonical_url

    @staticmethod
    def _title_key(document: CleanDocument) -> str:
        return re.sub(r"\s+", " ", unicodedata.normalize("NFC", document.title)).strip().casefold()

    @staticmethod
    def _body_key(document: CleanDocument) -> str:
        normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFC", document.body)).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
