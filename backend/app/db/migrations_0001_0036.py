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
import hashlib
import json
import time
import unicodedata
import uuid
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


async def _apply_migration_0012(conn: aiosqlite.Connection) -> None:
    async with conn.execute("PRAGMA table_info(idempotency_records)") as cur:
        columns = {row[1] async for row in cur}
    if "request_hash" not in columns:
        await conn.execute("ALTER TABLE idempotency_records ADD COLUMN request_hash TEXT")

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


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (table,)
    ) as cur:
        return await cur.fetchone() is not None


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

_DIRAP_SOURCE_FILES_SQL = """
CREATE TABLE IF NOT EXISTS dirap_source_files (
    id           TEXT    PRIMARY KEY,
    task_id      TEXT    NOT NULL REFERENCES tasks(id),
    file_path    TEXT    NOT NULL,
    file_name    TEXT    NOT NULL,
    note         TEXT,
    attached_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dirap_source_files_task
    ON dirap_source_files(task_id);
"""

_DIRAP_EXTRACTIONS_SQL = """
CREATE TABLE IF NOT EXISTS dirap_extractions (
    id                TEXT    PRIMARY KEY,
    source_file_id    TEXT    NOT NULL REFERENCES dirap_source_files(id),
    source_sha256     TEXT    NOT NULL,
    extracted_at      INTEGER NOT NULL,
    extractor_version TEXT    NOT NULL,
    file_type         TEXT    NOT NULL,
    status            TEXT    NOT NULL DEFAULT 'fresh',
    record_count      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dirap_extractions_source
    ON dirap_extractions(source_file_id, extracted_at);

CREATE TABLE IF NOT EXISTS dirap_extraction_records (
    id            TEXT    PRIMARY KEY,
    extraction_id TEXT    NOT NULL REFERENCES dirap_extractions(id),
    seq           INTEGER NOT NULL,
    content       TEXT    NOT NULL,
    provenance    TEXT
);

CREATE INDEX IF NOT EXISTS idx_dirap_extraction_records_extraction
    ON dirap_extraction_records(extraction_id, seq);
"""

_DIRAP_KNOWLEDGE_RECORDS_SQL = """
CREATE TABLE IF NOT EXISTS dirap_knowledge_records (
    id                   TEXT    PRIMARY KEY,
    task_id              TEXT    NOT NULL REFERENCES tasks(id),
    extraction_id        TEXT    NOT NULL REFERENCES dirap_extractions(id),
    extraction_record_id TEXT    NOT NULL REFERENCES dirap_extraction_records(id),
    source_file_id       TEXT    NOT NULL REFERENCES dirap_source_files(id),
    source_sha256        TEXT    NOT NULL,
    extractor_version    TEXT    NOT NULL,
    provenance           TEXT,
    content              TEXT    NOT NULL,
    status               TEXT    NOT NULL DEFAULT 'draft',
    note                 TEXT,
    created_at           INTEGER NOT NULL,
    updated_at           INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dirap_knowledge_records_task
    ON dirap_knowledge_records(task_id, created_at);

CREATE INDEX IF NOT EXISTS idx_dirap_knowledge_records_extraction
    ON dirap_knowledge_records(extraction_id);
"""

# Controlled review lifecycle: draft -> review_pending -> active|rejected.
# The four verification dimensions are stored independently and are never
# client-writable: they are computed by the server from the submitted
# evidence references (see backend/app/api/dirap.py).
_DIRAP_KNOWLEDGE_REVIEW_SQL = """
ALTER TABLE dirap_knowledge_records
    ADD COLUMN source_verification_state TEXT NOT NULL DEFAULT 'unverified';
ALTER TABLE dirap_knowledge_records
    ADD COLUMN calculation_verification_state TEXT NOT NULL DEFAULT 'unverified';
ALTER TABLE dirap_knowledge_records
    ADD COLUMN owner_acceptance_state TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE dirap_knowledge_records
    ADD COLUMN authority_status TEXT NOT NULL DEFAULT 'none';
CREATE TABLE IF NOT EXISTS dirap_knowledge_evidence (
    id                  TEXT    PRIMARY KEY,
    knowledge_record_id TEXT    NOT NULL REFERENCES dirap_knowledge_records(id),
    evidence_type       TEXT    NOT NULL,
    reference           TEXT    NOT NULL,
    note                TEXT,
    created_at          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dirap_knowledge_evidence_record
    ON dirap_knowledge_evidence(knowledge_record_id, created_at);
"""

# Contract fix (Codex review 2026-08-08): the owner acceptance dimension uses
# the vocabulary value ``accepted``, not ``approved``. This migration normalizes
# any record already written with the legacy ``approved`` value. Migration 0018
# is intentionally left untouched (historical, already applied).
_DIRAP_KNOWLEDGE_REVIEW_CONTRACT_FIX_SQL = """
UPDATE dirap_knowledge_records
   SET owner_acceptance_state = 'accepted'
 WHERE owner_acceptance_state = 'approved';
"""

_MEMORY_HUB_SQL = """
CREATE TABLE IF NOT EXISTS memory_hub_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    content TEXT NOT NULL,
    project_id TEXT,
    task_id TEXT,
    session_id TEXT,
    producer_agent TEXT NOT NULL,
    producer_model TEXT,
    producer_session TEXT,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    source_sha256 TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('normal', 'sensitive', 'restricted')),
    lifecycle TEXT NOT NULL CHECK (lifecycle IN ('proposed', 'verified', 'active', 'superseded', 'rejected')),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES memory_hub_records(id),
    verified_by TEXT,
    verified_at INTEGER,
    activated_by TEXT,
    activated_at INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_hub_records_scope
    ON memory_hub_records(project_id, task_id, lifecycle, sensitivity);
CREATE INDEX IF NOT EXISTS idx_memory_hub_records_key
    ON memory_hub_records(memory_key, kind, version);
CREATE TABLE IF NOT EXISTS memory_hub_evidence (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES memory_hub_records(id),
    evidence_type TEXT NOT NULL,
    reference TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_hub_evidence_record
    ON memory_hub_evidence(record_id, created_at);
CREATE TRIGGER IF NOT EXISTS memory_hub_evidence_no_update
BEFORE UPDATE ON memory_hub_evidence BEGIN
  SELECT RAISE(ABORT, 'memory_hub_evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS memory_hub_evidence_no_delete
BEFORE DELETE ON memory_hub_evidence BEGIN
  SELECT RAISE(ABORT, 'memory_hub_evidence is immutable');
END;
CREATE TABLE IF NOT EXISTS memory_hub_imports (
    legacy_memory_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    record_id TEXT NOT NULL REFERENCES memory_hub_records(id),
    imported_at INTEGER NOT NULL,
    PRIMARY KEY (legacy_memory_id, content_sha256)
);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_hub_fts USING fts5(
    memory_key, content, content='memory_hub_records', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS memory_hub_ai AFTER INSERT ON memory_hub_records BEGIN
  INSERT INTO memory_hub_fts(rowid, memory_key, content) VALUES (new.rowid, new.memory_key, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memory_hub_ad AFTER DELETE ON memory_hub_records BEGIN
  INSERT INTO memory_hub_fts(memory_hub_fts, rowid, memory_key, content) VALUES ('delete', old.rowid, old.memory_key, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memory_hub_au AFTER UPDATE OF memory_key, content ON memory_hub_records BEGIN
  INSERT INTO memory_hub_fts(memory_hub_fts, rowid, memory_key, content) VALUES ('delete', old.rowid, old.memory_key, old.content);
  INSERT INTO memory_hub_fts(rowid, memory_key, content) VALUES (new.rowid, new.memory_key, new.content);
END;
"""


async def _apply_migration_0021_memory_hub_contract_closure(conn: aiosqlite.Connection) -> None:
    """Backfill explicit content hashes and enforce active-record scope identity."""
    if not await _column_exists(conn, "memory_hub_records", "content_sha256"):
        await conn.execute("ALTER TABLE memory_hub_records ADD COLUMN content_sha256 TEXT")
    if not await _column_exists(conn, "memory_hub_records", "source_artifact_sha256"):
        await conn.execute("ALTER TABLE memory_hub_records ADD COLUMN source_artifact_sha256 TEXT")

    async with conn.execute("SELECT id, content FROM memory_hub_records WHERE content_sha256 IS NULL") as cur:
        rows = await cur.fetchall()
    for record_id, content in rows:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        await conn.execute(
            "UPDATE memory_hub_records SET content_sha256 = ? WHERE id = ?",
            (digest, record_id),
        )

    async with conn.execute(
        """SELECT COALESCE(project_id, ''), COALESCE(task_id, ''), kind, memory_key, COUNT(*)
           FROM memory_hub_records WHERE lifecycle = 'active'
           GROUP BY COALESCE(project_id, ''), COALESCE(task_id, ''), kind, memory_key
           HAVING COUNT(*) > 1"""
    ) as cur:
        duplicate = await cur.fetchone()
    if duplicate:
        raise RuntimeError("Cannot apply Memory Hub scope index while duplicate active records exist")

    await conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_hub_active_scope_identity
           ON memory_hub_records(COALESCE(project_id, ''), COALESCE(task_id, ''), kind, memory_key)
           WHERE lifecycle = 'active'"""
    )


def _canonical_display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


async def _migration_audit(conn: aiosqlite.Connection, action: str, target: str, payload: dict) -> None:
    await conn.execute(
        """INSERT INTO audit_events (id, session_id, actor, action, target, payload_json, created_at)
           VALUES (?, NULL, 'migration', ?, ?, ?, ?)""",
        (str(uuid.uuid4()), action, target, json.dumps(payload), int(time.time())),
    )


async def _apply_migration_0022_security_integrity(conn: aiosqlite.Connection) -> None:
    """Normalize legacy identities without deleting content or task history."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        async with conn.execute("PRAGMA table_info(skills)") as cur:
            columns = {row[1] async for row in cur}
        if "normalized_name" not in columns:
            await conn.execute("ALTER TABLE skills ADD COLUMN normalized_name TEXT")

        async with conn.execute(
            "SELECT id, name, enabled, status, updated_at FROM skills ORDER BY updated_at ASC, id ASC"
        ) as cur:
            skills = await cur.fetchall()
        seen: set[str] = set()
        for skill_id, raw_name, _enabled, _status, _updated_at in skills:
            display = _canonical_display(raw_name or "") or f"Skill recovered {skill_id[:8]}"
            normalized = display.casefold()
            if normalized in seen:
                replacement = f"{display} (duplicate-{skill_id[:8]})"
                await conn.execute(
                    "UPDATE skills SET name = ?, normalized_name = ?, enabled = 0, status = 'draft' WHERE id = ?",
                    (replacement, f"{normalized}::duplicate::{skill_id}", skill_id),
                )
                await _migration_audit(conn, "migration.skill_duplicate_disabled", skill_id, {"canonical_name": display})
            else:
                seen.add(normalized)
                await conn.execute("UPDATE skills SET name = ?, normalized_name = ? WHERE id = ?", (display, normalized, skill_id))
                if display != (raw_name or ""):
                    await _migration_audit(conn, "migration.skill_name_normalized", skill_id, {"name": display})

        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_normalized_name ON skills(normalized_name)")

        async with conn.execute("SELECT id, title FROM sessions WHERE TRIM(COALESCE(title, '')) = ''") as cur:
            empty_sessions = await cur.fetchall()
        for session_id, _title in empty_sessions:
            recovered = f"Phiên khôi phục {session_id[:8]}"
            await conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (recovered, session_id))
            await _migration_audit(conn, "migration.session_title_recovered", session_id, {"title": recovered})

        async with conn.execute(
            """SELECT child.id, child.parent_task_id, child.session_id, parent.session_id
               FROM tasks child JOIN tasks parent ON parent.id = child.parent_task_id
               WHERE child.parent_task_id IS NOT NULL
                 AND COALESCE(child.session_id, '') != COALESCE(parent.session_id, '')"""
        ) as cur:
            invalid_parents = await cur.fetchall()
        for task_id, parent_id, _child_session, _parent_session in invalid_parents:
            await conn.execute("UPDATE tasks SET parent_task_id = NULL WHERE id = ?", (task_id,))
            await _migration_audit(conn, "migration.task_parent_detached", task_id, {"parent_task_id": parent_id})
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0023_end_user_work(conn: aiosqlite.Connection) -> None:
    """Add optional user-facing work metadata without guessing old values."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        if not await _column_exists(conn, "sessions", "goal"):
            await conn.execute("ALTER TABLE sessions ADD COLUMN goal TEXT")
        if not await _column_exists(conn, "sessions", "last_opened_at"):
            await conn.execute("ALTER TABLE sessions ADD COLUMN last_opened_at INTEGER")
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0024_artifacts_and_operation_claims(conn: aiosqlite.Connection) -> None:
    """Create durable, atomic operation claims and a managed artifact registry."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS operation_claims (
                identity TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                operation TEXT NOT NULL,
                scope TEXT NOT NULL,
                client_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('processing', 'completed', 'failed')),
                response_json TEXT NOT NULL DEFAULT '{}',
                status_code INTEGER NOT NULL DEFAULT 202,
                resource_id TEXT,
                error_code TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_operation_claims_expires ON operation_claims(expires_at)"
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id),
                relative_path TEXT NOT NULL,
                kind TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(session_id, relative_path)
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_session_created ON artifacts(session_id, created_at DESC)")
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0025_work_conversations(conn: aiosqlite.Connection) -> None:
    """Make the existing session record a durable Work and add its conversations.

    ``sessions`` deliberately remains the physical owner of legacy data.  This
    avoids a risky primary-key rewrite and lets old API clients keep working
    while the end-user UI calls the record a Work.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        for column, definition in (
            ("work_status", "TEXT NOT NULL DEFAULT 'not_started'"),
            ("progress_percent", "INTEGER NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100)"),
            ("completion_proposed_at", "INTEGER"),
            ("completed_at", "INTEGER"),
        ):
            if not await _column_exists(conn, "sessions", column):
                await conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")

        await conn.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                title TEXT NOT NULL,
                purpose TEXT,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_opened_at INTEGER,
                UNIQUE(session_id, title)
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session_updated ON conversations(session_id, updated_at DESC)")
        for table in ("chat_messages", "task_runs", "tasks", "task_events", "artifacts"):
            if not await _column_exists(conn, table, "conversation_id"):
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN conversation_id TEXT REFERENCES conversations(id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created ON chat_messages(conversation_id, created_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_conversation_started ON task_runs(conversation_id, started_at DESC)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS work_plan_phases (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                title TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'blocked', 'completed')),
                source TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user', 'hermes')),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS work_plan_steps (
                id TEXT PRIMARY KEY,
                phase_id TEXT NOT NULL REFERENCES work_plan_phases(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                title TEXT NOT NULL,
                description TEXT,
                result TEXT,
                sort_order INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'blocked', 'completed')),
                source TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user', 'hermes')),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_work_plan_phases_session_order ON work_plan_phases(session_id, sort_order)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_work_plan_steps_phase_order ON work_plan_steps(phase_id, sort_order)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS work_context_summaries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                conversation_id TEXT REFERENCES conversations(id),
                content TEXT NOT NULL,
                from_message_id TEXT REFERENCES chat_messages(id),
                through_message_id TEXT REFERENCES chat_messages(id),
                version INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(session_id, version)
            )"""
        )

        now = int(time.time())
        async with conn.execute("SELECT id, archived, created_at, updated_at FROM sessions") as cursor:
            sessions = await cursor.fetchall()
        for row in sessions:
            session_id = row[0]
            conversation_id = f"conversation-{session_id}"
            await conn.execute(
                """INSERT OR IGNORE INTO conversations
                   (id, session_id, title, purpose, status, created_at, updated_at, last_opened_at)
                   VALUES (?, ?, 'Trao đổi ban đầu', 'Lịch sử trao đổi được chuyển từ Công việc cũ', ?, ?, ?, ?)""",
                (conversation_id, session_id, "archived" if row[1] else "active", row[2], row[3], row[3]),
            )
            for table, clause in (
                ("chat_messages", "session_id = ?"),
                ("task_runs", "session_id = ?"),
                ("tasks", "session_id = ?"),
                ("artifacts", "session_id = ?"),
                ("task_events", "task_id IN (SELECT id FROM tasks WHERE session_id = ?)"),
            ):
                await conn.execute(
                    f"UPDATE {table} SET conversation_id = ? WHERE conversation_id IS NULL AND {clause}",
                    (conversation_id, session_id),
                )
            await _migration_audit(
                conn, "migration.work_conversation_created", session_id,
                {"conversation_id": conversation_id, "legacy_data_backfilled": True, "at": now},
            )
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0026_assistant_actions_marketplace(conn: aiosqlite.Connection) -> None:
    """Add the durable, local-only primitives for the Hermes workspace.

    These tables intentionally describe an action before it is executed.  They
    do not grant a plugin, a model response, or an ACP process any implicit
    authority.  The executor claims one approved package at a time and only
    understands a small allow-list of reversible, first-party work actions.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS assistant_threads (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                work_id TEXT REFERENCES sessions(id),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_threads_work ON assistant_threads(work_id, updated_at DESC)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS assistant_turns (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES assistant_threads(id),
                work_id TEXT REFERENCES sessions(id),
                conversation_id TEXT REFERENCES conversations(id),
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                model_id TEXT,
                error TEXT,
                created_at INTEGER NOT NULL,
                completed_at INTEGER
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_turns_thread_created ON assistant_turns(thread_id, created_at)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS assistant_turn_parts (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL REFERENCES assistant_turns(id) ON DELETE CASCADE,
                part_type TEXT NOT NULL CHECK (part_type IN ('text', 'source', 'tool_result', 'artifact', 'action_proposal', 'approval', 'error')),
                content_json TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_turn_parts_turn ON assistant_turn_parts(turn_id, sort_order)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS action_packages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                conversation_id TEXT REFERENCES conversations(id),
                title TEXT NOT NULL,
                description TEXT,
                package_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('draft', 'awaiting_approval', 'approved', 'executing', 'verifying', 'succeeded', 'partially_failed', 'failed', 'cancelled', 'expired')),
                approved_hash TEXT,
                approved_at INTEGER,
                approved_by TEXT,
                lease_owner TEXT,
                lease_expires_at INTEGER,
                heartbeat_at INTEGER,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_packages_status_lease ON action_packages(status, lease_expires_at)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS action_steps (
                id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL,
                kind TEXT NOT NULL,
                risk_level TEXT NOT NULL CHECK (risk_level IN ('read', 'write', 'external', 'destructive', 'system')),
                input_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'succeeded', 'failed', 'cancelled')),
                output_json TEXT,
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_steps_package_order ON action_steps(package_id, sort_order)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS action_attempts (
                id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
                step_id TEXT REFERENCES action_steps(id),
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                detail_json TEXT,
                started_at INTEGER NOT NULL,
                finished_at INTEGER
            )"""
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_attempts_package ON action_attempts(package_id, started_at)")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS marketplace_packages (
                package_id TEXT NOT NULL,
                version TEXT NOT NULL,
                catalog_name TEXT NOT NULL,
                publisher TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                package_hash TEXT NOT NULL,
                signature_valid INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                PRIMARY KEY(package_id, version, catalog_name)
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS installed_plugins (
                package_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                catalog_name TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                install_state TEXT NOT NULL CHECK (install_state IN ('installed_disabled', 'cannot_run_safely', 'enabled', 'failed', 'removed')),
                previous_version TEXT,
                installed_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0027_work_data_scope(conn: aiosqlite.Connection) -> None:
    """Add the explicit, user-facing data scope for every Work."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        if not await _column_exists(conn, "sessions", "data_scope"):
            await conn.execute(
                "ALTER TABLE sessions ADD COLUMN data_scope TEXT NOT NULL DEFAULT 'work_only' "
                "CHECK (data_scope IN ('work_only', 'approved_library'))"
            )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0028_assistant_conversation_link(conn: aiosqlite.Connection) -> None:
    """Bind a durable Assistant thread to at most one Work conversation.

    Existing turns already carry ``conversation_id``.  Backfill only when all
    conversation-scoped turns in a thread agree; ambiguous legacy threads stay
    unbound instead of guessing across conversation boundaries.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        if not await _column_exists(conn, "assistant_threads", "conversation_id"):
            await conn.execute(
                "ALTER TABLE assistant_threads ADD COLUMN conversation_id TEXT REFERENCES conversations(id)"
            )
        await conn.execute(
            """UPDATE assistant_threads
               SET conversation_id = (
                   SELECT MIN(turn.conversation_id)
                   FROM assistant_turns turn
                   WHERE turn.thread_id = assistant_threads.id AND turn.conversation_id IS NOT NULL
               )
               WHERE conversation_id IS NULL
                 AND 1 = (
                   SELECT COUNT(DISTINCT turn.conversation_id)
                   FROM assistant_turns turn
                   WHERE turn.thread_id = assistant_threads.id AND turn.conversation_id IS NOT NULL
                 )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assistant_threads_conversation "
            "ON assistant_threads(conversation_id, updated_at DESC)"
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0029_gyo_provider_profiles(conn: aiosqlite.Connection) -> None:
    """Add provider/model configuration without retaining credentials in SQLite.

    The database stores only an opaque keyring reference.  Retiring a profile
    is deliberately non-destructive so user-visible Assistant provenance can
    remain valid after a provider or model is removed from future routing.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS ai_provider_profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                provider_type TEXT NOT NULL CHECK (provider_type IN ('openai_responses', 'openai_compatible')),
                base_url TEXT,
                credential_ref TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                retired_at INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS ai_model_profiles (
                id TEXT PRIMARY KEY,
                provider_profile_id TEXT NOT NULL REFERENCES ai_provider_profiles(id),
                display_name TEXT NOT NULL,
                model_identifier TEXT NOT NULL,
                tier TEXT NOT NULL CHECK (tier IN ('fast', 'balanced', 'deep', 'vision')),
                capabilities_json TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 100,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
                retired_at INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(provider_profile_id, model_identifier)
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS assistant_run_metadata (
                assistant_turn_id TEXT PRIMARY KEY REFERENCES assistant_turns(id) ON DELETE CASCADE,
                provider_profile_id TEXT REFERENCES ai_provider_profiles(id),
                model_profile_id TEXT REFERENCES ai_model_profiles(id),
                route_mode TEXT NOT NULL CHECK (route_mode IN ('auto', 'manual')),
                selection_reason TEXT NOT NULL,
                fallback_from_model_profile_id TEXT REFERENCES ai_model_profiles(id),
                created_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_model_profiles_available "
            "ON ai_model_profiles(provider_profile_id, enabled, retired_at, priority, created_at)"
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_model_profiles_one_default "
            "ON ai_model_profiles(is_default) WHERE is_default = 1 AND retired_at IS NULL"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assistant_run_metadata_model "
            "ON assistant_run_metadata(model_profile_id, created_at DESC)"
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0030_work_memory_learning(conn: aiosqlite.Connection) -> None:
    """Persist opt-in Memory scopes and durable, proposal-only learning jobs.

    A Memory scope deliberately points at a visible Work plan step instead of
    exposing the older operational ``tasks`` entity in the Workspace UI.
    ``id`` is used as the internal Memory Hub task scope for new GYO records;
    existing legacy task-scoped Memory Hub records remain untouched.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS work_memory_scopes (
                id TEXT PRIMARY KEY,
                work_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                plan_step_id TEXT NOT NULL REFERENCES work_plan_steps(id) ON DELETE CASCADE,
                context_mode TEXT NOT NULL DEFAULT 'suggest_only'
                    CHECK (context_mode IN ('off', 'suggest_only', 'active_work_memory')),
                auto_learning_enabled INTEGER NOT NULL DEFAULT 0 CHECK (auto_learning_enabled IN (0, 1)),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(work_id, plan_step_id)
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS assistant_turn_contexts (
                user_turn_id TEXT PRIMARY KEY REFERENCES assistant_turns(id) ON DELETE CASCADE,
                work_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                plan_step_id TEXT REFERENCES work_plan_steps(id) ON DELETE SET NULL,
                memory_scope_id TEXT REFERENCES work_memory_scopes(id) ON DELETE SET NULL,
                context_mode TEXT NOT NULL DEFAULT 'suggest_only'
                    CHECK (context_mode IN ('off', 'suggest_only', 'active_work_memory')),
                auto_learning_enabled INTEGER NOT NULL DEFAULT 0 CHECK (auto_learning_enabled IN (0, 1)),
                created_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS gyo_learning_jobs (
                id TEXT PRIMARY KEY,
                assistant_turn_id TEXT NOT NULL UNIQUE REFERENCES assistant_turns(id) ON DELETE CASCADE,
                work_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                plan_step_id TEXT NOT NULL REFERENCES work_plan_steps(id) ON DELETE CASCADE,
                memory_scope_id TEXT NOT NULL REFERENCES work_memory_scopes(id) ON DELETE CASCADE,
                candidate_kind TEXT NOT NULL CHECK (candidate_kind IN ('memory', 'skill')),
                payload_hash TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'created', 'skipped', 'failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                candidate_ref TEXT,
                error_code TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_work_memory_scopes_work ON work_memory_scopes(work_id, plan_step_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gyo_learning_jobs_pending ON gyo_learning_jobs(status, created_at)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gyo_learning_jobs_scope_hash ON gyo_learning_jobs(memory_scope_id, candidate_kind, payload_hash, created_at)"
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0031_gyo_model_routing(conn: aiosqlite.Connection) -> None:
    """Add transparent, local-only routing policy and safe attempt metadata."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        async with conn.execute("PRAGMA table_info(ai_model_profiles)") as cur:
            model_columns = {row[1] async for row in cur}
        if "cost_class" not in model_columns:
            await conn.execute(
                "ALTER TABLE ai_model_profiles ADD COLUMN cost_class TEXT NOT NULL DEFAULT 'unknown' "
                "CHECK (cost_class IN ('free', 'unknown', 'may_charge'))"
            )
        async with conn.execute("PRAGMA table_info(assistant_run_metadata)") as cur:
            metadata_columns = {row[1] async for row in cur}
        if "fallback_chain_json" not in metadata_columns:
            await conn.execute("ALTER TABLE assistant_run_metadata ADD COLUMN fallback_chain_json TEXT")
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS gyo_routing_policy (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                auto_fallback_enabled INTEGER NOT NULL DEFAULT 0 CHECK (auto_fallback_enabled IN (0, 1)),
                updated_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "INSERT OR IGNORE INTO gyo_routing_policy (id, auto_fallback_enabled, updated_at) VALUES (1, 0, strftime('%s','now'))"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_model_profiles_cost_class ON ai_model_profiles(cost_class, enabled, retired_at)"
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0032_workspace_tasks(conn: aiosqlite.Connection) -> None:
    """Add the user-facing Workspace task domain without altering legacy tasks."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspace_tasks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'planned'
                    CHECK (status IN ('planned','ready','in_progress','blocked','waiting','done','cancelled')),
                priority INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 5),
                impact INTEGER NOT NULL DEFAULT 0 CHECK (impact BETWEEN 0 AND 5),
                due_at INTEGER,
                estimate_minutes INTEGER,
                blocked_reason TEXT,
                ai_eligibility TEXT NOT NULL DEFAULT 'assistable'
                    CHECK (ai_eligibility IN ('delegatable','assistable','human_only')),
                ai_reason TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_tasks_session_status
                ON workspace_tasks(session_id, status, due_at, updated_at DESC);

            CREATE TABLE IF NOT EXISTS workspace_task_blocks (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES workspace_tasks(id) ON DELETE CASCADE,
                starts_at INTEGER NOT NULL,
                ends_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                CHECK (ends_at > starts_at)
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_task_blocks_time
                ON workspace_task_blocks(starts_at, ends_at);

            CREATE TABLE IF NOT EXISTS workspace_ai_jobs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES workspace_tasks(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','waiting_user','completed','failed','cancelled')),
                stage_text TEXT,
                output_summary TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_ai_jobs_status
                ON workspace_ai_jobs(status, updated_at DESC);
            """
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


async def _apply_migration_0033_gyo_v3_action_packages(conn: aiosqlite.Connection) -> None:
    """GYO v3 vertical slice: revisioned immutable payloads, durable execution.

    Fully additive against the 0026 action-package tables:
    * ``action_packages`` gains revision/approval/reauthorization/snapshot/
      precondition/budget/capability/dto-version metadata columns.
    * ``action_steps`` is rebuilt only to widen its ``status`` CHECK with
      ``blocked`` and to add optimistic-version / postcondition / capability
      columns; existing rows are preserved.
    * ``action_execution_events`` records durable leased execution events,
      heartbeats and watchdog recoveries.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        for column, ddl in (
            ("revision", "ALTER TABLE action_packages ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"),
            ("approved_revision", "ALTER TABLE action_packages ADD COLUMN approved_revision INTEGER"),
            ("created_by", "ALTER TABLE action_packages ADD COLUMN created_by TEXT NOT NULL DEFAULT 'user'"),
            ("dto_version", "ALTER TABLE action_packages ADD COLUMN dto_version INTEGER NOT NULL DEFAULT 1"),
            ("snapshot_json", "ALTER TABLE action_packages ADD COLUMN snapshot_json TEXT"),
            ("preconditions_json", "ALTER TABLE action_packages ADD COLUMN preconditions_json TEXT"),
            ("budget_json", "ALTER TABLE action_packages ADD COLUMN budget_json TEXT"),
            ("capabilities_json", "ALTER TABLE action_packages ADD COLUMN capabilities_json TEXT"),
        ):
            if not await _column_exists(conn, "action_packages", column):
                await conn.execute(ddl)

        if not await _column_exists(conn, "action_steps", "expected_version_json"):
            # Rebuild action_steps (to widen the status CHECK with 'blocked' and add
            # optimistic-version / postcondition / capability columns) together with
            # its FK children so references resolve to the final ``action_steps`` name.
            # Using *_new shadow tables + rename preserves rows and keeps FKs valid.
            await conn.execute(
                """CREATE TABLE action_steps_new (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    risk_level TEXT NOT NULL CHECK (risk_level IN ('read', 'write', 'external', 'destructive', 'system')),
                    input_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'succeeded', 'failed', 'cancelled', 'blocked')),
                    output_json TEXT,
                    error TEXT,
                    expected_version_json TEXT,
                    postcondition_json TEXT,
                    capability TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )"""
            )
            await conn.execute(
                """INSERT INTO action_steps_new
                    (id, package_id, sort_order, kind, risk_level, input_json, status,
                     output_json, error, created_at, updated_at)
                    SELECT id, package_id, sort_order, kind, risk_level, input_json, status,
                      output_json, error, created_at, updated_at FROM action_steps"""
            )
            await conn.execute(
                """CREATE TABLE action_attempts_new (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
                    step_id TEXT REFERENCES action_steps_new(id),
                    attempt_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    detail_json TEXT,
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER
                )"""
            )
            await conn.execute("INSERT INTO action_attempts_new SELECT * FROM action_attempts")
            await conn.execute("DROP TABLE action_attempts")
            await conn.execute("DROP TABLE action_steps")
            await conn.execute("ALTER TABLE action_steps_new RENAME TO action_steps")
            await conn.execute("ALTER TABLE action_attempts_new RENAME TO action_attempts")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_steps_package_order ON action_steps(package_id, sort_order)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_action_attempts_package ON action_attempts(package_id, started_at)")
            # Monotonic optimistic-concurrency version for plan steps and Work.
            if not await _column_exists(conn, "work_plan_steps", "version"):
                await conn.execute("ALTER TABLE work_plan_steps ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            if not await _column_exists(conn, "sessions", "version"):
                await conn.execute("ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 1")



        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_steps_package_order ON action_steps(package_id, sort_order)"
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS action_execution_events (
                id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
                step_id TEXT REFERENCES action_steps(id),
                event_type TEXT NOT NULL,
                detail_json TEXT,
                created_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_execution_events_package ON action_execution_events(package_id, created_at)"
        )
        await conn.execute("PRAGMA legacy_alter_table = OFF")
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


# --- 0034: GYO v3 canonical payload binding + execution state widening ------
#
# Inventory before rebuild (verified against sqlite_master on a migrated DB):
# * action_packages (0026 base + 0033): id PK; session_id NOT NULL REFERENCES
#   sessions(id); conversation_id REFERENCES conversations(id); title NOT NULL;
#   description; package_hash NOT NULL; status NOT NULL CHECK(draft,
#   awaiting_approval, approved, executing, verifying, succeeded,
#   partially_failed, failed, cancelled, expired); approved_hash; approved_at;
#   approved_by; lease_owner; lease_expires_at; heartbeat_at; attempt_count
#   NOT NULL DEFAULT 0; created_at/updated_at NOT NULL; revision NOT NULL
#   DEFAULT 1; approved_revision; created_by NOT NULL DEFAULT 'user';
#   dto_version NOT NULL DEFAULT 1; snapshot_json; preconditions_json;
#   budget_json; capabilities_json.
#   Index: idx_action_packages_status_lease(status, lease_expires_at).
#   Triggers: none. Children FK -> action_packages(id) ON DELETE CASCADE:
#   action_steps.package_id, action_attempts.package_id,
#   action_execution_events.package_id.
# * action_steps (rebuilt by 0033): id PK; package_id NOT NULL REFERENCES
#   action_packages(id) ON DELETE CASCADE; sort_order/kind/input_json/
#   created_at/updated_at NOT NULL; risk_level CHECK(read, write, external,
#   destructive, system); status CHECK(pending, executing, succeeded, failed,
#   cancelled, blocked) DEFAULT 'pending'; output_json; error;
#   expected_version_json; postcondition_json; capability.
#   Index: idx_action_steps_package_order(package_id, sort_order).
#   Triggers: none. Children FK -> action_steps(id): action_attempts.step_id,
#   action_execution_events.step_id.
# * action_execution_events (0033): id PK; package_id NOT NULL ON DELETE
#   CASCADE; step_id REFERENCES action_steps(id); event_type NOT NULL;
#   detail_json; created_at NOT NULL.
#   Index: idx_action_execution_events_package(package_id, created_at).
#
# SQLite cannot widen a CHECK constraint or add a NOT NULL column without a
# default in place, so both tables are shadow-rebuilt.  Every copied row is
# inserted through Python so the new NOT NULL binding columns always receive
# real values.  Legacy package_hash/approved_hash are mirrored unchanged and
# remain compatibility metadata only; they never authorize approval or
# execution going forward.

_P0_DEFAULT_BUDGET_V34: dict = {
    "max_steps": 20,
    "max_calls": 50,
    "max_retries_per_step": 2,
    "max_duration_seconds": 900,
    "max_mutable_entities": 100,
    "max_artifacts": 5,
    "max_external_effects": 0,
}
_DEFAULT_APPROVAL_TTL_SECONDS_V34 = 900


def _canonical_payload_text_v34(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _iso_utc_v34(epoch_seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(epoch_seconds))


def _legacy_resolved_payload_v34(
    row: dict, step_rows: list[dict]
) -> tuple[str, str, int]:
    """Deterministically synthesize a v1 canonical payload for a pre-0034 row.

    Returns ``(resolved_payload_json, payload_hash, expires_at_epoch)`` derived
    only from the package's own stored data so re-running the synthesis on the
    same row always yields the same hash.
    """
    ttl = _DEFAULT_APPROVAL_TTL_SECONDS_V34
    try:
        budget = json.loads(row.get("budget_json") or "{}")
        if not isinstance(budget, dict) or not budget:
            budget = dict(_P0_DEFAULT_BUDGET_V34)
    except (TypeError, ValueError):
        budget = dict(_P0_DEFAULT_BUDGET_V34)
    try:
        snapshot = json.loads(row.get("snapshot_json") or "{}")
        targets = snapshot.get("targets") if isinstance(snapshot, dict) else None
        if not isinstance(targets, list):
            targets = []
    except (TypeError, ValueError):
        targets = []
    try:
        preconditions = json.loads(row.get("preconditions_json") or "[]")
        if not isinstance(preconditions, list):
            preconditions = []
    except (TypeError, ValueError):
        preconditions = []

    created_at = int(row["created_at"])
    payload = {
        "payload_schema_version": 1,
        "dto_version": int(row.get("dto_version") or 1),
        "revision": int(row.get("revision") or 1),
        "title": row["title"],
        "description": row.get("description"),
        "actions": [
            {"kind": s["kind"], "input": json.loads(s["input_json"])}
            for s in step_rows
        ],
        "targets": targets,
        "diffs": [],
        "preconditions": preconditions,
        "context_snapshot": {"sources": [], "context_hash": None},
        "capability_version": "p0-v1",
        "budget": budget,
        "budget_version": "p0-v1",
        "policy_version": "p0-v1",
        "tool_contract_version": "p0-v1",
        "captured_at": _iso_utc_v34(created_at),
        "captured_tz_offset_minutes": 0,
        "expires_at": _iso_utc_v34(created_at + ttl),
    }
    payload_json = _canonical_payload_text_v34(payload)
    return payload_json, hashlib.sha256(payload_json.encode("utf-8")).hexdigest(), created_at + ttl


_ACTION_PACKAGES_V34_SQL = """
CREATE TABLE action_packages_v34 (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    conversation_id TEXT REFERENCES conversations(id),
    title TEXT NOT NULL,
    description TEXT,
    package_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'draft', 'awaiting_approval', 'approved', 'executing', 'verifying',
        'succeeded', 'partially_failed', 'failed', 'cancelled', 'expired',
        'blocked', 'interrupted', 'cancel_requested')),
    approved_hash TEXT,
    approved_at INTEGER,
    approved_by TEXT,
    lease_owner TEXT,
    lease_expires_at INTEGER,
    heartbeat_at INTEGER,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    approved_revision INTEGER,
    created_by TEXT NOT NULL DEFAULT 'user',
    dto_version INTEGER NOT NULL DEFAULT 1,
    snapshot_json TEXT,
    preconditions_json TEXT,
    budget_json TEXT,
    capabilities_json TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1,
    resolved_payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    approved_payload_hash TEXT,
    expires_at INTEGER,
    approval_ttl_seconds INTEGER NOT NULL DEFAULT 900
)
"""

_ACTION_STEPS_V34_SQL = """
CREATE TABLE action_steps_v34 (
    id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL REFERENCES action_packages(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL,
    kind TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('read', 'write', 'external', 'destructive', 'system')),
    input_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'executing', 'succeeded', 'failed', 'cancelled', 'blocked',
        'cancel_requested', 'interrupted')),
    output_json TEXT,
    error TEXT,
    expected_version_json TEXT,
    postcondition_json TEXT,
    capability TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
)
"""

_PACKAGE_COPY_COLUMNS = (
    "id, session_id, conversation_id, title, description, package_hash, status,"
    " approved_hash, approved_at, approved_by, lease_owner, lease_expires_at,"
    " heartbeat_at, attempt_count, created_at, updated_at, revision,"
    " approved_revision, created_by, dto_version, snapshot_json,"
    " preconditions_json, budget_json, capabilities_json"
)


async def _apply_migration_0034_gyo_v3_payload_binding(conn: aiosqlite.Connection) -> None:
    """GYO v3 CP1: canonical payload binding + widened execution states.

    * ``action_packages`` is shadow-rebuilt to widen its ``status`` CHECK with
      ``blocked`` / ``interrupted`` / ``cancel_requested`` and to bind every
      row to an immutable canonical ``resolved_payload_json`` +
      ``payload_hash`` plus an absolute ``expires_at`` deadline.
    * ``action_steps`` is shadow-rebuilt to widen its ``status`` CHECK with
      ``cancel_requested`` / ``interrupted`` and to add per-step retry and
      idempotency columns.
    * ``action_execution_events`` (the existing persistent event/outbox store)
      is upgraded additively: per-package monotonic ``sequence`` with a UNIQUE
      index, DTO/schema versions, and SSE delivery retry bookkeeping
      (``publish_attempts`` / ``last_publish_error`` / ``published_at``).  No
      parallel outbox table is introduced.
    * Backfill runs in bounded Python batches (no SQL sha256()) and is
      idempotent.  ALL legacy ``approved`` / ``awaiting_approval`` rows are
      invalidated: ``approved_payload_hash``, ``approved_revision``,
      ``approved_at``, ``approved_by`` cleared and any ``approved`` status
      reset to ``awaiting_approval`` so the worker never claims a legacy
      approval.  No legacy row receives an ``approved_payload_hash``.
    * Row iteration uses keyset pagination (rowid > last_rowid, LIMIT 200) with
      no ``fetchall`` on the entire table.  Steps needed for payload synthesis
      are fetched per-batch only for the packages in that batch.
    * Sequence backfill is deterministic by ``(package_id, created_at, rowid)``
      and assigns per-package monotonic sequences one-by-one, never via a
      bulk ``MAX+1`` update that would give duplicates within a batch.
    * ``PRAGMA foreign_keys`` is disabled only around the rebuild transaction
      and restored in ``finally`` even when the migration fails.  A non-empty
      ``PRAGMA foreign_key_check`` rolls the whole migration back.
    """
    cur = await conn.execute("PRAGMA foreign_keys")
    fk_row = await cur.fetchone()
    fk_was_on = bool(fk_row and fk_row[0])
    try:
        if fk_was_on:
            await conn.execute("PRAGMA foreign_keys = OFF")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(_ACTION_PACKAGES_V34_SQL)
            insert_sql = (
                f"INSERT INTO action_packages_v34 ({_PACKAGE_COPY_COLUMNS},"
                " schema_version, resolved_payload_json, payload_hash,"
                " approved_payload_hash, expires_at, approval_ttl_seconds)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)"
            )
            BATCH = 200
            last_rowid = 0
            while True:
                async with conn.execute(
                    f"SELECT rowid, {_PACKAGE_COPY_COLUMNS} FROM action_packages WHERE rowid > ? ORDER BY rowid LIMIT ?",
                    (last_rowid, BATCH),
                ) as cursor:
                    batch_rows = [dict(r) for r in await cursor.fetchall()]
                if not batch_rows:
                    break
                last_rowid = int(batch_rows[-1]["rowid"])
                # Fetch steps only for this batch's packages (bounded).
                pkg_ids = [r["id"] for r in batch_rows]
                steps_by_package: dict[str, list[dict]] = {}
                if pkg_ids:
                    placeholders = ",".join("?" for _ in pkg_ids)
                    async with conn.execute(
                        f"SELECT package_id, sort_order, kind, input_json FROM action_steps"
                        f" WHERE package_id IN ({placeholders}) ORDER BY package_id, sort_order",
                        pkg_ids,
                    ) as scur:
                        for r in await scur.fetchall():
                            steps_by_package.setdefault(r["package_id"], []).append(dict(r))
                params = []
                for row in batch_rows:
                    payload_json, payload_hash_value, expires_at = (
                        _legacy_resolved_payload_v34(
                            row, steps_by_package.get(row["id"], [])
                        )
                    )
                    # Absolute invalidation: no legacy row keeps an approval.
                    orig_status = row["status"]
                    new_status = orig_status
                    new_approved_hash = row["approved_hash"]
                    new_approved_at = row["approved_at"]
                    new_approved_by = row["approved_by"]
                    new_approved_revision = row["approved_revision"]
                    if orig_status == "approved":
                        new_status = "awaiting_approval"
                        new_approved_hash = None
                        new_approved_at = None
                        new_approved_by = None
                        new_approved_revision = None
                    elif orig_status == "awaiting_approval":
                        new_approved_hash = None
                        new_approved_at = None
                        new_approved_by = None
                        new_approved_revision = None
                    # approved_payload_hash is always NULL for legacy rows.
                    params.append((
                        row["id"], row["session_id"], row["conversation_id"],
                        row["title"], row["description"], row["package_hash"],
                        new_status, new_approved_hash, new_approved_at,
                        new_approved_by, row["lease_owner"], row["lease_expires_at"],
                        row["heartbeat_at"], row["attempt_count"], row["created_at"],
                        row["updated_at"], row["revision"], new_approved_revision,
                        row["created_by"], row["dto_version"], row["snapshot_json"],
                        row["preconditions_json"], row["budget_json"],
                        row["capabilities_json"], payload_json, payload_hash_value,
                        None,
                        expires_at, _DEFAULT_APPROVAL_TTL_SECONDS_V34,
                    ))
                await conn.executemany(insert_sql, params)

            await conn.execute("DROP TABLE action_packages")
            await conn.execute(
                "ALTER TABLE action_packages_v34 RENAME TO action_packages"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_packages_status_lease"
                " ON action_packages(status, lease_expires_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_packages_expires"
                " ON action_packages(status, expires_at)"
            )

            await conn.execute(_ACTION_STEPS_V34_SQL)
            await conn.execute(
                """INSERT INTO action_steps_v34
                   (id, package_id, sort_order, kind, risk_level, input_json,
                    status, output_json, error, expected_version_json,
                    postcondition_json, capability, retry_count, idempotency_key,
                    created_at, updated_at)
                   SELECT id, package_id, sort_order, kind, risk_level, input_json,
                    status, output_json, error, expected_version_json,
                    postcondition_json, capability, 0, NULL, created_at, updated_at
                   FROM action_steps"""
            )
            await conn.execute("DROP TABLE action_steps")
            await conn.execute("ALTER TABLE action_steps_v34 RENAME TO action_steps")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_steps_package_order"
                " ON action_steps(package_id, sort_order)"
            )
            await conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_action_steps_idempotency
                   ON action_steps(package_id, idempotency_key)
                   WHERE idempotency_key IS NOT NULL"""
            )

            for column, ddl in (
                ("sequence", "ALTER TABLE action_execution_events ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0"),
                ("dto_version", "ALTER TABLE action_execution_events ADD COLUMN dto_version INTEGER NOT NULL DEFAULT 1"),
                ("schema_version", "ALTER TABLE action_execution_events ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1"),
                ("publish_attempts", "ALTER TABLE action_execution_events ADD COLUMN publish_attempts INTEGER NOT NULL DEFAULT 0"),
                ("last_publish_error", "ALTER TABLE action_execution_events ADD COLUMN last_publish_error TEXT"),
                ("published_at", "ALTER TABLE action_execution_events ADD COLUMN published_at INTEGER"),
            ):
                if not await _column_exists(conn, "action_execution_events", column):
                    await conn.execute(ddl)
            # Deterministic per-package sequence backfill: ordered by (package_id, created_at, rowid).
            # Each pending row gets next sequence = max_existing + increment, one-by-one within batch.
            while True:
                async with conn.execute(
                    """SELECT rowid, package_id, created_at FROM action_execution_events
                       WHERE sequence = 0 ORDER BY package_id, created_at, rowid
                       LIMIT 200"""
                ) as cursor:
                    pending = [dict(r) for r in await cursor.fetchall()]
                if not pending:
                    break
                # Collect current max per package present in this batch.
                distinct_pids = list({r["package_id"] for r in pending})
                max_by_pid: dict[str, int] = {}
                for pid in distinct_pids:
                    async with conn.execute(
                        "SELECT COALESCE(MAX(sequence), 0) FROM action_execution_events WHERE package_id = ?",
                        (pid,),
                    ) as c2:
                        max_by_pid[pid] = int((await c2.fetchone())[0])
                for r in pending:
                    pid = r["package_id"]
                    rid = r["rowid"]
                    next_seq = max_by_pid[pid] + 1
                    await conn.execute(
                        "UPDATE action_execution_events SET sequence = ? WHERE rowid = ?",
                        (next_seq, rid),
                    )
                    max_by_pid[pid] = next_seq
            await conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS
                   idx_action_execution_events_package_sequence
                   ON action_execution_events(package_id, sequence)"""
            )

            check_cur = await conn.execute("PRAGMA foreign_key_check")
            violations = await check_cur.fetchall()
            if violations:
                raise RuntimeError(
                    "Migration 0034 aborted: PRAGMA foreign_key_check returned "
                    f"{len(violations)} violation(s), first={tuple(violations[0])}"
                )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    finally:
        await conn.execute("PRAGMA foreign_keys = ON" if fk_was_on else "PRAGMA foreign_keys = OFF")


async def _apply_migration_0035_artifact_structural_validation(conn: aiosqlite.Connection) -> None:
    """Record structural validation separately from artifact metadata.

    Existing artifacts intentionally start as ``pending`` rather than being
    grandfathered into trusted assistant context.  This migration does not
    claim malware scanning; it only records a bounded structural inspection.
    """
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artifact_validations (
            artifact_id TEXT PRIMARY KEY REFERENCES artifacts(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('pending', 'structurally_validated', 'rejected', 'failed')),
            media_type TEXT,
            validator_version TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            validated_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_artifact_validations_status ON artifact_validations(status);
        INSERT OR IGNORE INTO artifact_validations (artifact_id, status, media_type, validator_version, detail_json, validated_at)
        SELECT id, 'pending', NULL, 'v1', '{}', NULL FROM artifacts;
        """
    )


async def _apply_migration_0036_gyo_history_workflow_contract(conn: aiosqlite.Connection) -> None:
    """Additive bindings for Work-scoped GYO history and task hand-off.

    Existing rows remain readable.  No conversation/thread is guessed for a
    legacy AI job; only a new canonical hand-off writes the optional bindings.
    """
    await conn.execute("BEGIN IMMEDIATE")
    try:
        if not await _column_exists(conn, "assistant_threads", "pinned_at"):
            await conn.execute("ALTER TABLE assistant_threads ADD COLUMN pinned_at INTEGER")
        if not await _column_exists(conn, "workspace_ai_jobs", "conversation_id"):
            await conn.execute(
                "ALTER TABLE workspace_ai_jobs ADD COLUMN conversation_id TEXT REFERENCES conversations(id)"
            )
        if not await _column_exists(conn, "workspace_ai_jobs", "assistant_thread_id"):
            await conn.execute(
                "ALTER TABLE workspace_ai_jobs ADD COLUMN assistant_thread_id TEXT REFERENCES assistant_threads(id)"
            )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assistant_threads_work_history "
            "ON assistant_threads(work_id, pinned_at DESC, updated_at DESC, id DESC)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_ai_jobs_task_active "
            "ON workspace_ai_jobs(task_id, status, updated_at DESC)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_ai_jobs_conversation "
            "ON workspace_ai_jobs(conversation_id, assistant_thread_id)"
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


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
    ("0012_idempotency_request_hash", _apply_migration_0012),
    ("0013_telegram_callback_tokens", _TELEGRAM_CALLBACK_TOKENS_SQL),
    ("0014_skill_versions", _apply_migration_0014),
    ("0015_dirap_source_files", _DIRAP_SOURCE_FILES_SQL),
    ("0016_dirap_extractions", _DIRAP_EXTRACTIONS_SQL),
    ("0017_dirap_knowledge_records", _DIRAP_KNOWLEDGE_RECORDS_SQL),
    ("0018_dirap_knowledge_review", _DIRAP_KNOWLEDGE_REVIEW_SQL),
    ("0019_dirap_knowledge_review_contract_fix", _DIRAP_KNOWLEDGE_REVIEW_CONTRACT_FIX_SQL),
    ("0020_memory_hub", _MEMORY_HUB_SQL),
    ("0021_memory_hub_contract_closure", _apply_migration_0021_memory_hub_contract_closure),
    ("0022_security_integrity", _apply_migration_0022_security_integrity),
    ("0023_end_user_work", _apply_migration_0023_end_user_work),
    ("0024_artifacts_and_operation_claims", _apply_migration_0024_artifacts_and_operation_claims),
    ("0025_work_conversations", _apply_migration_0025_work_conversations),
    ("0026_assistant_actions_marketplace", _apply_migration_0026_assistant_actions_marketplace),
    ("0027_work_data_scope", _apply_migration_0027_work_data_scope),
    ("0028_assistant_conversation_link", _apply_migration_0028_assistant_conversation_link),
    ("0029_gyo_provider_profiles", _apply_migration_0029_gyo_provider_profiles),
    ("0030_work_memory_learning", _apply_migration_0030_work_memory_learning),
    ("0031_gyo_model_routing", _apply_migration_0031_gyo_model_routing),
    ("0032_workspace_tasks", _apply_migration_0032_workspace_tasks),
    ("0033_gyo_v3_action_packages", _apply_migration_0033_gyo_v3_action_packages),
    ("0034_gyo_v3_payload_binding", _apply_migration_0034_gyo_v3_payload_binding),
    ("0035_artifact_structural_validation", _apply_migration_0035_artifact_structural_validation),
    ("0036_gyo_history_workflow_contract", _apply_migration_0036_gyo_history_workflow_contract),
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

            try:
                if isinstance(step, str):
                    await conn.executescript(step)
                else:
                    await step(conn)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (version, int(time.time())),
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
            logger.info("Migration %s applied.", version)
    finally:
        await conn.close()
