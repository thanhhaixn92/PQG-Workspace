from __future__ import annotations

import time
from pathlib import Path

from app.db.connection import get_db_connection
from app.services.audit import log_audit_event


STALE_TASK_SECONDS = 10 * 60
STALE_STATUSES = ("queued", "running", "waiting_approval")


async def recover_stale_task_runs(db_path: Path, max_age_seconds: int = STALE_TASK_SECONDS) -> int:
    """Mark old in-flight task runs as failed after backend restart."""
    now = int(time.time())
    cutoff = now - max_age_seconds
    recovered = 0

    async with get_db_connection(db_path) as db:
        async with db.execute(
            """
            SELECT id, session_id, status
            FROM task_runs
            WHERE status IN ('queued', 'running', 'waiting_approval')
              AND started_at < ?
            """,
            (cutoff,),
        ) as cur:
            rows = await cur.fetchall()

        for row in rows:
            task_id, session_id, old_status = row
            await db.execute(
                """
                UPDATE task_runs
                SET status = 'failed', error = ?, finished_at = ?
                WHERE id = ?
                """,
                ("Recovered stale task after backend restart.", now, task_id),
            )
            await log_audit_event(
                db,
                session_id,
                "system",
                "task_run.recovered_stale",
                target=task_id,
                payload={"old_status": old_status, "max_age_seconds": max_age_seconds},
            )
            recovered += 1

        if recovered:
            await db.commit()

    return recovered
