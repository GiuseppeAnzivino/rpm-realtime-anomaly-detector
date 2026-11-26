"""
TEST SUITE (AUTHENTICATION SERVICE TESTS)
    Description: Validates the authentication service login workflow, credential verification, account status checks, and password hash upgrades.
    Responsibility: Ensures successful authentication produces valid access tokens, invalid credentials and disabled accounts are rejected, and outdated password hashes are upgraded transparently.
    Independence: Isolated service-level tests using an in-memory SQLite database, mocked time, and controlled password hashes to validate authentication behavior without external services.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from business.service import AuthService
from business.exceptions import AuthenticationError, InvalidCredentialsError
from business.security import hash_password, verify_password
from business.tokens import MIN_SECRET_LENGTH, TokenSettings, decode_access_token
from data.models import Base, User, UserRole
from data.repository import UserRepository


#region Test Configuration
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SETTINGS = TokenSettings(jwt_secret="a" * MIN_SECRET_LENGTH)
PASSWORD = "correct-password-1"

# Generate a valid Argon2 hash with weaker parameters to simulate an outdated hash.
# The reduced parameters ensure that needs_rehash() detects it during authentication.
OUTDATED_HASH = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
#endregion


#region Fixtures
@pytest.fixture(name="session")
def fixture_session():
    """Provide an isolated in-memory database session for each test.

        The database schema is created before the test and the engine is disposed
        after the session is closed to prevent resources from leaking between tests.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture(name="repository")
def fixture_repository(session):
    """Provide a user repository backed by the test database.

        Args:
            session: SQLAlchemy session fixture used for database operations.
    """
    return UserRepository(session)


@pytest.fixture(name="user")
def fixture_user(repository):
    """Create a clinician account with a valid password hash for authentication tests.

        Args:
            repository: User repository fixture used to persist the test account.
    """
    return repository.add(
        User(
            email="mario@example.com",
            password_hash=hash_password(PASSWORD),
            full_name="Mario",
            role=UserRole.CLINICIAN,
        )
    )


@pytest.fixture(name="service")
def fixture_service(repository, user):
    """Provide an authentication service with a deterministic clock.

        Args:
            repository: User repository used by the authentication service.
            user: Persisted user fixture required for the service setup.
    """
    return AuthService(repository, SETTINGS, clock=Mock(return_value=NOW))

#endregion


#region Login Tests
def test_login_success_returns_a_valid_access_token(service, user):
    """Verify that valid credentials produce an access token with the expected claims and lifetime."""
    result = service.login("mario@example.com", PASSWORD)

    claims = decode_access_token(result.access_token, SETTINGS)
    assert claims["sub"] == str(user.user_id)
    assert claims["role"] == "clinician"
    assert claims["iat"] == int(NOW.timestamp())
    assert result.expires_in == 15 * 60


def test_login_email_is_normalised(service):
    """Verify that login accepts an email address with surrounding whitespace and mixed case."""
    assert service.login("  Mario@Example.com ", PASSWORD).access_token


def test_login_wrong_password_is_rejected(service):
    """Verify that incorrect passwords are rejected during authentication."""
    with pytest.raises(InvalidCredentialsError):
        service.login("mario@example.com", "wrong-password")


def test_login_unknown_user_is_rejected(service):
    """Verify that login attempts for nonexistent accounts are rejected."""
    with pytest.raises(InvalidCredentialsError):
        service.login("nobody@example.com", PASSWORD)


def test_login_disabled_account_is_rejected(service, repository, user):
    """Verify that inactive accounts cannot authenticate successfully.

        Args:
            service: Authentication service fixture.
            repository: User repository used to update the account status.
            user: Persisted user whose active status is disabled for the test.
    """
    repository.set_active(user.user_id, False)
    with pytest.raises(InvalidCredentialsError):
        service.login("mario@example.com", PASSWORD)


def test_invalid_credentials_is_an_authentication_error(service):
    """Verify that invalid credentials are also classified as authentication errors."""
    with pytest.raises(AuthenticationError):
        service.login("nobody@example.com", PASSWORD)

#endregion


#region Password Hash Upgrade Tests
def test_login_upgrades_an_outdated_hash(service, repository, user):
    """Verify that login upgrades an outdated password hash after successful authentication.

        The original hash uses weaker Argon2 parameters and should be replaced with
        a hash generated using the application's current password hashing configuration.
    """
    repository.set_password_hash(user.user_id, OUTDATED_HASH)

    service.login("mario@example.com", PASSWORD)

    updated = repository.get_by_id(user.user_id)
    assert updated.password_hash != OUTDATED_HASH
    assert verify_password(PASSWORD, updated.password_hash)


def test_login_keeps_an_up_to_date_hash(service, repository, user):
    """Verify that login does not rehash a password that already meets current requirements."""
    original = user.password_hash

    service.login("mario@example.com", PASSWORD)

    assert repository.get_by_id(user.user_id).password_hash == original

#endregion