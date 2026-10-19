"""Unit tests for the job manager's process/IPC/lock machinery.

Fake workers are module-level functions (not closures) because
multiprocessing's "spawn" start method pickles the target by import
reference -- a locally-defined function can't be spawned.
"""

import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.analytics.jobs import AnalyticsJobManager
from app.schemas.common import VersionedRunSchema


def _run(now=None):
    return VersionedRunSchema(
        run_id=uuid4(), input_version="v1", output_version="v1",
        created_at=now or datetime.now(timezone.utc),
    )


def _wait_until(predicate, *, timeout=5.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _worker_reports_progress_then_done(
    database_url, project_id_hex, run_id_hex, input_version, output_version,
    created_at_iso, queue, parent_pid,
):
    queue.put(("progress", "keywords", 0, 2))
    queue.put(("progress", "keywords", 1, 2))
    queue.put(("progress", "keywords", 2, 2))
    queue.put(("done", None))


def _worker_fails(
    database_url, project_id_hex, run_id_hex, input_version, output_version,
    created_at_iso, queue, parent_pid,
):
    queue.put(("failed", "fixture failure"))


def _worker_crashes_without_reporting(
    database_url, project_id_hex, run_id_hex, input_version, output_version,
    created_at_iso, queue, parent_pid,
):
    os._exit(1)  # simulate an abnormal process death: no final message sent


def _worker_blocks_until_killed(
    database_url, project_id_hex, run_id_hex, input_version, output_version,
    created_at_iso, queue, parent_pid,
):
    queue.put(("progress", "loading", 0, 0))
    time.sleep(30)


def test_submit_runs_worker_and_reports_progress_then_done(tmp_path):
    manager = AnalyticsJobManager(
        f"sqlite:///{tmp_path / 'job1.db'}", _worker=_worker_reports_progress_then_done,
    )
    assert manager.submit(uuid4(), _run()) is True
    assert manager.is_running() is True

    assert _wait_until(lambda: manager.poll().get("status") == "done")
    # the "done" message can arrive a moment before the OS fully reaps the
    # process -- is_running() only needs to settle to False shortly after.
    assert _wait_until(lambda: manager.is_running() is False)


def test_submit_refuses_a_second_job_while_one_is_running(tmp_path):
    manager = AnalyticsJobManager(
        f"sqlite:///{tmp_path / 'job2.db'}", _worker=_worker_blocks_until_killed,
    )
    assert manager.submit(uuid4(), _run()) is True
    assert _wait_until(lambda: manager.poll().get("status") == "running")

    assert manager.submit(uuid4(), _run()) is False

    manager._process.terminate()
    assert _wait_until(lambda: not manager.is_running())


def test_worker_failure_is_reported_and_allows_retry(tmp_path):
    manager = AnalyticsJobManager(f"sqlite:///{tmp_path / 'job3.db'}", _worker=_worker_fails)
    assert manager.submit(uuid4(), _run()) is True

    assert _wait_until(lambda: manager.poll().get("status") == "failed")
    state = manager.poll()
    assert state["error"] == "fixture failure"
    # the "failed" message can arrive a moment before the OS fully reaps
    # the process -- is_running() only needs to settle to False shortly
    # after, not in the same instant as the message.
    assert _wait_until(lambda: manager.is_running() is False)

    # retry: submit() must allow starting again now that the old process
    # is no longer alive
    manager._worker = _worker_reports_progress_then_done
    assert manager.submit(uuid4(), _run()) is True
    assert _wait_until(lambda: manager.poll().get("status") == "done")


def test_abnormal_process_exit_without_a_final_message_is_reported_as_failed(tmp_path):
    manager = AnalyticsJobManager(
        f"sqlite:///{tmp_path / 'job4.db'}", _worker=_worker_crashes_without_reporting,
    )
    assert manager.submit(uuid4(), _run()) is True

    assert _wait_until(lambda: manager.poll().get("status") == "failed")
    assert "exit code" in manager.poll()["error"]
    assert manager.is_running() is False


def test_db_file_lock_blocks_a_second_manager_on_the_same_database(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'shared.db'}"
    first = AnalyticsJobManager(db_url, _worker=_worker_blocks_until_killed)
    second = AnalyticsJobManager(db_url, _worker=_worker_reports_progress_then_done)

    assert first.submit(uuid4(), _run()) is True
    assert _wait_until(lambda: first.poll().get("status") == "running")

    assert second.submit(uuid4(), _run()) is False
    assert "다른 서버 프로세스" in second.poll()["error"]

    first._process.terminate()
    assert _wait_until(lambda: not first.is_running())

    # the lock is released once the first manager reaps its finished job
    assert second.submit(uuid4(), _run()) is True
    assert _wait_until(lambda: second.poll().get("status") == "done")


def test_poll_state_identifies_which_project_the_job_is_for(tmp_path):
    manager = AnalyticsJobManager(
        f"sqlite:///{tmp_path / 'job6.db'}", _worker=_worker_reports_progress_then_done,
    )
    project_id = uuid4()
    assert manager.submit(project_id, _run()) is True
    assert manager.poll()["project_id"] == str(project_id)
    assert _wait_until(lambda: manager.poll().get("status") == "done")
    assert manager.poll()["project_id"] == str(project_id)


def test_poll_and_is_running_are_safe_with_no_job_submitted(tmp_path):
    manager = AnalyticsJobManager(f"sqlite:///{tmp_path / 'job5.db'}")
    assert manager.is_running() is False
    assert manager.poll() == {"status": "idle"}
