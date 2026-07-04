"""Database schema migrations.

Design decisions
----------------
* Migrations are idempotent: every statement uses ``CREATE TABLE IF NOT
  EXISTS`` so re-running on an existing DB is safe.
* A ``schema_migrations`` table records which migration versions have been
  applied (satisfies the "migration version tracking" rule in
  docs/02_DATA_STORAGE_MODEL.md section 6).
* WAL and foreign_keys are also set here through the shared connection
  factory (``open_db``), which applies them on every connection.
* The function takes a ``db_path`` argument instead of using module-level
  globals so that tests can pass a temp path (clarification point #2).
* Migrations that perform ``ALTER TABLE ADD COLUMN`` use a pre-check via
  ``PRAGMA table_info`` to avoid catching partial-failure state.  The
  schema_migrations record is inserted ONLY after **all** statements for
  that version have completed successfully.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite

from app.db.connection import open_db

logger = logging.getLogger(__name__)

# A migration entry can be a raw SQL string or a callable that accepts
# an aiosqlite.Connection and returns a coroutine.
MigrationStep = str | Callable[[aiosqlite.Connection], Awaitable[None]]

# Schema SQL is a single migration labelled "0001_initial".
# Future migrations add new entries to MIGRATIONS list.

_SCHEMA_SQL = """
-- Tracking table (must come first so we can insert version records)
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT    PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Business sessions: maps app session <-> ACP session
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT    PRIMARY KEY,
    acp_session_id TEXT    UNIQUE,
    title          TEXT,
    workspace_path TEXT    NOT NULL,
    created_at     INTEGER NOT NULL,
    updated_at     INTEGER NOT NULL,
    archived       INTEGER DEFAULT 0
);

-- Task runs: debug / replay / audit for prompt execution
CREATE TABLE IF NOT EXISTS task_runs (
    id          TEXT    PRIMARY KEY,
    session_id  TEXT    NOT NULL REFERENCES sessions(id),
    status      TEXT    NOT NULL,
    started_at  INTEGER NOT NULL,
    finished_at INTEGER,
    error       TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Long-term memory entries visible to the app
CREATE TABLE IF NOT EXISTS memory_entries (
    id               TEXT    PRIMARY KEY,
    session_id       TEXT    REFERENCES sessions(id),
    key              TEXT    NOT NULL,
    value            TEXT    NOT NULL,
    kind             TEXT    NOT NULL,
    importance_score REAL    DEFAULT 0,
    last_accessed_at INTEGER,
    created_at       INTEGER NOT NULL
);

-- Reusable instruction skills
CREATE TABLE IF NOT EXISTS skills (
    id          TEXT    PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    content     TEXT    NOT NULL,
    enabled     INTEGER DEFAULT 1,
    updated_at  INTEGER NOT NULL
);

-- Tool permission policies
CREATE TABLE IF NOT EXISTS tool_permissions (
    id             TEXT    PRIMARY KEY,
    tool_name      TEXT    NOT NULL,
    risk_level     TEXT    NOT NULL,
    default_policy TEXT    NOT NULL,
    created_at     INTEGER NOT NULL
);

-- Append-only audit log (write/external/destructive actions)
CREATE TABLE IF NOT EXISTS audit_events (
    id           TEXT    PRIMARY KEY,
    session_id   TEXT    REFERENCES sessions(id),
    actor        TEXT    NOT NULL,
    action       TEXT    NOT NULL,
    target       TEXT,
    payload_json TEXT,
    created_at   INTEGER NOT NULL
);

-- File metadata cache (not source-of-truth for file content)
CREATE TABLE IF NOT EXISTS files_index (
    id         TEXT    PRIMARY KEY,
    session_id TEXT    REFERENCES sessions(id),
    path       TEXT    NOT NULL,
    mime_type  TEXT,
    size_bytes INTEGER,
    created_at INTEGER NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_sessions_updated    ON sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_task_runs_session   ON task_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_session      ON memory_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_session       ON audit_events(session_id);
"""

_CHAT_MESSAGES_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT    PRIMARY KEY,
    session_id TEXT    NOT NULL REFERENCES sessions(id),
    task_id    TEXT    REFERENCES task_runs(id),
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages(session_id, created_at);
"""

_APPROVAL_REQUESTS_SQL = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id          TEXT    PRIMARY KEY,
    session_id  TEXT    REFERENCES sessions(id),
    action      TEXT    NOT NULL,
    target      TEXT    NOT NULL,
    risk_level  TEXT    NOT NULL,
    description TEXT,
    status      TEXT    NOT NULL,
    decision    TEXT,
    created_at  INTEGER NOT NULL,
    resolved_at INTEGER,
    expires_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_session_status
    ON approval_requests(session_id, status, created_at);
"""

_APPROVAL_PAYLOAD_SQL = """
ALTER TABLE approval_requests ADD COLUMN payload_json TEXT;
"""

_TASKS_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT    PRIMARY KEY,
    session_id  TEXT    REFERENCES sessions(id),
    parent_task_id TEXT REFERENCES tasks(id),
    title       TEXT,
    description TEXT,
    status      TEXT    NOT NULL DEFAULT 'queued',
    priority    INTEGER DEFAULT 0,
    task_type   TEXT    DEFAULT 'prompt',
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""

_TASK_RUNS_TASK_ID_SQL = """
ALTER TABLE task_runs ADD COLUMN task_id TEXT REFERENCES tasks(id);
"""

_TASK_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS task_events (
    id          TEXT    PRIMARY KEY,
    task_id     TEXT    NOT NULL REFERENCES tasks(id),
    run_id      TEXT    REFERENCES task_runs(id),
    type        TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    data_json   TEXT,
    created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, created_at);
"""

_TASK_ACTIONS_SQL = """
CREATE TABLE IF NOT EXISTS task_actions (
    id          TEXT    PRIMARY KEY,
    task_id     TEXT    NOT NULL REFERENCES tasks(id),
    tool_name   TEXT    NOT NULL,
    risk_level  TEXT    NOT NULL DEFAULT 'read',
    status      TEXT    NOT NULL DEFAULT 'pending',
    description TEXT,
    input_json  TEXT,
    output_json TEXT,
    created_at  INTEGER NOT NULL,
    resolved_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_task_actions_task ON task_actions(task_id);
"""

_APPROVAL_ACTION_REF_SQL = """
ALTER TABLE approval_requests ADD COLUMN task_action_id TEXT REFERENCES task_actions(id);
"""

_IDEMPOTENCY_HASH_SQL = """
ALTER TABLE idempotency_records ADD COLUMN request_hash TEXT;
"""

_IDEMPOTENCY_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_records (
    key             TEXT    PRIMARY KEY,
    request_hash    TEXT,
    response_json   TEXT    NOT NULL,
    status_code     INTEGER NOT NULL,
    created_at      INTEGER NOT NULL,
    expires_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_records(expires_at);
"""

_NOTIFICATION_OUTBOX_SQL = """
CREATE TABLE IF NOT EXISTS notification_outbox (
    id              TEXT    PRIMARY KEY,
    channel         TEXT    NOT NULL,
    event_type      TEXT    NOT NULL,
    payload_json    TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    attempt_count   INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 5,
    last_error      TEXT,
    locked_at       INTEGER,
    locked_by       TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending ON notification_outbox(status, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_locked ON notification_outbox(locked_at);
"""

_TELEGRAM_CALLBACK_TOKENS_SQL = """
CREATE TABLE IF NOT EXISTS telegram_callback_tokens (
    token       TEXT    PRIMARY KEY,
    task_id     TEXT    NOT NULL REFERENCES tasks(id),
    action_type TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    expires_at  INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telegram_callback_tokens_status
    ON telegram_callback_tokens(status, expires_at);
"""

_SKILL_VERSIONS_SQL = """
ALTER TABLE skills ADD COLUMN status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE skills ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS skill_versions (
    id              TEXT    PRIMARY KEY,
    skill_id        TEXT    NOT NULL REFERENCES skills(id),
    version_number  INTEGER NOT NULL,
    name            TEXT    NOT NULL,
    description     TEXT,
    content         TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_versions_skill
    ON skill_versions(skill_id, version_number);
"""


async def _column_exists(conn: aiosqlite.Connection, table: str, column: str) -> bool:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        cols = {row[1] async for row in cur}
    return column in cols


async def _apply_migration_0014(conn: aiosqlite.Connection) -> None:
    """Apply migration 0014 with per-statement column safety.

    Each ``ALTER TABLE ADD COLUMN`` is guarded by a ``PRAGMA table_info``
    check so that an already-present column does not cause a partial-failure
    state.  The ``schema_migrations`` record is inserted *after* all steps
    succeed.
    """
    if not await _column_exists(conn, "skills", "status"):
        await conn.execute("ALTER TABLE skills ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")

    if not await _column_exists(conn, "skills", "version"):
        await conn.execute("ALTER TABLE skills ADD COLUMN version INTEGER NOT NULL DEFAULT 1")

    await conn.execute(
        """CREATE TABLE IF NOT EXISTS skill_versions (
            id              TEXT    PRIMARY KEY,
            skill_id        TEXT    NOT NULL REFERENCES skills(id),
            version_number  INTEGER NOT NULL,
            name            TEXT    NOT NULL,
            description     TEXT,
            content         TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            updated_at      INTEGER NOT NULL
        )"""
    )

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_skill_versions_skill ON skill_versions(skill_id, version_number)"
    )

# Ordered list of (version_tag, sql) migration entries.
MIGRATIONS: list[tuple[str, MigrationStep]] = [
    ("0001_initial", _SCHEMA_SQL),
    ("0002_chat_messages", _CHAT_MESSAGES_SQL),
    ("0003_approval_requests", _APPROVAL_REQUESTS_SQL),
    ("0004_approval_payload", _APPROVAL_PAYLOAD_SQL),
    ("0005_tasks", _TASKS_SQL),
    ("0006_task_runs_task_id", _TASK_RUNS_TASK_ID_SQL),
    ("0007_task_events", _TASK_EVENTS_SQL),
    ("0008_task_actions", _TASK_ACTIONS_SQL),
    ("0009_approval_action_ref", _APPROVAL_ACTION_REF_SQL),
    ("0010_idempotency", _IDEMPOTENCY_SQL),
    ("0011_notification_outbox", _NOTIFICATION_OUTBOX_SQL),
    ("0012_idempotency_request_hash", _IDEMPOTENCY_HASH_SQL),
    ("0013_telegram_callback_tokens", _TELEGRAM_CALLBACK_TOKENS_SQL),
    ("0014_skill_versions", _apply_migration_0014),
]


async def run_migrations(db_path: Path) -> None:
    """Apply any pending migrations to the DB at *db_path*.

    Safe to call on every startup:
    - Already-applied migrations are skipped.
    - WAL and foreign_keys are guaranteed by the connection factory.
    """
    conn = await open_db(db_path)
    try:
        # Ensure the tracking table itself exists before checking versions.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT    PRIMARY KEY,
                applied_at INTEGER NOT NULL
            );
            """
        )
        await conn.commit()

        async with conn.execute(
            "SELECT version FROM schema_migrations;"
        ) as cursor:
            applied = {row[0] async for row in cursor}

        for version, step in MIGRATIONS:
            if version in applied:
                logger.debug("Migration %s already applied, skipping.", version)
                continue
            logger.info("Applying migration: %s", version)

            if isinstance(step, str):
                try:
                    await conn.executescript(step)
                except Exception as exc:
                    if "duplicate column name" in str(exc).lower():
                        logger.info("Column already exists in migration %s, recording.", version)
                    else:
                        raise
            else:
                await step(conn)

            await conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                (version, int(time.time())),
            )
            await conn.commit()
            logger.info("Migration %s applied.", version)
    finally:
        await conn.close()
