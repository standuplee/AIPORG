import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit_app"))


def _page(rows):
    from datetime import datetime, timezone
    from uuid import UUID

    import streamlit as st

    from app.schemas.document import CleanDocument
    from app.sentiment.review import review_summary
    from sentiment_review import render_review

    docs = [CleanDocument(document_id=UUID(r["id"]), title=r["title"], body="본문", canonical_url=r["url"],
                          cleaned_at=datetime(2026, 8, 20, tzinfo=timezone.utc), query="석탄화력 특별법", metadata=r["meta"]) for r in rows]

    def on_decide(doc, label):
        st.session_state["decided"] = (str(doc.document_id), label.value if label else None)

    render_review(docs, review_summary(docs), on_decide)


ID_A, ID_B = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
ROWS = [
    {"id": ID_A, "title": "특별법 통과 환영", "url": "https://x.example/a",
     "meta": {"sentiment": "positive", "sentiment_evidence": "경제가 살아날 것이다", "sentiment_reason": "기대", "sentiment_basis": "BODY", "sentiment_review": "AI_ONLY", "body_available": True}},
    {"id": ID_B, "title": "일정 안내", "url": "https://x.example/b",
     "meta": {"sentiment_reason": "근거 구절 확인 실패", "sentiment_basis": "SNIPPET", "sentiment_review": "AI_ONLY", "body_available": False}},
]


def _run(rows):
    at = AppTest.from_function(_page, kwargs={"rows": rows}).run()
    assert not at.exception, at.exception
    return at


def test_page_shows_ai_label_evidence_and_sample_progress():
    at = _run(ROWS)
    text = " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])
    assert "검수 0 / 표본 2" in text and "특별법 통과 환영" in text and "긍정" in text and "경제가 살아날 것이다" in text
    assert "미분류" in text and "스니펫" in text  # the snippet-only document says its basis


def test_agree_and_correct_buttons_call_the_decision_callback_with_expected_label():
    at = _run(ROWS)
    at.button(key=f"agree_{ID_A}").click().run()
    assert at.session_state["decided"] == (ID_A, "positive")
    at.button(key=f"set_negative_{ID_A}").click().run()
    assert at.session_state["decided"] == (ID_A, "negative")
    at.button(key=f"set_none_{ID_B}").click().run()
    assert at.session_state["decided"] == (ID_B, None)


def test_no_documents_show_an_empty_state():
    at = _run([])
    assert any("검수할 문서가 없다" in i.value for i in at.info)
