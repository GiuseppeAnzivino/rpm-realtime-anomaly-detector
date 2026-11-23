"""
TEST SUITE (UNIT TESTS)
    Description: Contains unit tests for validating the administrative account bootstrap process of the Auth-Service microservice.
    Responsibility: Verifies administrator account creation, password hashing, email normalization, idempotent execution, default full name assignment, and validation of required environment variables and password length.
    Independence: Uses an isolated in-memory SQLite database, pytest fixtures, and environment variable monkeypatching to test the bootstrap process without requiring an external database or application services.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from business.admin_bootstrap import bootstrap_admin
from business.security import verify_password
from business.exceptions import DuplicateEmailError
from data.models import Base, UserRole
from data.repository import UserRepository


#region Test Fixtures

@pytest.fixture(name="repository")
def fixture_repository():
    """
        Provide a UserRepository instance backed by an isolated in-memory SQLite database.

        Creates the ORM tables before yielding the repository and disposes of the
        database engine after the test completes.

        Yields:
            UserRepository: The repository connected to the test database.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield UserRepository(session)
    engine.dispose()


@pytest.fixture(name="admin_env")
def fixture_admin_env(monkeypatch):
    """
        Configure the environment variables required for administrator bootstrap.

        Args:
            monkeypatch: Pytest fixture used to modify environment variables
                temporarily and restore them after the test.
    """
    monkeypatch.setenv("ADMIN_EMAIL", "  Admin@Example.com ")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-very-strong-password")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Root Admin")


#endregion


#region Administrator Bootstrap Tests

def test_creates_admin_with_hashed_password(repository, admin_env):
    """
        Verify that the bootstrap process creates an administrator account
        with normalized email and a securely hashed password.

        Args:
            repository: The repository used to persist the administrator account.
            admin_env: Fixture providing the required administrator environment variables.

        Asserts:
            The administrator has the expected role, active status, normalized
            email, full name, and a password hash that verifies successfully.
    """
    admin = bootstrap_admin(repository)

    assert admin is not None
    assert admin.email == "admin@example.com"
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True
    assert admin.full_name == "Root Admin"
    assert admin.password_hash != "a-very-strong-password"
    assert verify_password("a-very-strong-password", admin.password_hash)


def test_is_idempotent_and_does_not_overwrite(repository, admin_env, monkeypatch):
    """
        Verify that repeated bootstrap execution does not recreate or overwrite
        an existing administrator account.

        Args:
            repository: The repository used to retrieve the administrator account.
            admin_env: Fixture providing the initial administrator environment variables.
            monkeypatch: Fixture used to modify the administrator password
                between bootstrap executions.

        Asserts:
            The second execution returns None, preserves the original account
            identifier, and does not overwrite the previously stored password.
    """
    first = bootstrap_admin(repository)
    monkeypatch.setenv("ADMIN_PASSWORD", "another-strong-password")

    assert bootstrap_admin(repository) is None
    stored = repository.get_by_email("admin@example.com")
    assert stored.user_id == first.user_id
    assert verify_password("a-very-strong-password", stored.password_hash)


def test_default_full_name(repository, admin_env, monkeypatch):
    """
        Verify that the bootstrap process uses the default administrator name
        when ADMIN_FULL_NAME is not configured.

        Args:
            repository: The repository used to persist the administrator account.
            admin_env: Fixture providing the initial administrator environment variables.
            monkeypatch: Fixture used to remove the optional full-name environment variable.

        Asserts:
            The created administrator receives the default name "Administrator".
    """
    monkeypatch.delenv("ADMIN_FULL_NAME")
    assert bootstrap_admin(repository).full_name == "Administrator"


def test_concurrent_creation_is_handled(repository, admin_env, monkeypatch):
    """
        Verify that bootstrap tolerates the administrator being created
        concurrently by another service instance.

        Simulates a race condition in which the initial lookup finds no user,
        but the insertion fails because the email has been registered in the
        meantime.

        Args:
            repository: The repository used by the bootstrap process.
            admin_env: Fixture providing the administrator environment variables.
            monkeypatch: Fixture used to make the repository insertion fail.

        Asserts:
            The bootstrap returns None instead of propagating the exception,
            and no account is stored by this execution.
    """
    def raise_duplicate(user):
        raise DuplicateEmailError("A user with this email already exists")

    monkeypatch.setattr(repository, "add", raise_duplicate)

    assert bootstrap_admin(repository) is None
    assert repository.get_by_email("admin@example.com") is None


#endregion


#region Environment Configuration Validation Tests

@pytest.mark.parametrize("missing", ["ADMIN_EMAIL", "ADMIN_PASSWORD"])
def test_missing_variable_raises(repository, admin_env, monkeypatch, missing):
    """
        Verify that bootstrap rejects missing required environment variables.

        Args:
            repository: The repository passed to the bootstrap process.
            admin_env: Fixture providing the initial administrator environment variables.
            monkeypatch: Fixture used to remove environment variables.
            missing: Name of the required environment variable to remove.

        Asserts:
            A RuntimeError is raised when a required configuration variable
            is unavailable.
    """
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError):
        bootstrap_admin(repository)


def test_short_password_raises(repository, admin_env, monkeypatch):
    """
        Verify that bootstrap rejects administrator passwords that do not
        satisfy the minimum length requirement.

        Args:
            repository: The repository passed to the bootstrap process.
            admin_env: Fixture providing the initial administrator environment variables.
            monkeypatch: Fixture used to replace the configured administrator password.

        Asserts:
            A RuntimeError is raised when the configured password is too short.
    """
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError):
        bootstrap_admin(repository)


#endregion