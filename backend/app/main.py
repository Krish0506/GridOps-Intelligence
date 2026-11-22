"""FastAPI application entrypoint for GridOps Intelligence."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from backend.app.api import router
from backend.app.database import engine

app = FastAPI(
    title="GridOps Intelligence API",
    description="Synthetic utility asset intelligence and decision-support platform.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic process health check."""
    return {"status": "ok", "service": "gridops-api"}


@app.get("/health/db", tags=["health"])
def database_health() -> dict[str, str]:
    """Verify that the API can reach PostgreSQL."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


app.include_router(router)
