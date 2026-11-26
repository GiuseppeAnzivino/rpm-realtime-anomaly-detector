"""
TEST SUITE (SCHEMA VALIDATION TESTS)
    Description: Verifies the validation rules and default values of authentication-related Pydantic schemas.
    Responsibility: Ensures login, refresh and logout requests reject missing or empty values and token responses require the refresh token and apply default values.
    Independence: Isolated unit tests that validate schema behavior without requiring application startup, database access, or external services.
"""

import pytest
from pydantic import ValidationError

from api.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse

#region Login Request Validation Tests
def test_login_request_requires_email_and_password():
    """Verify that a login request cannot be created without a password."""
    with pytest.raises(ValidationError):
        LoginRequest(email="mario@example.com")


def test_login_request_rejects_an_empty_password():
    """Verify that an empty password is rejected during schema validation."""
    with pytest.raises(ValidationError):
        LoginRequest(email="mario@example.com", password="")
#endregion


#region Refresh Request Validation Tests
def test_refresh_request_accepts_a_token():
    """Verify that a refresh request keeps the supplied refresh token."""
    assert RefreshRequest(refresh_token="abc").refresh_token == "abc"


def test_refresh_request_requires_the_token():
    """Verify that a refresh request cannot be created without a refresh token."""
    with pytest.raises(ValidationError):
        RefreshRequest()


def test_refresh_request_rejects_an_empty_token():
    """Verify that an empty refresh token is rejected during schema validation."""
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="")
#endregion


#region Logout Request Validation Tests
def test_logout_request_accepts_a_token():
    """Verify that a logout request keeps the supplied refresh token."""
    assert LogoutRequest(refresh_token="abc").refresh_token == "abc"


def test_logout_request_requires_the_token():
    """Verify that a logout request cannot be created without a refresh token."""
    with pytest.raises(ValidationError):
        LogoutRequest()


def test_logout_request_rejects_an_empty_token():
    """Verify that an empty refresh token is rejected during schema validation."""
    with pytest.raises(ValidationError):
        LogoutRequest(refresh_token="")
#endregion


#region Token Response Validation Tests
def test_token_response_defaults_to_bearer():
    """Verify that the token response defaults to the bearer token type."""
    response = TokenResponse(access_token="token", refresh_token="refresh", expires_in=900)
    assert response.token_type == "bearer"


def test_token_response_keeps_the_refresh_token():
    """Verify that the token response carries the refresh token."""
    response = TokenResponse(access_token="token", refresh_token="refresh", expires_in=900)
    assert response.refresh_token == "refresh"


def test_token_response_requires_the_refresh_token():
    """Verify that a token response cannot be created without a refresh token."""
    with pytest.raises(ValidationError):
        TokenResponse(access_token="token", expires_in=900)
#endregion