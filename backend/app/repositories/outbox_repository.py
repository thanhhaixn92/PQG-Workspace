from __future__ import annotations

import uuid
import time
from typing import Optional

import aiosqlite


class OutboxRepository:

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert(
        self,
        channel: str,
        event_type: str,
        payload_json: str,
        max_attempts: int = 5,
    ) -> str:
        outbox_id = f"out-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await self._db.execute(
            """INSERT INTO notification_outbox (id, channel, event_type, payload_json, status, max_attempts, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (outbox_id, channel, event_type, payload_json, max_attempts, now, now),
        )
        return outbox_id

    async def claim_pending(
        self, worker_id: str, batch_size: int = 10, lease_seconds: int = 30
    ) -> list[dict]:
        now = int(time.time())
        lock_deadline = now - lease_seconds
        await self._db.execute(
            """UPDATE notification_outbox SET locked_at = ?, locked_by = ?
               WHERE id IN (
                   SELECT id FROM notification_outbox
                   WHERE status = 'pending' AND (locked_at IS NULL OR locked_at < ?)
                   LIMIT ?
               )""",
            (now, worker_id, lock_deadline, batch_size),
        )
        async with self._db.execute(
            "SELECT * FROM notification_outbox WHERE locked_by = ? AND locked_at = ?",
            (worker_id, now),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def mark_sent(self, outbox_id: str) -> None:
        now = int(time.time())
        await self._db.execute(
            "UPDATE notification_outbox SET status = 'sent', updated_at = ? WHERE id = ?",
            (now, outbox_id),
        )

    async def mark_retry(self, outbox_id: str, error: str) -> None:
        now = int(time.time())
        await self._db.execute(
            """UPDATE notification_outbox
               SET status = 'retrying', attempt_count = attempt_count + 1, last_error = ?,
                   locked_at = NULL, locked_by = NULL, updated_at = ?
               WHERE id = ?""",
            (error, now, outbox_id),
        )
        await self._check_dead_letter(outbox_id)

    async def mark_dead_letter(self, outbox_id: str, error: str) -> None:
        now = int(time.time())
        await self._db.execute(
            "UPDATE notification_outbox SET status = 'dead_letter', last_error = ?, locked_at = NULL, locked_by = NULL, updated_at = ? WHERE id = ?",
            (error, now, outbox_id),
        )

    async def _check_dead_letter(self, outbox_id: str) -> None:
        async with self._db.execute(
            "SELECT attempt_count, max_attempts FROM notification_outbox WHERE id = ?",
            (outbox_id,),
        ) as cur:
            row = await cur.fetchone()
        if row and row[0] >= row[1]:
            await self.mark_dead_letter(outbox_id, "Max attempts reached")

    async def get_pending_count(self) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM notification_outbox WHERE status IN ('pending', 'retrying')",
        ) as cur:
            row = await cur.fetchone()
        return row[0]
