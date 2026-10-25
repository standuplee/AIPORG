import asyncio
from datetime import date

from app.research.report import ImplicationDraft, build_report, render_markdown
from app.schemas.research import IssueInput
from app.search.documents import FactResearchResult, KeyFact, TimelineItem
from app.search.opinion import ChannelInsight, DiscussionTopic, KeywordCount, OpinionResearchResult, OverallSentiment, ReactionTheme, ReactionTone

ISSUE = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="이슈")
FACT = FactResearchResult(
    summary="s", key_facts=[KeyFact(fact="2026년 8월 20일 본회의 통과", source_result_ids=["a"])], organizations=[], persons=[],
    locations=[], current_status="국회 본회의 통과(공포 여부 미확인)",
    timeline=[TimelineItem(date="2026-08-20", event="본회의 통과", source_result_ids=["a", "b"])],
    uncertainties=["확인 필요: 시행일"], missing_information=[])
OPINION = OpinionResearchResult(
    overall_sentiment=OverallSentiment.SPLIT, analysis_summary="요약", key_topics=["고용 전환"], discussion_size=9,
    discussion_topics=[DiscussionTopic(topic_id="T1", topic="고용 전환", summary="노동자 고용 전환이 다뤄진다", source_result_ids=["d1", "d2"])],
    reaction_themes=[ReactionTheme(theme="예산 확보", tone=ReactionTone.CONCERN, summary="예산이 부족할까 걱정", source_result_ids=["p1", "p2"])],
    channel_insights=[ChannelInsight(channel="BLOG", sample_size=6, main_reactions=["예산 확보"], sentiment=OverallSentiment.SPLIT)],
    issue="이슈", queries=["q"], corpus_size=9, relevant_count=7, reaction_count=6, reactions=[], channel_counts={"BLOG": 6}, filtered_out={},
    keywords=[KeywordCount(keyword="전환", doc_count=2)])


class _Qwen:
    async def chat(self, system, user, schema):
        return ImplicationDraft(implications=[
            "법안 통과 이후 시행 일정 안내가 필요하다.",
            "예산 3000억 원 확보가 시급하다.",   # number not in upstream -> must be dropped
            "  ",
        ])


def test_report_copies_upstream_and_drops_ungrounded_implications():
    r = asyncio.run(build_report(_Qwen(), ISSUE, FACT, OPINION, {"a": ("기사 A", "https://a"), "b": ("기사 B", "https://b"), "z": ("미사용", "https://z")},
                                {"p1": ("블로그 1", "https://p1"), "p2": ("블로그 2", "https://p2"), "d1": ("기사 D1", "https://d1"), "d2": ("기사 D2", "https://d2"), "p9": ("미사용", "https://p9")}))
    assert r.core_content == ["2026년 8월 20일 본회의 통과"] and r.current_status.startswith("국회 본회의 통과")
    assert r.timeline == ["2026-08-20: 본회의 통과"]
    assert r.implications == ["법안 통과 이후 시행 일정 안내가 필요하다."]
    assert [s.result_id for s in r.sources] == ["a", "b"]  # only documents the facts cite
    assert [s.result_id for s in r.reaction_sources] == ["p1", "p2"]
    assert [t.topic for t in r.discussion_topics] == ["고용 전환"] and [s.result_id for s in r.topic_sources] == ["d1", "d2"]
    md = render_markdown(r)
    assert "## 주요 논점" in md and "**고용 전환** — 노동자 고용 전환이 다뤄진다 (근거 글 2건: [기사 D1](https://d1)" in md
    assert md.index("## 주요 논점") < md.index("## 여론 표정")   # topics and reactions are two separate sections
    for heading in ("## 핵심 내용", "## 현황", "## 여론 표정", "## 연관 키워드", "## 채널별 특징", "## 시사점", "## 출처", "## 한계"):
        assert heading in md
    assert "[기사 A](https://a)" in md and "긍정·우려 혼재" in md and "예산 확보" in md and "근거: [블로그 1](https://p1)" in md and "유효 반응 6건" in md and "확인 필요: 시행일" in md


def test_zero_reactions_allows_fact_only_implications_without_opinion_language():
    from app.search.opinion import INSUFFICIENT_DETAIL

    seen = {}

    class FactOnly:
        async def chat(self, system, user, schema):
            seen["system"] = system
            return ImplicationDraft(implications=[
                "단계적 투자계획이므로 진행 상황을 지속적으로 확인할 필요가 있다.",
                "지역사회의 기대가 높아 보인다.",        # opinion language without any verified reaction -> dropped
                "투자액 9999억 원이 확정됐다.",           # number not in upstream -> dropped
            ])

    empty = OPINION.model_copy(update={
        "reaction_count": 0, "reaction_themes": [], "channel_insights": [], "keywords": [], "overall_sentiment": OverallSentiment.UNKNOWN,
        "analysis_summary": f"분석 가능한 온라인 반응이 부족함. {INSUFFICIENT_DETAIL}"})
    r = asyncio.run(build_report(FactOnly(), ISSUE, FACT, empty, {"a": ("기사 A", "https://a")}, {}))
    assert "분석 가능한 온라인 반응이 없다" in seen["system"] or "온라인 반응이 없다" in seen["system"]
    assert r.implications == ["단계적 투자계획이므로 진행 상황을 지속적으로 확인할 필요가 있다."]
    assert r.overall_tone == "분석 가능한 온라인 반응이 부족함" and r.channel_notes == ["유효 반응 표본 부족"] and r.reaction_summary == INSUFFICIENT_DETAIL
    md = render_markdown(r)
    assert "여론 기반 시사점은 도출하지 않았으며" in md and "진행 상황을 지속적으로 확인" in md and "(유효 반응 0건)" in md
    assert "고용 전환" in md.split("## 주요 논점")[1].split("## 여론 표정")[0]   # the discussion section is filled although no reaction is
