"""
APPLICATION ENTRYPOINT
Description: Defines the FastAPI application instance for the authentication microservice.
Responsibility: Creates and configures the application and exposes the service health-check endpoint.
Independence: Provides the application entrypoint consumed by the ASGI server, without embedding business logic or data-access operations.
"""

from fastapi import FastAPI

#region Application Configuration
app = FastAPI(title="Auth Service")
#endregion

#region Health Check Endpoint
@app.get("/health")
def health() -> dict[str, str]:
    """
    Return the service liveness status.

    Returns:
        dict[str, str]: A response indicating that the service is running.
    """
    return {"status": "ok"}
#endregion