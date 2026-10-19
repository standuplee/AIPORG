"""Streamlit rendering for the analytics screen.

Split out of console.py so the bounded-summary/page rendering (pure
functions over already-fetched dicts) can be unit-tested without the full
console app context. The job manager's cache_resource wrapper lives here
too since it needs ``streamlit`` imported, which the manager class itself
(``app/analytics/jobs.py``) deliberately does not depend on.
"""

from __future__ import annotations

import streamlit as st

from app.analytics.jobs import AnalyticsJobManager

_STATUS_LABELS = {
    "running": "진행 중",
    "done": "완료",
    "failed": "실패",
}

_PHASE_LABELS = {
    "loading": "입력 조회",
    "keywords": "키워드 집계",
    "issues": "이슈 집계",
    "fingerprint": "지문 계산",
    "saving": "저장",
}


@st.cache_resource
def get_job_manager(database_url: str) -> AnalyticsJobManager:
    """One job manager per Streamlit server process -- st.cache_resource
    keys by argument, so every session/rerun with the same database_url
    shares this same instance (and therefore its one active job slot)."""

    return AnalyticsJobManager(database_url)


def render_job_sidebar_status(state: dict[str, object]) -> None:
    """Render one job state dict (AnalyticsJobManager.poll()'s return
    value) into the sidebar. Pure rendering -- no polling/manager access
    here, so it's testable with a plain dict and renders nothing for the
    idle (no job ever submitted) state."""

    status = state.get("status", "idle")
    if status == "idle":
        return

    label = _STATUS_LABELS.get(str(status), str(status))
    with st.sidebar:
        st.divider()
        st.caption(f"통계 집계: {label}")
        if status == "running":
            phase = _PHASE_LABELS.get(state.get("phase"), str(state.get("phase", "")))
            completed = state.get("completed", 0) or 0
            total = state.get("total", 0) or 0
            if total:
                st.progress(min(completed / total, 1.0), text=f"{phase} ({completed}/{total})")
            else:
                st.caption(phase)
        elif status == "done":
            st.success("완료됨 — 새로고침하면 결과가 보인다.")
        elif status == "failed":
            st.error(f"실패: {state.get('error', '')}")


def render_analytics_summary(summary: dict[str, object]) -> None:
    """Render a bounded analytics summary
    (AnalyticsRepository.get_latest_summary) -- never the full metrics
    JSON, which real collected data put at several MB with up to ~46k
    keywords (2026-10-19, HANDOFF.md) and crashed the browser tab."""

    column_a, column_b = st.columns(2)
    column_a.metric("고유 문서 수", summary.get("unique_documents", 0))
    column_b.metric("댓글 수", summary.get("comment_count", 0))

    channel_mentions = summary.get("channel_mentions") or {}
    if channel_mentions:
        st.subheader("채널별 언급량")
        st.bar_chart(channel_mentions)

    sentiment_distribution = summary.get("sentiment_distribution") or {}
    if sentiment_distribution:
        st.subheader("감성 분포 (문서 metadata 라벨 집계, 형태소 분류 아님)")
        st.bar_chart(sentiment_distribution)

    comparison = summary.get("comparison")
    if comparison and comparison.get("status") == "available":
        change = comparison.get("change")
        change_percent = comparison.get("change_percent")
        st.caption(f"전월 대비: {change}건 ({change_percent:.1f}%)")

    top_keywords = summary.get("top_keywords") or []
    if top_keywords:
        st.subheader("TOP 키워드 (상위 30개)")
        st.dataframe(top_keywords, use_container_width=True)


def render_document_page(
    rows: list[dict[str, object]], *, offset: int, page_size: int, total: int,
) -> None:
    """Render one bounded page of canonical documents
    (DocumentRepository.list_canonical_page) -- body/metadata are never
    fetched, so this is safe for a project with thousands of documents."""

    if total == 0:
        st.info("아직 고유 문서가 없다.")
        return
    first = offset + 1
    last = min(offset + page_size, total)
    st.caption(f"고유 문서 {total}건 중 {first}~{last}건 표시.")
    st.dataframe(
        [
            {
                "제목": row["title"],
                "출처": row["source"],
                "채널": row["channel"].value if hasattr(row["channel"], "value") else row["channel"],
                "게시일": row["published_at"].isoformat() if row["published_at"] else None,
                "URL": row["canonical_url"],
            }
            for row in rows
        ],
        use_container_width=True,
    )
