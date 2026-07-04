"""Session management and prompt routing REST API."""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.api.schemas import (
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionResponse,
    PromptRequest,
    TaskRunResponse,
    ChatMessageResponse,
    AuditEventResponse,
    ArchiveSessionResponse,
    CleanupSmokeTestsResponse,
    MemoryEntry,
    SseDoneEvent,
)
from app.db.connection import get_db_connection
from app.dependencies import get_db, get_hermes_client, get_settings
from app.api.runtime import check_hermes_preflight
from app.services.audit import log_audit_event
from app.services.content_quality import enrich_desktop_file_blocks
from app.services.context import CONTEXT_VERSION_CACHE, get_context_version
from app.services.event_bus import event_bus
from app.settings import Settings

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


HERMES_RESPONSE_GUIDANCE = """=== HERMES LOCAL STACK RESPONSE GUIDE ===
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


def _compose_hermes_prompt(user_prompt: str, context_str: str = "", context_version: int = 0) -> str:
    """Add lightweight UX guidance while preserving the original user prompt."""
    parts = [HERMES_RESPONSE_GUIDANCE.strip()]
    if context_str:
        parts.append(context_str.strip())
    if context_version:
        parts.append(f"=== CONTEXT VERSION: {context_version} ===")
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
    (workspace / "outputs").mkdir(parents=True, exist_ok=True)
    return str(workspace)


async def _run_prompt_task(
    client: Any,
    session_id: str,
    task_id: str,
    prompt: str,
    db_path: Any,
) -> None:
    """Background task to send prompt and update DB task_run status and audit logs."""
    try:
        async with get_db_connection(db_path) as db:
            await db.execute(
                "UPDATE task_runs SET status = 'running' WHERE id = ?",
                (task_id,),
            )
            await db.commit()

        assistant_text = await client.send_prompt(session_id, prompt)
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
                    INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), session_id, task_id, "assistant", assistant_text, now),
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
                db, session_id, "system", "hermes.error", payload={"task_id": task_id, "error": str(e)}
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()
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
        INSERT INTO sessions (id, title, workspace_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, request.title, workspace_path, now, now),
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


@router.post("/cleanup-smoke-tests", response_model=CleanupSmokeTestsResponse)
async def cleanup_smoke_test_sessions(
    conn: aiosqlite.Connection = Depends(get_db),
) -> CleanupSmokeTestsResponse:
    """Archive generated smoke-test sessions without deleting their data."""
    now = int(time.time())
    async with conn.execute(
        "SELECT id FROM sessions WHERE archived = 0 AND title LIKE 'Smoke Test%'"
    ) as cursor:
        rows = await cursor.fetchall()

    session_ids = [row[0] for row in rows]
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

    if request.archived is not None:
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
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    async with conn.execute(
        """
        SELECT id, session_id, task_id, role, content, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (session_id,),
    ) as cursor:
        rows = await cursor.fetchall()

    return [ChatMessageResponse(**dict(row)) for row in rows]


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


from app.services.context import build_context

@router.post("/{session_id}/prompt", response_model=TaskRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_prompt(
    session_id: str,
    request: PromptRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    client: Any = Depends(get_hermes_client),
    settings: Settings = Depends(get_settings),
) -> TaskRunResponse:
    """Submit a prompt to the Hermes agent for a specific session."""
    # Validate session exists
    async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    preflight = check_hermes_preflight(settings, run_doctor=True)
    if preflight.status not in {"ready", "mock"}:
        message_by_status = {
            "missing": "Không tìm thấy Hermes executable. Hãy kiểm tra HERMES_EXECUTABLE_PATH trong backend/.env.",
            "not_configured": "Hermes chưa được cấu hình. Hãy tạo backend/.env và cấu hình HERMES_EXECUTABLE_PATH.",
            "auth_unknown": "Hermes cần đăng nhập lại hoặc kiểm tra provider. Hãy chạy hermes auth hoặc hermes doctor rồi thử lại.",
            "auth_expired": "Hermes đã đăng nhập nhưng token không còn hợp lệ. Hãy chạy hermes auth để đăng nhập lại.",
        }
        message = message_by_status.get(preflight.status, preflight.guidance)
        await log_audit_event(
            conn,
            session_id=session_id,
            actor="system",
            action="runtime.preflight_blocked",
            payload={
                "runtime": "hermes",
                "status": preflight.status,
                "auth_status": preflight.auth_status,
                "executable_found": preflight.executable_found,
                "message": message,
            },
        )
        await conn.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, message)

    task_id = str(uuid.uuid4())
    now = int(time.time())
    status_str = "queued"

    # Create task run
    await conn.execute(
        """
        INSERT INTO task_runs (id, session_id, status, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, session_id, status_str, now),
    )
    await conn.execute(
        """
        INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), session_id, task_id, "user", request.prompt, now),
    )
    await conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    await conn.commit()

    # 1) Context Injection
    context_str = await build_context(conn, session_id)
    ctx_version = await get_context_version(conn)
    last_version = CONTEXT_VERSION_CACHE.get(session_id, 0)
    if ctx_version != last_version:
        CONTEXT_VERSION_CACHE[session_id] = ctx_version
        await log_audit_event(
            conn, session_id, "system", "context.version_changed",
            payload={"old_version": last_version, "new_version": ctx_version},
        )
    final_prompt = _compose_hermes_prompt(request.prompt, context_str, context_version=ctx_version)

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

    # Spawn hermes (lazy) and send prompt in background
    # Note: We send asynchronously to avoid blocking the HTTP response.
    # In a production setup, we might use a proper background worker.
    asyncio.create_task(
        _run_prompt_task(
            client=client,
            session_id=session_id,
            task_id=task_id,
            prompt=final_prompt,
            db_path=settings.db_path_resolved,
        )
    )

    return TaskRunResponse(
        id=task_id,
        session_id=session_id,
        status=status_str,
        started_at=now,
        retry_count=0,
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

    for row in reversed(rows):
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
    async with db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Session not found")
            
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
