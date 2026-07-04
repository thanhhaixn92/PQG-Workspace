"""Tests for FastAPI lifespan events (startup/shutdown)."""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from app.main import create_app
from app.settings import Settings


@pytest.mark.asyncio
async def test_lifespan_creates_db_and_runs_migrations(tmp_path):
    """Verify that the lifespan event initializes the DB from scratch."""
    db_path = tmp_path / "lifespan_test.db"
    real_db_path = Path("app.db").resolve()
    real_db_stat_before = real_db_path.stat() if real_db_path.exists() else None
    
    # Assert DB does not exist yet.
    assert not db_path.exists()

    test_settings = Settings(
        db_path=str(db_path),
        cors_origins=["http://localhost:5173"],
        log_level="WARNING",
    )

    from fastapi.testclient import TestClient

    app = create_app(settings_override=test_settings)

    # Use TestClient as a context manager, which automatically triggers the FastAPI lifespan.
    with TestClient(app) as client:
        # DB should now exist
        assert db_path.exists()
        
        # Verify that we can query health, meaning migrations ran.
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["db"] == "ok"

    # Verify tables actually exist by checking schema_migrations.
    async with aiosqlite.connect(str(db_path)) as conn:
        async with conn.execute("SELECT version FROM schema_migrations;") as cursor:
            versions = [row[0] async for row in cursor]
            assert "0001_initial" in versions

    # Ensure the test did not create or mutate the real dev app.db.
    if real_db_stat_before is None:
        assert not real_db_path.exists(), "Test contaminated workspace app.db"
    else:
        real_db_stat_after = real_db_path.stat()
        assert real_db_stat_after.st_size == real_db_stat_before.st_size
        assert real_db_stat_after.st_mtime_ns == real_db_stat_before.st_mtime_ns
