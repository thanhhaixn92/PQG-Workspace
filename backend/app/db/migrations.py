"""Database schema migrations.

Design decisions
-----------------
* Migrations are idempotent: every statement uses ``CREATE TABLE IF NOT
  EXISTS`` so re-running on an existing DB is safe.
* A ``schema_migrations`` table records which migration versions have been
  applied (satisfies the "migration version tracking" rule in
  docs/02_DATA_STORAGE_MODEL.md section 6).
* WAL and foreign_keys are also set here through the shared connection
  factory (``open_db``), which applies them on every connection.
* The function takes a ``db_path`` argument instead of using module-level
  globals so that tests can pass a temp path (clarification point #2).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from app.db.connection import open_db

logger = logging.getLogger(__name__)

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

# Ordered list of (version_tag, sql) migration entries.
MIGRATIONS: list[tuple[str, str]] = [
    ("0001_initial", _SCHEMA_SQL),
    ("0002_chat_messages", _CHAT_MESSAGES_SQL),
    ("0003_approval_requests", _APPROVAL_REQUESTS_SQL),
    ("0004_approval_payload", _APPROVAL_PAYLOAD_SQL),
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

        for version, sql in MIGRATIONS:
            if version in applied:
                logger.debug("Migration %s already applied, skipping.", version)
                continue
            logger.info("Applying migration: %s", version)
            try:
                await conn.executescript(sql)
            except Exception as exc:
                if version == "0004_approval_payload" and "duplicate column name" in str(exc).lower():
                    logger.info("approval_requests.payload_json already exists, recording migration.")
                else:
                    raise
            await conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                (version, int(time.time())),
            )
            await conn.commit()
            logger.info("Migration %s applied.", version)
    finally:
        await conn.close()
