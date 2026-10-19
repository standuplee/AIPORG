"""Background analytics aggregation.

A single OS process per aggregation job, isolated from the Streamlit UI
process's memory/interpreter (real collected data put the full metrics
JSON at several MB with up to ~46k keywords -- see HANDOFF.md, 2026-10-19),
with throttled progress IPC and one-active-job-per-server enforcement.

No new schema or DB table (AGENTS.md rule 1): job state lives only in this
process's memory (the manager instance, meant to be held by
``st.cache_resource``) and in the existing ``analytics_snapshots`` row the
worker writes through the existing ``IssuesToAnalyticsWorkflow``/repository
path (rule 3 -- no direct DB write outside a repository). The worker
process builds its own DB session; no ORM session or Streamlit object
crosses the process boundary.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from datetime import datetime
from queue import Empty
from threading import Lock
from uuid import UUID

PROGRESS_THROTTLE_SECONDS = 0.2  # at most 5/sec, per design doc
_LOCK_SUFFIX = ".analytics-job.lock"


class _ParentDied(Exception):
    """Raised inside the worker process when its parent has exited --
    an abort signal, not a computation failure. Nothing is reported back:
    nobody holds the manager (and therefore the queue) anymore."""


def _make_progress_reporter(queue: "mp.Queue", parent_pid: int):
    """Build the ``on_progress(phase, completed, total)`` callback passed
    into AnalyticsService/IssuesToAnalyticsWorkflow inside the worker.

    Throttled to PROGRESS_THROTTLE_SECONDS except for the first and last
    message of a phase (completed in {0, total}), so the sidebar always
    sees a phase start and its true final count. Doubles as the parent-
    death watchdog: every call checks the real parent is still the one
    that spawned this process (a dead parent gets a new child reparented
    to it, changing getppid()) and aborts the job if not.
    """

    last_sent = 0.0

    def on_progress(phase: str, completed: int, total: int) -> None:
        nonlocal last_sent
        if os.getppid() != parent_pid:
            raise _ParentDied()
        now = time.monotonic()
        is_edge = completed == 0 or completed == total
        if not is_edge and now - last_sent < PROGRESS_THROTTLE_SECONDS:
            return
        last_sent = now
        try:
            queue.put_nowait(("progress", phase, completed, total))
        except Exception:
            pass  # a full/closed queue must never block or crash the worker

    return on_progress


def _run_in_process(
    database_url: str,
    project_id_hex: str,
    run_id_hex: str,
    input_version: str,
    output_version: str,
    created_at_iso: str,
    queue: "mp.Queue",
    parent_pid: int,
) -> None:
    """Entry point executed in the spawned child process."""

    from app.analytics.service import AnalyticsService
    from app.core.state_machine import InvalidStateTransitionError
    from app.db.session import create_session_factory, session_scope
    from app.repositories.sqlalchemy import (
        SqlAlchemyAnalyticsRepository,
        SqlAlchemyDocumentRepository,
        SqlAlchemyFactRepository,
        SqlAlchemyIssueRepository,
        SqlAlchemyProjectRepository,
    )
    from app.schemas.common import VersionedRunSchema
    from app.workflows.issues_to_analytics import IssuesToAnalyticsWorkflow

    on_progress = _make_progress_reporter(queue, parent_pid)
    try:
        factory = create_session_factory(database_url)
        with session_scope(factory) as session:
            workflow = IssuesToAnalyticsWorkflow(
                project_repository=SqlAlchemyProjectRepository(session),
                document_repository=SqlAlchemyDocumentRepository(session),
                fact_repository=SqlAlchemyFactRepository(session),
                issue_repository=SqlAlchemyIssueRepository(session),
                analytics_repository=SqlAlchemyAnalyticsRepository(session),
                analytics_service=AnalyticsService(on_progress=on_progress),
                on_progress=on_progress,
            )
            run = VersionedRunSchema(
                run_id=UUID(run_id_hex),
                input_version=input_version,
                output_version=output_version,
                created_at=datetime.fromisoformat(created_at_iso),
            )
            workflow.run(UUID(project_id_hex), run)
        # session_scope's `with` above has already committed by this line --
        # only report success once the result is actually durable (the
        # st.rerun-before-commit bug from 2026-10-19 is the cautionary
        # precedent for reporting "done" from inside the transaction).
        queue.put(("done", None))
    except _ParentDied:
        return  # no result to report -- nobody is listening anymore
    except (ValueError, InvalidStateTransitionError) as exc:
        queue.put(("failed", str(exc)))
    except Exception as exc:  # pragma: no cover - defensive: must always report
        queue.put(("failed", f"{type(exc).__name__}: {exc}"))


class AnalyticsJobManager:
    """Owns at most one in-flight background aggregation job.

    Meant to be created once per Streamlit server process (cached via
    ``st.cache_resource`` so every session/rerun shares the same instance)
    and polled from a ``st.fragment`` in the sidebar.
    """

    def __init__(self, database_url: str, *, _worker=_run_in_process) -> None:
        self._database_url = database_url
        self._lock = Lock()
        self._process: mp.Process | None = None
        self._queue: "mp.Queue | None" = None
        self._state: dict[str, object] = {"status": "idle"}
        self._lock_file_handle = None
        self._project_id: UUID | None = None
        # overridable only for tests exercising the process/IPC/lock
        # machinery itself without paying for a real analytics run
        self._worker = _worker

    def is_running(self) -> bool:
        with self._lock:
            self._reap_if_finished_locked()
            return self._process is not None

    def submit(self, project_id: UUID, run) -> bool:
        """Start a job if none is running anywhere against this DB file.

        Returns False (and leaves ``poll()``'s state explaining why)
        without starting a second job if one is already in flight -- in
        this process or, via the on-disk lock file, in another server
        process still attached to the same database.
        """

        with self._lock:
            self._reap_if_finished_locked()
            if self._process is not None:
                return False
            if not self._acquire_db_lock():
                self._state = {
                    "status": "failed",
                    "error": "다른 서버 프로세스가 이미 같은 DB로 통계 집계를 실행 중이다.",
                }
                return False
            ctx = mp.get_context("spawn")
            queue: "mp.Queue" = ctx.Queue()
            process = ctx.Process(
                target=self._worker,
                args=(
                    self._database_url, str(project_id), str(run.run_id),
                    run.input_version, run.output_version,
                    run.created_at.isoformat(), queue, os.getpid(),
                ),
                daemon=True,
            )
            try:
                process.start()
            except Exception as exc:
                self._release_db_lock()
                self._state = {"status": "failed", "error": f"작업 시작 실패: {exc}"}
                return False
            self._process = process
            self._queue = queue
            self._project_id = project_id
            self._state = {"status": "running", "phase": "loading", "completed": 0, "total": 0}
            return True

    def poll(self) -> dict[str, object]:
        """Drain whatever progress messages are queued (non-blocking) and
        return the latest known state. Safe to call with no job running."""

        with self._lock:
            if self._queue is not None:
                while True:
                    try:
                        message = self._queue.get_nowait()
                    except Empty:
                        break
                    self._apply_message(message)
            self._reap_if_finished_locked()
            result = dict(self._state)
            if self._project_id is not None:
                result["project_id"] = str(self._project_id)
            return result

    def _apply_message(self, message: tuple) -> None:
        kind = message[0]
        if kind == "progress":
            _, phase, completed, total = message
            self._state = {
                "status": "running", "phase": phase, "completed": completed, "total": total,
            }
        elif kind == "done":
            self._state = {"status": "done"}
        elif kind == "failed":
            _, error = message
            self._state = {"status": "failed", "error": error}

    def _reap_if_finished_locked(self) -> None:
        """Call with ``self._lock`` held. Joins and releases resources for
        a process that has already exited, whether it reported done/failed
        or crashed without sending a final message."""

        if self._process is None or self._process.is_alive():
            return
        if self._state.get("status") == "running":
            exitcode = self._process.exitcode
            self._state = {
                "status": "failed",
                "error": f"작업 프로세스가 예기치 않게 종료됐다(exit code {exitcode}).",
            }
        self._process.join()
        self._process = None
        self._queue = None
        self._release_db_lock()

    def _lock_path(self) -> str:
        # sqlite:///relative/path.db or sqlite:////absolute/path.db
        path = self._database_url.split("///", 1)[-1]
        return f"{path}{_LOCK_SUFFIX}"

    def _acquire_db_lock(self) -> bool:
        import fcntl

        handle = open(self._lock_path(), "w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._lock_file_handle = handle
        return True

    def _release_db_lock(self) -> None:
        if self._lock_file_handle is None:
            return
        import fcntl

        fcntl.flock(self._lock_file_handle, fcntl.LOCK_UN)
        self._lock_file_handle.close()
        self._lock_file_handle = None
