"""Session management and prompt routing REST API."""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.api.schemas import (
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionResponse,
    PromptRequest,
    TaskRunResponse,
    ChatMessageResponse,
    ChatMessagePageResponse,
    AuditEventResponse,
    ArchiveSessionResponse,
    CleanupSmokeTestsResponse,
    CleanupSmokeTestsConfirmRequest,
    CleanupSmokeTestsPreviewResponse,
    SessionSummaryResponse,
    MemoryEntry,
    SseDoneEvent,
)
from app.db.connection import get_db_connection
from app.dependencies import get_db, get_gyo_orchestrator, get_settings
from app.services.audit import log_audit_event
from app.services.content_quality import enrich_desktop_file_blocks
from app.services.event_bus import event_bus
from app.services.assistant_context import AssistantContextPackBuilder
from app.services.gyo_orchestrator import GyoOrchestrator, GyoRunRequest
from app.settings import Settings

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


GYO_RESPONSE_GUIDANCE = """=== PQG WORKSPACE RESPONSE GUIDE ===
Reply in Vietnamese unless the user explicitly asks for another language.
For final user-visible results, prefer these sections when relevant:
- Kết quả
- File đầu ra
- Cần kiểm tra
- Bước tiếp theo
Do not expose raw tool JSON or desktop-local-file JSON as prose; keep file references in fenced blocks when needed.
Do not claim that facts or sources were verified unless you actually verified them.
For publishing/news/article tasks, use a clear title, lead, main body, and source references.
Separate verified facts from analysis. Avoid strange or uncertain phrases.
Save generated output files inside the session workspace, preferably under an outputs/ folder.
Do not save generated user output inside backend/, frontend/, or infra/ unless the user explicitly asks.
"""

PUBLISHING_KEYWORDS = [
    "viết bài", "bài báo", "đăng website", "tin tức", "biên tập",
    "tạo file word", "xuất bản", "soạn thảo", "bản tin", "article", "news",
]

PUBLISHING_GUIDANCE = """=== HƯỚNG DẪN VIẾT NỘI DUNG XUẤT BẢN ===
Bài viết cần có cấu trúc rõ ràng:
- Tựa đề (h1 rõ ràng, hấp dẫn)
- Lead (đoạn mở đầu tóm tắt nội dung chính)
- Nội dung chính (triển khai chi tiết, có tiểu mục hợp lý)
- Nguồn tham khảo (link hoặc tài liệu tham khảo cụ thể)
Viết tiếng Việt tự nhiên, tránh dùng cụm từ lạ nếu không chắc chắn.
Phân biệt rõ dữ kiện đã xác minh và nhận định cá nhân.
Không khẳng định thông tin đã xác minh nếu chưa có nguồn cụ thể.
Lưu file đầu ra vào thư mục outputs/.
Không lưu file đầu ra vào backend/, frontend/, hoặc infra/.
"""


def _is_publishing_prompt(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in PUBLISHING_KEYWORDS)


def _compose_gyo_prompt(user_prompt: str) -> str:
    """Add lightweight UX guidance while preserving the original user prompt."""
    parts = [GYO_RESPONSE_GUIDANCE.strip()]
    if _is_publishing_prompt(user_prompt):
        parts.append(PUBLISHING_GUIDANCE.strip())
    parts.append(f"=== USER PROMPT ===\n{user_prompt}")
    return "\n\n".join(parts)


def _slugify_workspace_name(title: str, session_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.strip()).strip("-").lower()
    if not slug:
        slug = "session"
    return f"{slug[:40]}-{session_id[:8]}"


def _resolve_session_workspace(request: CreateSessionRequest, session_id: str, settings: Settings) -> str:
    provided = (request.workspace_path or "").strip()
    if provided:
        return provided

    workspace = settings.default_workspace_root_resolved / _slugify_workspace_name(request.title, session_id)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "working").mkdir(parents=True, exist_ok=True)
    (workspace / "outputs").mkdir(parents=True, exist_ok=True)
    return str(workspace)


async def _run_prompt_task(
    gyo_orchestrator: GyoOrchestrator | None,
    session_id: str,
    task_id: str,
    prompt: str,
    db_path: Any,
    use_task_api: bool = False,
    conversation_id: str | None = None,
    context_text: str = "",
) -> None:
    """Run a legacy Work prompt through native GYO without write authority."""
    try:
        async with get_db_connection(db_path) as db:
            await db.execute(
                "UPDATE task_runs SET status = 'running' WHERE id = ?",
                (task_id,),
            )
            await db.commit()

        if gyo_orchestrator is None:
            raise RuntimeError("GYO runtime is unavailable")
        result = await gyo_orchestrator.run(GyoRunRequest(
            work_id=session_id,
            prompt=prompt,
            context=context_text,
            assistant_turn_id=task_id,
        ))
        async with get_db_connection(db_path) as audit_db:
            await log_audit_event(
                audit_db, session_id, "system", "model.attempt", target=task_id,
                payload={"model_id": result.model_id, "status": result.status, "route_mode": result.route_mode,
                         "selection_reason": result.selection_reason},
                commit=False,
            )
            await audit_db.commit()
        if result.status != "completed" or not result.text.strip():
            raise RuntimeError("GYO model run failed")
        assistant_text = result.text
        async with get_db_connection(db_path) as db:
            now = int(time.time())
            async with db.execute(
                "SELECT workspace_path FROM sessions WHERE id = ?",
                (session_id,),
            ) as cursor:
                session_row = await cursor.fetchone()
            workspace_path = Path(session_row["workspace_path"]) if session_row else Path.cwd()
            if assistant_text:
                assistant_text, quality_results = enrich_desktop_file_blocks(
                    assistant_text,
                    workspace_path=workspace_path,
                    project_root=Path(__file__).resolve().parents[3],
                )
                for result in quality_results:
                    await log_audit_event(
                        db,
                        session_id,
                        "system",
                        "content.quality_check",
                        target=result.file_path,
                        payload=result.model_dump(),
                    )
            if assistant_text:
                await db.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at, conversation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), session_id, task_id, "assistant", assistant_text, now, conversation_id),
                )
            await db.execute(
                "UPDATE task_runs SET status = 'completed', finished_at = ? WHERE id = ?",
                (now, task_id),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await log_audit_event(
                db, session_id, "system", "task_run.completed", payload={"task_id": task_id}
            )
            await db.commit()
            if use_task_api:
                try:
                    from app.services.legacy_task_adapter import LegacyTaskAdapter
                    from app.services.task_service import TaskService
                    awaited_adapter = LegacyTaskAdapter(TaskService(db))
                    await awaited_adapter.update_from_task_run(db, task_id, "completed")
                except Exception as _adapter_exc:
                    await log_audit_event(
                        db, session_id, "system", "task_service_adapter.error",
                        payload={"task_id": task_id, "error": str(_adapter_exc)},
                    )
        await event_bus.publish(session_id, SseDoneEvent())
    except Exception as e:
        async with get_db_connection(db_path) as db:
            now = int(time.time())
            await db.execute(
                "UPDATE task_runs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                (str(e), now, task_id),
            )
            await log_audit_event(
                db, session_id, "system", "task_run.failed", payload={"task_id": task_id, "error": str(e)}
            )
            await log_audit_event(
                db, session_id, "system", "gyo.error", payload={"task_id": task_id, "reason": "model_run_failed"}
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()
            if use_task_api:
                try:
                    from app.services.legacy_task_adapter import LegacyTaskAdapter
                    from app.services.task_service import TaskService
                    awaited_adapter = LegacyTaskAdapter(TaskService(db))
                    await awaited_adapter.update_from_task_run(db, task_id, "failed", error=str(e))
                except Exception:
                    pass
        await event_bus.publish(session_id, SseDoneEvent())


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    now = int(time.time())
    workspace_path = _resolve_session_workspace(request, session_id, settings)

    await conn.execute(
        """
        INSERT INTO sessions (id, title, goal, data_scope, workspace_path, created_at, updated_at, last_opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, request.title, request.goal, request.data_scope, workspace_path, now, now, now),
    )
    await conn.execute(
        """INSERT INTO conversations (id, session_id, title, purpose, status, created_at, updated_at, last_opened_at)
           VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
        (f"conversation-{session_id}", session_id, "Trao đổi ban đầu", "Phiên trao đổi đầu tiên của Công việc", now, now, now),
    )
    await conn.commit()

    # Log audit event
    await log_audit_event(
        conn,
        session_id=session_id,
        actor="user",
        action="session.created",
        payload={
            "title": request.title,
            "has_goal": bool(request.goal),
            "data_scope": request.data_scope,
            "workspace_path": workspace_path,
            "auto_created_workspace": not bool((request.workspace_path or "").strip()),
        },
    )

    return SessionResponse(
        id=session_id,
        title=request.title,
        workspace_path=workspace_path,
        created_at=now,
        updated_at=now,
        archived=0,
        goal=request.goal,
        data_scope=request.data_scope,
        last_opened_at=now,
    )


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[SessionResponse]:
    """List all sessions."""
    async with conn.execute(
        "SELECT * FROM sessions WHERE archived = 0 ORDER BY updated_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()
    
    return [SessionResponse(**dict(row)) for row in rows]


async def _smoke_cleanup_candidates(conn: aiosqlite.Connection) -> list[dict[str, str]]:
    async with conn.execute(
        "SELECT id, title FROM sessions WHERE archived = 0 AND title LIKE 'Smoke Test%' ORDER BY id"
    ) as cursor:
        rows = await cursor.fetchall()
    return [{"id": row[0], "title": row[1]} for row in rows]


def _smoke_cleanup_token(items: list[dict[str, str]]) -> str:
    identity = "\x1f".join(item["id"] for item in items)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@router.get("/cleanup-smoke-tests/preview", response_model=CleanupSmokeTestsPreviewResponse)
async def preview_cleanup_smoke_test_sessions(
    conn: aiosqlite.Connection = Depends(get_db),
) -> CleanupSmokeTestsPreviewResponse:
    """Preview the exact generated sessions that a later confirmation may archive."""
    items = await _smoke_cleanup_candidates(conn)
    return CleanupSmokeTestsPreviewResponse(items=items, confirmation_token=_smoke_cleanup_token(items))


@router.post("/cleanup-smoke-tests", response_model=CleanupSmokeTestsResponse)
async def cleanup_smoke_test_sessions(
    request: CleanupSmokeTestsConfirmRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> CleanupSmokeTestsResponse:
    """Archive only the exact previewed generated sessions, without deleting data."""
    now = int(time.time())
    items = await _smoke_cleanup_candidates(conn)
    if request.confirmation_token != _smoke_cleanup_token(items):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cleanup preview changed; review the current candidates before confirming",
        )
    session_ids = [item["id"] for item in items]
    if session_ids:
        await conn.executemany(
            "UPDATE sessions SET archived = 1, updated_at = ? WHERE id = ?",
            [(now, session_id) for session_id in session_ids],
        )
        await log_audit_event(
            conn,
            session_id=None,
            actor="user",
            action="session.cleanup_smoke_tests",
            payload={"archived_count": len(session_ids), "session_ids": session_ids},
        )
        await conn.commit()

    return CleanupSmokeTestsResponse(archived_count=len(session_ids))


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> SessionResponse:
    """Rename or archive a session."""
    async with conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    current = dict(row)
    updates: list[str] = []
    params: list[Any] = []
    now = int(time.time())

    if request.title is not None:
        title = request.title.strip()
        if not title:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Title cannot be empty")
        updates.append("title = ?")
        params.append(title)

    if request.goal is not None:
        updates.append("goal = ?")
        params.append(" ".join(request.goal.split()) or None)

    if request.data_scope is not None:
        updates.append("data_scope = ?")
        params.append(request.data_scope)

    if request.archived is not None:
        if request.archived and current["archived"] != 1:
            async with conn.execute(
                "SELECT id FROM task_runs WHERE session_id = ? "
                "AND status IN ('queued', 'running', 'waiting_approval') LIMIT 1",
                (session_id,),
            ) as cursor:
                active_run = await cursor.fetchone()
            if active_run:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Cannot archive a session while a task is active; cancel or resolve it first",
                )
        updates.append("archived = ?")
        params.append(1 if request.archived else 0)

    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(session_id)
        await conn.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
            params,
        )

        if request.title is not None and request.title.strip() != current["title"]:
            await log_audit_event(
                conn,
                session_id=session_id,
                actor="user",
                action="session.renamed",
                payload={"old_title": current["title"], "new_title": request.title.strip()},
            )

        if request.goal is not None and (" ".join(request.goal.split()) or None) != current.get("goal"):
            await log_audit_event(
                conn,
                session_id=session_id,
                actor="user",
                action="session.goal_updated",
                payload={"has_goal": bool(request.goal.strip())},
            )

        if request.data_scope is not None and request.data_scope != current.get("data_scope", "work_only"):
            await log_audit_event(
                conn,
                session_id=session_id,
                actor="user",
                action="session.data_scope_updated",
                payload={"data_scope": request.data_scope},
            )

        if request.archived is True and current["archived"] != 1:
            await log_audit_event(
                conn,
                session_id=session_id,
                actor="user",
                action="session.archived",
                payload={"title": current["title"]},
            )

        await conn.commit()

    async with conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cursor:
        updated = await cursor.fetchone()

    return SessionResponse(**dict(updated))


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> SessionSummaryResponse:
    """Return a small end-user work summary without exposing diagnostic payloads."""
    async with conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    session = dict(row)
    now = int(time.time())
    await conn.execute("UPDATE sessions SET last_opened_at = ? WHERE id = ?", (now, session_id))
    async with conn.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,)) as cur:
        message_count = (await cur.fetchone())[0]
    async with conn.execute("SELECT COUNT(*) FROM approval_requests WHERE session_id = ? AND status = 'pending'", (session_id,)) as cur:
        pending_approval_count = (await cur.fetchone())[0]
    async with conn.execute("SELECT COUNT(*) FROM artifacts WHERE session_id = ?", (session_id,)) as cur:
        artifact_count = (await cur.fetchone())[0]
    async with conn.execute(
        "SELECT status FROM task_runs WHERE session_id = ? ORDER BY started_at DESC, rowid DESC LIMIT 1", (session_id,)
    ) as cur:
        task = await cur.fetchone()
    await log_audit_event(
        conn,
        session_id=session_id,
        actor="user",
        action="session.summary_opened",
        payload={"message_count": message_count, "artifact_count": artifact_count},
    )
    await conn.commit()
    session["last_opened_at"] = now
    return SessionSummaryResponse(
        session=SessionResponse(**session),
        message_count=message_count,
        pending_approval_count=pending_approval_count,
        artifact_count=artifact_count,
        latest_task_status=task[0] if task else None,
    )


@router.delete("/{session_id}", response_model=ArchiveSessionResponse)
async def archive_session(
    session_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> ArchiveSessionResponse:
    """Soft archive a session. Chat, task, and audit data remain in SQLite."""
    await update_session(
        session_id=session_id,
        request=UpdateSessionRequest(archived=True),
        conn=conn,
    )
    return ArchiveSessionResponse(status="archived")


@router.get("/{session_id}/memory", response_model=list[MemoryEntry])
async def list_session_memory(
    session_id: str, 
    conn: aiosqlite.Connection = Depends(get_db)
):
    """List memory entries specific to this session."""
    entries = []
    async with conn.execute(
        "SELECT id, session_id, key, value, kind, importance_score, last_accessed_at, created_at "
        "FROM memory_entries WHERE session_id = ? ORDER BY importance_score DESC",
        (session_id,)
    ) as cursor:
        async for row in cursor:
            entries.append(
                MemoryEntry(
                    id=row[0],
                    session_id=row[1],
                    key=row[2],
                    value=row[3],
                    kind=row[4],
                    importance_score=row[5],
                    last_accessed_at=row[6],
                    created_at=row[7]
                )
            )
    return entries


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_session_messages(
    session_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[ChatMessageResponse]:
    """List persisted user-visible chat messages for a session."""
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cursor:
        session = await cursor.fetchone()
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if session[0]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Session is archived")

    async with conn.execute(
        """
        SELECT id, session_id, task_id, role, content, created_at, conversation_id
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (session_id,),
    ) as cursor:
        rows = await cursor.fetchall()

    return [ChatMessageResponse(**dict(row)) for row in rows]


@router.get("/{session_id}/messages/page", response_model=ChatMessagePageResponse)
async def list_session_messages_page(
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    before_id: str | None = Query(None),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ChatMessagePageResponse:
    """Return the newest page, or the page immediately before one persisted message."""
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cursor:
        session = await cursor.fetchone()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session[0]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Session is archived")

    before_rowid: int | None = None
    if before_id is not None:
        async with conn.execute(
            "SELECT rowid FROM chat_messages WHERE id = ? AND session_id = ?",
            (before_id, session_id),
        ) as cursor:
            cursor_row = await cursor.fetchone()
        if cursor_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Message cursor not found")
        before_rowid = int(cursor_row[0])

    where = "session_id = ?" + (" AND rowid < ?" if before_rowid is not None else "")
    params: list[object] = [session_id]
    if before_rowid is not None:
        params.append(before_rowid)
    params.append(limit + 1)
    async with conn.execute(
        f"""SELECT id, session_id, task_id, role, content, created_at, conversation_id, rowid
            FROM chat_messages WHERE {where}
            ORDER BY rowid DESC LIMIT ?""",
        params,
    ) as cursor:
        rows = await cursor.fetchall()
    has_more = len(rows) > limit
    selected = list(reversed(rows[:limit]))
    messages = [ChatMessageResponse(**{key: row[key] for key in ChatMessageResponse.model_fields}) for row in selected]
    return ChatMessagePageResponse(messages=messages, has_more=has_more)


@router.get("/{session_id}/task-runs/latest", response_model=TaskRunResponse | None)
async def get_latest_session_task_run(
    session_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> TaskRunResponse | None:
    """Return the newest task run for a session so the UI can recover state after refresh."""
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    async with conn.execute(
        """
        SELECT id, session_id, status, started_at, finished_at, error, retry_count
        FROM task_runs
        WHERE session_id = ?
        ORDER BY started_at DESC, rowid DESC
        LIMIT 1
        """,
        (session_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        return None
    return TaskRunResponse(**dict(row))


@router.get("/{session_id}/task-runs/{task_id}", response_model=TaskRunResponse)
async def get_session_task_run(
    session_id: str,
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> TaskRunResponse:
    """Return one task run, constrained to the owning session."""
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    async with conn.execute(
        """
        SELECT id, session_id, status, started_at, finished_at, error, retry_count
        FROM task_runs
        WHERE session_id = ? AND id = ?
        """,
        (session_id, task_id),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task run not found")
    return TaskRunResponse(**dict(row))


@router.get("/{session_id}/audit-events", response_model=list[AuditEventResponse])
async def list_session_audit_events(
    session_id: str,
    limit: int = 100,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[AuditEventResponse]:
    """List persisted audit events for a session, newest first."""
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    bounded_limit = max(1, min(limit, 200))
    async with conn.execute(
        """
        SELECT id, session_id, actor, action, target, payload_json, created_at
        FROM audit_events
        WHERE session_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT ?
        """,
        (session_id, bounded_limit),
    ) as cursor:
        rows = await cursor.fetchall()

    return [AuditEventResponse(**dict(row)) for row in rows]


@router.post("/{session_id}/prompt", response_model=TaskRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_prompt(
    session_id: str,
    request: PromptRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    gyo_orchestrator: GyoOrchestrator = Depends(get_gyo_orchestrator),
    settings: Settings = Depends(get_settings),
) -> TaskRunResponse:
    """Submit a prompt to native GYO for a specific session."""
    return await _submit_prompt_for_conversation(session_id, None, request, conn, gyo_orchestrator, settings)


async def _submit_prompt_for_conversation(
    session_id: str,
    conversation_id: str | None,
    request: PromptRequest,
    conn: aiosqlite.Connection,
    gyo_orchestrator: GyoOrchestrator | None,
    settings: Settings,
) -> TaskRunResponse:
    """Core prompt path shared by legacy sessions and new Work conversations."""
    # Validate session exists
    async with conn.execute("SELECT id, archived FROM sessions WHERE id = ?", (session_id,)) as cursor:
        work = await cursor.fetchone()
        if not work:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if work[1]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Work is archived")
    if conversation_id is None:
        conversation_id = f"conversation-{session_id}"
    async with conn.execute(
        "SELECT id, status FROM conversations WHERE id = ? AND session_id = ?",
        (conversation_id, session_id),
    ) as cursor:
        conversation = await cursor.fetchone()
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    if conversation[1] != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Conversation is archived")

    task_id = str(uuid.uuid4())
    now = int(time.time())
    status_str = "queued"

    # Create task run
    await conn.execute(
        """
        INSERT INTO task_runs (id, session_id, status, started_at, conversation_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (task_id, session_id, status_str, now, conversation_id),
    )
    await conn.execute(
        """
        INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at, conversation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), session_id, task_id, "user", request.prompt, now, conversation_id),
    )
    await conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    await conn.execute(
        "UPDATE conversations SET updated_at = ?, last_opened_at = ? WHERE id = ?",
        (now, now, conversation_id),
    )
    await conn.commit()

    # Legacy task runs use the same deterministic Work context boundary as
    # the modern Assistant.  Memory Hub remains opt-in (suggest_only here).
    context_pack = await AssistantContextPackBuilder(conn).build(session_id, conversation_id)
    final_prompt = _compose_gyo_prompt(request.prompt)

    # Log audit events
    await log_audit_event(
        conn,
        session_id=session_id,
        actor="user",
        action="prompt.submitted",
        payload={"task_id": task_id, "prompt_length": len(request.prompt)},
    )
    await log_audit_event(
        conn,
        session_id=session_id,
        actor="system",
        action="task_run.started",
        payload={"task_id": task_id},
    )

    # Optional TaskService integration behind USE_TASK_API flag
    if settings.use_task_api:
        from app.services.legacy_task_adapter import LegacyTaskAdapter
        from app.services.task_service import TaskService
        adapter = LegacyTaskAdapter(TaskService(conn))
        await adapter.on_prompt_submit(conn, session_id, task_id, request.prompt, conversation_id)

    # The legacy task/run contract remains asynchronous, but it calls the
    # native GYO orchestration seam only; there is no ACP fallback.
    asyncio.create_task(
        _run_prompt_task(
            gyo_orchestrator=gyo_orchestrator,
            session_id=session_id,
            task_id=task_id,
            prompt=final_prompt,
            db_path=settings.db_path_resolved,
            use_task_api=settings.use_task_api,
            conversation_id=conversation_id,
            context_text=context_pack.text,
        )
    )

    return TaskRunResponse(
        id=task_id,
        session_id=session_id,
        status=status_str,
        started_at=now,
        retry_count=0,
        conversation_id=conversation_id,
    )


@router.get("/{session_id}/events")
async def session_events(
    session_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> EventSourceResponse:
    """Subscribe to the SSE stream for a specific session."""
    # Validate session exists
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
            
    if event_bus.has_subscriber(session_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Session already has an active subscriber.")

    async def event_generator():
        # event_bus.subscribe raises 409 if already subscribed
        async for event in event_bus.subscribe(session_id):
            yield ServerSentEvent(
                event=event.type,
                data=event.model_dump_json(),
            )

    return EventSourceResponse(event_generator())


def _curator_candidate_from_messages(rows: list[aiosqlite.Row]) -> dict[str, str] | None:
    """Extract a small deterministic memory candidate from recent chat."""
    markers = [
        ("preference", "sở thích", ("tôi thích", "tôi muốn", "ưu tiên", "thích dùng")),
        ("workflow_rule", "quy tắc làm việc", ("luôn", "mỗi khi", "hãy luôn", "đừng")),
        ("style_rule", "quy tắc phong cách", ("trả lời", "viết", "giọng", "phong cách")),
        ("project_fact", "thông tin dự án", ("dự án", "workspace", "repo", "webapp")),
    ]

    # Rows are selected newest-first. Only user language may become user memory.
    for row in rows:
        if row["role"] != "user":
            continue
        content = str(row["content"]).strip()
        lowered = content.lower()
        if len(content) < 12:
            continue
        for kind, label, candidates in markers:
            if any(marker in lowered for marker in candidates):
                short = " ".join(content.split())[:240]
                return {
                    "kind": kind,
                    "key": f"{label} từ phiên chat",
                    "value": short,
                    "proposal": f"Đề xuất ghi nhớ {label}: {short}",
                    "reason": f"Phát hiện {label} trong lịch sử chat gần đây.",
                }
    return None



@router.post("/{session_id}/curate")
async def curate_session(
    session_id: str, 
    db: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Manually trigger the Curator job to evaluate the session and propose memory updates.
    Returns the proposal and emits an approval_required event.
    """
    import uuid
    from fastapi import HTTPException
    from app.api.approvals import register_pending_approval
    
    # Verify session exists
    async with db.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cur:
        session = await cur.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session[0]:
            raise HTTPException(status_code=409, detail="Session is archived")
            
    async with db.execute(
        """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT 20
        """,
        (session_id,),
    ) as cur:
        rows = await cur.fetchall()

    candidate = _curator_candidate_from_messages(rows)
    if not candidate:
        await log_audit_event(
            db,
            session_id,
            "system",
            "curator.no_proposal",
            payload={"reason": "no_clear_memory_candidate"},
        )
        await db.commit()
        return {
            "status": "no_proposal",
            "proposal": None,
            "message": "Chưa có thông tin đủ rõ để đề xuất bộ nhớ.",
        }

    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    proposal = candidate["proposal"]
    
    await log_audit_event(db, session_id, "system", "curator.proposed", approval_id, {"proposal": proposal, **candidate})
    
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="update_memory",
        target="memory_entries",
        risk_level="write_internal",
        description=proposal,
        settings=settings,
        payload={
            "kind": candidate["kind"],
            "key": candidate["key"],
            "value": candidate["value"],
            "importance_score": 5.0,
            "reason": candidate["reason"],
        },
    )
    
    await db.commit()
    
    from app.api.schemas import SseApprovalRequiredEvent
    event = SseApprovalRequiredEvent(
        approval_id=approval_id,
        action="update_memory",
        target="memory_entries",
        risk_level="write_internal",
        description=proposal
    )
    await event_bus.publish(session_id, event)
    
    return {
        "status": "curator_proposed",
        "approval_id": approval_id,
        "proposal": {
            "kind": candidate["kind"],
            "key": candidate["key"],
            "value": candidate["value"],
            "reason": candidate["reason"],
            "text": proposal,
        },
    }
