from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import aiosqlite
import pytest

from app.api.assistant_runs import execute_assistant_run_claim
from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.services.assistant_runs import (
    enqueue_assistant_run,
    execute_one_assistant_run,
    finalize_cancel_requested_runs,
    get_assistant_run,
    recover_stale_assistant_runs,
    request_assistant_run_cancel,
)
from app.settings import Settings


async def _bound_thread(client, title: str = "Durable Work") -> tuple[str, dict]:
    work_id = (await client.post("/api/sessions", json={"title": title})).json()["id"]
    conversation = (
        await client.post(
            f"/api/works/{work_id}/conversations",
            json={"title": "Durable conversation"},
        )
    ).json()
    thread = (
        await client.post(
            f"/api/assistant/works/{work_id}/conversations/{conversation['id']}/assistant-thread"
        )
    ).json()
    return work_id, thread


def _settings(db_path) -> Settings:
    return Settings(
        db_path=str(db_path),
        cors_origins=["http://localhost:5173"],
        outbox_dispatcher_enabled=False,
        local_actor_subject="user",
    )


@pytest.mark.asyncio
async def test_migration_0038_is_recorded_and_idempotent(migrated_db_path):
    await run_migrations(migrated_db_path)
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT version FROM schema_migrations WHERE version = '0038_durable_assistant_runs'"
        ) as cur:
            assert (await cur.fetchone())["version"] == "0038_durable_assistant_runs"
        async with db.execute("PRAGMA table_info(assistant_runs)") as cur:
            columns = {row["name"] async for row in cur}
        assert {
            "id",
            "assistant_turn_id",
            "user_turn_id",
            "thread_id",
            "status",
            "attempt_count",
            "lease_owner",
            "lease_expires_at",
            "cancel_requested_at",
        }.issubset(columns)


@pytest.mark.asyncio
async def test_db_enforces_one_active_durable_run_per_thread(client, migrated_db_path):
    work_id, thread = await _bound_thread(client, "Single active")
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        for turn_id in ("active-a", "active-b"):
            await db.execute(
                """INSERT INTO assistant_turns
                   (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
                   VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
                (turn_id, thread["id"], work_id, thread["conversation_id"], now),
            )
        await enqueue_assistant_run(
            db,
            assistant_turn_id="active-a",
            user_turn_id=None,
            thread_id=thread["id"],
            work_id=work_id,
            conversation_id=thread["conversation_id"],
            requested_model_profile_id=None,
            route_mode="auto",
            now=now,
        )
        with pytest.raises(aiosqlite.IntegrityError):
            await enqueue_assistant_run(
                db,
                assistant_turn_id="active-b",
                user_turn_id=None,
                thread_id=thread["id"],
                work_id=work_id,
                conversation_id=thread["conversation_id"],
                requested_model_profile_id=None,
                route_mode="auto",
                now=now,
            )
        await db.rollback()


@pytest.mark.asyncio
async def test_worker_claims_lease_and_reconciles_completed_turn(client, migrated_db_path):
    work_id, thread = await _bound_thread(client, "Lease run")
    now = int(time.time())
    settings = _settings(migrated_db_path)
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
               VALUES ('lease-turn', ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
            (thread["id"], work_id, thread["conversation_id"], now),
        )
        await enqueue_assistant_run(
            db,
            assistant_turn_id="lease-turn",
            user_turn_id=None,
            thread_id=thread["id"],
            work_id=work_id,
            conversation_id=thread["conversation_id"],
            requested_model_profile_id=None,
            route_mode="auto",
            now=now,
        )
        await db.commit()

    async def executor(claim):
        async with get_db_connection(migrated_db_path) as db:
            async with db.execute("SELECT * FROM assistant_runs WHERE id = ?", (claim.id,)) as cur:
                running = await cur.fetchone()
            assert running["status"] == "running"
            assert running["lease_owner"] == "test-worker"
            assert running["lease_expires_at"] > int(time.time())
            await db.execute(
                "UPDATE assistant_turns SET status = 'completed', completed_at = ? WHERE id = ?",
                (int(time.time()), claim.assistant_turn_id),
            )
            await db.commit()

    assert await execute_one_assistant_run(settings, "test-worker", executor, run_id="lease-turn") is True
    async with get_db_connection(migrated_db_path) as db:
        run = await get_assistant_run(db, run_id="lease-turn")
        assert run["status"] == "completed"
        assert run["attempt_count"] == 1
        assert run["lease_owner"] is None


@pytest.mark.asyncio
async def test_stale_running_lease_is_requeued_after_restart(client, migrated_db_path):
    work_id, thread = await _bound_thread(client, "Recover run")
    now = int(time.time())
    settings = _settings(migrated_db_path)
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
               VALUES ('stale-turn', ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
            (thread["id"], work_id, thread["conversation_id"], now),
        )
        await enqueue_assistant_run(
            db,
            assistant_turn_id="stale-turn",
            user_turn_id=None,
            thread_id=thread["id"],
            work_id=work_id,
            conversation_id=thread["conversation_id"],
            requested_model_profile_id=None,
            route_mode="auto",
            now=now,
        )
        await db.execute(
            """UPDATE assistant_runs
               SET status = 'running', lease_owner = 'dead-worker',
                   lease_expires_at = ?, heartbeat_at = ?, attempt_count = 1
               WHERE id = 'stale-turn'""",
            (now - 10, now - 40),
        )
        await db.commit()

    assert await recover_stale_assistant_runs(settings) == 1
    async with get_db_connection(migrated_db_path) as db:
        run = await get_assistant_run(db, run_id="stale-turn")
        assert run["status"] == "queued"
        assert run["lease_owner"] is None
        async with db.execute("SELECT status FROM assistant_turns WHERE id = 'stale-turn'") as cur:
            assert (await cur.fetchone())["status"] == "running"


@pytest.mark.asyncio
async def test_cancel_requested_is_durable_before_local_terminal(client, test_app, migrated_db_path):
    class DelayedGyo:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def stream(self, request):
            self.started.set()
            await self.release.wait()
            yield SimpleNamespace(type="token", data={"text": "late provider text"})
            yield SimpleNamespace(
                type="done",
                data={
                    "text": "late provider text",
                    "status": "completed",
                    "model_id": "late-model",
                    "structured_parts": [],
                    "route_mode": "auto",
                    "selection_reason": "test",
                    "fallback_chain": [],
                },
            )

        async def cancel(self, _turn_id: str) -> str:
            return "cancelled"

    gyo = DelayedGyo()
    test_app.state.gyo_orchestrator = gyo
    # Isolated ASGI tests do not run lifespan. Mark the worker as active so this
    # test can drive the real durable worker explicitly instead of inline mode.
    test_app.state.assistant_run_worker_active = True
    settings = _settings(migrated_db_path)
    work_id, thread = await _bound_thread(client, "Cancel requested")

    created = await client.post(
        f"/api/assistant/threads/{thread['id']}/runs",
        json={"prompt": "Do not keep late output", "work_id": work_id},
    )
    assert created.status_code == 202, created.text
    assistant_turn_id = created.json()[1]["id"]
    initial = await client.get(f"/api/assistant/runs/{assistant_turn_id}")
    assert initial.status_code == 200
    assert initial.json()["status"] == "queued"

    async def executor(claim):
        await execute_assistant_run_claim(claim, gyo_orchestrator=gyo, settings=settings)

    worker = asyncio.create_task(
        execute_one_assistant_run(
            settings,
            "cancel-worker",
            executor,
            run_id=assistant_turn_id,
        )
    )
    await asyncio.wait_for(gyo.started.wait(), timeout=2)

    cancelled = await client.post(f"/api/assistant/turns/{assistant_turn_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "running"
    assert cancelled.json()["run_status"] == "cancel_requested"
    assert cancelled.json()["remote_compute_stop_proven"] is False

    pending = await client.get(f"/api/assistant/runs/{assistant_turn_id}")
    assert pending.json()["status"] == "cancel_requested"
    gyo.release.set()
    await asyncio.wait_for(worker, timeout=3)

    final = await client.get(f"/api/assistant/runs/{assistant_turn_id}")
    assert final.json()["status"] == "cancelled"
    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assistant = next(turn for turn in turns if turn["id"] == assistant_turn_id)
    assert assistant["status"] == "cancelled"
    assert len(assistant["parts"]) == 1
    assert assistant["parts"][0]["part_type"] == "error"
    assert "Nội dung đến muộn" in assistant["parts"][0]["content"]["message"]
    assert "late provider text" not in str(assistant["parts"])


@pytest.mark.asyncio
async def test_queued_cancel_can_finalize_after_restart(client, migrated_db_path):
    work_id, thread = await _bound_thread(client, "Queued cancel")
    now = int(time.time())
    settings = _settings(migrated_db_path)
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
               VALUES ('queued-cancel-turn', ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
            (thread["id"], work_id, thread["conversation_id"], now),
        )
        await enqueue_assistant_run(
            db,
            assistant_turn_id="queued-cancel-turn",
            user_turn_id=None,
            thread_id=thread["id"],
            work_id=work_id,
            conversation_id=thread["conversation_id"],
            requested_model_profile_id=None,
            route_mode="auto",
            now=now,
        )
        requested = await request_assistant_run_cancel(
            db,
            assistant_turn_id="queued-cancel-turn",
            now=now + 1,
        )
        assert requested["status"] == "cancel_requested"
        await db.commit()

    assert await finalize_cancel_requested_runs(settings) == 1
    async with get_db_connection(migrated_db_path) as db:
        run = await get_assistant_run(db, run_id="queued-cancel-turn")
        assert run["status"] == "cancelled"
        async with db.execute("SELECT status FROM assistant_turns WHERE id = 'queued-cancel-turn'") as cur:
            assert (await cur.fetchone())["status"] == "cancelled"
