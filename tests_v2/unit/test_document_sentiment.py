import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.enums import SentimentLabel
from app.schemas.document import CleanDocument
from app.sentiment.document_classifier import SentimentBatch, SentimentItem, classify_documents

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _doc(body="특별법 통과로 지역 경제가 살아날 것이다.", title="석탄화력 특별법", body_available=True):
    return CleanDocument(document_id=uuid4(), title=title, body=body, canonical_url=f"https://x.example/{uuid4()}", cleaned_at=NOW,
                         query="석탄화력 특별법", metadata={"body_available": body_available})


class FakeQwen:
    """answers: {document_id: (label, evidence)}; docs missing from `answers` are skipped."""

    def __init__(self, answers, fail_calls=(), skip_on_retry=True):
        self.answers, self.fail_calls, self.calls = answers, set(fail_calls), 0

    async def chat(self, system, user, schema, **kw):
        self.calls += 1
        if self.calls in self.fail_calls:
            raise RuntimeError("ollama down")
        ids = [d["document_id"] for d in json.loads(user)["documents"]]
        return SentimentBatch(results=[SentimentItem(document_id=i, label=self.answers[i][0], evidence=self.answers[i][1], reason="r")
                                       for i in ids if i in self.answers])


def _run(qwen, docs, **kw):
    return asyncio.run(classify_documents(qwen, "석탄화력 특별법", docs, **kw))


def test_positive_label_needs_an_evidence_phrase_that_exists_in_title_or_body():
    good, bad = _doc(), _doc()
    qwen = FakeQwen({str(good.document_id): ("positive", "지역 경제가 살아날 것이다"), str(bad.document_id): ("negative", "원문에 없는 문장")})
    out = _run(qwen, [good, bad])
    assert out[good.document_id].label is SentimentLabel.POSITIVE and out[good.document_id].evidence == "지역 경제가 살아날 것이다"
    assert out[bad.document_id].label is None and "근거" in out[bad.document_id].reason


def test_evidence_matching_ignores_whitespace_and_case():
    doc = _doc(body="Special Law\n통과로   지역 경제가\n살아날 것이다")
    out = _run(FakeQwen({str(doc.document_id): ("positive", "통과로 지역 경제가 살아날 것이다")}), [doc])
    assert out[doc.document_id].label is SentimentLabel.POSITIVE


def test_neutral_is_accepted_without_evidence_and_unclear_becomes_none():
    a, b = _doc(), _doc()
    out = _run(FakeQwen({str(a.document_id): ("neutral", ""), str(b.document_id): ("unclear", "")}), [a, b])
    assert out[a.document_id].label is SentimentLabel.NEUTRAL and out[b.document_id].label is None


def test_missing_answers_are_asked_once_more_then_left_unclassified():
    docs = [_doc() for _ in range(5)]
    answers = {str(d.document_id): ("neutral", "") for d in docs[:3]}
    qwen = FakeQwen(answers)
    out = _run(qwen, docs, batch=5)
    assert qwen.calls == 2  # one re-ask for the two it skipped
    assert [out[d.document_id].reason for d in docs[3:]] == ["qwen_no_answer"] * 2 and all(out[d.document_id].label is SentimentLabel.NEUTRAL for d in docs[:3])


def test_a_failing_batch_leaves_its_documents_unclassified_with_reason():
    docs = [_doc() for _ in range(4)]
    qwen = FakeQwen({str(d.document_id): ("neutral", "") for d in docs}, fail_calls={1})
    out = _run(qwen, docs, batch=2)
    assert [out[d.document_id].reason for d in docs[:2]] == ["qwen_failed"] * 2 and all(out[d.document_id].label is None for d in docs[:2])
    assert all(out[d.document_id].label is SentimentLabel.NEUTRAL for d in docs[2:])


def test_snippet_only_documents_are_marked_basis_snippet():
    full, snippet = _doc(), _doc(body_available=False)
    out = _run(FakeQwen({str(full.document_id): ("neutral", ""), str(snippet.document_id): ("neutral", "")}), [full, snippet])
    assert out[full.document_id].basis == "BODY" and out[snippet.document_id].basis == "SNIPPET"
