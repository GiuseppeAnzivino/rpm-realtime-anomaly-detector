"""
TEST SUITE (AUTHENTICATION API INTEGRATION TESTS)
    Description: Validates the authentication API endpoints through HTTP requests using the FastAPI test client.
    Responsibility: Ensures login requests produce valid access tokens, invalid credentials return the expected HTTP responses, credential validation prevents malformed requests, and logout behaves as expected.
    Independence: Integration tests exercise the real API routes, authentication service, repository, and database using an isolated in-memory SQLite database without external infrastructure.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import router
from business.security import hash_password
from business.tokens import MIN_SECRET_LENGTH, TokenSettings, decode_access_token
from data.models import Base, User, UserRole
from data.repository import UserRepository



#region Test Configuration
PASSWORD = "correct-password-1"
SETTINGS = TokenSettings(jwt_secret="a" * MIN_SECRET_LENGTH)
#endregion


#region Fixtures
@pytest.fixture(name="client")
def fixture_client():
    """Provide a test client backed by the real authentication stack and an in-memory database.

        The database is initialized with one active account and one disabled account.
        The application is configured with a dedicated session factory and token settings
        to keep the test environment isolated from production configuration.
    """
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        repository = UserRepository(session)
        repository.add(
            User(
                email="mario@example.com",
                password_hash=hash_password(PASSWORD),
                full_name="Mario",
                role=UserRole.CLINICIAN,
            )
        )
        disabled = repository.add(
            User(
                email="disabled@example.com",
                password_hash=hash_password(PASSWORD),
                full_name="Disabled",
                role=UserRole.CLINICIAN,
            )
        )
        repository.set_active(disabled.user_id, False)

    # Assemble the application with the actual router and test-specific dependencies.
    app = FastAPI()
    app.include_router(router)
    app.state.session_factory = factory
    app.state.token_settings = SETTINGS
    yield TestClient(app)
    engine.dispose()

#endregion


#region Login Endpoint Tests
def test_login_returns_a_valid_access_token(client):
    """Verify that successful login returns a valid bearer token and expected response fields."""
    response = client.post(
        "/auth/login", json={"email": "mario@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert decode_access_token(body["access_token"], SETTINGS)["role"] == "clinician"


def test_login_email_is_case_insensitive(client):
    """Verify that the login endpoint accepts email addresses with different casing."""
    response = client.post(
        "/auth/login", json={"email": "MARIO@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "email, password",
    [
        ("mario@example.com", "wrong-password"),
        ("nobody@example.com", PASSWORD),
        ("disabled@example.com", PASSWORD),
    ],
)
def test_login_with_invalid_credentials_returns_401(client, email, password):
    """Verify that incorrect credentials, unknown accounts, and disabled accounts return HTTP 401.

        Args:
            client: FastAPI test client used to submit login requests.
            email: Email address supplied in the login request.
            password: Password supplied in the login request.
    """
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401


def test_wrong_password_and_unknown_email_give_the_same_answer(client):
    """Verify that invalid passwords and unknown accounts produce identical responses.

        This prevents the endpoint from revealing whether a given email address
        is associated with a registered account.
    """
    wrong_password = client.post(
        "/auth/login", json={"email": "mario@example.com", "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert wrong_password.json() == unknown_email.json()


def test_login_with_invalid_body_returns_422(client):
    """Verify that requests missing required login fields are rejected with HTTP 422."""
    response = client.post("/auth/login", json={"email": "mario@example.com"})
    assert response.status_code == 422

#endregion


#region Logout Endpoint Tests
# Remove this test if the placeholder logout endpoint is no longer part of the API.
def test_logout_placeholder_returns_204(client):
    """Verify that the placeholder logout endpoint returns HTTP 204 No Content."""
    assert client.post("/auth/logout").status_code == 204

#endregion