"""End-to-end check of the per-issue narrative report layout (overview
paragraph -> 핵심 과제 table -> 출처 -> closing paragraph), driven through
the real Streamlit page against a migrated temp SQLite database and the
real evidence->issue pipeline (not a mock) -- the same fixtures already
used to integration-test IssuesToAnalyticsWorkflow.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from streamlit.testing.v1 import AppTest

from app.db.session import create_session_factory, session_scope
from app.repositories.sqlalchemy import SqlAlchemyNarrativeRepository
from tests_v2.integration.test_issues_to_analytics_workflow import run_info, seed, workflow

# AppTest.from_function re-execs the target function's source in a temp
# file elsewhere on disk, so a path built from that function's own
# __file__ would point at the wrong place -- put streamlit_app on
# sys.path once here instead (same process, so it sticks).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit_app"))


@pytest.fixture(autouse=True)
def _restore_real_main_module():
    """Streamlit's script runner replaces ``sys.modules["__main__"]`` with
    a fake module pointing at AppTest's temp script file and never restores
    it (streamlit/runtime/scriptrunner/script_runner.py, ``_new_module``).
    Left in place, that breaks any later ``multiprocessing`` "spawn" test in
    the same pytest process -- the child re-execs whatever path
    ``sys.modules["__main__"].__file__`` points to, which is now a deleted
    temp file (discovered via test_analytics_jobs.py failing when collected
    after this file). Restore it so this file cleans up after itself."""

    original = sys.modules.get("__main__")
    yield
    if original is not None:
        sys.modules["__main__"] = original
    else:
        sys.modules.pop("__main__", None)


@pytest.fixture
def factory(tmp_path):
    url = f"sqlite:///{tmp_path / 'narrative_report.db'}"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    factory = create_session_factory(url)
    yield factory
    factory.kw["bind"].dispose()


def _render_page_narrative(database_url, project_id_hex):
    import streamlit as st
    from app.db.session import create_session_factory
    import console

    st.session_state["active_project_id"] = project_id_hex
    console.page_narrative(create_session_factory(database_url))


def _app(database_url, project_id):
    at = AppTest.from_function(
        _render_page_narrative,
        kwargs={"database_url": database_url, "project_id_hex": str(project_id)},
    )
    at.run()
    assert not at.exception, at.exception
    return at


def test_template_fallback_renders_overview_table_sources_and_closing(factory, monkeypatch):
    # No AIPORG2_GEMINI_API_KEY -> deterministic template path.
    # Set (not delete): console.py's module-level load_dotenv() runs the
    # first time this process imports it (inside the AppTest below) and
    # python-dotenv never overrides an already-present env var -- an
    # empty string still counts as "present", so this survives that load
    # and the repo's real .env key is never read into this test.
    monkeypatch.setenv("AIPORG2_GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    with session_scope(factory) as session:
        project_id, _ids = seed(session)
        workflow(session).run(project_id, run_info())

    database_url = factory.kw["bind"].url.render_as_string()

    at = _app(database_url, project_id)
    assert len(at.button) == 1  # only "초안 생성" before any draft exists

    at.button[0].click().run()
    assert not at.exception, at.exception

    markdown_texts = [element.value for element in at.markdown]
    assert any(text.startswith("#### 이슈:") for text in markdown_texts)

    assert len(at.dataframe) >= 1
    table = at.dataframe[0].value
    assert list(table.columns) == ["핵심 과제", "정책 · 현황", "온라인 반응"]
    assert all(
        cell.split()[0].count("★") + cell.split()[0].count("☆") == 5
        for cell in table["온라인 반응"]
    )

    captions = [element.value for element in at.caption]
    assert any(caption.startswith("출처: ") for caption in captions)

    expander_labels = [element.label for element in at.expander]
    assert any("근거 보기" in label for label in expander_labels)

    with session_scope(factory) as session:
        [saved] = SqlAlchemyNarrativeRepository(session).list_outputs(project_id)
        assert saved.issue_id is not None
        roles = {sentence.role for sentence in saved.sentences}
        assert "overview" in roles
        assert "closing" in roles


def test_saved_version_without_issue_id_falls_back_to_bullet_list(factory, monkeypatch):
    """A legacy output row (saved before issue_id existed) must still
    render -- as the old bullet+citation list, not crash the page."""

    # Set (not delete): console.py's module-level load_dotenv() runs the
    # first time this process imports it (inside the AppTest below) and
    # python-dotenv never overrides an already-present env var -- an
    # empty string still counts as "present", so this survives that load
    # and the repo's real .env key is never read into this test.
    monkeypatch.setenv("AIPORG2_GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    with session_scope(factory) as session:
        project_id, _ids = seed(session)
        workflow(session).run(project_id, run_info())

    database_url = factory.kw["bind"].url.render_as_string()
    at = _app(database_url, project_id)
    at.button[0].click().run()
    assert not at.exception, at.exception

    with session_scope(factory) as session:
        repository = SqlAlchemyNarrativeRepository(session)
        [saved] = repository.list_outputs(project_id)
        legacy = saved.model_copy(update={"issue_id": None})
        from app.models.narrative import Narrative

        row = session.get(Narrative, legacy.run.run_id)
        row.context = {"kind": "narrative_output", "data": legacy.model_dump(mode="json")}

    at = _app(database_url, project_id)
    assert not at.exception, at.exception
    bullets = [element.value for element in at.markdown if element.value.startswith("- ")]
    assert bullets  # old per-sentence bullet rendering, not the table layout
