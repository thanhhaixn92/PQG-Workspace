"""Shared pytest fixtures for Hermes Local Stack backend tests.

Key design decisions
---------------------
* ``tmp_db_path`` provides a temp-directory DB path so tests never touch
  ``app.db`` in the workspace (clarification point #2).
* ``test_app`` creates a fresh FastAPI app with settings overridden to use
  the temp DB.  This exercises the same lifespan / migration path as
  production but in isolation.
* ``client`` is an ``httpx.AsyncClient`` against the test app; all routes
  use dependency injection so settings/db are automatically redirected to
  the temp DB.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.connection import open_db
from app.db.migrations import run_migrations
from app.main import create_app
from app.settings import Settings


@pytest.fixture()
def temp_db_path(tmp_path):
    """Return a Path to a fresh SQLite DB in a temp directory."""
    return tmp_path / "test_app.db"


@pytest_asyncio.fixture()
async def migrated_db_path(temp_db_path):
    """Run migrations against temp DB and return its path."""
    await run_migrations(temp_db_path)
    return temp_db_path


@pytest_asyncio.fixture()
async def test_app(migrated_db_path):
    """Create a FastAPI app pointing at the temp DB via DI override."""
    from app.dependencies import get_db, get_settings
    from app.db.connection import get_db_connection

    test_settings = Settings(
        db_path=str(migrated_db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )

    application = create_app(settings_override=test_settings)

    # Override both settings and db dependencies.
    application.dependency_overrides[get_settings] = lambda: test_settings

    async def _override_db():
        async with get_db_connection(migrated_db_path) as conn:
            yield conn

    application.dependency_overrides[get_db] = _override_db

    yield application


@pytest_asyncio.fixture()
async def client(test_app):
    """Async HTTP client backed by the test FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app, client=("127.0.0.1", 12345)),
        base_url="http://testserver",
    ) as ac:
        yield ac
