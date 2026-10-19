# Analytics Background Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Preserve pre-existing documentation edits.

**Goal:** Keep Streamlit responsive during analytics and prevent browser memory exhaustion by querying bounded summaries from persisted snapshots.

**Architecture:** Existing SQLite JSON snapshots remain authoritative. Repository read methods project only requested values and page canonical document metadata. A server-cached job manager starts a spawned process with its own DB session, drains throttled progress independently of UI, and exposes small immutable copies to a sidebar fragment. No new database/Pydantic schema.

**Tech Stack:** Python multiprocessing spawn, threading for IPC monitoring, SQLAlchemy/SQLite JSON functions, Streamlit fragment/AppTest, pytest.

## Tasks

- [ ] Repository reads (`app/repositories/sqlalchemy.py`, `tests_v2/unit/test_analytics_ui_queries.py`): test empty/project-scoped/latest selection, stable top-30 keyword ordering, exclusion of huge provenance, SQL pagination and canonical dedup. Then implement `get_latest_summary`, `count_canonical`, `list_canonical_page`, `count_by_project` for evidence. No full snapshot/Document hydration.
- [ ] Progress (`app/analytics/service.py`, `app/workflows/issues_to_analytics.py` and unit tests): optional callback for actual keyword processed/total and phase changes. Default signatures remain backward compatible. Test unchanged metrics and empty inputs before adding code.
- [ ] Worker/manager (`app/analytics/jobs.py`, unit and integration tests): spawn a process, own transaction, success only after commit, one active job, bounded/throttled IPC and monitor independent of browsers. Handle exceptions, abnormal exits, start failures, cleanup and retries. Parent-death watchdog and per-DB file lock prevent orphan overlaps. Test temporary migrated SQLite success/rollback.
- [ ] UI (`streamlit_app/console.py`, `streamlit_app/analytics_ui.py`, AppTest unit tests): query summaries/pages only, no full JSON widget, background submit, sidebar periodic phase/count/error state and one-time completion refresh. Main console uses cached manager; worker never calls Streamlit. Test bounded output and submission/failed/completed states. Explain query semantics in collection caption.
- [ ] Run `.venv/bin/python -m pytest tests_v2/integration -q` and full `tests_v2 tests -q`, inspect actual UI using AppTest and read-only persisted summary. Update HANDOFF and spec/plan, inspect diff, commit only this feature and push according to repository handoff rule.

For every module, write/run failing unit tests before implementation; fix any integration failure before continuing. No live collection or writes to the user's DB during verification.
