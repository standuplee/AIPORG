"""Fact Research Synthesizer: fetched documents -> key facts, timeline, status, gaps."""

import json
import re

from app.research.query_expansion import QwenQueryExpansionService
from app.schemas.research import IssueInput, ResearchQuestion
from app.search.documents import FactResearchResult, FetchedDocument, FetchStatus
from app.search.schemas import SourceType

MAX_DOCUMENTS = 8
EXCERPT_CHARS = 3000
NUM_CTX = 24576  # 8 x 3000 chars of Korean plus the prompt; Ollama's default window would truncate silently
MAX_SOURCES_PER_FACT = 2
_RESULT_ID = re.compile(r"\s*[:,]?\s*\b[0-9a-f]{12}\b(?:\s*,\s*\b[0-9a-f]{12}\b)*")
_OFFICIAL = {SourceType.GOVERNMENT, SourceType.LEGISLATURE, SourceType.PUBLIC_AGENCY, SourceType.COMPANY}

SYNTH_PROMPT = """
당신은 월간 이슈 보고서를 위한 조사 보조자다. 주어진 문서 발췌만으로 이슈의 사실관계를 정리한다.

규칙:
1. 문서 발췌에 있는 내용만 쓴다. 없는 사실·숫자를 만들거나 계산·환산하지 않는다.
2. 문장의 주체(기업·기관)가 이 이슈의 주체와 다르면 쓰지 않는다
   (예: 다른 계열사나 다른 사업에 관한 문장).
3. 문서들의 내용(날짜·금액·일정·상태)이 명백히 다르면 하나를 확정하지 말고
   key_facts와 timeline에서 빼고 uncertainties에 "확인 필요: ..." 로 적는다.
4. 각 key_fact와 timeline 항목의 source_result_ids에는 그 내용을 가장 직접 담은 문서
   최대 2개만 넣는다. 공식 출처(GOVERNMENT 등)가 있으면 우선한다. 모든 문서를 나열하지 않는다.
5. current_status에는 발표·MOU·계획·착공·완료·통과·공포 중 어느 단계인지 구분해 쓴다.
   계획이나 협약을 완료·확정된 것처럼 쓰지 않는다. 법안은 "국회 본회의 통과"처럼 단계명을
   그대로 쓰고, 공포·시행이 문서에 없으면 그 단계는 미확인이라고 적는다. "완료"라고만 쓰지 않는다.
6. timeline은 날짜가 문서에 분명히 있는 사건만 쓴다. date는 문서 표현 그대로 쓰고,
   event에 같은 날짜를 반복하지 않는다. 문서가 쓴 시제(계획이면 계획)를 따른다.
7. missing_information에는 보고서에 꼭 필요한데 문서에 없는 핵심 정보만 쓴다.
   없으면 빈 목록. 미래 예측("실제로 이행될지")은 쓰지 않는다.
8. organizations, persons, locations는 문서에 나온 이름만 쓴다.
"""


def select_documents(docs: list[FetchedDocument]) -> list[FetchedDocument]:
    """Readable documents, official sources first, capped for the context window."""
    ok = [d for d in docs if d.fetch_status is FetchStatus.OK and d.text]
    ok.sort(key=lambda d: d.source_type not in _OFFICIAL)  # stable: keeps search order within a group
    return ok[:MAX_DOCUMENTS]


def _prompt(issue: IssueInput, questions: list[ResearchQuestion], docs: list[FetchedDocument]) -> str:
    return json.dumps(
        {
            "region": issue.region,
            "period": f"{issue.start_date} ~ {issue.end_date}",
            "issue": issue.issue,
            "research_questions": [q.question for q in questions],
            "documents": [
                {
                    "result_id": d.result_id,
                    "source_type": d.source_type.value,
                    "title": d.title,
                    "published_at": d.published_at.date().isoformat() if d.published_at else None,
                    "excerpt": (d.text or "")[:EXCERPT_CHARS],
                }
                for d in docs
            ],
        },
        ensure_ascii=False,
    )


async def synthesize_facts(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    questions: list[ResearchQuestion],
    docs: list[FetchedDocument],
) -> FactResearchResult:
    chosen = select_documents(docs)
    if not chosen:
        raise ValueError("no readable documents to synthesize")
    out: FactResearchResult = await qwen.chat(SYNTH_PROMPT, _prompt(issue, questions, chosen), FactResearchResult, num_ctx=NUM_CTX)
    rank = {d.result_id: n for n, d in enumerate(chosen)}  # chosen is already official-first

    def sources(ids):
        # Only documents Qwen was shown; official-first backstop for the 2-source cap.
        return sorted({i for i in ids if i in rank}, key=rank.get)[:MAX_SOURCES_PER_FACT]

    facts = [f.model_copy(update={"source_result_ids": sources(f.source_result_ids)}) for f in out.key_facts]
    timeline = [t.model_copy(update={"source_result_ids": sources(t.source_result_ids)}) for t in out.timeline]
    def clean(text: str) -> str:
        return _RESULT_ID.sub("", text).strip()  # Qwen sometimes pastes document ids into prose

    return out.model_copy(update={
        "uncertainties": [c for c in (clean(u) for u in out.uncertainties) if c],
        "missing_information": [c for c in (clean(m) for m in out.missing_information) if c],
        "key_facts": [f for f in facts if f.source_result_ids],
        # ISO-style dates sort chronologically; free-text dates keep Qwen's order after them.
        "timeline": sorted((t for t in timeline if t.source_result_ids), key=lambda t: (0, t.date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t.date or "") else (1, "")),
    })
