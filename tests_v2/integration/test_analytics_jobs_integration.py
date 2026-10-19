"""Real end-to-end check of the background worker: a spawned OS process,
its own DB session, committing through the actual IssuesToAnalyticsWorkflow
against a temp migrated SQLite file -- not a mock.
"""

import time
from datetime import date, datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest

from app.analytics.jobs import AnalyticsJobManager
from app.core.enums import ChannelType, WorkflowState
from app.db.session import create_session_factory, session_scope
from app.repositories.sqlalchemy import SqlAlchemyAnalyticsRepository, SqlAlchemyProjectRepository
from app.schemas.common import (
    AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema, VersionedRunSchema,
)
from app.schemas.project import ProjectCreate
from tests_v2.integration.test_issues_to_analytics_workflow import seed


@pytest.fixture
def factory(tmp_path):
    url = f"sqlite:///{tmp_path / 'analytics_jobs.db'}"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    factory = create_session_factory(url)
    yield url, factory
    factory.kw["bind"].dispose()


def _wait_until(predicate, *, timeout=15.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_worker_process_commits_a_real_snapshot_to_the_migrated_database(factory):
    url, session_factory = factory
    with session_scope(session_factory) as session:
        project_id, ids = seed(session)
    run = VersionedRunSchema(
        run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    manager = AnalyticsJobManager(url)
    assert manager.submit(project_id, run) is True
    assert _wait_until(lambda: manager.poll().get("status") == "done")

    with session_scope(session_factory) as session:
        saved = SqlAlchemyAnalyticsRepository(session).get_latest(project_id)
        assert saved is not None
        assert saved.metrics["unique_documents"] == 2
        assert SqlAlchemyProjectRepository(session).get_workflow(project_id).workflow_state is (
            WorkflowState.ANALYTICS_COMPLETED
        )


def test_worker_process_reports_failure_and_rolls_back_without_writing(factory):
    url, session_factory = factory
    with session_scope(session_factory) as session:
        project = SqlAlchemyProjectRepository(session).create(ProjectCreate(
            name="not ready for analytics",
            target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
            analysis_period=AnalysisPeriodSchema(start=date(2026, 9, 1), end=date(2026, 9, 30)),
            comparison_period=ComparisonPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
            channels=[ChannelType.NEWS],
        ))
        project_id = project.project_id
        # intentionally left at CREATED -- not ISSUES_COMPLETED
    run = VersionedRunSchema(
        run_id=uuid4(), input_version="issues:v1", output_version="analytics:v1",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    manager = AnalyticsJobManager(url)
    assert manager.submit(project_id, run) is True
    assert _wait_until(lambda: manager.poll().get("status") == "failed")
    assert "issues_completed" in manager.poll()["error"]

    with session_scope(session_factory) as session:
        assert SqlAlchemyAnalyticsRepository(session).get_latest(project_id) is None
        assert SqlAlchemyProjectRepository(session).get_workflow(project_id).workflow_state is (
            WorkflowState.CREATED
        )
