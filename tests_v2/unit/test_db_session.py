from sqlalchemy import ForeignKey, String, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
import pytest

from app.db.session import session_scope


class _Base(DeclarativeBase):
    pass


class _Value(_Base):
    __tablename__ = "values"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String)


class _Child(_Base):
    __tablename__ = "children"
    id: Mapped[int] = mapped_column(primary_key=True)
    value_id: Mapped[int] = mapped_column(ForeignKey("values.id"))


def test_session_scope_commits_and_rolls_back() -> None:
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with session_scope(factory) as session:
        session.add(_Value(id=1, value="saved"))

    with pytest.raises(RuntimeError):
        with session_scope(factory) as session:
            session.add(_Value(id=2, value="rolled back"))
            raise RuntimeError("stop")

    with factory() as session:
        assert session.scalars(select(_Value.value).order_by(_Value.id)).all() == ["saved"]


def test_sqlite_session_factory_enforces_foreign_keys() -> None:
    from app.db.session import create_session_factory

    factory = create_session_factory("sqlite://")
    engine = factory.kw["bind"]
    _Base.metadata.create_all(engine)

    with pytest.raises(IntegrityError):
        with session_scope(factory) as session:
            session.add(_Child(id=1, value_id=999))
