"""Unit tests for streamlit_app/analytics_ui.py's pure rendering functions.

AppTest.from_function runs a plain callable as the Streamlit script by
re-executing just that function's own source -- module-level imports and
globals from the file it's defined in are not carried over, so each
wrapper below does its own imports instead of relying on this test
module's top-level imports.
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest.from_function re-execs the target function's source in a temp
# file elsewhere on disk, so a path built from that function's own
# __file__ would point at the wrong place. Put streamlit_app on sys.path
# once here, in this module (same process, so it sticks), and let the
# wrapper functions below import analytics_ui by plain name.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit_app"))


def _render_sidebar_status(state):
    from analytics_ui import render_job_sidebar_status

    render_job_sidebar_status(state)


def _render_summary(summary):
    from analytics_ui import render_analytics_summary

    render_analytics_summary(summary)


def _render_document_page(rows, offset, page_size, total):
    from analytics_ui import render_document_page

    render_document_page(rows, offset=offset, page_size=page_size, total=total)


def _run(callable_, **kwargs):
    at = AppTest.from_function(callable_, kwargs=kwargs)
    at.run()
    assert not at.exception, at.exception
    return at


def test_sidebar_status_renders_nothing_for_idle() -> None:
    at = _run(_render_sidebar_status, state={"status": "idle"})
    assert len(at.sidebar) == 0


def test_sidebar_status_shows_progress_bar_while_running() -> None:
    at = _run(
        _render_sidebar_status,
        state={"status": "running", "phase": "keywords", "completed": 3, "total": 10},
    )
    assert "진행 중" in at.sidebar.caption[0].value
    assert "3/10" in at.sidebar.progress[0].text


def test_sidebar_status_shows_done_and_failed() -> None:
    at = _run(_render_sidebar_status, state={"status": "done"})
    assert "완료" in at.sidebar.success[0].value

    at = _run(_render_sidebar_status, state={"status": "failed", "error": "원인 메시지"})
    assert "원인 메시지" in at.sidebar.error[0].value


def test_analytics_summary_renders_bounded_fields_only() -> None:
    summary = {
        "unique_documents": 42,
        "comment_count": 5,
        "channel_mentions": {"news": 30, "video": 12},
        "sentiment_distribution": {"positive": 10, "neutral": 32},
        "comparison": {"status": "available", "change": 7, "change_percent": 20.0},
        "top_keywords": [{"keyword": "폭염", "count": 100}],
    }
    at = _run(_render_summary, summary=summary)
    assert at.metric[0].value == "42"
    assert at.metric[1].value == "5"
    assert "7건" in at.caption[0].value and "20.0%" in at.caption[0].value
    assert at.dataframe[0].value.to_dict("records") == [{"keyword": "폭염", "count": 100}]


def test_analytics_summary_handles_missing_optional_sections() -> None:
    at = _run(_render_summary, summary={"unique_documents": 0, "comment_count": 0})
    assert at.metric[0].value == "0"
    assert len(at.dataframe) == 0  # no top_keywords -> no table rendered


def test_document_page_shows_bounded_range_and_fields() -> None:
    from datetime import datetime, timezone

    rows = [
        {
            "title": "기사 제목", "source": "연합뉴스", "channel": "news",
            "published_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "canonical_url": "https://example.test/1",
        },
    ]
    at = _run(_render_document_page, rows=rows, offset=50, page_size=50, total=53)
    assert "51~53" in at.caption[0].value
    record = at.dataframe[0].value.to_dict("records")[0]
    assert record["제목"] == "기사 제목"
    assert record["채널"] == "news"


def test_document_page_empty_total_shows_info_not_a_table() -> None:
    at = _run(_render_document_page, rows=[], offset=0, page_size=50, total=0)
    assert len(at.info) == 1
    assert len(at.dataframe) == 0
