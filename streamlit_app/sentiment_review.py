"""Sample review of the AI's document sentiment labels: a person agrees or corrects, and the report says how many were checked."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.enums import SentimentLabel  # noqa: E402
from app.schemas.document import CleanDocument  # noqa: E402
from app.sentiment.review import record_review, review_summary, select_review_sample  # noqa: E402

LABEL_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립", "mixed": "혼재"}
STATE_KO = {"AI_ONLY": "AI 분류, 미검수", "AGREED": "검수: 동의", "CORRECTED": "검수: 수정됨"}


def render_review(docs: list[CleanDocument], summary: dict[str, dict[str, int]], on_decide) -> None:
    """Pure rendering. `on_decide(document, label)` gets the AI's own label for 'agree' and the chosen one for a correction."""
    if not docs:
        st.info("검수할 문서가 없다. 감성 분류를 먼저 실행하라.")
        return
    for issue, s in summary.items():
        st.markdown(f"**{issue}** · 검수 {s['reviewed']} / 표본 {s['sample']} (일치 {s['agreed']}, 수정 {s['corrected']})")
    st.caption("표본은 이슈별로 고정된 규칙으로 뽑는다. 검수하지 않은 이슈는 보고서에 'AI 분류, 미검수'로 표시된다.")
    by_id = {d.document_id: d for d in docs}
    for doc_id in select_review_sample(docs):
        doc = by_id[doc_id]
        meta = doc.metadata
        ai = SentimentLabel(meta["sentiment"]) if meta.get("sentiment") in LABEL_KO else None
        with st.container(border=True):
            st.markdown(f"**{doc.title}**")
            st.caption(f"{doc.query} · {'본문 기준' if meta.get('sentiment_basis') == 'BODY' else '스니펫 기준'} · {STATE_KO.get(meta.get('sentiment_review'), '미분류 실행 전')}")
            st.link_button("원문 보기", doc.canonical_url, key=f"link_{doc_id}")
            st.markdown(f"AI 판정: **{LABEL_KO[ai.value] if ai else '미분류'}**")
            if meta.get("sentiment_evidence"):
                st.markdown(f"근거: “{meta['sentiment_evidence']}”")
            elif meta.get("sentiment_reason"):
                st.caption(f"사유: {meta['sentiment_reason']}")
            agree, *choices = st.columns(6)
            agree.button("AI 판정에 동의", key=f"agree_{doc_id}", type="primary", on_click=on_decide, args=(doc, ai))
            for col, (value, name) in zip(choices, [*LABEL_KO.items(), ("none", "미분류")]):
                col.button(name, key=f"set_{value}_{doc_id}", on_click=on_decide, args=(doc, None if value == "none" else SentimentLabel(value)))


def page_sentiment_review(factory, project_id: UUID) -> None:
    from app.db.session import session_scope
    from app.repositories.sqlalchemy import SqlAlchemyDocumentRepository
    from app.research.query_expansion import QwenQueryExpansionService
    from app.sentiment.document_classifier import classify_project

    st.header("4-2. 감성 분류 검수")
    if st.button("AI 감성 분류 실행 (로컬 Qwen, 수 분 걸릴 수 있음)"):
        with st.spinner("문서별 감성을 분류하는 중입니다"):
            with session_scope(factory) as session:
                counts = asyncio.run(classify_project(QwenQueryExpansionService(), session, project_id))
        st.success(f"분류 결과: {counts}")
    with session_scope(factory) as session:
        docs = SqlAlchemyDocumentRepository(session).list_canonical(project_id)

    def on_decide(doc: CleanDocument, label: SentimentLabel | None) -> None:
        with session_scope(factory) as session:
            record_review(SqlAlchemyDocumentRepository(session), project_id, doc, label=label)

    render_review(docs, review_summary(docs), on_decide)
