"""FastAPI application factory for jhcontext server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from .storage.sqlite import SQLiteStorage


_storage: SQLiteStorage | None = None


def get_storage() -> SQLiteStorage:
    global _storage
    if _storage is None:
        _storage = SQLiteStorage()
    return _storage


def create_app(db_path: str | None = None) -> Any:
    """Create FastAPI app. Import guarded for optional dependency."""
    from fastapi import FastAPI

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _storage
        _storage = SQLiteStorage(db_path=db_path)
        yield
        _storage.close()

    app = FastAPI(
        title="jhcontext Server",
        description="PAC-AI: Protocol for Auditable Context in AI",
        version="0.2.0",
        lifespan=lifespan,
    )

    from .routes import envelopes, artifacts, decisions, provenance, compliance

    app.include_router(envelopes.router, prefix="/envelopes", tags=["envelopes"])
    app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
    app.include_router(decisions.router, prefix="/decisions", tags=["decisions"])
    app.include_router(provenance.router, prefix="/provenance", tags=["provenance"])
    app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    return app
