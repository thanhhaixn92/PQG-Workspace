"""Public Task API routes for CP4.

These endpoints expose TaskService without changing the legacy session/chat API.
They operate on app-owned task metadata only; Hermes execution remains behind the
existing backend policy boundary.
"""
from __future__ import annotations

import json
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import (
    PublicTaskActionCreateRequest,
    PublicTaskActionDecisionRequest,
    PublicTaskActionResponse,
    PublicTaskCreateRequest,
    PublicTaskEventResponse,
    PublicTaskResponse,
)
from app.dependencies import get_db
from app.repositories.idempotency_repository import IdempotencyConflict
from app.repositories.task_repository import TaskRepository
from app.services.audit import log_audit_event
from app.services.state_machine import TransitionError
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _task_response(task: dict, duplicate: bool = False) -> PublicTaskResponse:
    data = dict(task)
    data["duplicate"] = duplicate
    return PublicTaskResponse(**data)


def _action_response(action: dict) -> PublicTaskActionResponse:
    return PublicTaskActionResponse(**dict(action))


async def _get_task_or_404(db: aiosqlite.Connection, task_id: str) -> dict:
    task = await TaskRepository(db).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=PublicTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: PublicTaskCreateRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublicTaskResponse:
    """Create a public task record.

    Idempotency-Key is optional. If provided, the same key with the same payload
    returns the original task; the same key with a different payload returns 409.
    """
    service = TaskService(conn)
    try:
        task, duplicate = await service.create_task(
            session_id=request.session_id,
            title=request.title,
            description=request.description,
            task_type=request.task_type,
            parent_task_id=request.parent_task_id,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_audit_event(
        conn=conn,
        session_id=request.session_id,
        actor="api",
        action="task.created" if not duplicate else "task.create_replayed",
        target=task["id"],
        payload={
            "idempotency_key": bool(idempotency_key),
            "duplicate": duplicate,
            "task_type": request.task_type,
        },
    )
    await conn.commit()
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return _task_response(task, duplicate=duplicate)


@router.get("", response_model=list[PublicTaskResponse])
async def list_tasks(
    conn: aiosqlite.Connection = Depends(get_db),
    session_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PublicTaskResponse]:
    tasks = await TaskRepository(conn).list_tasks(
        session_id=session_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="task.listed",
        payload={"status": status_filter, "limit": limit, "offset": offset},
    )
    await conn.commit()
    return [_task_response(task) for task in tasks]


@router.get("/{task_id}", response_model=PublicTaskResponse)
async def get_task(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> PublicTaskResponse:
    task = await _get_task_or_404(conn, task_id)
    await log_audit_event(
        conn=conn,
        session_id=task.get("session_id"),
        actor="api",
        action="task.viewed",
        target=task_id,
    )
    await conn.commit()
    return _task_response(task)


@router.get("/{task_id}/events", response_model=list[PublicTaskEventResponse])
async def list_task_events(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[PublicTaskEventResponse]:
    task = await _get_task_or_404(conn, task_id)
    events = await TaskRepository(conn).get_events(task_id)
    await log_audit_event(
        conn=conn,
        session_id=task.get("session_id"),
        actor="api",
        action="task.events_listed",
        target=task_id,
        payload={"count": len(events)},
    )
    await conn.commit()
    return [PublicTaskEventResponse(**event) for event in events]


@router.get("/{task_id}/events/stream")
async def stream_task_events(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> EventSourceResponse:
    task = await _get_task_or_404(conn, task_id)
    events = await TaskRepository(conn).get_events(task_id)
    await log_audit_event(
        conn=conn,
        session_id=task.get("session_id"),
        actor="api",
        action="task.events_streamed",
        target=task_id,
        payload={"count": len(events)},
    )
    await conn.commit()

    async def _generate():
        for event in events:
            yield {
                "event": event["type"],
                "data": json.dumps(event, ensure_ascii=False),
            }
        if task["status"] in {"succeeded", "failed", "cancelled"}:
            yield {
                "event": "done",
                "data": json.dumps({"type": "done", "task_id": task_id}),
            }

    return EventSourceResponse(_generate())


@router.post("/{task_id}/start", response_model=PublicTaskResponse)
async def start_task(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> PublicTaskResponse:
    service = TaskService(conn)
    try:
        task = await service.start_task(task_id)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_audit_event(conn, task.get("session_id"), "api", "task.started", task_id)
    await conn.commit()
    return _task_response(task)


@router.post("/{task_id}/cancel", response_model=PublicTaskResponse)
async def cancel_task(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> PublicTaskResponse:
    service = TaskService(conn)
    try:
        task = await service.cancel_task(task_id)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_audit_event(conn, task.get("session_id"), "api", "task.cancelled", task_id)
    await conn.commit()
    return _task_response(task)


@router.post("/{task_id}/actions", response_model=PublicTaskActionResponse, status_code=status.HTTP_201_CREATED)
async def request_task_action(
    task_id: str,
    request: PublicTaskActionCreateRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> PublicTaskActionResponse:
    service = TaskService(conn)
    try:
        task = await service.request_approval(
            task_id,
            request.tool_name,
            request.description,
            risk_level=request.risk_level,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    actions = await service.get_task_with_events(task_id)
    action = actions["actions"][-1]
    await log_audit_event(
        conn=conn,
        session_id=task.get("session_id"),
        actor="api",
        action="task_action.requested",
        target=action["id"],
        payload={"task_id": task_id, "risk_level": request.risk_level},
    )
    await conn.commit()
    return _action_response(action)


@router.post("/{task_id}/actions/{action_id}/decision", response_model=PublicTaskResponse)
async def decide_task_action(
    task_id: str,
    action_id: str,
    request: PublicTaskActionDecisionRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> PublicTaskResponse:
    service = TaskService(conn)
    try:
        task = await service.resolve_approval(
            task_id,
            action_id,
            approved=request.approved,
            output_json=request.output_json,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Task not found") from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await log_audit_event(
        conn=conn,
        session_id=task.get("session_id"),
        actor="api",
        action="task_action.allowed" if request.approved else "task_action.denied",
        target=action_id,
        payload={"task_id": task_id},
    )
    await conn.commit()
    return _task_response(task)
