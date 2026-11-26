"""
TEST SUITE (UNIT TESTS)
    Description: Contains unit tests for validating the FastAPI application entrypoint, its lifecycle, the registered routers and the health-check endpoint of the Auth-Service microservice.
    Responsibility: Verifies the startup sequence (token settings, database initialization and admin bootstrap), the shutdown cleanup, the failure modes caused by missing configuration, the login of the bootstrapped admin, and the health endpoint response.
    Independence: Uses FastAPI's TestClient with a temporary SQLite database, without requiring a running server or external infrastructure.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as real_create_engine

import main
from business.security import verify_password
from business.tokens import MIN_SECRET_LENGTH, decode_access_token
from data.models import UserRole
from data.repository import UserRepository
from main import app


#region Fixtures

@pytest.fixture(name="database_url")
def fixture_database_url(tmp_path, monkeypatch):
    """Point DATABASE_URL to a temporary SQLite file database."""
    url = f"sqlite:///{tmp_path / 'auth_test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest.fixture(name="admin_env")
def fixture_admin_env(monkeypatch):
    """Provide valid admin bootstrap credentials through the environment."""
    monkeypatch.setenv("ADMIN_EMAIL", "Admin@Example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-very-strong-password")
    monkeypatch.setenv("ADMIN_FULL_NAME", "Root Admin")


@pytest.fixture(name="token_env")
def fixture_token_env(monkeypatch):
    """Provide a valid JWT signing secret through the environment."""
    monkeypatch.setenv("JWT_SECRET", "a" * MIN_SECRET_LENGTH)


#endregion


#region Health Endpoint Tests

def test_health_endpoint_returns_ok():
    """
        Verify that the health endpoint returns a successful response.

        The client is used without a context manager, so the lifespan is not
        executed and no database is required.

        Asserts:
            The endpoint responds with HTTP 200 and returns the expected
            status payload indicating that the service is healthy.
    """
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


#endregion


#region Lifespan Tests

def test_startup_initializes_database_and_creates_admin(database_url, admin_env, token_env):
    """
        Verify that startup creates the schema, the admin account and the app state.

        Asserts:
            The admin exists with the admin role and a correctly hashed
            password, the token settings, engine and session factory are stored
            in the application state, and the service answers requests.
    """
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.engine is not None
        assert app.state.token_settings.jwt_secret == "a" * MIN_SECRET_LENGTH

        with app.state.session_factory() as session:
            admin = UserRepository(session).get_by_email("admin@example.com")

        assert admin is not None
        assert admin.role == UserRole.ADMIN
        assert admin.password_hash != "a-very-strong-password"
        assert verify_password("a-very-strong-password", admin.password_hash)


def test_admin_can_log_in_after_startup(database_url, admin_env, token_env):
    """
        Verify that the bootstrapped admin can authenticate through the real application.

        Asserts:
            The login answers HTTP 200 and returns a valid access token that
            carries the admin role.
    """
    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "a-very-strong-password"},
        )

        assert response.status_code == 200
        claims = decode_access_token(
            response.json()["access_token"], app.state.token_settings
        )
        assert claims["role"] == "admin"


def test_restart_does_not_duplicate_admin(database_url, admin_env, token_env):
    """
        Verify that restarting the application keeps a single admin account.

        Asserts:
            After two consecutive startups on the same database, the admin
            still exists and keeps the same identifier.
    """
    with TestClient(app):
        with app.state.session_factory() as session:
            first_id = UserRepository(session).get_by_email("admin@example.com").user_id

    with TestClient(app):
        with app.state.session_factory() as session:
            second_id = UserRepository(session).get_by_email("admin@example.com").user_id

    assert first_id == second_id


def test_shutdown_disposes_engine(database_url, admin_env, token_env):
    """
        Verify that the database engine is disposed when the application stops.

        Asserts:
            The engine's dispose method is called exactly once on shutdown.
    """
    created = []

    def spy_create_engine(*args, **kwargs):
        engine = real_create_engine(*args, **kwargs)
        created.append(engine)
        return engine

    with patch.object(main, "create_engine", spy_create_engine):
        with patch("sqlalchemy.engine.Engine.dispose", autospec=True) as dispose:
            with TestClient(app):
                pass

    dispose.assert_called_once_with(created[0])


def test_startup_fails_without_jwt_secret(database_url, admin_env, monkeypatch):
    """
        Verify that startup fails when JWT_SECRET is not configured.

        Asserts:
            A RuntimeError mentioning JWT_SECRET is raised while the
            application starts.
    """
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
        with TestClient(app):
            pass


def test_startup_fails_with_short_jwt_secret(database_url, admin_env, monkeypatch):
    """
        Verify that startup fails when JWT_SECRET is too short.

        Asserts:
            A RuntimeError about the minimum length is raised while the
            application starts.
    """
    monkeypatch.setenv("JWT_SECRET", "short")

    with pytest.raises(RuntimeError, match="at least"):
        with TestClient(app):
            pass


def test_startup_fails_without_database_url(monkeypatch, admin_env, token_env):
    """
        Verify that startup fails when DATABASE_URL is not configured.

        Asserts:
            A RuntimeError mentioning DATABASE_URL is raised while the
            application starts.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with TestClient(app):
            pass


def test_startup_fails_without_admin_credentials(database_url, token_env, monkeypatch):
    """
        Verify that startup fails when the admin credentials are missing.

        Asserts:
            A RuntimeError mentioning the admin credentials is raised while
            the application starts.
    """
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_EMAIL"):
        with TestClient(app):
            pass


#endregion