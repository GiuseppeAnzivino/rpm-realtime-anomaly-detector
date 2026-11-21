"""FastAPI application entrypoint for the authentication service."""

from fastapi import FastAPI

app = FastAPI(title="Auth Service")


@app.get("/health")
def health() -> dict[str, str]:
    """Return service liveness status."""
    return {"status": "ok"}