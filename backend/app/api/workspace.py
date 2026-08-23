"""Workspace v2.4 task dashboard routes.

This user-facing Task domain deliberately remains separate from the legacy
operational ``tasks`` API and is always scoped to one Work/session.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.api.schemas import (
    WorkspaceAiJobResponse, WorkspaceDashboardResponse, WorkspaceTaskCreateRequest,
    WorkspaceTaskResponse, WorkspaceTaskUpdateRequest,
)
from app.dependencies import get_db, get_trusted_actor
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyFailed, IdempotencyInProgress, IdempotencyRepository
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


async def _require_active_work(conn: aiosqlite.Connection, work_id: str) -> aiosqlite.Row:
    async with conn.execute("SELECT id, title, archived FROM sessions WHERE id = ?", (work_id,)) as cur:
        work = await cur.fetchone()
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    if work["archived"]:
        raise HTTPException(status_code=409, detail="Work is archived")
    return work


async def _task_row(conn: aiosqlite.Connection, task_id: str) -> aiosqlite.Row:
    async with conn.execute(
        """SELECT task.*, work.title AS work_title FROM workspace_tasks task
           JOIN sessions work ON work.id = task.session_id WHERE task.id = ?""", (task_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace task not found")
    return row


def _task_response(row: aiosqlite.Row | dict[str, Any]) -> WorkspaceTaskResponse:
    return WorkspaceTaskResponse(**dict(row))


def _payload_hash(request: WorkspaceTaskCreateRequest) -> str:
    return hashlib.sha256(json.dumps(request.model_dump(), sort_keys=True).encode()).hexdigest()


@router.post("/tasks", response_model=WorkspaceTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace_task(
    request: WorkspaceTaskCreateRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkspaceTaskResponse:
    await _require_active_work(conn, request.session_id)
    payload_hash = _payload_hash(request)
    claim: dict[str, Any] | None = None
    if idempotency_key:
        try:
            claim, inserted = await IdempotencyRepository(conn).claim_operation(
                actor="user", operation="workspace_task.create", scope=request.session_id,
                client_key=idempotency_key, request_hash=payload_hash,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not inserted:
            if claim["state"] == "completed":
                response.status_code = status.HTTP_200_OK
                return WorkspaceTaskResponse(**json.loads(claim["response_json"]))
            if claim["state"] == "processing":
                raise HTTPException(status_code=409, detail="Task creation is already in progress")
            raise HTTPException(status_code=409, detail="A previous request failed; use a new idempotency key")
    now = int(time.time()); task_id = f"workspace-task-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """INSERT INTO workspace_tasks
           (id, session_id, title, description, priority, impact, due_at, estimate_minutes, ai_eligibility, ai_reason, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, request.session_id, request.title, request.description, request.priority, request.impact,
         request.due_at, request.estimate_minutes, request.ai_eligibility, request.ai_reason, now, now),
    )
    row = await _task_row(conn, task_id); item = _task_response(row)
    await log_audit_event(conn, request.session_id, "user", "workspace_task.created", task_id, {"ai_eligibility": request.ai_eligibility}, commit=False)
    if claim is not None:
        try:
            await IdempotencyRepository(conn).finalize_operation(claim, response=item.model_dump(), status_code=201, resource_id=task_id)
        except (IdempotencyConflict, IdempotencyFailed, IdempotencyInProgress) as exc:
            await conn.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        await conn.commit()
    return item


@router.patch("/tasks/{task_id}", response_model=WorkspaceTaskResponse)
async def update_workspace_task(task_id: str, request: WorkspaceTaskUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> WorkspaceTaskResponse:
    current = await _task_row(conn, task_id)
    await _require_active_work(conn, current["session_id"])
    if current["version"] != request.version:
        raise HTTPException(status_code=409, detail="Task changed elsewhere; refresh before saving")
    updates: list[str] = []; params: list[Any] = []
    for name, value in request.model_dump(exclude={"version"}, exclude_unset=True).items():
        if name == "title" and value is not None:
            value = " ".join(value.split())
            if not value:
                raise HTTPException(status_code=422, detail="Task title cannot be empty")
        updates.append(f"{name} = ?"); params.append(value)
    if not updates:
        return _task_response(current)
    now = int(time.time()); updates.extend(["version = version + 1", "updated_at = ?"]); params.extend([now, task_id, request.version])
    cursor = await conn.execute(
        f"UPDATE workspace_tasks SET {', '.join(updates)} WHERE id = ? AND version = ?", params
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="Task changed elsewhere; refresh before saving")
    await log_audit_event(conn, current["session_id"], "user", "workspace_task.updated", task_id, {"fields": sorted(request.model_fields_set - {"version"})})
    await conn.commit()
    return _task_response(await _task_row(conn, task_id))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_task(task_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> Response:
    current = await _task_row(conn, task_id)
    await _require_active_work(conn, current["session_id"])
    await conn.execute("DELETE FROM workspace_tasks WHERE id = ?", (task_id,))
    await log_audit_event(conn, current["session_id"], "user", "workspace_task.deleted", task_id, {})
    await conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _ai_job_response(conn: aiosqlite.Connection, job_id: str) -> WorkspaceAiJobResponse:
    async with conn.execute(
        """SELECT job.*, task.title AS task_title, task.session_id, work.title AS work_title
           FROM workspace_ai_jobs job JOIN workspace_tasks task ON task.id = job.task_id
           JOIN sessions work ON work.id = task.session_id WHERE job.id = ?""",
        (job_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace AI job not found")
    return WorkspaceAiJobResponse(**dict(row))


@router.post("/tasks/{task_id}/ai-jobs", response_model=WorkspaceAiJobResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace_ai_job(
    task_id: str,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    actor: str = Depends(get_trusted_actor),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkspaceAiJobResponse:
    """Idempotently resolve a canonical Work conversation and GYO thread.

    A task hand-off is an entry into the existing assistant boundary, not an
    execution request. The client only receives opaque, server-resolved IDs.
    """
    task = await _task_row(conn, task_id)
    await _require_active_work(conn, task["session_id"])
    if task["ai_eligibility"] == "human_only":
        raise HTTPException(status_code=409, detail="This task must remain human-led")
    claim: dict[str, Any] | None = None
    if idempotency_key:
        request_hash = hashlib.sha256(json.dumps({"task_id": task_id}, sort_keys=True).encode()).hexdigest()
        try:
            claim, inserted = await IdempotencyRepository(conn).claim_operation(
                actor=actor, operation="workspace_ai_job.create", scope=task["session_id"],
                client_key=idempotency_key, request_hash=request_hash,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not inserted:
            if claim["state"] == "completed" and claim.get("resource_id"):
                response.status_code = status.HTTP_200_OK
                return await _ai_job_response(conn, claim["resource_id"])
            if claim["state"] == "processing":
                raise HTTPException(status_code=409, detail="GYO hand-off is already in progress")
            raise HTTPException(status_code=409, detail="A previous hand-off failed; use a new idempotency key")
    try:
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute(
            """SELECT * FROM workspace_ai_jobs WHERE task_id = ?
               AND status IN ('queued', 'running', 'waiting_user')
               ORDER BY updated_at DESC, id DESC LIMIT 1""",
            (task_id,),
        ) as cur:
            job = await cur.fetchone()
        now = int(time.time())
        if job is None:
            result_status = status.HTTP_201_CREATED
            job_id = f"workspace-ai-{uuid.uuid4().hex[:16]}"
            conversation_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO conversations (id, session_id, title, purpose, status, created_at, updated_at, last_opened_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                (conversation_id, task["session_id"], f"GYO — {task['title'][:120]}", "GYO task hand-off", now, now, now),
            )
            thread_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO assistant_threads (id, title, work_id, conversation_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (thread_id, "GYO Thread", task["session_id"], conversation_id, now, now),
            )
            await conn.execute(
                """INSERT INTO workspace_ai_jobs
                   (id, task_id, conversation_id, assistant_thread_id, status, stage_text, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'waiting_user', ?, ?, ?)""",
                (job_id, task_id, conversation_id, thread_id, "Sẵn sàng nhận yêu cầu cho GYO.", now, now),
            )
        else:
            result_status = status.HTTP_200_OK
            job_id = job["id"]
            conversation_id = job["conversation_id"]
            thread_id = job["assistant_thread_id"]
            # 0036 leaves legacy jobs unbound. Bind them only to a new canonical
            # conversation/thread instead of guessing from unrelated history.
            if not conversation_id or not thread_id:
                conversation_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO conversations (id, session_id, title, purpose, status, created_at, updated_at, last_opened_at)
                       VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (conversation_id, task["session_id"], f"GYO — {task['title'][:120]}", "GYO task hand-off", now, now, now),
                )
                thread_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO assistant_threads (id, title, work_id, conversation_id, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                    (thread_id, "GYO Thread", task["session_id"], conversation_id, now, now),
                )
                await conn.execute(
                    "UPDATE workspace_ai_jobs SET conversation_id = ?, assistant_thread_id = ?, updated_at = ? WHERE id = ?",
                    (conversation_id, thread_id, now, job_id),
                )
            response.status_code = result_status
        await log_audit_event(
            conn, task["session_id"], actor, "workspace_task.gyo_handoff_requested", job_id,
            {"task_id": task_id, "conversation_id": conversation_id, "assistant_thread_id": thread_id}, commit=False,
        )
        await conn.commit()
        item = await _ai_job_response(conn, job_id)
        if claim is not None:
            await IdempotencyRepository(conn).finalize_operation(
                claim, response=item.model_dump(), status_code=result_status, resource_id=job_id,
            )
        return item
    except Exception:
        await conn.rollback()
        if claim is not None:
            await IdempotencyRepository(conn).fail_operation(claim, "workspace_ai_job_create_failed")
        raise


async def _dashboard_tasks(conn: aiosqlite.Connection, where: str = "1=1", params: tuple[Any, ...] = ()) -> list[WorkspaceTaskResponse]:
    async with conn.execute(
        f"""SELECT task.*, work.title AS work_title FROM workspace_tasks task
             JOIN sessions work ON work.id = task.session_id
             WHERE work.archived = 0 AND {where}
             ORDER BY task.priority DESC, task.impact DESC, task.due_at IS NULL, task.due_at, task.updated_at DESC""", params
    ) as cur:
        return [_task_response(row) for row in await cur.fetchall()]


@router.get("/today", response_model=WorkspaceDashboardResponse)
async def workspace_today(conn: aiosqlite.Connection = Depends(get_db)) -> WorkspaceDashboardResponse:
    tasks = await _dashboard_tasks(conn, "task.status NOT IN ('done', 'cancelled')")
    recommendation = tasks[0] if tasks else None
    attention: list[dict[str, Any]] = []
    for task in tasks:
        if task.status == "blocked":
            attention.append({"id": f"task:{task.id}:blocked", "type": "blocked", "task_id": task.id, "title": task.title, "detail": task.blocked_reason or "Task đang bị chặn"})
        elif task.due_at and task.due_at < int(time.time()):
            attention.append({"id": f"task:{task.id}:overdue", "type": "overdue", "task_id": task.id, "title": task.title, "detail": "Đã quá hạn"})
        if len(attention) == 3:
            break
    reason = None if recommendation is None else "Ưu tiên theo mức độ ưu tiên, tác động và hạn hoàn thành."
    return WorkspaceDashboardResponse(generated_at=int(time.time()), recommendation=recommendation, recommendation_reason=reason, alternatives=tasks[1:6], timeline=tasks[:7], attention_items=attention)


@router.get("/upcoming", response_model=list[WorkspaceTaskResponse])
async def workspace_upcoming(conn: aiosqlite.Connection = Depends(get_db)) -> list[WorkspaceTaskResponse]:
    return await _dashboard_tasks(conn, "task.status NOT IN ('done', 'cancelled')")


@router.get("/history", response_model=list[WorkspaceTaskResponse])
async def workspace_history(conn: aiosqlite.Connection = Depends(get_db)) -> list[WorkspaceTaskResponse]:
    return await _dashboard_tasks(conn, "task.status IN ('done', 'cancelled')")


@router.get("/ai-jobs", response_model=list[WorkspaceAiJobResponse])
async def workspace_ai_jobs(conn: aiosqlite.Connection = Depends(get_db)) -> list[WorkspaceAiJobResponse]:
    async with conn.execute(
        """SELECT job.*, task.title AS task_title, task.session_id, work.title AS work_title
           FROM workspace_ai_jobs job JOIN workspace_tasks task ON task.id = job.task_id
           JOIN sessions work ON work.id = task.session_id WHERE work.archived = 0
           ORDER BY job.updated_at DESC"""
    ) as cur:
        return [WorkspaceAiJobResponse(**dict(row)) for row in await cur.fetchall()]
