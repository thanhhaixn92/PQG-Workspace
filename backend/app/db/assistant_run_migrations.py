"""Durable Assistant run migration for R1.

Migration 0038 is additive. It keeps ``assistant_turns`` as the user-visible
history record and adds ``assistant_runs`` as the durable execution owner.
"""
from __future__ import annotations

import aiosqlite


async def apply_0038_durable_assistant_runs(conn: aiosqlite.Connection) -> None:
    """Add lease-backed durable execution state for GYO Assistant runs."""
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS assistant_runs (
            id TEXT PRIMARY KEY,
            assistant_turn_id TEXT NOT NULL UNIQUE
                REFERENCES assistant_turns(id) ON DELETE CASCADE,
            user_turn_id TEXT REFERENCES assistant_turns(id) ON DELETE SET NULL,
            thread_id TEXT NOT NULL REFERENCES assistant_threads(id) ON DELETE CASCADE,
            work_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'created' CHECK (status IN (
                'created', 'queued', 'running', 'waiting_input',
                'waiting_approval', 'waiting_external', 'retry_scheduled',
                'cancel_requested', 'completed', 'failed', 'cancelled'
            )),
            requested_model_profile_id TEXT,
            route_mode TEXT NOT NULL DEFAULT 'auto'
                CHECK (route_mode IN ('auto', 'manual')),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            lease_owner TEXT,
            lease_expires_at INTEGER,
            heartbeat_at INTEGER,
            retry_at INTEGER,
            cancel_requested_at INTEGER,
            error_code TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            started_at INTEGER,
            completed_at INTEGER
        )"""
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_runs_queue "
        "ON assistant_runs(status, retry_at, created_at, id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_assistant_runs_turn "
        "ON assistant_runs(assistant_turn_id)"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_runs_one_active_thread "
        "ON assistant_runs(thread_id) WHERE status IN ("
        "'created','queued','running','waiting_input','waiting_approval',"
        "'waiting_external','retry_scheduled','cancel_requested')"
    )

    # Preserve an in-flight legacy response across an upgrade/restart. The
    # nearest preceding user turn is a durable source for prompt/attachments.
    # Existing invariants allow only one running Assistant response per thread;
    # the MAX(rowid) guard stays fail-closed if malformed historical data has
    # more than one.
    await conn.execute(
        """INSERT OR IGNORE INTO assistant_runs (
            id, assistant_turn_id, user_turn_id, thread_id, work_id,
            conversation_id, status, requested_model_profile_id, route_mode,
            attempt_count, created_at, updated_at
        )
        SELECT
            turn.id,
            turn.id,
            (
                SELECT user_turn.id
                FROM assistant_turns AS user_turn
                WHERE user_turn.thread_id = turn.thread_id
                  AND user_turn.role = 'user'
                  AND user_turn.rowid < turn.rowid
                ORDER BY user_turn.rowid DESC
                LIMIT 1
            ),
            turn.thread_id,
            turn.work_id,
            turn.conversation_id,
            'queued',
            NULL,
            'auto',
            0,
            turn.created_at,
            turn.created_at
        FROM assistant_turns AS turn
        WHERE turn.role = 'assistant'
          AND turn.status = 'running'
          AND turn.rowid = (
              SELECT MAX(candidate.rowid)
              FROM assistant_turns AS candidate
              WHERE candidate.thread_id = turn.thread_id
                AND candidate.role = 'assistant'
                AND candidate.status = 'running'
          )"""
    )
