"""
TEST SUITE (UNIT TESTS)
    Description: Contains unit tests for validating the FastAPI application entrypoint and health-check endpoint of the Auth-Service microservice.
    Responsibility: Verifies that the application exposes a functioning health endpoint and returns the expected HTTP status code and response payload.
    Independence: Uses FastAPI's TestClient to test the application directly without requiring a running server or external infrastructure.
"""

from fastapi.testclient import TestClient

from main import app


#region Test Client Setup

client = TestClient(app)


#endregion


#region Health Endpoint Tests

def test_health_endpoint_returns_ok():
    """
        Verify that the health endpoint returns a successful response.

        Asserts:
            The endpoint responds with HTTP 200 and returns the expected
            status payload indicating that the service is healthy.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


#endregion