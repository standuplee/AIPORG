"""Document-level sentiment: Qwen proposes a label and a quoted phrase, the code keeps the label only if the quote is really there."""

import json
import logging
import re
from typing import Literal

from app.core.enums import SentimentLabel
from app.schemas.common import SchemaBase
from app.schemas.document import CleanDocument, DocumentId

PROMPT_VERSION = "doc-sentiment-v1"
BODY_CHARS = 1500
PROMPT = (
    "너는 온라인 글이 주어진 이슈를 어떻게 평가하는지 분류하는 분석가다. 입력의 제목과 본문(text)만 근거로 쓴다.\n"
    "- label: positive(이슈·정책·결과를 긍정적으로 평가/기대), negative(비판·우려·반대·부정적 결과), neutral(사실 전달·평가 없음), "
    "mixed(긍정과 부정이 함께 있음), unclear(판단할 근거 부족).\n"
    "- 단순히 사건·일정·수치를 나열한 글은 neutral이다. 슬픈 사건 자체의 묘사와 행정에 대한 비판은 구분한다.\n"
    "- positive/negative/mixed이면 evidence에 판단 근거가 된 문장을 text에서 글자 그대로 복사한다. 바꿔 쓰거나 요약하지 않는다.\n"
    "- 문서마다 document_id를 그대로 돌려준다. 입력에 없는 사실은 쓰지 않는다."
)


class SentimentItem(SchemaBase):
    document_id: str
    label: Literal["positive", "negative", "neutral", "mixed", "unclear"]
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
    if answer.label == "neutral":
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
