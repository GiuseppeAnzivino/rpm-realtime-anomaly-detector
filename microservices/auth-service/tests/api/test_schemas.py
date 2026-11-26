"""
TEST SUITE (SCHEMA VALIDATION TESTS)
    Description: Verifies the validation rules and default values of authentication-related Pydantic schemas.
    Responsibility: Ensures login requests reject missing or empty credentials and token responses correctly apply default values.
    Independence: Isolated unit tests that validate schema behavior without requiring application startup, database access, or external services.
"""

import pytest
from pydantic import ValidationError

from api.schemas import LoginRequest, TokenResponse

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


#region Token Response Validation Tests
def test_token_response_defaults_to_bearer():
    """Verify that the token response defaults to the bearer token type."""
    response = TokenResponse(access_token="token", expires_in=900)
    assert response.token_type == "bearer"
#endregion