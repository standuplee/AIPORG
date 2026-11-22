"""Document-level sentiment: Qwen proposes a label and a quoted phrase, the code keeps the label only if the quote is really there."""

import json
import logging
import re
from typing import Literal

from app.core.enums import SentimentLabel
from app.schemas.common import SchemaBase
from app.schemas.document import CleanDocument, DocumentId

PROMPT_VERSION = "doc-sentiment-v2"
BODY_CHARS = 1500
PROMPT = (
    "너는 온라인 글이 주어진 이슈를 어떻게 평가하는지 분류하는 분석가다. 입력의 제목과 본문(text)만 근거로 쓴다.\n"
    "핵심 원칙: 사건이 좋은 일인지가 아니라, 글이 '평가·감정·입장'을 직접 표현하는지를 본다.\n"
    "- 법 통과, 발표, 협약, 일정, 수치를 전하는 보도·보도자료는 평가 표현이 없으면 neutral이다. "
    "'통과됐다'는 긍정이 아니다.\n"
    "- label: positive(글쓴이나 인용된 사람이 환영·기대·찬성·성과 평가를 명시), negative(비판·우려·반대·부정 평가를 명시), "
    "neutral(사실 전달, 명시적 평가 없음), mixed(긍정·부정 평가가 함께 있음), unclear(판단할 근거 부족).\n"
    "- evaluative: 평가·감정·입장을 드러내는 표현(예: 환영, 기대, 우려, 비판, 숙원, 첩첩산중)이 text에 실제로 있으면 true, "
    "사실만 전하면 false. positive/negative/mixed인데 false이면 안 된다.\n"
    "- positive/negative/mixed이면 evidence에 그 평가 표현이 들어 있는 문장을 text에서 글자 그대로 복사한다. "
    "사실만 담은 문장은 evidence가 될 수 없다. 바꿔 쓰거나 요약하지 않는다. evidence는 비워 둘 수 없다.\n"
    "- reason은 판단 이유를 네 말로 한 문장 쓴다. 본문 문장을 reason에 옮기지 말고 evidence에 넣는다.\n"
    "- 문서마다 document_id를 그대로 돌려준다. 입력에 없는 사실은 쓰지 않는다."
)


class SentimentItem(SchemaBase):
    document_id: str
    label: Literal["positive", "negative", "neutral", "mixed", "unclear"]
    evaluative: bool = True
    evidence: str = ""
    reason: str = ""


class SentimentBatch(SchemaBase):
    results: list[SentimentItem]


class SentimentVerdict(SchemaBase):
    label: SentimentLabel | None
    evidence: str | None = None
    reason: str
    basis: Literal["BODY", "SNIPPET"]


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _basis(doc: CleanDocument) -> Literal["BODY", "SNIPPET"]:
    return "BODY" if doc.metadata.get("body_available") else "SNIPPET"


def _judge(doc: CleanDocument, answer: SentimentItem) -> SentimentVerdict:
    basis = _basis(doc)
    if answer.label == "unclear":
        return SentimentVerdict(label=None, reason=answer.reason or "unclear", basis=basis)
    if answer.label == "neutral" or not answer.evaluative:
        return SentimentVerdict(label=SentimentLabel.NEUTRAL, reason=answer.reason, basis=basis)
    evidence = answer.evidence.strip()
    if not evidence or _norm(evidence) not in _norm(f"{doc.title} {doc.body}"):
        return SentimentVerdict(label=None, reason="근거 구절 확인 실패", basis=basis)
    return SentimentVerdict(label=SentimentLabel(answer.label), evidence=evidence, reason=answer.reason, basis=basis)


async def classify_documents(qwen, issue: str, docs: list[CleanDocument], batch: int = 5) -> dict[DocumentId, SentimentVerdict]:
    """A document Qwen skips is asked once more; one it still skips, or whose batch errors, stays unclassified with the reason."""
    verdicts: dict[DocumentId, SentimentVerdict] = {}
    for i in range(0, len(docs), batch):
        todo, failed = docs[i : i + batch], False
        for _ in range(2):
            payload = {"issue": issue, "documents": [{"document_id": str(d.document_id), "title": d.title, "text": d.body[:BODY_CHARS]} for d in todo]}
            try:
                out: SentimentBatch = await qwen.chat(PROMPT, json.dumps(payload, ensure_ascii=False), SentimentBatch)
            except Exception:  # noqa: BLE001 - one bad batch must not stop the month's classification
                logging.getLogger(__name__).warning("sentiment batch failed", exc_info=True)
                failed = True
                break
            answers = {a.document_id: a for a in out.results}
            for d in todo:
                if str(d.document_id) in answers:
                    verdicts[d.document_id] = _judge(d, answers[str(d.document_id)])
            todo = [d for d in todo if d.document_id not in verdicts]
            if not todo:
                break
        for d in todo:
            verdicts[d.document_id] = SentimentVerdict(label=None, reason="qwen_failed" if failed else "qwen_no_answer", basis=_basis(d))
    return verdicts


REVIEWED = {"AGREED", "CORRECTED"}


def store_sentiment(repo, project_id, document: CleanDocument, verdict: SentimentVerdict, *, model: str) -> bool:
    """upsert_clean overwrites the metadata, so the new keys are merged into what the document already has."""
    if document.metadata.get("sentiment_review") in REVIEWED:
        return False
    meta = {k: v for k, v in document.metadata.items() if k != "sentiment"}
    if verdict.label is not None:
        meta["sentiment"] = verdict.label.value
    meta.update(sentiment_evidence=verdict.evidence, sentiment_reason=verdict.reason, sentiment_basis=verdict.basis,
                sentiment_model=model, sentiment_prompt_version=PROMPT_VERSION, sentiment_review="AI_ONLY")
    repo.upsert_clean(project_id, document.model_copy(update={"metadata": meta}))
    return True


async def classify_project(qwen, session, project_id) -> dict[str, int]:
    """Classify every canonical document not yet reviewed by a person, one issue (document.query) at a time."""
    from app.repositories.sqlalchemy import SqlAlchemyDocumentRepository

    repo = SqlAlchemyDocumentRepository(session)
    counts = {label.value: 0 for label in SentimentLabel} | {"unclassified": 0, "skipped_reviewed": 0}
    by_issue: dict[str, list[CleanDocument]] = {}
    for doc in repo.list_canonical(project_id):
        if doc.metadata.get("sentiment_review") in REVIEWED:
            counts["skipped_reviewed"] += 1
        else:
            by_issue.setdefault(doc.query or "", []).append(doc)
    for issue, docs in by_issue.items():
        verdicts = await classify_documents(qwen, issue, docs)
        for doc in docs:
            verdict = verdicts[doc.document_id]
            store_sentiment(repo, project_id, doc, verdict, model=qwen.model)
            counts[verdict.label.value if verdict.label else "unclassified"] += 1
    return counts
