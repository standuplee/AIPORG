from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.enums import SentimentLabel
from app.schemas.document import CleanDocument
from app.sentiment.review import record_review, review_summary, sample_size, select_review_sample

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _doc(issue="석탄화력 특별법", **meta):
    return CleanDocument(document_id=uuid4(), title="t", body="b", canonical_url=f"https://x.example/{uuid4()}", cleaned_at=NOW, query=issue, metadata=meta)


class _Repo:
    def __init__(self):
        self.saved = []

    def upsert_clean(self, project_id, document):
        self.saved.append(document)


def test_sample_size_rules():
    assert [sample_size(n) for n in (0, 10, 20, 60, 150, 500)] == [0, 10, 20, 20, 30, 40]


def test_selection_is_deterministic_and_per_issue():
    docs = [_doc("A") for _ in range(30)] + [_doc("B") for _ in range(5)]
    first = select_review_sample(docs)
    assert first == select_review_sample(docs) and set(first) == set(select_review_sample(list(reversed(docs))))
    by_issue = {d.document_id: d.query for d in docs}
    assert sum(1 for i in first if by_issue[i] == "A") == 20 and sum(1 for i in first if by_issue[i] == "B") == 5


def test_record_review_agreed_and_corrected_keep_ai_label():
    repo = _Repo()
    agreed = _doc(sentiment="positive", sentiment_review="AI_ONLY")
    record_review(repo, uuid4(), agreed, label=SentimentLabel.POSITIVE)
    assert repo.saved[-1].metadata["sentiment_review"] == "AGREED" and repo.saved[-1].metadata["sentiment"] == "positive"
    corrected = _doc(sentiment="positive", sentiment_review="AI_ONLY", body_available=True)
    record_review(repo, uuid4(), corrected, label=SentimentLabel.NEGATIVE)
    meta = repo.saved[-1].metadata
    assert (meta["sentiment_review"], meta["sentiment"], meta["sentiment_ai_label"], meta["body_available"]) == ("CORRECTED", "negative", "positive", True)
    unclassified = _doc(sentiment_review="AI_ONLY")
    record_review(repo, uuid4(), unclassified, label=None)  # the person also finds it unclassifiable
    assert repo.saved[-1].metadata["sentiment_review"] == "AGREED" and "sentiment" not in repo.saved[-1].metadata
    record_review(repo, uuid4(), unclassified, label=SentimentLabel.MIXED)
    assert repo.saved[-1].metadata["sentiment_ai_label"] == "unclassified" and repo.saved[-1].metadata["sentiment"] == "mixed"


def test_a_second_correction_keeps_the_original_ai_label():
    repo = _Repo()
    doc = _doc(sentiment="positive", sentiment_review="CORRECTED", sentiment_ai_label="negative")
    record_review(repo, uuid4(), doc, label=SentimentLabel.NEUTRAL)
    assert repo.saved[-1].metadata["sentiment_ai_label"] == "negative"


def test_summary_counts_only_reviewed_documents_in_the_sample():
    docs = [_doc("A") for _ in range(25)]
    picked = select_review_sample(docs)
    by_id = {d.document_id: d for d in docs}
    reviewed = [by_id[i] for i in picked[:3]]
    for n, d in enumerate(reviewed):
        d.metadata.update(sentiment_review="AGREED" if n < 2 else "CORRECTED")
    outside = next(d for d in docs if d.document_id not in set(picked))
    outside.metadata.update(sentiment_review="AGREED")  # not in the sample: must not count
    assert review_summary(docs) == {"A": {"sample": 20, "reviewed": 3, "agreed": 2, "corrected": 1}}
