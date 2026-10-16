from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.core.enums import ChannelType
from app.models import Base
from app.repositories.sqlalchemy import SqlAlchemyProjectRepository
from app.schemas.common import AnalysisPeriodSchema, ComparisonPeriodSchema, TargetSchema
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
