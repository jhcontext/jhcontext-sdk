"""FastAPI application factory for jhcontext server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from .storage.sqlite import SQLiteStorage
from .storage.pii_vault import SQLitePIIVault


_storage: SQLiteStorage | None = None
_pii_vault: SQLitePIIVault | None = None


def get_storage() -> SQLiteStorage:
    global _storage
    if _storage is None:
        _storage = SQLiteStorage()
    return _storage


def get_pii_vault() -> SQLitePIIVault | None:
    return _pii_vault


def create_app(db_path: str | None = None, pii_vault_path: str | None = None) -> Any:
    """Create FastAPI app. Import guarded for optional dependency."""
    from fastapi import FastAPI

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _storage, _pii_vault
        _storage = SQLiteStorage(db_path=db_path)
        _pii_vault = SQLitePIIVault(db_path=pii_vault_path)
        yield
        _storage.close()
        _pii_vault.close()

    app = FastAPI(
        title="jhcontext Server",
        description="PAC-AI: Protocol for Auditable Context in AI",
        version="0.3.0",
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
        return {"status": "ok", "version": "0.3.0"}

    return app
