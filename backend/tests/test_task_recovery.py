from __future__ import annotations

import time

import aiosqlite
import pytest

from app.db.migrations import run_migrations
from app.services.task_recovery import recover_stale_task_runs


@pytest.mark.asyncio
async def test_recover_stale_task_runs_marks_old_inflight_tasks_failed(tmp_path) -> None:
    db_path = tmp_path / "recovery.db"
    await run_migrations(db_path)
    old_started = int(time.time()) - 3600
    fresh_started = int(time.time())

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO sessions (id, title, workspace_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("sess-1", "S1", "/tmp", old_started, old_started),
        )
        await db.execute(
            "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("task-old", "sess-1", "running", old_started),
        )
        await db.execute(
            "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("task-fresh", "sess-1", "running", fresh_started),
        )
        await db.commit()

    recovered = await recover_stale_task_runs(db_path, max_age_seconds=600)
    assert recovered == 1

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT status, error FROM task_runs WHERE id = 'task-old'") as cur:
            assert await cur.fetchone() == ("failed", "Recovered stale task after backend restart.")
        async with db.execute("SELECT status FROM task_runs WHERE id = 'task-fresh'") as cur:
            assert await cur.fetchone() == ("running",)
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE action = 'task_run.recovered_stale'"
        ) as cur:
            assert await cur.fetchone() == ("task_run.recovered_stale", "task-old")
