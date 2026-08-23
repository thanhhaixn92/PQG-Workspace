"""Durable Assistant run queue, lease and recovery primitives.

This service owns execution lifetime. SSE remains a delivery mechanism only;
``assistant_runs`` is authoritative across request disconnects and restarts.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import aiosqlite

from app.db.connection import get_db_connection
from app.services.audit import log_audit_event
from app.settings import Settings


RUN_LEASE_SECONDS = 30
RUN_HEARTBEAT_SECONDS = 5
RUN_EXECUTION_TIMEOUT_SECONDS = 10 * 60
ACTIVE_RUN_STATUSES = frozenset(
    {
        "created",
        "queued",
        "running",
        "waiting_input",
        "waiting_approval",
        "waiting_external",
        "retry_scheduled",
        "cancel_requested",
    }
)
TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class AssistantRunClaim:
    id: str
    assistant_turn_id: str
    user_turn_id: str | None
    thread_id: str
    work_id: str | None
    conversation_id: str | None
    requested_model_profile_id: str | None
    route_mode: str
    attempt_count: int


RunExecutor = Callable[[AssistantRunClaim], Awaitable[None]]


def run_public_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Return safe run state without lease-owner or internal error details."""
    return {
        "id": row["id"],
        "assistant_turn_id": row["assistant_turn_id"],
        "user_turn_id": row["user_turn_id"],
        "thread_id": row["thread_id"],
        "work_id": row["work_id"],
        "conversation_id": row["conversation_id"],
        "status": row["status"],
        "route_mode": row["route_mode"],
        "attempt_count": row["attempt_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "cancel_requested_at": row["cancel_requested_at"],
        "retry_at": row["retry_at"],
        "error_code": row["error_code"],
    }


async def get_assistant_run(
    conn: aiosqlite.Connection,
    *,
    run_id: str | None = None,
    assistant_turn_id: str | None = None,
) -> aiosqlite.Row | None:
    if bool(run_id) == bool(assistant_turn_id):
        raise ValueError("Provide exactly one run identifier")
    if run_id is not None:
        query, value = "SELECT * FROM assistant_runs WHERE id = ?", run_id
    else:
        query, value = "SELECT * FROM assistant_runs WHERE assistant_turn_id = ?", assistant_turn_id
    async with conn.execute(query, (value,)) as cur:
        return await cur.fetchone()


async def enqueue_assistant_run(
    conn: aiosqlite.Connection,
    *,
    assistant_turn_id: str,
    user_turn_id: str | None,
    thread_id: str,
    work_id: str | None,
    conversation_id: str | None,
    requested_model_profile_id: str | None,
    route_mode: str,
    now: int,
) -> str:
    """Persist one queued run. The partial unique index enforces one active run/thread."""
    run_id = assistant_turn_id
    await conn.execute(
        """INSERT INTO assistant_runs (
            id, assistant_turn_id, user_turn_id, thread_id, work_id,
            conversation_id, status, requested_model_profile_id, route_mode,
            attempt_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, 0, ?, ?)""",
        (
            run_id,
            assistant_turn_id,
            user_turn_id,
            thread_id,
            work_id,
            conversation_id,
            requested_model_profile_id,
            route_mode,
            now,
            now,
        ),
    )
    return run_id


async def request_assistant_run_cancel(
    conn: aiosqlite.Connection,
    *,
    assistant_turn_id: str,
    now: int,
) -> aiosqlite.Row | None:
    """Move an active durable run to cancel_requested without claiming compute stopped."""
    row = await get_assistant_run(conn, assistant_turn_id=assistant_turn_id)
    if row is None:
        return None
    if row["status"] in TERMINAL_RUN_STATUSES:
        return row
    if row["status"] != "cancel_requested":
        updated = await conn.execute(
            """UPDATE assistant_runs
               SET status = 'cancel_requested', cancel_requested_at = ?, updated_at = ?
               WHERE id = ? AND status IN (
                   'created','queued','running','waiting_input','waiting_approval',
                   'waiting_external','retry_scheduled'
               )""",
            (now, now, row["id"]),
        )
        if updated.rowcount != 1:
            return await get_assistant_run(conn, run_id=row["id"])
    return await get_assistant_run(conn, run_id=row["id"])


async def is_cancel_requested(db_path, run_id: str) -> bool:
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT status FROM assistant_runs WHERE id = ?", (run_id,)) as cur:
            row = await cur.fetchone()
        return row is not None and row["status"] == "cancel_requested"


async def _claim_run(
    settings: Settings,
    worker_id: str,
    *,
    run_id: str | None = None,
) -> AssistantRunClaim | None:
    now = int(time.time())
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            where = "status = 'queued'"
            params: list[Any] = []
            if run_id is not None:
                where += " AND id = ?"
                params.append(run_id)
            async with conn.execute(
                f"SELECT * FROM assistant_runs WHERE {where} ORDER BY created_at, id LIMIT 1",
                params,
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                await conn.rollback()
                return None
            updated = await conn.execute(
                """UPDATE assistant_runs
                   SET status = 'running', lease_owner = ?, lease_expires_at = ?,
                       heartbeat_at = ?, started_at = COALESCE(started_at, ?),
                       attempt_count = attempt_count + 1, updated_at = ?
                   WHERE id = ? AND status = 'queued'""",
                (worker_id, now + RUN_LEASE_SECONDS, now, now, now, row["id"]),
            )
            if updated.rowcount != 1:
                await conn.rollback()
                return None
            await log_audit_event(
                conn,
                row["work_id"],
                "system",
                "assistant.run.started",
                target=row["id"],
                payload={"attempt": row["attempt_count"] + 1},
                commit=False,
            )
            await conn.commit()
            return AssistantRunClaim(
                id=row["id"],
                assistant_turn_id=row["assistant_turn_id"],
                user_turn_id=row["user_turn_id"],
                thread_id=row["thread_id"],
                work_id=row["work_id"],
                conversation_id=row["conversation_id"],
                requested_model_profile_id=row["requested_model_profile_id"],
                route_mode=row["route_mode"],
                attempt_count=row["attempt_count"] + 1,
            )
        except Exception:
            await conn.rollback()
            raise


async def _heartbeat(settings: Settings, worker_id: str, run_id: str, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=RUN_HEARTBEAT_SECONDS)
            break
        except asyncio.TimeoutError:
            pass
        now = int(time.time())
        async with get_db_connection(settings.db_path_resolved) as conn:
            updated = await conn.execute(
                """UPDATE assistant_runs
                   SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                   WHERE id = ? AND status = 'running' AND lease_owner = ?""",
                (now, now + RUN_LEASE_SECONDS, now, run_id, worker_id),
            )
            await conn.commit()
        if updated.rowcount != 1:
            return


async def _ensure_cancel_part(conn: aiosqlite.Connection, assistant_turn_id: str, now: int) -> None:
    async with conn.execute(
        "SELECT 1 FROM assistant_turn_parts WHERE turn_id = ? LIMIT 1",
        (assistant_turn_id,),
    ) as cur:
        if await cur.fetchone() is not None:
            return
    message = "Bạn đã hủy phản hồi này. Nội dung đến muộn sẽ không được lưu hoặc hiển thị."
    await conn.execute(
        """INSERT INTO assistant_turn_parts
           (id, turn_id, part_type, content_json, sort_order, created_at)
           VALUES (?, ?, 'error', ?, 0, ?)""",
        (
            str(uuid.uuid4()),
            assistant_turn_id,
            json.dumps({"text": message, "message": message}),
            now,
        ),
    )


async def _finalize_cancel_row(conn: aiosqlite.Connection, row: aiosqlite.Row, now: int) -> None:
    message = "Bạn đã hủy phản hồi này. Nội dung đến muộn sẽ không được lưu hoặc hiển thị."
    await conn.execute(
        """UPDATE assistant_turns
           SET status = 'cancelled', completed_at = ?, error = ?
           WHERE id = ? AND status = 'running'""",
        (now, message, row["assistant_turn_id"]),
    )
    await _ensure_cancel_part(conn, row["assistant_turn_id"], now)
    await conn.execute(
        "UPDATE assistant_threads SET updated_at = ? WHERE id = ?",
        (now, row["thread_id"]),
    )
    await conn.execute(
        """UPDATE assistant_runs
           SET status = 'cancelled', completed_at = ?, updated_at = ?,
               lease_owner = NULL, lease_expires_at = NULL, heartbeat_at = ?
           WHERE id = ? AND status = 'cancel_requested'""",
        (now, now, now, row["id"]),
    )
    await log_audit_event(
        conn,
        row["work_id"],
        "system",
        "assistant.run.cancelled",
        target=row["id"],
        payload={"local_terminal": True, "remote_compute_stop_proven": False},
        commit=False,
    )


async def finalize_cancel_requested_runs(settings: Settings) -> int:
    """Finalize cancellation once no live lease can still own local completion."""
    now = int(time.time())
    finalized = 0
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute(
                """SELECT * FROM assistant_runs
                   WHERE status = 'cancel_requested'
                     AND (lease_owner IS NULL OR lease_expires_at IS NULL OR lease_expires_at < ?)
                   ORDER BY updated_at, id""",
                (now,),
            ) as cur:
                rows = await cur.fetchall()
            for row in rows:
                await _finalize_cancel_row(conn, row, now)
                finalized += 1
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    return finalized


async def recover_stale_assistant_runs(settings: Settings) -> int:
    """Requeue expired running leases so a restart can continue the durable run."""
    now = int(time.time())
    recovered = 0
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute(
                """SELECT * FROM assistant_runs
                   WHERE status = 'running'
                     AND lease_expires_at IS NOT NULL
                     AND lease_expires_at < ?
                   ORDER BY lease_expires_at, id""",
                (now,),
            ) as cur:
                rows = await cur.fetchall()
            for row in rows:
                updated = await conn.execute(
                    """UPDATE assistant_runs
                       SET status = 'queued', lease_owner = NULL,
                           lease_expires_at = NULL, updated_at = ?
                       WHERE id = ? AND status = 'running'
                         AND lease_expires_at < ?""",
                    (now, row["id"], now),
                )
                if updated.rowcount != 1:
                    continue
                await log_audit_event(
                    conn,
                    row["work_id"],
                    "system",
                    "assistant.run.recovered",
                    target=row["id"],
                    payload={"attempt_count": row["attempt_count"]},
                    commit=False,
                )
                recovered += 1
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    return recovered


async def _mark_run_failed(settings: Settings, claim: AssistantRunClaim, error_code: str) -> None:
    now = int(time.time())
    failure_text = "Trợ lý GYO không thể hoàn tất yêu cầu này. Không có thay đổi nào được thực hiện."
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT * FROM assistant_runs WHERE id = ?", (claim.id,)) as cur:
                row = await cur.fetchone()
            if row is None:
                await conn.rollback()
                return
            if row["status"] == "cancel_requested":
                await _finalize_cancel_row(conn, row, now)
            elif row["status"] == "running":
                await conn.execute(
                    """UPDATE assistant_turns
                       SET status = 'failed', completed_at = ?, error = ?
                       WHERE id = ? AND status = 'running'""",
                    (now, failure_text, claim.assistant_turn_id),
                )
                async with conn.execute(
                    "SELECT 1 FROM assistant_turn_parts WHERE turn_id = ? LIMIT 1",
                    (claim.assistant_turn_id,),
                ) as cur:
                    has_parts = await cur.fetchone() is not None
                if not has_parts:
                    await conn.execute(
                        """INSERT INTO assistant_turn_parts
                           (id, turn_id, part_type, content_json, sort_order, created_at)
                           VALUES (?, ?, 'error', ?, 0, ?)""",
                        (
                            str(uuid.uuid4()),
                            claim.assistant_turn_id,
                            json.dumps({"text": failure_text, "message": failure_text}),
                            now,
                        ),
                    )
                await conn.execute(
                    """UPDATE assistant_runs
                       SET status = 'failed', error_code = ?, completed_at = ?,
                           updated_at = ?, lease_owner = NULL, lease_expires_at = NULL
                       WHERE id = ? AND status = 'running'""",
                    (error_code, now, now, claim.id),
                )
                await log_audit_event(
                    conn,
                    claim.work_id,
                    "system",
                    "assistant.run.failed",
                    target=claim.id,
                    payload={"error_code": error_code, "attempt": claim.attempt_count},
                    commit=False,
                )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def _reconcile_claim_result(settings: Settings, claim: AssistantRunClaim) -> str:
    now = int(time.time())
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT * FROM assistant_runs WHERE id = ?", (claim.id,)) as cur:
                run = await cur.fetchone()
            if run is None:
                await conn.rollback()
                return "missing"
            if run["status"] == "cancel_requested":
                await _finalize_cancel_row(conn, run, now)
                await conn.commit()
                return "cancelled"
            async with conn.execute(
                "SELECT status FROM assistant_turns WHERE id = ?",
                (claim.assistant_turn_id,),
            ) as cur:
                turn = await cur.fetchone()
            turn_status = turn["status"] if turn is not None else None
            if run["status"] != "running":
                await conn.rollback()
                return run["status"]
            if turn_status not in TERMINAL_RUN_STATUSES:
                await conn.rollback()
                return "running"
            await conn.execute(
                """UPDATE assistant_runs
                   SET status = ?, completed_at = ?, updated_at = ?,
                       lease_owner = NULL, lease_expires_at = NULL, heartbeat_at = ?
                   WHERE id = ? AND status = 'running'""",
                (turn_status, now, now, now, claim.id),
            )
            await log_audit_event(
                conn,
                claim.work_id,
                "system",
                f"assistant.run.{turn_status}",
                target=claim.id,
                payload={"attempt": claim.attempt_count},
                commit=False,
            )
            await conn.commit()
            return turn_status
        except Exception:
            await conn.rollback()
            raise


async def execute_one_assistant_run(
    settings: Settings,
    worker_id: str,
    executor: RunExecutor,
    *,
    run_id: str | None = None,
) -> bool:
    """Claim and execute one durable run, with heartbeat and terminal reconciliation."""
    claim = await _claim_run(settings, worker_id, run_id=run_id)
    if claim is None:
        return False
    heartbeat_stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(settings, worker_id, claim.id, heartbeat_stop))
    try:
        await asyncio.wait_for(executor(claim), timeout=RUN_EXECUTION_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await _mark_run_failed(settings, claim, "execution_timeout")
    except Exception:
        await _mark_run_failed(settings, claim, "executor_failed")
    finally:
        heartbeat_stop.set()
        await heartbeat_task
    result = await _reconcile_claim_result(settings, claim)
    if result == "running":
        await _mark_run_failed(settings, claim, "non_terminal_executor")
    return True


async def run_assistant_run_worker_loop(
    settings: Settings,
    stop: asyncio.Event,
    executor: RunExecutor,
) -> None:
    """Continuously recover and execute durable Assistant runs."""
    worker_id = f"assistant-run-{uuid.uuid4()}"
    while not stop.is_set():
        try:
            await recover_stale_assistant_runs(settings)
            await finalize_cancel_requested_runs(settings)
            ran = await execute_one_assistant_run(settings, worker_id, executor)
        except Exception:
            ran = False
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.2 if ran else 1.0)
        except asyncio.TimeoutError:
            pass
