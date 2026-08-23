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

REMEDIATION_TABLES = {"operation_claims", "artifacts"}


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

    remediation_missing = REMEDIATION_TABLES - tables
    assert not remediation_missing, f"Missing remediation tables: {remediation_missing}"


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
                    "0010_idempotency", "0011_notification_outbox",
                    "0012_idempotency_request_hash"}
    missing = cp1_versions - set(versions)
    assert not missing, f"Missing CP1 migrations: {missing}"


@pytest.mark.asyncio
async def test_migration_is_idempotent(temp_db_path):
    """Running migrations twice must not raise an error."""
    from app.db.migrations import run_migrations

    await run_migrations(temp_db_path)
    await run_migrations(temp_db_path)  # second run must be a no-op


@pytest.mark.asyncio
async def test_end_user_work_migrations_are_recorded_and_nullable(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute("PRAGMA table_info(sessions)") as cur:
            columns = {row[1] async for row in cur}
        assert {"goal", "last_opened_at"}.issubset(columns)
        async with conn.execute("SELECT version FROM schema_migrations WHERE version IN ('0023_end_user_work', '0024_artifacts_and_operation_claims')") as cur:
            versions = {row[0] async for row in cur}
        assert versions == {"0023_end_user_work", "0024_artifacts_and_operation_claims"}
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_0025_backfills_a_default_conversation_for_legacy_work(temp_db_path):
    """A pre-Work-Hub session must retain its existing chat/run links after upgrade."""
    from app.db.migrations import run_migrations

    await run_migrations(temp_db_path)
    conn = await open_db(temp_db_path)
    try:
        # Simulate the schema/data immediately before 0025.  The retained
        # columns are harmless: a real old database simply lacks them.
        await conn.execute("DROP TABLE IF EXISTS work_context_summaries")
        await conn.execute("DROP TABLE IF EXISTS work_plan_steps")
        await conn.execute("DROP TABLE IF EXISTS work_plan_phases")
        await conn.execute("DELETE FROM schema_migrations WHERE version = '0025_work_conversations'")
        await conn.execute(
            "INSERT INTO sessions (id, title, workspace_path, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, 0)",
            ("legacy-work", "Legacy work", "C:/workspace/legacy-work", 10, 10),
        )
        await conn.execute(
            "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("legacy-run", "legacy-work", "completed", 11),
        )
        await conn.execute(
            "INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-message", "legacy-work", "legacy-run", "user", "Keep this chat", 12),
        )
        await conn.commit()
    finally:
        await conn.close()

    await run_migrations(temp_db_path)

    conn = await open_db(temp_db_path)
    try:
        async with conn.execute("SELECT id, title FROM conversations WHERE session_id = ?", ("legacy-work",)) as cur:
            conversation = await cur.fetchone()
        assert tuple(conversation) == ("conversation-legacy-work", "Trao đổi ban đầu")
        async with conn.execute("SELECT conversation_id FROM chat_messages WHERE id = ?", ("legacy-message",)) as cur:
            assert (await cur.fetchone())[0] == "conversation-legacy-work"
        async with conn.execute("SELECT conversation_id FROM task_runs WHERE id = ?", ("legacy-run",)) as cur:
            assert (await cur.fetchone())[0] == "conversation-legacy-work"
        async with conn.execute("SELECT 1 FROM schema_migrations WHERE version = '0025_work_conversations'") as cur:
            assert await cur.fetchone() is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_0028_binds_only_unambiguous_assistant_threads(temp_db_path):
    """The additive thread link backfills one matching conversation and leaves ambiguity unbound."""
    from app.db.migrations import MIGRATIONS, run_migrations

    conn = await open_db(temp_db_path)
    try:
        for version, step in MIGRATIONS:
            if version == "0028_assistant_conversation_link":
                break
            if isinstance(step, str):
                await conn.executescript(step)
            else:
                await step(conn)
            await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, 1))
            await conn.commit()
        await conn.execute("INSERT INTO sessions (id, title, workspace_path, created_at, updated_at, archived) VALUES (?, ?, ?, ?, ?, 0)", ("work-0028", "Work", "C:/tmp/work", 1, 1))
        await conn.executemany("INSERT INTO conversations (id, session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", [("conversation-a", "work-0028", "A", 1, 1), ("conversation-b", "work-0028", "B", 1, 1)])
        await conn.executemany("INSERT INTO assistant_threads (id, title, work_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", [("thread-single", "Single", "work-0028", 1, 1), ("thread-mixed", "Mixed", "work-0028", 1, 1)])
        await conn.executemany("INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, created_at) VALUES (?, ?, ?, ?, 'user', 'completed', ?)", [("turn-single", "thread-single", "work-0028", "conversation-a", 1), ("turn-mixed-a", "thread-mixed", "work-0028", "conversation-a", 1), ("turn-mixed-b", "thread-mixed", "work-0028", "conversation-b", 2)])
        await conn.commit()
    finally:
        await conn.close()

    await run_migrations(temp_db_path)

    conn = await open_db(temp_db_path)
    try:
        async with conn.execute("SELECT id, conversation_id FROM assistant_threads ORDER BY id") as cur:
            assert [tuple(row) async for row in cur] == [("thread-mixed", None), ("thread-single", "conversation-a")]
        async with conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_assistant_threads_conversation'") as cur:
            assert await cur.fetchone() is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_0022_rolls_back_partial_data_and_is_not_recorded(temp_db_path, monkeypatch):
    """A failure inside 0022 must leave neither a partial repair nor its version."""
    from app.db import migrations

    await migrations.run_migrations(temp_db_path)
    conn = await open_db(temp_db_path)
    try:
        await conn.execute(
            "INSERT INTO skills (id, name, description, content, enabled, status, version, updated_at, normalized_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("skill-rollback", "  Legacy   Skill  ", None, "content", 1, "draft", 1, 1, "legacy-placeholder"),
        )
        await conn.execute("DELETE FROM schema_migrations WHERE version = '0022_security_integrity'")
        await conn.commit()
    finally:
        await conn.close()

    original_audit = migrations._migration_audit

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("simulated migration audit failure")

    monkeypatch.setattr(migrations, "_migration_audit", fail_audit)
    with pytest.raises(RuntimeError, match="simulated migration audit failure"):
        await migrations.run_migrations(temp_db_path)

    conn = await open_db(temp_db_path)
    try:
        async with conn.execute("SELECT name FROM skills WHERE id = 'skill-rollback'") as cur:
            assert (await cur.fetchone())[0] == "  Legacy   Skill  "
        async with conn.execute("SELECT 1 FROM schema_migrations WHERE version = '0022_security_integrity'") as cur:
            assert await cur.fetchone() is None
    finally:
        await conn.close()

    monkeypatch.setattr(migrations, "_migration_audit", original_audit)
    await migrations.run_migrations(temp_db_path)
    conn = await open_db(temp_db_path)
    try:
        async with conn.execute("SELECT name, normalized_name FROM skills WHERE id = 'skill-rollback'") as cur:
            row = await cur.fetchone()
            assert (row[0], row[1]) == ("Legacy Skill", "legacy skill")
        async with conn.execute("SELECT 1 FROM schema_migrations WHERE version = '0022_security_integrity'") as cur:
            assert await cur.fetchone() is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_0014_partial_schema_is_recovered(temp_db_path):
    """If skills has status but NOT version/skill_versions, 0014 must still complete.

    This guards against a scenario where the old ``executescript`` caught
    a *second* ``duplicate column name`` and recorded the migration before
    the remaining statements (version column + skill_versions table) executed.
    """
    from app.db.migrations import MIGRATIONS, run_migrations

    # Build a real pre-0014 schema. This keeps skills.status/version and
    # skill_versions absent before we simulate the partial migration state.
    conn = await open_db(temp_db_path)
    try:
        for version, step in MIGRATIONS:
            if version == "0014_skill_versions":
                break
            if isinstance(step, str):
                try:
                    await conn.executescript(step)
                except Exception as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
            else:
                await step(conn)
            await conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, 1),
            )
            await conn.commit()

        async with conn.execute("PRAGMA table_info(skills)") as cur:
            cols = {row[1] async for row in cur}
        assert "status" not in cols
        assert "version" not in cols

        await conn.execute(
            "ALTER TABLE skills ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'"
        )
        await conn.commit()
    finally:
        await conn.close()

    # Now 0014 is pending again.  Running migrations should:
    # 1. See status column already exists -> skip ALTER
    # 2. See version column missing -> add it
    # 3. Create skill_versions table + index
    # 4. Record migration
    await run_migrations(temp_db_path)

    # Verify the full schema is now present.
    conn3 = await open_db(temp_db_path)
    try:
        async with conn3.execute("PRAGMA table_info(skills)") as cur:
            cols = {row[1] async for row in cur}
        assert "status" in cols, "status column missing after 0014"
        assert "version" in cols, "version column missing after 0014"

        async with conn3.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_versions'"
        ) as cur:
            assert await cur.fetchone() is not None, "skill_versions table missing"

        async with conn3.execute(
            "SELECT version FROM schema_migrations WHERE version = '0014_skill_versions'"
        ) as cur:
            assert await cur.fetchone() is not None, "0014_skill_versions not recorded"
    finally:
        await conn3.close()
