"""
APPLICATION ENTRYPOINT
Description: Defines the FastAPI application instance for the authentication microservice.
Responsibility: Creates and configures the application, manages the startup and shutdown lifecycle (token settings, database initialization and admin bootstrap), registers the routers, and exposes the service health-check endpoint.
Independence: Provides the application entrypoint consumed by the ASGI server, without embedding business logic or data-access operations.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.routes import router as auth_router
from business.admin_bootstrap import bootstrap_admin
from business.tokens import get_token_settings
from data.init_db import get_database_url, init_db
from data.repository import UserRepository


#region Application Lifecycle

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage the application startup and shutdown.

    On startup, loads the token settings (a missing or too short JWT_SECRET
    stops the service before anything else), creates the database engine,
    creates any missing tables and ensures the initial admin account exists.
    The token settings, the engine and a session factory are stored in the
    application state for later use by request handlers.
    On shutdown, the engine is disposed regardless of the outcome.

    Args:
        app: The FastAPI application instance.
    """
    token_settings = get_token_settings()
    engine = create_engine(get_database_url(), pool_pre_ping=True)
    try:
        init_db(engine)
        with Session(engine) as session:
            repository = UserRepository(session)
            bootstrap_admin(repository)
        app.state.token_settings = token_settings
        app.state.engine = engine
        app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        yield
    finally:
        engine.dispose()
#endregion


#region Application Configuration
app = FastAPI(title="Auth Service", lifespan=lifespan)
app.include_router(auth_router)
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