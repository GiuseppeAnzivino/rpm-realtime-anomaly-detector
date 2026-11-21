"""Unit tests for data.init_db, using SQLite instead of PostgreSQL."""

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from data.init_db import get_database_url, init_db, main
from data.models import Base, User, UserRole


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


def test_init_db_creates_every_declared_table(engine):
    tables = init_db(engine)

    assert tables
    assert tables == sorted(Base.metadata.tables)
    assert inspect(engine).get_table_names() == tables


def test_init_db_is_idempotent(engine):
    first = init_db(engine)
    second = init_db(engine)

    assert first == second


def test_init_db_keeps_existing_rows(engine):
    init_db(engine)
    with Session(engine) as session:
        session.add(
            User(
                email="admin@example.com",
                password_hash="not-a-real-hash",
                full_name="Admin",
                role=UserRole.ADMIN,
            )
        )
        session.commit()

    init_db(engine)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_get_database_url_returns_the_configured_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    assert get_database_url() == "sqlite:///:memory:"


def test_get_database_url_fails_when_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()


def test_main_initialises_the_configured_database(monkeypatch, tmp_path):
    database_file = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file}")

    main()

    engine = create_engine(f"sqlite:///{database_file}")
    assert inspect(engine).get_table_names() == sorted(Base.metadata.tables)
    engine.dispose()