"""
TEST SUITE (AUTHENTICATION API INTEGRATION TESTS)
    Description: Validates the authentication API endpoints through HTTP requests using the FastAPI test client.
    Responsibility: Ensures login produces access and refresh tokens, refresh rotates them, logout revokes them, invalid credentials or tokens return the expected HTTP responses, and malformed requests are rejected.
    Independence: Integration tests exercise the real API routes, authentication service, repositories, and database using an isolated in-memory SQLite database without external infrastructure.
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


@pytest.fixture(name="login_body")
def fixture_login_body(client):
    """Log in the active account and provide the JSON body of the response.

        Args:
            client: FastAPI test client used to submit the login request.
    """
    response = client.post(
        "/auth/login", json={"email": "mario@example.com", "password": PASSWORD}
    )
    return response.json()

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


def test_login_returns_a_refresh_token(login_body):
    """Verify that successful login also returns a non-empty refresh token.

        Args:
            login_body: JSON body returned by a successful login.
    """
    assert login_body["refresh_token"]


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


#region Refresh Endpoint Tests
def test_refresh_returns_a_new_token_pair(client, login_body):
    """Verify that refreshing returns a valid access token and a different refresh token.

        Args:
            client: FastAPI test client used to submit the refresh request.
            login_body: JSON body returned by a successful login.
    """
    response = client.post(
        "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["refresh_token"] != login_body["refresh_token"]
    assert decode_access_token(body["access_token"], SETTINGS)["role"] == "clinician"


def test_refresh_with_a_reused_token_returns_401(client, login_body):
    """Verify that a refresh token that was already rotated is rejected with HTTP 401.

        Args:
            client: FastAPI test client used to submit the refresh requests.
            login_body: JSON body returned by a successful login.
    """
    client.post("/auth/refresh", json={"refresh_token": login_body["refresh_token"]})

    response = client.post(
        "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_with_an_unknown_token_returns_401(client):
    """Verify that a refresh token that was never issued is rejected with HTTP 401."""
    response = client.post("/auth/refresh", json={"refresh_token": "unknown"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_without_a_token_returns_422(client):
    """Verify that a refresh request without a token is rejected with HTTP 422."""
    assert client.post("/auth/refresh", json={}).status_code == 422

#endregion


#region Logout Endpoint Tests
def test_logout_returns_204_and_revokes_the_refresh_token(client, login_body):
    """Verify that logout returns HTTP 204 and the revoked token can no longer be refreshed.

        Args:
            client: FastAPI test client used to submit the requests.
            login_body: JSON body returned by a successful login.
    """
    token = login_body["refresh_token"]

    logout = client.post("/auth/logout", json={"refresh_token": token})
    refresh = client.post("/auth/refresh", json={"refresh_token": token})

    assert logout.status_code == 204
    assert refresh.status_code == 401


def test_logout_twice_returns_204_both_times(client, login_body):
    """Verify that logging out twice with the same token is idempotent.

        Args:
            client: FastAPI test client used to submit the requests.
            login_body: JSON body returned by a successful login.
    """
    token = login_body["refresh_token"]

    first = client.post("/auth/logout", json={"refresh_token": token})
    second = client.post("/auth/logout", json={"refresh_token": token})

    assert first.status_code == 204
    assert second.status_code == 204


def test_logout_with_an_unknown_token_returns_204(client):
    """Verify that logging out with an unknown token still returns HTTP 204."""
    response = client.post("/auth/logout", json={"refresh_token": "unknown"})
    assert response.status_code == 204


def test_logout_without_a_token_returns_422(client):
    """Verify that a logout request without a token is rejected with HTTP 422."""
    assert client.post("/auth/logout", json={}).status_code == 422

#endregion