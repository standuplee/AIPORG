"""Report Synthesizer V1: assemble Fact + Opinion results into one issue report.

Everything is copied from the two upstream results except the 시사점, the only part
Qwen writes, and that is checked for numbers that do not appear upstream.
"""

import json
import re

from app.research.query_expansion import QwenQueryExpansionService
from app.schemas.common import SchemaBase
from app.schemas.research import IssueInput
from app.search.documents import FactResearchResult
from app.search.opinion import INSUFFICIENT, DiscussionTopic, OpinionResearchResult, ReactionTheme

IMPLICATION_PROMPT = """
당신은 지방정부 월간 이슈 보고서의 시사점 작성자다.
주어진 사실 정리와 온라인 반응 정리만 근거로, 도정 운영·홍보 관점의 시사점을 2~3개 쓴다.

규칙:
1. 입력에 없는 사실, 기관, 숫자를 만들지 않는다. 입력의 숫자도 새로 계산하지 않는다.
2. 각 시사점은 입력에 있는 사실이나 반응에 근거한 해석 한 문장이다.
3. 확정되지 않은 계획을 완료된 것처럼 쓰지 않는다. current_status와 uncertainties를 따른다.
4. 반응이 소수 글에 근거한 표본임을 감안해 단정하지 않는다.
5. 각 시사점은 사실 정리의 항목과 reaction_themes의 논점을 직접 연결할 수 있어야 한다.
6. 제공된 reaction_themes에 없는 시민·주민·지역사회·업계·노동계의 기대·우려·평가·요구·반응을 서술하지 않는다.
   상식적으로 예상되는 경제적 효과, 사회적 기대, 우려, 파급효과를 새로 추론하지 않는다.
7. discussion_topics는 "수집된 글에서 반복해서 다뤄진 논점"이다. "~가 주요 논점으로 다뤄졌다"까지만 쓸 수 있고,
   시민의 기대나 우려가 있다고 쓰지 않는다.
"""

FACT_ONLY_PROMPT = """
당신은 지방정부 월간 이슈 보고서의 시사점 작성자다. 이 이슈에는 분석 가능한 온라인 반응이 없다.
주어진 사실 정리만 근거로, 보고서 담당자가 관리해야 할 포인트를 1~2개 쓴다.

규칙:
1. Reaction Theme이 근거로 제공되지 않았다. 시민, 주민, 지역사회, 업계, 노동계 등의 기대·우려·평가·요구·반응이
   존재한다고 서술하지 않는다.
2. 사실만으로 시사점을 쓸 때는 확인, 모니터링, 진행 상황 점검처럼 해당 사실에서 직접 이어지는 관리 포인트만 쓴다.
3. 상식적으로 예상되는 경제적 효과, 사회적 기대, 우려, 파급효과를 새로 추론하지 않는다.
4. 입력에 없는 사실, 기관, 숫자를 만들지 않는다. 계획이나 협약을 완료된 것처럼 쓰지 않는다.
5. discussion_topics가 있으면 "~가 주요 논점으로 다뤄졌다"까지만 쓸 수 있다. 그것을 시민의 기대나 우려로 바꾸지 않는다.
"""
# Last-resort insurance only; the prompts above are the real control. Keep this list short.
_OPINION_WORDS = ("기대", "우려", "여론", "반응")

NO_OPINION_NOTE = "온라인 반응 표본이 부족하여 여론 기반 시사점은 도출하지 않았으며, 아래는 확인된 사실에서 직접 이어지는 관리 포인트임"


class ImplicationDraft(SchemaBase):
    implications: list[str]


class SourceRef(SchemaBase):
    result_id: str
    title: str
    url: str


class IssueReport(SchemaBase):
    issue: str
    period: str
    core_content: list[str]
    current_status: str | None
    timeline: list[str]
    overall_tone: str
    reaction_summary: str
    discussion_topics: list[DiscussionTopic]
    topic_sources: list[SourceRef]
    discussion_size: int
    reaction_themes: list[ReactionTheme]
    reaction_sources: list[SourceRef]
    sample_size: int
    keywords: list[str]
    channel_notes: list[str]
    implications: list[str]
    implications_note: str | None
    uncertainties: list[str]
    sources: list[SourceRef]
    limitations: list[str]


_NUMBER = re.compile(r"\d[\d,.]*")


def _grounded(text: str, source_text: str) -> bool:
    return all(n in source_text for n in _NUMBER.findall(text))


async def build_report(
    qwen: QwenQueryExpansionService,
    issue: IssueInput,
    fact: FactResearchResult,
    opinion: OpinionResearchResult,
    source_index: dict[str, tuple[str, str]],
    opinion_index: dict[str, tuple[str, str]],
) -> IssueReport:
    no_opinion = opinion.reaction_count == 0
    upstream = json.dumps(
        {"facts": fact.model_dump(mode="json"), "opinion": opinion.model_dump(mode="json")}, ensure_ascii=False
    )
    facts_only = {
        "issue": issue.issue, "facts": [f.fact for f in fact.key_facts], "current_status": fact.current_status,
        "uncertainties": fact.uncertainties,
        "discussion_topics": [{"topic": t.topic, "summary": t.summary} for t in opinion.discussion_topics],
    }
    if no_opinion:
        draft: ImplicationDraft = await qwen.chat(FACT_ONLY_PROMPT, json.dumps(facts_only, ensure_ascii=False), ImplicationDraft)
    else:
        draft = await qwen.chat(
            IMPLICATION_PROMPT,
            json.dumps(
                {
                    **facts_only,
                    "tone": opinion.overall_sentiment.value,
                    "reaction_themes": [{"theme": t.theme, "tone": t.tone.value, "summary": t.summary} for t in opinion.reaction_themes],
                    "channels": [{"channel": c.channel, "sample_size": c.sample_size, "sentiment": c.sentiment.value, "reactions": c.main_reactions} for c in opinion.channel_insights],
                },
                ensure_ascii=False,
            ),
            ImplicationDraft,
        )
    implications = [
        x for x in draft.implications
        if x.strip() and _grounded(x, upstream) and not (no_opinion and any(w in x for w in _OPINION_WORDS))
    ][:3]
    used_ids = list(dict.fromkeys(i for f in [*fact.key_facts, *fact.timeline] for i in f.source_result_ids))
    return IssueReport(
        issue=issue.issue,
        period=f"{issue.start_date} ~ {issue.end_date}",
        core_content=[f.fact for f in fact.key_facts],
        current_status=fact.current_status,
        timeline=[f"{t.date or '일자 미상'}: {t.event}" for t in fact.timeline],
        overall_tone=INSUFFICIENT if no_opinion else opinion.overall_sentiment.value,
        reaction_summary=opinion.analysis_summary.removeprefix(INSUFFICIENT).lstrip(". ") if no_opinion else opinion.analysis_summary,
        discussion_topics=opinion.discussion_topics,
        topic_sources=[SourceRef(result_id=i, title=opinion_index[i][0], url=opinion_index[i][1])
                       for i in dict.fromkeys(i for t in opinion.discussion_topics for i in t.source_result_ids) if i in opinion_index],
        discussion_size=opinion.discussion_size,
        reaction_themes=opinion.reaction_themes,
        reaction_sources=[SourceRef(result_id=i, title=opinion_index[i][0], url=opinion_index[i][1])
                          for i in dict.fromkeys(i for t in opinion.reaction_themes for i in t.source_result_ids) if i in opinion_index],
        sample_size=opinion.reaction_count,
        keywords=[k.keyword for k in opinion.keywords[:10]],
        channel_notes=["유효 반응 표본 부족"] if no_opinion else [f"{c.channel} (유효 반응 {c.sample_size}건, {c.sentiment.value}): " + " / ".join(c.main_reactions) for c in opinion.channel_insights],
        implications=implications,
        implications_note=NO_OPINION_NOTE if no_opinion else None,
        uncertainties=fact.uncertainties,
        sources=[SourceRef(result_id=i, title=source_index[i][0], url=source_index[i][1]) for i in used_ids if i in source_index],
        limitations=[opinion.limitations, "사실 정리는 수집된 문서 중 최대 8건의 앞부분을 기준으로 했다."],
    )


def render_markdown(r: IssueReport) -> str:
    def bullets(items):
        return "\n".join(f"- {x}" for x in items) or "- (해당 없음)"

    out = [f"# {r.issue}", f"분석 기간: {r.period}", "", "## 핵심 내용", bullets(r.core_content), "", "## 현황", r.current_status or "(확인 안 됨)"]
    if r.timeline:
        out += ["", bullets(r.timeline)]
    label = {"POSITIVE": "기대·긍정", "CONCERN": "우려", "CRITICISM": "비판", "REQUEST": "요구", "NEUTRAL": "관심", "MIXED": "양면"}
    link = {x.result_id: f"[{x.title}]({x.url})" for x in r.reaction_sources}
    themes = [
        f"**{t.theme}** ({label[t.tone.value]}) — {t.summary}"
        + (" 근거: " + ", ".join(link[i] for i in t.source_result_ids[:3] if i in link) if t.source_result_ids else "")
        for t in r.reaction_themes
    ]
    tlink = {x.result_id: f"[{x.title}]({x.url})" for x in r.topic_sources}
    topics = [
        f"**{t.topic}** — {t.summary} (근거 글 {len(t.source_result_ids)}건: " + ", ".join(tlink[i] for i in t.source_result_ids[:3] if i in tlink) + ")"
        for t in r.discussion_topics
    ]
    out += ["", "## 주요 논점", f"수집된 관련 글 {r.discussion_size}건에서 반복해서 다뤄진 논점이며, 여론의 방향(기대·우려)을 뜻하지 않는다.", bullets(topics)]
    out += ["", "## 여론 표정", f"**{r.overall_tone}** (유효 반응 {r.sample_size}건)" + (f" — {r.reaction_summary}" if r.reaction_summary else ""), "", "주요 반응", bullets(themes),
            "", "## 연관 키워드", ", ".join(r.keywords) or "(없음)", "", "## 채널별 특징", bullets(r.channel_notes),
            "", "## 시사점"]
    if r.implications_note:
        out += [r.implications_note if r.implications else "온라인 반응 표본이 부족하여 여론 기반 시사점을 도출하지 않음"]
    out += [bullets(r.implications)] if r.implications else ([] if r.implications_note else [bullets([])])
    if r.uncertainties:
        out += ["", "## 확인 필요", bullets(r.uncertainties)]
    out += ["", "## 출처", bullets(f"[{s.title}]({s.url})" for s in r.sources), "", "## 한계", bullets(r.limitations)]
    return "\n".join(out) + "\n"
