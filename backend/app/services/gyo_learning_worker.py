"""Durable, proposal-only worker for structured GYO learning candidates."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any

import aiosqlite

from app.api.schemas import CompletedRunEvidence, MemoryLearningCandidateCreate, SkillLearningCandidateCreate
from app.db.connection import get_db_connection
from app.services.audit import log_audit_event
from app.services.learning import create_memory_candidate, create_skill_candidate
from app.settings import Settings

logger = logging.getLogger(__name__)
_DAY_SECONDS = 86_400
_REPEATED_SUCCESS_SECONDS = 30 * _DAY_SECONDS


def _payload_hash(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


async def enqueue_learning_job(
    conn: aiosqlite.Connection,
    *,
    assistant_turn_id: str,
    work_id: str,
    plan_step_id: str,
    memory_scope_id: str,
    candidate: dict[str, Any],
    now: int,
) -> str:
    """Insert a single durable job. Candidate text never reaches audit logs."""
    digest = _payload_hash(candidate)
    async with conn.execute("SELECT id FROM gyo_learning_jobs WHERE assistant_turn_id = ?", (assistant_turn_id,)) as cur:
        if await cur.fetchone() is not None:
            return "duplicate"
    await conn.execute(
        """INSERT INTO gyo_learning_jobs
           (id, assistant_turn_id, work_id, plan_step_id, memory_scope_id, candidate_kind, payload_hash, candidate_json, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (str(uuid.uuid4()), assistant_turn_id, work_id, plan_step_id, memory_scope_id, candidate["kind"],
         digest, json.dumps(candidate, ensure_ascii=False, separators=(",", ":")), now, now),
    )
    await log_audit_event(
        conn, work_id, "gyo", "gyo.learning_job_queued", target=assistant_turn_id,
        payload={"kind": candidate["kind"], "scope_id": memory_scope_id, "payload_hash": digest},
        commit=False,
    )
    return "queued"


async def _set_job(conn: aiosqlite.Connection, job: aiosqlite.Row, status: str, *, candidate_ref: str | None = None, error_code: str | None = None) -> None:
    now = int(time.time())
    await conn.execute(
        "UPDATE gyo_learning_jobs SET status = ?, attempts = attempts + 1, candidate_ref = ?, error_code = ?, updated_at = ? WHERE id = ?",
        (status, candidate_ref, error_code, now, job["id"]),
    )
    await log_audit_event(
        conn, job["work_id"], "gyo", "gyo.learning_job_processed", target=job["assistant_turn_id"],
        payload={"kind": job["candidate_kind"], "scope_id": job["memory_scope_id"], "payload_hash": job["payload_hash"], "outcome": status, "error_code": error_code},
        commit=False,
    )


async def _is_eligible(conn: aiosqlite.Connection, job: aiosqlite.Row) -> str | None:
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (job["work_id"],)) as cur:
        work = await cur.fetchone()
    if work is None or work["archived"]:
        return "work_archived"
    async with conn.execute(
        """SELECT scope.id FROM work_memory_scopes scope
           JOIN work_plan_steps step ON step.id = scope.plan_step_id AND step.session_id = scope.work_id
           WHERE scope.id = ? AND scope.work_id = ? AND scope.plan_step_id = ?
             AND scope.auto_learning_enabled = 1""",
        (job["memory_scope_id"], job["work_id"], job["plan_step_id"]),
    ) as cur:
        if await cur.fetchone() is None:
            return "scope_not_enabled"
    async with conn.execute(
        "SELECT status FROM assistant_turns WHERE id = ? AND work_id = ? AND role = 'assistant'",
        (job["assistant_turn_id"], job["work_id"]),
    ) as cur:
        turn = await cur.fetchone()
    if turn is None or turn["status"] != "completed":
        return "turn_not_completed"
    async with conn.execute(
        """SELECT 1 FROM gyo_learning_jobs WHERE memory_scope_id = ? AND candidate_kind = ?
           AND status = 'created' AND created_at >= ? AND id != ? LIMIT 1""",
        (job["memory_scope_id"], job["candidate_kind"], int(time.time()) - _DAY_SECONDS, job["id"]),
    ) as cur:
        if await cur.fetchone() is not None:
            return "rate_limited"
    async with conn.execute(
        """SELECT 1 FROM gyo_learning_jobs WHERE memory_scope_id = ? AND candidate_kind = ?
           AND payload_hash = ? AND status IN ('pending', 'processing', 'created') AND id != ? LIMIT 1""",
        (job["memory_scope_id"], job["candidate_kind"], job["payload_hash"], job["id"]),
    ) as cur:
        if await cur.fetchone() is not None:
            return "duplicate_payload"
    return None


async def _repeated_turn_ids(conn: aiosqlite.Connection, job: aiosqlite.Row) -> list[str]:
    async with conn.execute(
        """SELECT turn.id FROM assistant_turns turn
           JOIN assistant_turn_contexts context ON context.user_turn_id = turn.id
           WHERE turn.work_id = ? AND turn.role = 'assistant' AND turn.status = 'completed'
             AND context.memory_scope_id = ? AND turn.created_at >= ?
           ORDER BY turn.created_at DESC, turn.rowid DESC LIMIT 2""",
        (job["work_id"], job["memory_scope_id"], int(time.time()) - _REPEATED_SUCCESS_SECONDS),
    ) as cur:
        ids = [row["id"] for row in await cur.fetchall()]
    return ids if len(ids) >= 2 and job["assistant_turn_id"] in ids else []


async def process_pending_learning_jobs(settings: Settings, *, limit: int = 10) -> int:
    """Claim and process bounded jobs; safe to call repeatedly after restart."""
    processed = 0
    async with get_db_connection(settings.db_path_resolved) as conn:
        # A previous local process may have stopped after claiming a job.
        await conn.execute("UPDATE gyo_learning_jobs SET status = 'pending' WHERE status = 'processing'")
        await conn.commit()
        async with conn.execute(
            "SELECT * FROM gyo_learning_jobs WHERE status = 'pending' ORDER BY created_at LIMIT ?", (limit,)
        ) as cur:
            jobs = await cur.fetchall()
        for job in jobs:
            update = await conn.execute(
                "UPDATE gyo_learning_jobs SET status = 'processing', updated_at = ? WHERE id = ? AND status = 'pending'",
                (int(time.time()), job["id"]),
            )
            if update.rowcount != 1:
                continue
            reason = await _is_eligible(conn, job)
            if reason:
                await _set_job(conn, job, "skipped", error_code=reason)
                await conn.commit(); processed += 1
                continue
            try:
                candidate = json.loads(job["candidate_json"])
                evidence_ids = [job["assistant_turn_id"]]
                if job["candidate_kind"] == "skill":
                    evidence_ids = await _repeated_turn_ids(conn, job)
                    if not evidence_ids:
                        await _set_job(conn, job, "skipped", error_code="insufficient_repeated_success")
                        await conn.commit(); processed += 1
                        continue
                    result = await create_skill_candidate(conn, SkillLearningCandidateCreate(
                        evidence=CompletedRunEvidence(work_id=job["work_id"], task_id=job["memory_scope_id"], assistant_turn_ids=evidence_ids),
                        basis="repeated_success", name=candidate["name"].strip(),
                        description=candidate.get("description"), content=candidate["content"].strip(),
                    ))
                    reference = result.id
                else:
                    result = await create_memory_candidate(conn, MemoryLearningCandidateCreate(
                        evidence=CompletedRunEvidence(work_id=job["work_id"], task_id=job["memory_scope_id"], assistant_turn_ids=evidence_ids),
                        kind=candidate["memory_kind"], memory_key=candidate["memory_key"].strip(),
                        content=candidate["content"].strip(), confidence=float(candidate.get("confidence", 0.5)), sensitivity="normal",
                    ))
                    reference = result["id"]
            except Exception:
                logger.exception("GYO learning job failed safely")
                await _set_job(conn, job, "failed", error_code="candidate_rejected")
            else:
                await _set_job(conn, job, "created", candidate_ref=reference)
            await conn.commit(); processed += 1
    return processed


async def run_gyo_learning_worker_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_pending_learning_jobs(settings)
        except Exception:
            logger.exception("GYO learning worker loop failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except TimeoutError:
            pass
