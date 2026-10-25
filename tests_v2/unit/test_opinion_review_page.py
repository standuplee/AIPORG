import json
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.research.review import ReviewStatus, load_session, new_session, save_session, set_status, set_topic
from app.schemas.research import IssueInput
from app.search.documents import FactResearchResult, KeyFact
from app.search.opinion import DiscussionPost, DiscussionTopic, OpinionCandidates, ReactionPost

PAGE = str(Path(__file__).resolve().parents[2] / "streamlit_app" / "opinion_review.py")


def _post(i: int) -> ReactionPost:
    return ReactionPost(result_id=f"id{i}", channel="BLOG", title=f"글 {i}", reaction_evidence=f"쉼터가 부족하다 {i}",
                        verification_reason=f"이유 {i}", url=f"https://blog.example/{i}", snippet=f"문맥 {i}",
                        relevance_reason="충남 폭염 대응을 다룸" if i == 0 else None)


@pytest.fixture
def session_file(tmp_path, monkeypatch):
    issue = IssueInput(region="충청남도", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), issue="폭염 대응")
    cands = OpinionCandidates(issue="폭염 대응", queries=["q"], corpus_size=9, relevant_count=5, filtered_out={}, exclude_keywords=[],
                              candidates=[_post(i) for i in range(4)],
                              discussion_posts=[DiscussionPost(result_id=f"d{i}", channel="BLOG", title=f"논점 글 {i}", url=f"https://d/{i}", snippet="s", content_type="POLICY_INFORMATION") for i in range(3)],
                              topics=[DiscussionTopic(topic_id="T1", topic="무더위쉼터 확대", summary="쉼터 확대가 다뤄진다", source_result_ids=["d0", "d1"]),
                                      DiscussionTopic(topic_id="T2", topic="AI·드론", summary="기술 활용이 다뤄진다", source_result_ids=["d1", "d2"])])
    fact = FactResearchResult(summary="s", key_facts=[KeyFact(fact="TF 가동", source_result_ids=["f1"])], organizations=[], persons=[],
                              locations=[], current_status="추진 중", timeline=[], uncertainties=[], missing_information=[])
    path = tmp_path / "session_heat.json"
    save_session(path, new_session(issue, cands, fact, {"f1": ["충남도 보도자료", "https://chungnam.go.kr/1"]}))
    monkeypatch.setenv("AIPORG_RESEARCH_DIR", str(tmp_path))
    return path


def test_nothing_is_pre_approved_and_store_rereads_the_file(session_file):
    s = load_session(session_file)
    assert set(s.statuses.values()) == {ReviewStatus.PENDING} and not s.all_reviewed() and s.approved_ids() == set()
    set_status(session_file, "id0", ReviewStatus.APPROVED)
    set_status(session_file, "id1", ReviewStatus.REJECTED)  # a second writer sees the first one's decision
    s = load_session(session_file)
    assert s.counts() == {"PENDING": 2, "APPROVED": 1, "REJECTED": 1} and s.approved_ids() == {"id0"}
    with pytest.raises(KeyError):
        set_status(session_file, "nope", ReviewStatus.APPROVED)


def test_page_shows_cards_and_blocks_analysis_until_every_candidate_is_decided(session_file, monkeypatch):
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "검토 0 / 4" in text and "미검토 4" in text and "글 0" in text
    assert "“쉼터가 부족하다 0”" in " ".join(m.value for m in at.markdown) or any("쉼터가 부족하다 0" in m.value for m in at.markdown)
    assert any("충남 폭염 대응을 다룸" in c.value for c in at.caption)           # relevance reason is shown when present
    analyze = next(b for b in at.button if b.label.startswith("승인한 반응으로"))
    assert analyze.disabled

    at.button(key="use_id0").click().run()
    at.button(key="drop_id1").click().run()
    assert "검토 2 / 4" in " ".join(m.value for m in at.markdown) and "승인 1" in " ".join(m.value for m in at.markdown)
    assert next(b for b in at.button if b.label.startswith("승인한 반응으로")).disabled
    assert at.button(key="use_id0").disabled and not at.button(key="undo_id0").disabled

    at.button(key="drop_id2").click().run()
    at.button(key="drop_id3").click().run()
    assert not next(b for b in at.button if b.label.startswith("승인한 반응으로")).disabled
    assert load_session(session_file).approved_ids() == {"id0"}


def test_analysis_uses_only_approved_ids_and_writes_a_reviewed_report(session_file, monkeypatch):
    from app.research.query_expansion import QwenQueryExpansionService
    from app.research.report import ImplicationDraft

    async def chat(self, system, user, schema, *, num_ctx=None):
        assert schema is ImplicationDraft  # only 1 approved reaction -> no theme call, fact-only implications
        return ImplicationDraft(implications=["진행 상황을 지속적으로 점검할 필요가 있다."])

    monkeypatch.setattr(QwenQueryExpansionService, "chat", chat)
    for rid, st in (("id0", ReviewStatus.APPROVED), ("id1", ReviewStatus.REJECTED), ("id2", ReviewStatus.REJECTED), ("id3", ReviewStatus.REJECTED)):
        set_status(session_file, rid, st)
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    next(b for b in at.button if b.label.startswith("승인한 반응으로")).click().run()
    assert not at.exception
    md = session_file.parent / "report_reviewed_heat.md"
    assert md.exists() and "TF 가동" in md.read_text() and "분석 가능한 온라인 반응이 부족함" in md.read_text()
    saved = json.loads((session_file.parent / "reviewed_opinion_heat.json").read_text())
    assert saved["reaction_count"] == 1 and saved["filtered_out"]["reviewer_rejected"] == 3


def test_topics_start_selected_and_the_reviewer_can_drop_one(session_file):
    assert load_session(session_file).selected_topic_ids() == {"T1", "T2"}
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not at.exception and at.checkbox(key="topic_T1").value and at.checkbox(key="topic_T2").value
    assert any("1. 주요 논점 후보" in m.value for m in at.markdown) and any("2. 확인된 반응 후보" in m.value for m in at.markdown)
    at.checkbox(key="topic_T2").uncheck().run()
    assert load_session(session_file).selected_topic_ids() == {"T1"}
    # topic choices never gate the analysis button: only reactions must be decided
    assert next(b for b in at.button if b.label.startswith("승인한 반응으로")).disabled
    with pytest.raises(KeyError):
        set_topic(session_file, "T9", True)


def test_analysis_report_contains_only_the_kept_topics(session_file, monkeypatch):
    from app.research.query_expansion import QwenQueryExpansionService
    from app.research.report import ImplicationDraft

    async def chat(self, system, user, schema, *, num_ctx=None):
        return ImplicationDraft(implications=[])

    monkeypatch.setattr(QwenQueryExpansionService, "chat", chat)
    set_topic(session_file, "T2", False)
    for i in range(4):
        set_status(session_file, f"id{i}", ReviewStatus.REJECTED)
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    next(b for b in at.button if b.label.startswith("승인한 반응으로")).click().run()
    md = (session_file.parent / "report_reviewed_heat.md").read_text()
    assert "무더위쉼터 확대" in md and "AI·드론" not in md and "분석 가능한 온라인 반응이 부족함" in md
