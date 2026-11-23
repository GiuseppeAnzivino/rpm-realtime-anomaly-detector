"""
TEST SUITE (UNIT TESTS)
Description: Contains unit tests for validating the database initialization utilities of the Auth-Service microservice, using SQLite as an isolated alternative to PostgreSQL.
Responsibility: Verifies database table creation, initialization idempotency, preservation of existing records, database URL retrieval and validation, and successful execution of the application entry point.
Independence: Uses pytest, SQLAlchemy, and temporary or in-memory SQLite databases to validate initialization behavior without requiring an external database server.
"""

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from data.init_db import get_database_url, init_db, main
from data.models import Base, User, UserRole


#region Test Fixtures

@pytest.fixture(name="engine")
def fixture_engine():
    """
        Provide a SQLAlchemy engine connected to an isolated in-memory SQLite database.

        The engine is disposed of after the test to release database resources.

        Yields:
            Engine: The SQLAlchemy engine used by the current test.
    """
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


#endregion


#region Database Table Creation Tests

def test_init_db_creates_every_declared_table(engine):
    """
        Verify that database initialization creates all tables declared
        in the SQLAlchemy metadata.

        Args:
            engine: The SQLAlchemy engine connected to the test database.

        Asserts:
            The returned table list is not empty, contains every declared
            table in sorted order, and matches the actual database schema.
    """
    tables = init_db(engine)

    assert tables
    assert tables == sorted(Base.metadata.tables)
    assert inspect(engine).get_table_names() == tables


def test_init_db_is_idempotent(engine):
    """
        Verify that repeated database initialization produces the same schema.

        Args:
            engine: The SQLAlchemy engine connected to the test database.

        Asserts:
            Consecutive initialization calls return identical table lists
            without causing errors or modifying the existing schema.
    """
    first = init_db(engine)
    second = init_db(engine)

    assert first == second


#endregion


#region Existing Data Preservation Tests

def test_init_db_keeps_existing_rows(engine):
    """
        Verify that database initialization preserves records already stored
        in existing tables.

        Args:
            engine: The SQLAlchemy engine connected to the test database.

        Asserts:
            A previously persisted user remains in the database after
            initialization is executed again.
    """
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


#endregion


#region Database Configuration Tests

def test_get_database_url_returns_the_configured_value(monkeypatch):
    """
        Verify that the database URL is correctly retrieved from the environment.

        Args:
            monkeypatch: The pytest fixture used to modify environment variables.

        Asserts:
            The returned URL matches the value assigned to DATABASE_URL.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    assert get_database_url() == "sqlite:///:memory:"


def test_get_database_url_fails_when_missing(monkeypatch):
    """
        Verify that database configuration validation rejects a missing URL.

        Args:
            monkeypatch: The pytest fixture used to modify environment variables.

        Asserts:
            RuntimeError is raised when DATABASE_URL is not defined.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()


#endregion


#region Application Entry Point Tests

def test_main_initialises_the_configured_database(monkeypatch, tmp_path):
    """
        Verify that the application entry point initializes the database
        specified through the DATABASE_URL environment variable.

        Args:
            monkeypatch: The pytest fixture used to configure environment variables.
            tmp_path: A temporary directory provided by pytest for database storage.

        Asserts:
            The database file is created and contains every table declared
            in the SQLAlchemy metadata after main() completes.
    """
    database_file = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file}")

    main()

    engine = create_engine(f"sqlite:///{database_file}")
    assert inspect(engine).get_table_names() == sorted(Base.metadata.tables)
    engine.dispose()


#endregion