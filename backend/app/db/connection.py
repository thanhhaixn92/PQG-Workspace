"""SQLite connection factory.

Security / correctness notes
------------------------------
* `PRAGMA foreign_keys = ON` is a *per-connection* setting in SQLite; it
  is NOT persisted to the database file.  Every connection must set it
  immediately after opening.
* `PRAGMA journal_mode = WAL` IS persistent once set, but we re-assert it
  here to be explicit and to make the intent clear.
* aiosqlite wraps sqlite3 and runs in a thread pool internally.  We use
  `isolation_level=None` (autocommit) so that each caller controls
  transactions explicitly; migrations use explicit BEGIN/COMMIT.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

logger = logging.getLogger(__name__)


async def open_db(db_path: Path) -> aiosqlite.Connection:
    """Open a connection and apply mandatory per-connection PRAGMAs.

    Callers are responsible for closing the connection.
    Use :func:`get_db_connection` for a managed context if preferred.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row

    # Per-connection settings - MUST be set on every new connection.
    await conn.execute("PRAGMA foreign_keys = ON;")
    # WAL is persistent but we assert it each time for observability.
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.commit()
    return conn


@asynccontextmanager
async def get_db_connection(db_path: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager / generator that yields a ready connection.

    Usage (in dependency injection)::

        async with get_db_connection(settings.db_path_resolved) as conn:
            ...
    """
    conn = await open_db(db_path)
    try:
        yield conn
    finally:
        await conn.close()
