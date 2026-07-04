"""FastAPI dependency providers.

Provides:
  - get_settings  - application settings (overridable in tests)
  - get_db        - per-request DB connection (overridable in tests)

All routes should declare these as FastAPI dependencies rather than
importing module-level singletons directly.  This makes test overrides
straightforward via ``app.dependency_overrides``.
"""
from __future__ import annotations

from typing import AsyncGenerator, Any

import aiosqlite
from fastapi import Depends, Request

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


def get_hermes_client(request: Request) -> Any:
    """Dependency: returns the Hermes client from app state."""
    return request.app.state.hermes_client
