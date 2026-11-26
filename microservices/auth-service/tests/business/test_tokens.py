"""
TEST SUITE (JWT TOKEN VALIDATION TESTS)
    Description: Verifies JWT configuration, access token generation, expiration, signature validation, and token claim handling.
    Responsibility: Ensures token settings are correctly loaded, access tokens are generated with the expected claims and lifetime, and invalid or expired tokens are rejected.
    Independence: Isolated unit tests that validate token-related business logic without requiring application startup, database access, or external services.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from business.exceptions import AuthenticationError, InvalidTokenError
from business.tokens import (
    MIN_SECRET_LENGTH,
    TokenSettings,
    create_access_token,
    decode_access_token,
    get_token_settings,
)



#region Test Configuration
SECRET = "a" * MIN_SECRET_LENGTH
SETTINGS = TokenSettings(jwt_secret=SECRET)
#endregion


#region Token Settings Tests
def test_missing_secret_raises(monkeypatch):
    """Verify that token settings cannot be loaded without a configured JWT secret.

        Args:
            monkeypatch: Pytest fixture used to control environment variables.
    """
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="not set"):
        get_token_settings()


def test_short_secret_raises(monkeypatch):
    """Verify that JWT secrets shorter than the minimum required length are rejected.

        Args:
            monkeypatch: Pytest fixture used to control environment variables.
    """
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(RuntimeError, match="at least"):
        get_token_settings()


def test_default_settings(monkeypatch):
    """Verify that default JWT configuration values are applied when optional variables are absent.

        Args:
            monkeypatch: Pytest fixture used to control environment variables.
    """
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.delenv("ACCESS_TOKEN_MINUTES", raising=False)
    settings = get_token_settings()
    assert settings.jwt_secret == SECRET
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_minutes == 15


def test_access_token_minutes_override(monkeypatch):
    """Verify that the access token lifetime can be overridden through the environment.

        Args:
            monkeypatch: Pytest fixture used to control environment variables.
    """
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "5")
    assert get_token_settings().access_token_minutes == 5

#endregion


#region Access Token Tests
def test_access_token_roundtrip():
    """Verify that an access token can be generated and decoded with its expected claims."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "admin", SETTINGS)
    claims = decode_access_token(token, SETTINGS)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "admin"
    assert claims["type"] == "access"


def test_access_token_lifetime_follows_the_settings():
    """Verify that the token expiration interval matches the configured lifetime."""
    issued = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token = create_access_token(uuid.uuid4(), "admin", SETTINGS, now=issued)
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_exp": False})
    assert claims["exp"] - claims["iat"] == 15 * 60


def test_expired_token_is_rejected():
    """Verify that tokens issued in the past beyond their expiration are rejected."""
    issued = datetime.now(timezone.utc) - timedelta(hours=1)
    token = create_access_token(uuid.uuid4(), "admin", SETTINGS, now=issued)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SETTINGS)


def test_token_signed_with_another_secret_is_rejected():
    """Verify that tokens signed with a different secret cannot be validated."""
    other = TokenSettings(jwt_secret="b" * MIN_SECRET_LENGTH)
    token = create_access_token(uuid.uuid4(), "admin", other)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SETTINGS)


def test_malformed_token_is_rejected():
    """Verify that malformed JWT strings are rejected during decoding."""
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt", SETTINGS)


def test_token_of_the_wrong_type_is_rejected():
    """Verify that tokens with an unexpected type claim are rejected."""
    payload = {
        "sub": "1",
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError, match="type"):
        decode_access_token(token, SETTINGS)


def test_invalid_token_is_an_authentication_error():
    """Verify that invalid JWTs are surfaced as authentication errors."""
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-jwt", SETTINGS)

#endregion