"""Reaction review page: a person approves or rejects each AI-suggested reaction before analysis.

Run: ./.venv/bin/streamlit run streamlit_app/opinion_review.py --server.address 127.0.0.1
Sessions are JSON files (session_*.json) in $AIPORG_RESEARCH_DIR (default output/research).
"""

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.query_expansion import QwenQueryExpansionService  # noqa: E402
from app.research.report import build_report, render_markdown  # noqa: E402
from app.research.review import ReviewStatus, load_session, set_status, set_topic  # noqa: E402
from app.search.opinion import analyze_reactions  # noqa: E402

LABEL = {ReviewStatus.PENDING: "미검토", ReviewStatus.APPROVED: "승인", ReviewStatus.REJECTED: "제외"}


def research_dir() -> Path:
    return Path(os.environ.get("AIPORG_RESEARCH_DIR", "output/research"))


def _decide(path: Path, result_id: str, status: ReviewStatus) -> None:
    set_status(path, result_id, status)


def _toggle_topic(path: Path, topic_id: str) -> None:
    set_topic(path, topic_id, st.session_state[f"topic_{topic_id}"])


def render_topic(path: Path, topic, selected: bool, posts: dict) -> None:
    with st.container(border=True):
        st.checkbox(f"**{topic.topic}**", value=selected, key=f"topic_{topic.topic_id}",
                    on_change=_toggle_topic, args=(path, topic.topic_id))
        st.write(topic.summary)
        with st.expander(f"근거 글 {len(topic.source_result_ids)}건"):
            for rid in topic.source_result_ids:
                if rid in posts:
                    st.markdown(f"- [{posts[rid].title}]({posts[rid].url}) · {posts[rid].channel} · {posts[rid].content_type}")


def render_card(path: Path, post, status: ReviewStatus) -> None:
    with st.container(border=True):
        st.markdown(f"**{post.title}**")
        st.caption(f"{post.channel} · 현재 상태: {LABEL[status]}")
        st.link_button("원문 보기", post.url, key=f"link_{post.result_id}")
        st.markdown("**이슈 관련 문맥**")
        st.write(post.snippet or "(요약 없음)")
        if post.relevance_reason:
            st.caption(f"AI의 관련성 판단: {post.relevance_reason}")
        st.markdown("**AI가 찾은 반응**")
        st.write(f"“{post.reaction_evidence}”")
        st.markdown("**AI 판단**")
        st.write(post.verification_reason)
        use, drop, undo = st.columns(3)
        use.button("사용", key=f"use_{post.result_id}", type="primary", disabled=status is ReviewStatus.APPROVED,
                   on_click=_decide, args=(path, post.result_id, ReviewStatus.APPROVED))
        drop.button("제외", key=f"drop_{post.result_id}", disabled=status is ReviewStatus.REJECTED,
                    on_click=_decide, args=(path, post.result_id, ReviewStatus.REJECTED))
        undo.button("미검토로", key=f"undo_{post.result_id}", disabled=status is ReviewStatus.PENDING,
                    on_click=_decide, args=(path, post.result_id, ReviewStatus.PENDING))


def run_analysis(path: Path, session) -> str:
    qwen = QwenQueryExpansionService()
    result = asyncio.run(analyze_reactions(qwen, session.issue, session.candidates, session.approved_ids(), session.selected_topic_ids()))
    opinion_index = {p.result_id: (p.title, p.url) for p in session.candidates.discussion_posts}
    opinion_index.update({c.result_id: (c.title, c.url) for c in session.candidates.candidates})
    fact_index = {i: (v[0], v[1]) for i, v in session.fact_sources.items()}
    report = asyncio.run(build_report(qwen, session.issue, session.fact, result, fact_index, opinion_index))
    name = path.stem.removeprefix("session_")
    (path.parent / f"reviewed_opinion_{name}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (path.parent / f"report_reviewed_{name}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown = render_markdown(report)
    (path.parent / f"report_reviewed_{name}.md").write_text(markdown, encoding="utf-8")
    return markdown


def main() -> None:
    st.set_page_config(page_title="반응 자료 검토", layout="wide")
    st.title("반응 자료 검토")
    files = sorted(research_dir().glob("session_*.json"))
    if not files:
        st.info(f"검토할 세션이 없습니다: {research_dir()}/session_*.json")
        return
    path = st.sidebar.selectbox("이슈", files, format_func=lambda p: load_session(p).issue.issue)
    session = load_session(path)
    counts = session.counts()
    total = len(session.statuses)
    reviewed = total - counts["PENDING"]
    st.subheader(session.issue.issue)
    st.caption(f"{session.issue.region} · {session.issue.start_date} ~ {session.issue.end_date}")
    topics = session.candidates.topics
    posts = {p.result_id: p for p in session.candidates.discussion_posts}
    st.markdown("### 1. 주요 논점 후보")
    st.caption(f"수집된 관련 글 {len(posts)}건에서 반복해서 다뤄진 논점입니다(정책·기사 내용 포함). "
               "여론의 방향이 아니라 '무엇이 많이 이야기되는가'입니다. 보고서에 넣지 않을 논점은 체크를 해제하세요.")
    if not topics:
        st.info("2건 이상의 글이 다룬 논점이 없습니다.")
    for topic in topics:
        render_topic(path, topic, session.topic_selected.get(topic.topic_id, True), posts)

    st.markdown("### 2. 확인된 반응 후보")
    st.markdown(f"**검토 {reviewed} / {total}** · 승인 {counts['APPROVED']} · 제외 {counts['REJECTED']} · 미검토 {counts['PENDING']}")
    st.caption("글쓴이나 외부 인물이 이 이슈를 평가·기대·우려·비판·요구한 실제 반응만 '사용'하세요. "
               "정책 당사자의 설명, 기사 재게시, 다른 지역·일반론은 제외합니다. 반응은 이 목록에서만 보고서의 '여론 표정'으로 들어갑니다.")

    show = st.radio("보기", ["전체", "미검토", "승인", "제외"], horizontal=True)
    wanted = {"전체": None, "미검토": ReviewStatus.PENDING, "승인": ReviewStatus.APPROVED, "제외": ReviewStatus.REJECTED}[show]
    for post in session.candidates.candidates:
        status = session.statuses[post.result_id]
        if wanted is None or status is wanted:
            render_card(path, post, status)

    st.divider()
    if not session.all_reviewed():
        st.warning(f"미검토 {counts['PENDING']}건이 남아 있어 분석할 수 없습니다.")
    if st.button("승인한 반응으로 분석 실행", disabled=not session.all_reviewed(), type="primary"):
        with st.spinner("논점과 보고서를 만드는 중입니다 (로컬 Qwen, 수 분 걸릴 수 있습니다)"):
            st.session_state[f"report:{path.name}"] = run_analysis(path, session)
    if f"report:{path.name}" in st.session_state:
        st.markdown(st.session_state[f"report:{path.name}"])


main()
