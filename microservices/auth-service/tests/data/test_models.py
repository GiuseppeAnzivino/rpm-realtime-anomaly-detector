"""Unit tests for the SQLAlchemy ORM models of the authentication service."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.models import Base, User, UserRole


@pytest.fixture(name="session")
def fixture_session():
    """Provide a session bound to an empty in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def test_user_model_stores_explicit_fields():
    """A User keeps the values passed to the constructor."""
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


def test_user_model_repr_does_not_expose_password_hash():
    """The string representation shows the main fields but never the password hash."""
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
    """The representation works on a new User whose role has not been assigned yet."""
    user = User(
        email="new@example.com",
        password_hash="$2b$12$fakehashvalue",
        full_name="New User",
    )

    assert "role=None" in repr(user)


def test_user_defaults_are_applied_on_persist(session):
    """Technical column defaults are applied when the User is saved to the database."""
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
    """A User without an explicit role cannot be saved."""
    session.add(
        User(
            email="norole@example.com",
            password_hash="$2b$12$fakehashvalue",
            full_name="No Role",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_role_is_stored_as_enum_value(session):
    """The role column stores the enum value ('admin'), not the member name ('ADMIN')."""
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