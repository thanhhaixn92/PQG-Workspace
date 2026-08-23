"""End-user Work Hub API.

The underlying ``sessions`` identifier is retained for compatibility.  New
clients call it a Work and address conversations explicitly, so one project
can contain several independent exchanges with Trợ lý GYO.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    ChatMessagePageResponse, ChatMessageResponse, ConversationCreateRequest,
    ConversationResponse, ConversationUpdateRequest, PromptRequest,
    SessionResponse, TaskRunResponse, WorkCompletionResponse,
    WorkContextSummaryResponse, WorkDashboardResponse, WorkPlanPhaseCreateRequest,
    WorkPlanPhaseResponse, WorkPlanPhaseUpdateRequest, WorkPlanStepCreateRequest, WorkPlanStepResponse,
    WorkPlanStepUpdateRequest, WorkUpdateRequest, WorkMemoryContextResponse, WorkMemoryContextUpdateRequest,
)
from app.api.sessions import _submit_prompt_for_conversation
from app.dependencies import get_db, get_gyo_orchestrator, get_settings
from app.services.gyo_orchestrator import GyoOrchestrator
from app.services.audit import log_audit_event
from app.services.work_memory_scope import get_work_memory_scope, scope_summary, update_work_memory_scope
from app.settings import Settings

router = APIRouter(prefix="/api/works", tags=["works"])


def _work(row: aiosqlite.Row, **summary: Any) -> SessionResponse:
    values = dict(row)
    values.update(summary)
    return SessionResponse(**values)


async def _work_summary(conn: aiosqlite.Connection, row: aiosqlite.Row) -> SessionResponse:
    """Return the user-facing Work summary from one consistent server calculation."""
    work_id = row["id"]
    async with conn.execute(
        """SELECT step.id, step.phase_id, step.session_id, step.title,
                  step.description, step.result, step.sort_order, step.status,
                  step.source, step.created_at, step.updated_at
           FROM work_plan_steps AS step
           JOIN work_plan_phases AS phase ON phase.id = step.phase_id
           WHERE step.session_id = ?
           ORDER BY phase.sort_order, phase.created_at, step.sort_order, step.created_at""",
        (work_id,),
    ) as cur:
        steps = await cur.fetchall()
    total = len(steps)
    completed = sum(step["status"] == "completed" for step in steps)
    blocked = sum(step["status"] == "blocked" for step in steps)
    next_row = next((step for step in steps if step["status"] != "completed"), None)
    async with conn.execute(
        "SELECT COUNT(*) FROM approval_requests WHERE session_id = ? AND status = 'pending'",
        (work_id,),
    ) as cur:
        pending = (await cur.fetchone())[0]
    values: dict[str, Any] = {
        "progress_source": "plan_steps" if total else "stored",
        "progress_percent": round(completed * 100 / total) if total else row["progress_percent"],
        "next_step": dict(next_row) if next_row else None,
        "blocked_step_count": blocked,
        "pending_approval_count": pending,
    }
    return _work(row, **values)


async def _require_work(conn: aiosqlite.Connection, work_id: str, *, mutable: bool = False) -> aiosqlite.Row:
    async with conn.execute("SELECT * FROM sessions WHERE id = ?", (work_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Work not found")
    if mutable and row["archived"]:
        raise HTTPException(status_code=409, detail="Work is archived")
    return row


async def _conversation(conn: aiosqlite.Connection, work_id: str, conversation_id: str, *, mutable: bool = False) -> aiosqlite.Row:
    await _require_work(conn, work_id, mutable=mutable)
    async with conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND session_id = ?", (conversation_id, work_id)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found in this Work")
    if mutable and row["status"] != "active":
        raise HTTPException(status_code=409, detail="Conversation is archived")
    return row


async def _conversation_response(conn: aiosqlite.Connection, row: aiosqlite.Row) -> ConversationResponse:
    values = dict(row)
    async with conn.execute("SELECT COUNT(*) FROM chat_messages WHERE conversation_id = ?", (values["id"],)) as cur:
        values["message_count"] = (await cur.fetchone())[0]
    async with conn.execute(
        "SELECT status FROM task_runs WHERE conversation_id = ? ORDER BY started_at DESC, rowid DESC LIMIT 1", (values["id"],)
    ) as cur:
        task = await cur.fetchone()
    values["latest_task_status"] = task[0] if task else None
    return ConversationResponse(**values)


async def _phases(conn: aiosqlite.Connection, work_id: str) -> list[WorkPlanPhaseResponse]:
    async with conn.execute(
        "SELECT * FROM work_plan_phases WHERE session_id = ? ORDER BY sort_order, created_at", (work_id,)
    ) as cur:
        phase_rows = await cur.fetchall()
    result: list[WorkPlanPhaseResponse] = []
    for phase in phase_rows:
        phase_values = dict(phase)
        async with conn.execute(
            "SELECT * FROM work_plan_steps WHERE phase_id = ? ORDER BY sort_order, created_at", (phase["id"],)
        ) as cur:
            step_rows = await cur.fetchall()
        phase_values["steps"] = [WorkPlanStepResponse(**dict(step)) for step in step_rows]
        result.append(WorkPlanPhaseResponse(**phase_values))
    return result


@router.get("", response_model=list[SessionResponse])
async def list_works(conn: aiosqlite.Connection = Depends(get_db)) -> list[SessionResponse]:
    async with conn.execute("SELECT * FROM sessions WHERE archived = 0 ORDER BY updated_at DESC") as cur:
        rows = await cur.fetchall()
    return [await _work_summary(conn, row) for row in rows]


@router.get("/{work_id}/dashboard", response_model=WorkDashboardResponse)
async def get_work_dashboard(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> WorkDashboardResponse:
    work = await _require_work(conn, work_id)
    now = int(time.time())
    await conn.execute("UPDATE sessions SET last_opened_at = ? WHERE id = ?", (now, work_id))
    await conn.commit()
    async with conn.execute(
        "SELECT * FROM conversations WHERE session_id = ? AND status = 'active' ORDER BY updated_at DESC", (work_id,)
    ) as cur:
        conversations = [await _conversation_response(conn, row) for row in await cur.fetchall()]
    phases = await _phases(conn, work_id)
    next_step = next(
        (step for phase in phases for step in phase.steps if step.status != "completed"), None
    )
    async with conn.execute(
        "SELECT COUNT(*) FROM approval_requests WHERE session_id = ? AND status = 'pending'", (work_id,)
    ) as cur:
        pending = (await cur.fetchone())[0]
    async with conn.execute(
        "SELECT id, session_id, relative_path, kind, sha256, size_bytes, created_at FROM artifacts WHERE session_id = ? ORDER BY created_at DESC LIMIT 8", (work_id,)
    ) as cur:
        artifacts = [dict(row) for row in await cur.fetchall()]
    async with conn.execute(
        "SELECT * FROM work_context_summaries WHERE session_id = ? ORDER BY version DESC LIMIT 1", (work_id,)
    ) as cur:
        summary = await cur.fetchone()
    async with conn.execute(
        """SELECT action, target, created_at FROM audit_events
           WHERE session_id = ? AND action IN ('tool.called', 'mcp.tool_called', 'skill.applied')
           ORDER BY created_at DESC LIMIT 24""", (work_id,)
    ) as cur:
        capability_rows = await cur.fetchall()
    capabilities_used: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in capability_rows:
        key = (item["action"], item["target"])
        if key not in seen:
            seen.add(key)
            capabilities_used.append({"kind": item["action"], "name": item["target"] or "Trợ lý GYO", "used_at": item["created_at"]})
    work_values = dict(work)
    work_values["last_opened_at"] = now
    work_response = await _work_summary(conn, work_values)
    return WorkDashboardResponse(
        work=work_response, next_step=next_step, conversations=conversations,
        phases=phases, pending_approval_count=pending, artifacts=artifacts,
        context_summary=WorkContextSummaryResponse(**dict(summary)) if summary else None,
        capabilities_used=capabilities_used, progress_source=work_response.progress_source,
    )


@router.patch("/{work_id}", response_model=SessionResponse)
async def update_work(work_id: str, request: WorkUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> SessionResponse:
    current = await _require_work(conn, work_id, mutable=True)
    updates: list[str] = []
    params: list[Any] = []
    if request.title is not None:
        title = " ".join(request.title.split())
        if not title:
            raise HTTPException(status_code=422, detail="Work title cannot be empty")
        updates.append("title = ?"); params.append(title)
    if request.goal is not None:
        updates.append("goal = ?"); params.append(" ".join(request.goal.split()) or None)
    if request.data_scope is not None:
        updates.append("data_scope = ?"); params.append(request.data_scope)
    if request.work_status is not None:
        updates.append("work_status = ?"); params.append(request.work_status)
    if request.progress_percent is not None:
        updates.append("progress_percent = ?"); params.append(request.progress_percent)
    if not updates:
        return _work(current)
    now = int(time.time())
    updates.append("updated_at = ?"); params.append(now); params.append(work_id)
    await conn.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", params)
    await log_audit_event(conn, work_id, "user", "work.updated", payload={"fields": [u.split()[0] for u in updates[:-1]]})
    await conn.commit()
    return _work(await _require_work(conn, work_id))


@router.post("/{work_id}/completion-proposal", response_model=WorkCompletionResponse)
async def propose_completion(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> WorkCompletionResponse:
    await _require_work(conn, work_id, mutable=True)
    now = int(time.time())
    await conn.execute(
        "UPDATE sessions SET work_status = 'waiting_confirmation', completion_proposed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, work_id),
    )
    await log_audit_event(conn, work_id, "gyo", "work.completion_proposed", payload={})
    await conn.commit()
    return WorkCompletionResponse(work=_work(await _require_work(conn, work_id)))


@router.post("/{work_id}/confirm-completion", response_model=WorkCompletionResponse)
async def confirm_completion(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> WorkCompletionResponse:
    work = await _require_work(conn, work_id, mutable=True)
    if work["work_status"] != "waiting_confirmation":
        raise HTTPException(status_code=409, detail="GYO has not proposed completion for this Work")
    now = int(time.time())
    await conn.execute(
        "UPDATE sessions SET work_status = 'completed', progress_percent = 100, completed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, work_id),
    )
    await log_audit_event(conn, work_id, "user", "work.completed_confirmed", payload={})
    await conn.commit()
    return WorkCompletionResponse(work=_work(await _require_work(conn, work_id)))


@router.post("/{work_id}/reopen", response_model=WorkCompletionResponse)
async def reopen_work(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> WorkCompletionResponse:
    await _require_work(conn, work_id, mutable=True)
    now = int(time.time())
    await conn.execute("UPDATE sessions SET work_status = 'in_progress', completed_at = NULL, updated_at = ? WHERE id = ?", (now, work_id))
    await log_audit_event(conn, work_id, "user", "work.reopened", payload={})
    await conn.commit()
    return WorkCompletionResponse(work=_work(await _require_work(conn, work_id)))


@router.get("/{work_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> list[ConversationResponse]:
    await _require_work(conn, work_id)
    async with conn.execute("SELECT * FROM conversations WHERE session_id = ? ORDER BY updated_at DESC", (work_id,)) as cur:
        rows = await cur.fetchall()
    return [await _conversation_response(conn, row) for row in rows]


@router.post("/{work_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(work_id: str, request: ConversationCreateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> ConversationResponse:
    await _require_work(conn, work_id, mutable=True)
    now = int(time.time()); conversation_id = str(uuid.uuid4())
    try:
        await conn.execute(
            "INSERT INTO conversations (id, session_id, title, purpose, created_at, updated_at, last_opened_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (conversation_id, work_id, request.title, request.purpose, now, now, now),
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A conversation with this title already exists") from exc
    await log_audit_event(conn, work_id, "user", "conversation.created", target=conversation_id, payload={"title": request.title})
    await conn.commit()
    return await _conversation_response(conn, await _conversation(conn, work_id, conversation_id))


@router.patch("/{work_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(work_id: str, conversation_id: str, request: ConversationUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> ConversationResponse:
    await _require_work(conn, work_id, mutable=True)
    current = await _conversation(conn, work_id, conversation_id)
    restoring = request.archived is False
    if current["status"] != "active" and not restoring:
        raise HTTPException(status_code=409, detail="Conversation is archived")
    if current["status"] != "active" and request.model_fields_set != {"archived"}:
        raise HTTPException(status_code=409, detail="Restore the conversation before editing it")
    updates: list[str] = []; params: list[Any] = []
    if request.title is not None:
        title = " ".join(request.title.split())
        if not title: raise HTTPException(status_code=422, detail="Conversation title cannot be empty")
        updates.append("title = ?"); params.append(title)
    if request.purpose is not None:
        updates.append("purpose = ?"); params.append(" ".join(request.purpose.split()) or None)
    if request.archived is not None:
        updates.append("status = ?"); params.append("archived" if request.archived else "active")
    if updates:
        updates.append("updated_at = ?"); params.append(int(time.time())); params.append(conversation_id)
        await conn.execute(f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?", params)
        await log_audit_event(conn, work_id, "user", "conversation.updated", target=conversation_id, payload={})
        await conn.commit()
    return await _conversation_response(conn, await _conversation(conn, work_id, conversation_id))


@router.get("/{work_id}/conversations/{conversation_id}/messages", response_model=ChatMessagePageResponse)
async def conversation_messages(work_id: str, conversation_id: str, limit: int = 100, before_id: str | None = None, conn: aiosqlite.Connection = Depends(get_db)) -> ChatMessagePageResponse:
    await _conversation(conn, work_id, conversation_id)
    limit = max(1, min(limit, 200))
    before_rowid: int | None = None
    if before_id:
        async with conn.execute("SELECT rowid FROM chat_messages WHERE id = ? AND conversation_id = ?", (before_id, conversation_id)) as cur:
            row = await cur.fetchone()
        if row is None: raise HTTPException(status_code=404, detail="Message cursor not found")
        before_rowid = row[0]
    where = "conversation_id = ?" + (" AND rowid < ?" if before_rowid else "")
    params: list[Any] = [conversation_id] + ([before_rowid] if before_rowid else []) + [limit + 1]
    async with conn.execute(f"SELECT id, session_id, task_id, role, content, created_at, conversation_id FROM chat_messages WHERE {where} ORDER BY rowid DESC LIMIT ?", params) as cur:
        rows = await cur.fetchall()
    has_more = len(rows) > limit
    return ChatMessagePageResponse(messages=[ChatMessageResponse(**dict(row)) for row in reversed(rows[:limit])], has_more=has_more)


@router.post("/{work_id}/conversations/{conversation_id}/prompt", response_model=TaskRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_conversation_prompt(work_id: str, conversation_id: str, request: PromptRequest, conn: aiosqlite.Connection = Depends(get_db), gyo_orchestrator: GyoOrchestrator = Depends(get_gyo_orchestrator), settings: Settings = Depends(get_settings)) -> TaskRunResponse:
    return await _submit_prompt_for_conversation(work_id, conversation_id, request, conn, gyo_orchestrator, settings)


@router.get("/{work_id}/plan", response_model=list[WorkPlanPhaseResponse])
async def get_plan(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> list[WorkPlanPhaseResponse]:
    await _require_work(conn, work_id)
    return await _phases(conn, work_id)


async def _memory_context_response(conn: aiosqlite.Connection, work_id: str, step_id: str) -> WorkMemoryContextResponse:
    scope = await get_work_memory_scope(conn, work_id, step_id)
    active_memory_count, excluded = await scope_summary(conn, scope)
    return WorkMemoryContextResponse(
        work_id=work_id,
        plan_step_id=step_id,
        scope_id=scope.id,
        context_mode=scope.context_mode,
        auto_learning_enabled=scope.auto_learning_enabled,
        active_memory_count=active_memory_count,
        excluded=excluded,
    )


@router.get("/{work_id}/plan/steps/{step_id}/memory-context", response_model=WorkMemoryContextResponse)
async def get_step_memory_context(work_id: str, step_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> WorkMemoryContextResponse:
    return await _memory_context_response(conn, work_id, step_id)


@router.put("/{work_id}/plan/steps/{step_id}/memory-context", response_model=WorkMemoryContextResponse)
async def put_step_memory_context(
    work_id: str,
    step_id: str,
    request: WorkMemoryContextUpdateRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> WorkMemoryContextResponse:
    scope = await update_work_memory_scope(
        conn, work_id, step_id,
        context_mode=request.context_mode,
        auto_learning_enabled=request.auto_learning_enabled,
    )
    await log_audit_event(
        conn, work_id, "user", "work.memory_context_updated", target=step_id,
        payload={"scope_id": scope.id, "context_mode": scope.context_mode, "auto_learning_enabled": scope.auto_learning_enabled},
    )
    await conn.commit()
    return await _memory_context_response(conn, work_id, step_id)


@router.post("/{work_id}/plan/phases", response_model=WorkPlanPhaseResponse, status_code=status.HTTP_201_CREATED)
async def create_phase(work_id: str, request: WorkPlanPhaseCreateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> WorkPlanPhaseResponse:
    await _require_work(conn, work_id, mutable=True)
    async with conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM work_plan_phases WHERE session_id = ?", (work_id,)) as cur:
        order = (await cur.fetchone())[0]
    now = int(time.time()); phase_id = str(uuid.uuid4())
    await conn.execute("INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (phase_id, work_id, request.title, order, now, now))
    await log_audit_event(conn, work_id, "user", "work.plan_phase_created", target=phase_id, payload={"title": request.title})
    await conn.commit()
    async with conn.execute("SELECT * FROM work_plan_phases WHERE id = ?", (phase_id,)) as cur: row = await cur.fetchone()
    return WorkPlanPhaseResponse(**dict(row), steps=[])


@router.patch("/{work_id}/plan/phases/{phase_id}", response_model=WorkPlanPhaseResponse)
async def update_phase(work_id: str, phase_id: str, request: WorkPlanPhaseUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> WorkPlanPhaseResponse:
    await _require_work(conn, work_id, mutable=True)
    async with conn.execute(
        "SELECT * FROM work_plan_phases WHERE id = ? AND session_id = ?", (phase_id, work_id)
    ) as cur:
        current = await cur.fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Phase not found in this Work")
    updates: list[str] = []
    params: list[Any] = []
    if request.title is not None:
        title = " ".join(request.title.split())
        if not title:
            raise HTTPException(status_code=422, detail="Phase title cannot be empty")
        updates.append("title = ?"); params.append(title)
    for key, value in (("status", request.status), ("sort_order", request.sort_order)):
        if value is not None:
            updates.append(f"{key} = ?"); params.append(value)
    if updates:
        updates.append("updated_at = ?"); params.append(int(time.time())); params.append(phase_id)
        await conn.execute(f"UPDATE work_plan_phases SET {', '.join(updates)} WHERE id = ?", params)
        await log_audit_event(conn, work_id, "user", "work.plan_phase_updated", target=phase_id, payload={})
        await conn.commit()
    return next(phase for phase in await _phases(conn, work_id) if phase.id == phase_id)


@router.post("/{work_id}/plan/steps", response_model=WorkPlanStepResponse, status_code=status.HTTP_201_CREATED)
async def create_step(work_id: str, request: WorkPlanStepCreateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> WorkPlanStepResponse:
    await _require_work(conn, work_id, mutable=True)
    async with conn.execute("SELECT id FROM work_plan_phases WHERE id = ? AND session_id = ?", (request.phase_id, work_id)) as cur:
        if not await cur.fetchone(): raise HTTPException(status_code=404, detail="Phase not found in this Work")
    async with conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM work_plan_steps WHERE phase_id = ?", (request.phase_id,)) as cur: order = (await cur.fetchone())[0]
    now = int(time.time()); step_id = str(uuid.uuid4())
    await conn.execute("INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (step_id, request.phase_id, work_id, request.title, request.description, order, now, now))
    await log_audit_event(conn, work_id, "user", "work.plan_step_created", target=step_id, payload={"title": request.title})
    await conn.commit()
    async with conn.execute("SELECT * FROM work_plan_steps WHERE id = ?", (step_id,)) as cur: row = await cur.fetchone()
    return WorkPlanStepResponse(**dict(row))


@router.patch("/{work_id}/plan/steps/{step_id}", response_model=WorkPlanStepResponse)
async def update_step(work_id: str, step_id: str, request: WorkPlanStepUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> WorkPlanStepResponse:
    await _require_work(conn, work_id, mutable=True)
    async with conn.execute("SELECT * FROM work_plan_steps WHERE id = ? AND session_id = ?", (step_id, work_id)) as cur: current = await cur.fetchone()
    if current is None: raise HTTPException(status_code=404, detail="Step not found in this Work")
    resulting_status = request.status if request.status is not None else current["status"]
    resulting_description = request.description if request.description is not None else current["description"]
    resulting_result = request.result if request.result is not None else current["result"]
    if resulting_status == "blocked" and not (
        (resulting_description or "").strip() or (resulting_result or "").strip()
    ):
        raise HTTPException(status_code=422, detail="A blocked step requires a description or next action")
    updates: list[str] = []; params: list[Any] = []
    for key, value in (("title", request.title), ("description", request.description), ("result", request.result), ("status", request.status), ("sort_order", request.sort_order)):
        if value is not None: updates.append(f"{key} = ?"); params.append(value)
    if updates:
        updates.append("updated_at = ?"); params.append(int(time.time())); params.append(step_id)
        await conn.execute(f"UPDATE work_plan_steps SET {', '.join(updates)} WHERE id = ?", params)
        await log_audit_event(conn, work_id, "user", "work.plan_step_updated", target=step_id, payload={})
        await conn.commit()
    async with conn.execute("SELECT * FROM work_plan_steps WHERE id = ?", (step_id,)) as cur: updated = await cur.fetchone()
    return WorkPlanStepResponse(**dict(updated))
