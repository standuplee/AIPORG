"""Issue-independent triage of search hits against one research question."""

import json

from app.research.query.regions import REGION_ALIASES
from app.research.query_expansion import QwenQueryExpansionService
from app.schemas.research import IssueDecomposition, IssueInput, QueryType, ResearchQuestion
from app.search.period import classify_period
from app.search.schemas import (
    AssessedResult,
    AssessmentBatch,
    PeriodStatus,
    SearchAnalysisResult,
    SearchResult,
)
from app.search.signals import build_metadata

BATCH_SIZE = 5
MIN_FETCH_SCORE = 2

ANALYZER_PROMPT = """
당신은 지방정부 정책·사회 이슈 조사 시스템의 검색결과 평가기다.
각 검색결과가 주어진 Research Question에 답하는 데 얼마나 유용한지 평가한다.
사실을 확정하거나 보고서를 작성하지 않는다.

relevance_score:
 3 = 질문에 직접 답하는 정보가 제목·스니펫에 있다.
 2 = 질문 해결에 쓸 만한 맥락·배경·관련 사실이 있다.
 1 = 같은 이름이나 지역이 언급될 뿐 질문과 약하게 관련된다.
 0 = 질문과 무관하다.

규칙:
1. title과 snippet에 있는 정보만 사용한다. 없는 사실을 추론하지 않는다.
2. 같은 기관명·지역명·인물명이 등장한다는 이유만으로 높게 평가하지 않는다.
   이슈의 사건·행위와 실제로 관련되어야 한다.
3. 같은 문서도 Research Question이 다르면 점수가 달라질 수 있다.
4. 날짜가 없다는 이유로 점수를 낮추지 않는다. period_status는 참고용이다.
5. matched_terms: 이슈·질문의 핵심어 중 title/snippet에 실제로 나온 것만.
6. discovered_entities: title/snippet에 실제로 나오되 이슈 입력에는 없던 기관·장소·인물·
   사업·법률·정책 이름만. 이슈 입력의 표현을 그대로 옮기지 않는다.
7. 입력의 모든 result_id에 대해 정확히 하나씩, 주어진 research_question_id와 함께 반환한다.
"""


def _terms(d: IssueDecomposition) -> list[str]:
    fields = (
        "subjects actions organizations locations amounts policies explicit_in_input "
        "persons dates laws projects"
    ).split()
    return list(dict.fromkeys(t for f in fields for t in getattr(d, f)))


def _payload(
    issue: IssueInput,
    decomposition: IssueDecomposition,
    question: ResearchQuestion,
    items: list[tuple[SearchResult, PeriodStatus]],
) -> str:
    return json.dumps(
        {
            "region": issue.region,
            "issue": issue.issue,
            "issue_terms": _terms(decomposition),
            "research_question": {"id": question.id, "type": question.type.value, "question": question.question},
            "results": [
                {
                    "result_id": r.result_id,
                    "title": r.title,
                    "snippet": r.snippet[:300],
                    "published_at": r.published_at.date().isoformat() if r.published_at else None,
                    "period_status": status.value,
                }
                for r, status in items
            ],
        },
        ensure_ascii=False,
    )


async def analyze_results(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    decomposition: IssueDecomposition,
    question: ResearchQuestion,
    results: list[SearchResult],
) -> SearchAnalysisResult:
    # BACKGROUND questions may use documents from before the period.
    historical = question.type is QueryType.BACKGROUND
    statuses = [classify_period(r, issue.start_date, issue.end_date, allow_historical=historical) for r in results]
    metadata = {r.result_id: build_metadata(r, s) for r, s in zip(results, statuses)}
    # Structurally empty/list/error pages are skipped; semantic noise is left to Qwen.
    pending = [(r, s) for r, s in zip(results, statuses) if not metadata[r.result_id].structural_noise]
    by_id = {r.result_id: r for r in results}
    assessments = {}
    for i in range(0, len(pending), BATCH_SIZE):
        todo = pending[i : i + BATCH_SIZE]
        # An 8B model sometimes skips an item; re-ask once for just the missing ones.
        for _ in range(2):
            out = await qwen.chat(ANALYZER_PROMPT, _payload(issue, decomposition, question, todo), AssessmentBatch)
            wanted = {r.result_id for r, _ in todo}
            assessments.update({a.result_id: a for a in out.assessments if a.result_id in wanted})
            todo = [(r, s) for r, s in todo if r.result_id not in assessments]
            if not todo:
                break
        if todo:
            raise ValueError(f"Qwen did not assess: {[r.result_id for r, _ in todo]}")

    def norm(t: str) -> str:
        return "".join(t.split()).casefold()

    # Input terms and region spellings ("충남") that Qwen may echo back as "discovered".
    known = {norm(t) for t in _terms(decomposition)} | {norm(a) for a in REGION_ALIASES.get(issue.region, [issue.region])}
    cleaned = {}
    for rid, a in assessments.items():
        r = by_id[rid]
        text = f"{r.title} {r.snippet}"
        cleaned[rid] = a.model_copy(update={
            "research_question_id": question.id,
            # Drop anything Qwen did not actually read in the hit, or merely echoed from the input.
            "matched_terms": [t for t in a.matched_terms if t in text],
            "discovered_entities": [
                e for e in a.discovered_entities
                if e in text and norm(e) not in known and not any(norm(e) in k for k in known)
            ],
        })
    assessed = [AssessedResult(result=r, metadata=metadata[r.result_id], assessment=cleaned.get(r.result_id)) for r in results]
    entities = list(dict.fromkeys(e for a in assessed if a.assessment for e in a.assessment.discovered_entities))
    return SearchAnalysisResult(research_question_id=question.id, results=assessed, discovered_entities=entities)


def select_for_fetch(analysis: SearchAnalysisResult) -> list[AssessedResult]:
    """Useful hits that are in period, date-unknown, or historical-allowed. Out-of-period stays in the data."""
    return [
        a
        for a in analysis.results
        if a.assessment
        and a.assessment.relevance_score >= MIN_FETCH_SCORE
        and a.metadata.period_status is not PeriodStatus.OUT_OF_PERIOD
    ]
