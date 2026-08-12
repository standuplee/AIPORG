from __future__ import annotations

from ..models import Document
from ..models_keyword_report import SourceReference


def build_source_references(docs: list[Document]) -> list[SourceReference]:
    by_url: dict[str, Document] = {}
    for doc in docs:
        by_url.setdefault(doc.url, doc)
    refs = [
        SourceReference(
            source_id=doc.doc_id,
            title=doc.title,
            url=doc.url,
            channel=doc.channel.value,
            published_at=doc.published_at.isoformat() if doc.published_at else "",
        )
        for doc in by_url.values()
    ]
    return sorted(refs, key=lambda ref: (ref.channel, ref.title, ref.url))
