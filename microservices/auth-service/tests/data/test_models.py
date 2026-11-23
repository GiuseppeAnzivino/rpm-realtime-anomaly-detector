"""
TEST SUITE (UNIT TESTS)
Description: Contains unit tests for validating the SQLAlchemy ORM models of the Auth-Service microservice.
Responsibility: Verifies user entity initialization, explicit field assignment, automatic column defaults, password hash protection in string representations, role constraints, and correct enum value persistence.
Independence: Uses pytest and an isolated in-memory SQLite database to validate ORM behavior without requiring an external database instance or other application services.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.models import Base, User, UserRole


#region Test Fixtures

@pytest.fixture(name="session")
def fixture_session():
    """
        Provide a database session backed by an isolated in-memory SQLite database.

        Creates all ORM tables before yielding the session and disposes of the
        database engine after the test completes.

        Yields:
            Session: An active SQLAlchemy session connected to the test database.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


#endregion


#region User Model Initialization Tests

def test_user_model_stores_explicit_fields():
    """
        Verify that a User instance retains the values explicitly provided
        during construction.

        Asserts:
            All explicitly assigned fields match their original values.
    """
    user = User(
        email="clinician@example.com",
        password_hash="$2b$12$fakehashvalue",
        full_name="Mario Rossi",
        role=UserRole.ADMIN,
        is_active=False,
    )

    assert user.email == "clinician@example.com"
    assert user.password_hash == "$2b$12$fakehashvalue"
    assert user.full_name == "Mario Rossi"
    assert user.role == UserRole.ADMIN
    assert user.is_active is False


#endregion


#region User Representation Tests

def test_user_model_repr_does_not_expose_password_hash():
    """
        Verify that the User string representation includes relevant account
        information without exposing sensitive authentication data.

        Asserts:
            The representation contains the email, role, and account status,
            but does not contain the stored password hash.
    """
    secret_hash = "super_secret_hash_should_not_appear"
    user = User(
        email="admin@example.com",
        password_hash=secret_hash,
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=False,
    )

    representation = repr(user)

    assert "admin@example.com" in representation
    assert "role='admin'" in representation
    assert "is_active=False" in representation
    assert secret_hash not in representation


def test_user_model_repr_handles_missing_role():
    """
        Verify that the User string representation handles an unassigned role.

        This covers newly instantiated User objects before database validation
        or persistence has been performed.

        Asserts:
            The representation displays None when the role has not been assigned.
    """
    user = User(
        email="new@example.com",
        password_hash="$2b$12$fakehashvalue",
        full_name="New User",
    )

    assert "role=None" in repr(user)


#endregion


#region Database Persistence and Default Value Tests

def test_user_defaults_are_applied_on_persist(session):
    """
        Verify that SQLAlchemy column defaults are applied when a User is persisted.

        Args:
            session: The SQLAlchemy session connected to the in-memory test database.

        Asserts:
            The persisted user has a generated UUID, an active account by default,
            and a creation timestamp represented by a datetime object.
    """
    user = User(
        email="clinician@example.com",
        password_hash="$2b$12$fakehashvalue",
        full_name="Mario Rossi",
        role=UserRole.CLINICIAN,
    )
    session.add(user)
    session.commit()

    stored = session.get(User, user.user_id)

    assert stored is not None
    assert isinstance(stored.user_id, uuid.UUID)
    assert stored.is_active is True
    assert isinstance(stored.created_at, datetime)


def test_user_without_role_is_rejected(session):
    """
        Verify that database constraints reject a User without an assigned role.

        Args:
            session: The SQLAlchemy session connected to the in-memory test database.

        Asserts:
            Committing a user without a role raises IntegrityError because
            the role column is defined as non-nullable.
    """
    session.add(
        User(
            email="norole@example.com",
            password_hash="$2b$12$fakehashvalue",
            full_name="No Role",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


#endregion


#region Enum Persistence Tests

def test_role_is_stored_as_enum_value(session):
    """
        Verify that the role column stores the enum value rather than its member name.

        Args:
            session: The SQLAlchemy session connected to the in-memory test database.

        Asserts:
            The raw database value is the lowercase string "admin", rather than
            the enum member name "ADMIN".
    """
    session.add(
        User(
            email="admin@example.com",
            password_hash="$2b$12$fakehashvalue",
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
    )
    session.commit()

    raw_role = session.execute(text("SELECT role FROM users")).scalar_one()

    assert raw_role == "admin"


#endregion