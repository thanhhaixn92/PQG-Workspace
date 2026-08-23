"""FastAPI dependency providers.

Provides:
  - get_settings      - application settings (overridable in tests)
  - get_db            - per-request DB connection (overridable in tests)
  - get_trusted_actor - actor subject supplied by trusted server authentication

All routes should declare these as FastAPI dependencies rather than
importing module-level singletons directly.  This makes test overrides
straightforward via ``app.dependency_overrides``.
"""
from __future__ import annotations

from typing import AsyncGenerator, Any

import aiosqlite
from fastapi import Depends, HTTPException, Request

from app.db.connection import get_db_connection
from app.settings import Settings, get_settings as _get_settings


def get_settings() -> Settings:
    """Dependency: returns the application Settings instance."""
    return _get_settings()


async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency: yields an open DB connection with PRAGMAs applied.

    Each request gets its own connection; it is closed after the request.
    ``PRAGMA foreign_keys = ON`` is set by the connection factory on
    every connection - not just during migration.
    """
    async with get_db_connection(settings.db_path_resolved) as conn:
        yield conn


def get_trusted_actor(request: Request) -> str:
    """Return the actor set by a trusted server-side authentication layer.

    ``X-Actor`` is deliberately never read here: a browser-controlled header is
    not an authenticated identity.  Until an authentication middleware sets a
    non-empty ``request.state.actor_subject``, governed writes fail closed with
    ``IDENTITY_ENFORCEMENT_INSUFFICIENT``.  Tests may override this dependency.
    """
    actor = getattr(request.state, "actor_subject", None)
    if not isinstance(actor, str) or not actor.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "IDENTITY_ENFORCEMENT_INSUFFICIENT", "message": "Authenticated actor identity required"},
        )
    return actor.strip()


def get_gyo_orchestrator(request: Request) -> Any:
    """Dependency: returns the native GYO provider orchestrator from app state."""
    return request.app.state.gyo_orchestrator
