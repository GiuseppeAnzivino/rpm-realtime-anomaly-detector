"""
TEST SUITE (AUTHENTICATION SERVICE TESTS)
    Description: Validates the authentication service login, refresh and logout workflows, credential verification, account status checks, refresh token rotation and password hash upgrades.
    Responsibility: Ensures successful authentication produces valid access and refresh tokens, invalid credentials and disabled accounts are rejected, refresh tokens are stored hashed, rotated and revoked correctly, and outdated password hashes are upgraded transparently.
    Independence: Isolated service-level tests using an in-memory SQLite database, mocked time, and controlled password hashes to validate authentication behavior without external services.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from business.service import AuthService, _ensure_utc
from business.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from business.security import hash_password, verify_password
from business.tokens import (
    MIN_SECRET_LENGTH,
    TokenSettings,
    decode_access_token,
    hash_refresh_token,
)
from data.models import Base, RefreshToken, User, UserRole
from data.repository import RefreshTokenRepository, UserRepository


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


@pytest.fixture(name="refresh_repository")
def fixture_refresh_repository(session):
    """Provide a refresh token repository backed by the test database.

        Args:
            session: SQLAlchemy session fixture used for database operations.
    """
    return RefreshTokenRepository(session)


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


@pytest.fixture(name="clock")
def fixture_clock():
    """Provide a controllable clock fixed at the reference time.

        Tests can move time forward by changing its return_value.
    """
    return Mock(return_value=NOW)


@pytest.fixture(name="service")
def fixture_service(repository, refresh_repository, clock, user):
    """Provide an authentication service with a deterministic clock.

        Args:
            repository: User repository used by the authentication service.
            refresh_repository: Refresh token repository used by the authentication service.
            clock: Controllable clock injected into the service.
            user: Persisted user fixture required for the service setup.
    """
    return AuthService(repository, refresh_repository, SETTINGS, clock=clock)

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
    assert result.refresh_token


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


#region Login Refresh Token Tests
def test_login_stores_only_the_hash_of_the_refresh_token(
    service, refresh_repository, user
):
    """Verify that login persists the refresh token hash for the user and never the plaintext token."""
    result = service.login("mario@example.com", PASSWORD)

    stored = refresh_repository.get_by_hash(hash_refresh_token(result.refresh_token))
    assert stored is not None
    assert stored.user_id == user.user_id
    assert stored.token_hash != result.refresh_token
    assert stored.revoked_at is None


def test_login_refresh_token_expires_after_the_configured_days(
    service, refresh_repository
):
    """Verify that the stored refresh token expires after the configured number of days."""
    result = service.login("mario@example.com", PASSWORD)

    stored = refresh_repository.get_by_hash(hash_refresh_token(result.refresh_token))
    assert _ensure_utc(stored.expires_at) == NOW + timedelta(days=SETTINGS.refresh_token_days)


def test_failed_login_does_not_store_a_refresh_token(service, session):
    """Verify that a rejected login does not create any refresh token."""
    with pytest.raises(InvalidCredentialsError):
        service.login("mario@example.com", "wrong-password")

    assert session.query(RefreshToken).count() == 0

#endregion


#region Refresh Tests
def test_refresh_returns_new_tokens_and_revokes_the_old_one(
    service, refresh_repository, user
):
    """Verify that refreshing issues a new token pair and revokes the presented refresh token."""
    first = service.login("mario@example.com", PASSWORD)

    second = service.refresh(first.refresh_token)

    old = refresh_repository.get_by_hash(hash_refresh_token(first.refresh_token))
    new = refresh_repository.get_by_hash(hash_refresh_token(second.refresh_token))
    claims = decode_access_token(second.access_token, SETTINGS)
    assert second.refresh_token != first.refresh_token
    assert second.expires_in == 15 * 60
    assert claims["sub"] == str(user.user_id)
    assert old.revoked_at is not None
    assert new.revoked_at is None


def test_refresh_token_can_be_used_only_once(service):
    """Verify that a refresh token that has already been rotated is rejected."""
    first = service.login("mario@example.com", PASSWORD)
    service.refresh(first.refresh_token)

    with pytest.raises(InvalidTokenError):
        service.refresh(first.refresh_token)


def test_refresh_rejects_an_unknown_token(service):
    """Verify that a refresh token that was never issued is rejected."""
    with pytest.raises(InvalidTokenError):
        service.refresh("unknown-token")


def test_refresh_rejects_an_expired_token(service, clock):
    """Verify that a refresh token is rejected after its expiry time."""
    result = service.login("mario@example.com", PASSWORD)
    clock.return_value = NOW + timedelta(days=SETTINGS.refresh_token_days + 1)

    with pytest.raises(InvalidTokenError):
        service.refresh(result.refresh_token)


def test_refresh_rejects_a_token_at_the_exact_expiry_time(service, clock):
    """Verify that a refresh token is already invalid at the exact instant of its expiry."""
    result = service.login("mario@example.com", PASSWORD)
    clock.return_value = NOW + timedelta(days=SETTINGS.refresh_token_days)

    with pytest.raises(InvalidTokenError):
        service.refresh(result.refresh_token)


def test_refresh_rejects_a_token_revoked_by_logout(service):
    """Verify that a refresh token revoked by logout cannot be used to refresh."""
    result = service.login("mario@example.com", PASSWORD)
    service.logout(result.refresh_token)

    with pytest.raises(InvalidTokenError):
        service.refresh(result.refresh_token)


def test_refresh_rejects_a_token_of_a_disabled_user(service, repository, user):
    """Verify that the refresh token of a disabled account is rejected."""
    result = service.login("mario@example.com", PASSWORD)
    repository.set_active(user.user_id, False)

    with pytest.raises(InvalidTokenError):
        service.refresh(result.refresh_token)


def test_refresh_rejects_a_token_of_a_deleted_user(service, repository, user):
    """Verify that the refresh token of a user who no longer exists is rejected."""
    result = service.login("mario@example.com", PASSWORD)
    repository.remove(user.user_id)

    with pytest.raises(InvalidTokenError):
        service.refresh(result.refresh_token)


def test_refresh_rejects_a_token_revoked_by_a_concurrent_request(
    repository, clock, user
):
    """Verify that a refresh fails and issues nothing when another request revokes the token first.

        The refresh token repository is mocked so that the atomic revocation reports
        that the token was already revoked after the initial checks passed.
    """
    refresh_tokens = Mock(spec=RefreshTokenRepository)
    refresh_tokens.get_by_hash.return_value = RefreshToken(
        user_id=user.user_id,
        token_hash="a" * 64,
        expires_at=NOW + timedelta(days=1),
    )
    refresh_tokens.revoke.return_value = False
    service = AuthService(repository, refresh_tokens, SETTINGS, clock=clock)

    with pytest.raises(InvalidTokenError):
        service.refresh("some-token")

    refresh_tokens.add.assert_not_called()


def test_invalid_refresh_token_is_an_authentication_error(service):
    """Verify that invalid refresh tokens are also classified as authentication errors."""
    with pytest.raises(AuthenticationError):
        service.refresh("unknown-token")

#endregion


#region Logout Tests
def test_logout_revokes_the_refresh_token(service, refresh_repository):
    """Verify that logout marks the stored refresh token as revoked."""
    result = service.login("mario@example.com", PASSWORD)

    service.logout(result.refresh_token)

    stored = refresh_repository.get_by_hash(hash_refresh_token(result.refresh_token))
    assert stored.revoked_at is not None


def test_logout_twice_does_not_raise(service):
    """Verify that logging out twice with the same token is accepted."""
    result = service.login("mario@example.com", PASSWORD)

    service.logout(result.refresh_token)
    service.logout(result.refresh_token)


def test_logout_with_an_unknown_token_does_not_raise(service):
    """Verify that logging out with a token that does not exist is silently accepted."""
    service.logout("unknown-token")

#endregion


#region UTC Normalization Tests
def test_ensure_utc_marks_a_naive_datetime_as_utc():
    """Verify that a naive datetime is interpreted as UTC."""
    naive = datetime(2026, 1, 1, 12, 0)

    assert _ensure_utc(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_ensure_utc_keeps_an_aware_datetime_unchanged():
    """Verify that a timezone-aware datetime is returned as it is."""
    assert _ensure_utc(NOW) is NOW

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