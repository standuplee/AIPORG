from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.core.enums import ChannelType
from app.models import Base
from app.repositories.sqlalchemy import SqlAlchemyDocumentRepository, SqlAlchemyProjectRepository
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
from app.schemas.document import RawDocument
from app.schemas.project import ProjectCreate


def test_alembic_upgrade_and_downgrade_on_empty_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "aiporg2.db"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database}")
    assert set(Base.metadata.tables).issubset(set(inspect(engine).get_table_names()))

    command.downgrade(config, "base")
    assert not set(Base.metadata.tables).intersection(inspect(engine).get_table_names())


def test_repository_writes_through_migrated_schema(tmp_path: Path) -> None:
    database = tmp_path / "repository.db"
    url = f"sqlite:///{database}"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with Session(engine) as session:
        created = SqlAlchemyProjectRepository(session).create(ProjectCreate(
            name="migration smoke",
            target=TargetSchema(
                organization="충청남도", primary_person="도지사", region="충남"
            ),
            analysis_period=AnalysisPeriodSchema(
                start=date(2026, 8, 1), end=date(2026, 8, 31)
            ),
            comparison_period=ComparisonPeriodSchema(
                start=date(2026, 7, 1), end=date(2026, 7, 31)
            ),
            channels=[ChannelType.NEWS],
        ))
        session.commit()
        assert SqlAlchemyProjectRepository(session).get(created.project_id) == created


def _project_create(name: str) -> ProjectCreate:
    return ProjectCreate(
        name=name,
        target=TargetSchema(organization="충청남도", primary_person="도지사", region="충남"),
        analysis_period=AnalysisPeriodSchema(start=date(2026, 8, 1), end=date(2026, 8, 31)),
        comparison_period=ComparisonPeriodSchema(start=date(2026, 7, 1), end=date(2026, 7, 31)),
        channels=[ChannelType.NEWS],
    )


def test_migration_scopes_document_id_uniqueness_to_project(tmp_path: Path) -> None:
    # Regression test for the migration 20261019_000002 fix: documents.id is
    # a deterministic hash of the URL alone (no project_id folded in), so
    # two different projects finding the same real-world URL must not
    # collide on a UNIQUE/PRIMARY KEY violation (confirmed live, 2026-10-19).
    database = tmp_path / "document_id_scope.db"
    url = f"sqlite:///{database}"
    config = Config("alembic_v2.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    assert inspect(engine).get_pk_constraint("documents")["constrained_columns"] == [
        "project_id", "id",
    ]

    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    shared_document_id = uuid4()
    with Session(engine) as session:
        project_repo = SqlAlchemyProjectRepository(session)
        project_a = project_repo.create(_project_create("project A"))
        project_b = project_repo.create(_project_create("project B"))
        session.commit()

        document_repo = SqlAlchemyDocumentRepository(session)

        def _raw() -> RawDocument:
            return RawDocument(
                document_id=shared_document_id, source="연합뉴스", channel=ChannelType.NEWS,
                platform="naver", title="두 프로젝트에서 같은 기사 발견",
                url="https://example.com/shared-across-projects",
                published_at=now, query="충남", body="본문", metadata={}, collected_at=now,
            )

        document_repo.upsert_raw(project_a.project_id, _raw())
        document_repo.upsert_raw(project_b.project_id, _raw())
        session.commit()

        assert document_repo.get_by_canonical_url(
            project_a.project_id, "https://example.com/shared-across-projects"
        ) is not None
        assert document_repo.get_by_canonical_url(
            project_b.project_id, "https://example.com/shared-across-projects"
        ) is not None
