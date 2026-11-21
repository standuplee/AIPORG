"""Sample-based human review of the AI's document sentiment labels."""

import hashlib
import math

from app.core.enums import SentimentLabel
from app.schemas.document import CleanDocument, DocumentId

SAMPLE_FLOOR = 20
SAMPLE_CAP = 40
SAMPLE_RATIO = 0.2


def sample_size(total: int) -> int:
    return min(total, SAMPLE_CAP, max(SAMPLE_FLOOR, math.ceil(SAMPLE_RATIO * total)))


def _by_issue(docs: list[CleanDocument]) -> dict[str, list[CleanDocument]]:
    groups: dict[str, list[CleanDocument]] = {}
    for d in docs:
        groups.setdefault(d.query or "", []).append(d)
    return groups


def _order(doc: CleanDocument) -> str:
    return hashlib.sha1(str(doc.document_id).encode()).hexdigest()


def select_review_sample(docs: list[CleanDocument]) -> list[DocumentId]:
    """Per issue, the first `sample_size` documents by hash of their id: stable across runs and input order."""
    picked: list[DocumentId] = []
    for _, group in sorted(_by_issue(docs).items()):
        picked += [d.document_id for d in sorted(group, key=_order)[: sample_size(len(group))]]
    return picked


def record_review(repo, project_id, document: CleanDocument, *, label: SentimentLabel | None) -> None:
    """Same label as the AI's -> AGREED. Otherwise CORRECTED, keeping the AI's original label (the first one, on repeat corrections)."""
    meta = {k: v for k, v in document.metadata.items() if k != "sentiment"}
    ai = document.metadata.get("sentiment")
    new = label.value if label else None
    if new == ai:
        meta["sentiment_review"] = "AGREED"
    else:
        meta["sentiment_review"] = "CORRECTED"
        meta.setdefault("sentiment_ai_label", ai or "unclassified")
    if new:
        meta["sentiment"] = new
    repo.upsert_clean(project_id, document.model_copy(update={"metadata": meta}))


def review_summary(docs: list[CleanDocument]) -> dict[str, dict[str, int]]:
    in_sample = set(select_review_sample(docs))
    out: dict[str, dict[str, int]] = {}
    for issue, group in sorted(_by_issue(docs).items()):
        reviewed = [d.metadata.get("sentiment_review") for d in group if d.document_id in in_sample]
        out[issue] = {"sample": sum(1 for d in group if d.document_id in in_sample),
                      "reviewed": sum(r in ("AGREED", "CORRECTED") for r in reviewed),
                      "agreed": reviewed.count("AGREED"), "corrected": reviewed.count("CORRECTED")}
    return out
