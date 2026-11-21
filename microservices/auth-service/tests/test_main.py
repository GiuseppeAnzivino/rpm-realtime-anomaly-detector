"""Unit tests for the FastAPI entrypoint of the authentication service."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint_returns_ok():
    """GET /health returns HTTP 200 and a healthy status payload."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}