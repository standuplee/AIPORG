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


class _Repo:
    def __init__(self):
        self.saved = []

    def upsert_clean(self, project_id, document):
        self.saved.append(document)


def test_store_merges_metadata_and_keeps_existing_keys():
    from app.sentiment.document_classifier import SentimentVerdict, store_sentiment
    doc, repo = _doc(), _Repo()
    verdict = SentimentVerdict(label=SentimentLabel.POSITIVE, evidence="경제가 살아날 것이다", reason="r", basis="BODY")
    assert store_sentiment(repo, uuid4(), doc, verdict, model="qwen3:8b") is True
    meta = repo.saved[0].metadata
    assert meta["body_available"] is True and meta["sentiment"] == "positive" and meta["sentiment_evidence"] == "경제가 살아날 것이다"
    assert (meta["sentiment_model"], meta["sentiment_prompt_version"], meta["sentiment_review"], meta["sentiment_basis"]) == ("qwen3:8b", "doc-sentiment-v2", "AI_ONLY", "BODY")


def test_unclassified_verdict_writes_no_sentiment_key_but_keeps_the_reason():
    from app.sentiment.document_classifier import SentimentVerdict, store_sentiment
    doc, repo = _doc(), _Repo()
    assert store_sentiment(repo, uuid4(), doc, SentimentVerdict(label=None, reason="근거 구절 확인 실패", basis="SNIPPET"), model="m") is True
    meta = repo.saved[0].metadata
    assert "sentiment" not in meta and meta["sentiment_reason"] == "근거 구절 확인 실패"


def test_reviewed_documents_are_not_overwritten():
    from app.sentiment.document_classifier import SentimentVerdict, store_sentiment
    for state in ("AGREED", "CORRECTED"):
        doc = _doc().model_copy(update={"metadata": {"sentiment": "negative", "sentiment_review": state}})
        repo = _Repo()
        assert store_sentiment(repo, uuid4(), doc, SentimentVerdict(label=SentimentLabel.POSITIVE, evidence="x", reason="r", basis="BODY"), model="m") is False
        assert repo.saved == []


def test_label_without_an_explicit_evaluation_is_downgraded_to_neutral():
    """A report that merely states an event ("법이 통과됐다") is neutral even if Qwen calls it positive."""

    doc = _doc(body="특별법이 국회 본회의를 통과했다.")

    class Q(FakeQwen):
        async def chat(self, system, user, schema, **kw):
            return SentimentBatch(results=[SentimentItem(document_id=str(doc.document_id), label="positive",
                                                          evidence="특별법이 국회 본회의를 통과했다", evaluative=False, reason="r")])

    out = _run(Q({}), [doc])
    assert out[doc.document_id].label is SentimentLabel.NEUTRAL
    assert out[doc.document_id].evidence is None


def test_prompt_version_marks_the_evaluation_rule():
    from app.sentiment.document_classifier import PROMPT_VERSION
    assert PROMPT_VERSION == "doc-sentiment-v2"
