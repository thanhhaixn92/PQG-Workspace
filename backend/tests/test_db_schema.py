"""Test: SQLite schema, WAL mode, and foreign_keys pragma.

Acceptance criteria (Phase 0):
- All required tables exist in the temp DB.
- ``journal_mode`` is ``wal``.
- ``foreign_keys`` pragma is 1 on a *fresh* connection opened via the app
  connection factory (not just on the migration connection).
- ``schema_migrations`` table exists and contains the initial version.

All tests use the ``migrated_db_path`` fixture (temp dir), never the real
``app.db`` workspace file.
"""
from __future__ import annotations

import pytest

from app.db.connection import open_db

# The expected tables after the initial migration.
REQUIRED_TABLES = {
    "schema_migrations",
    "sessions",
    "task_runs",
    "memory_entries",
    "skills",
    "tool_permissions",
    "audit_events",
    "files_index",
}

CP1_TABLES = {
    "tasks",
    "task_events",
    "task_actions",
    "idempotency_records",
    "notification_outbox",
}


@pytest.mark.asyncio
async def test_all_required_tables_exist(migrated_db_path):
    """All required tables must be present."""
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ) as cursor:
            tables = {row[0] async for row in cursor}
    finally:
        await conn.close()

    missing = REQUIRED_TABLES - tables
    assert not missing, f"Missing tables: {missing}"

    cp1_missing = CP1_TABLES - tables
    assert not cp1_missing, f"Missing CP1 tables: {cp1_missing}"


@pytest.mark.asyncio
async def test_wal_mode_enabled(migrated_db_path):
    """journal_mode must be 'wal' after migration."""
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
        mode = row[0]
    finally:
        await conn.close()

    assert mode == "wal", f"Expected 'wal', got: {mode!r}"


@pytest.mark.asyncio
async def test_foreign_keys_on_per_connection(migrated_db_path):
    """foreign_keys must be ON on every new connection via open_db.

    This test deliberately opens a *new* connection (not the migration
    connection) to verify that the per-connection PRAGMA is set by the
    connection factory, not just once during migration startup.
    """
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute("PRAGMA foreign_keys;") as cursor:
            row = await cursor.fetchone()
        fk_value = row[0]
    finally:
        await conn.close()

    assert fk_value == 1, f"Expected foreign_keys=1, got: {fk_value}"


@pytest.mark.asyncio
async def test_schema_migrations_version_recorded(migrated_db_path):
    """Initial migration version must be recorded in schema_migrations."""
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT version FROM schema_migrations;"
        ) as cursor:
            versions = [row[0] async for row in cursor]
    finally:
        await conn.close()

    assert "0001_initial" in versions, f"Got versions: {versions}"


@pytest.mark.asyncio
async def test_indexes_exist(migrated_db_path):
    """Required indexes must be created by migration."""
    expected_indexes = {
        "idx_sessions_updated",
        "idx_task_runs_session",
        "idx_memory_session",
        "idx_audit_session",
    }
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index';"
        ) as cursor:
            indexes = {row[0] async for row in cursor}
    finally:
        await conn.close()

    missing = expected_indexes - indexes
    assert not missing, f"Missing indexes: {missing}"


@pytest.mark.asyncio
async def test_cp1_migrations_recorded(migrated_db_path):
    """CP1 migration versions must be recorded in schema_migrations."""
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT version FROM schema_migrations;"
        ) as cursor:
            versions = [row[0] async for row in cursor]
    finally:
        await conn.close()

    cp1_versions = {"0005_tasks", "0006_task_runs_task_id", "0007_task_events",
                    "0008_task_actions", "0009_approval_action_ref",
                    "0010_idempotency", "0011_notification_outbox"}
    missing = cp1_versions - set(versions)
    assert not missing, f"Missing CP1 migrations: {missing}"


@pytest.mark.asyncio
async def test_migration_is_idempotent(temp_db_path):
    """Running migrations twice must not raise an error."""
    from app.db.migrations import run_migrations

    await run_migrations(temp_db_path)
    await run_migrations(temp_db_path)  # second run must be a no-op
