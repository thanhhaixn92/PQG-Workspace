"""DIRAP v3.0 Work Item API.

Reuses the existing task system (tasks table), session system,
file sandbox, approval, and audit. No parallel task/session/audit system.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.api.schemas import (
    AuditEventResponse,
    DirapExtractionDetailResponse,
    DirapExtractionRecordResponse,
    DirapExtractionSummaryResponse,
    DirapKnowledgeApproveRequest,
    DirapKnowledgeEvidenceResponse,
    DirapKnowledgeRecordCreateRequest,
    DirapKnowledgeRecordDetailResponse,
    DirapKnowledgeRecordResponse,
    DirapKnowledgeRejectRequest,
    DirapKnowledgeSubmitRequest,
    DirapKnowledgeSearchResponse,
    DirapKnowledgeSearchResult,
    DirapSourceFileAttachRequest,
    DirapSourceFileResponse,
    DirapUsabilityQueryType,
    DirapUsabilityResponse,
    DirapWorkItemCreateRequest,
    DirapWorkItemDetailResponse,
    DirapWorkItemResponse,
)
from app.db.connection import get_db_connection
from app.dependencies import get_db, get_settings
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository
from app.repositories.task_repository import TaskRepository
from app.services.audit import log_audit_event
from app.services.extraction import (
    EXTRACTOR_VERSION,
    extract_bytes,
    file_type_for,
    sha256_of_bytes,
    sha256_of_file,
)
from app.services.knowledge_search import (
    SearchRecord,
    normalize_search_text,
    search_records,
)
from app.services.sandbox import get_workspace_path, resolve_and_validate_path
from app.services.usability_policy import evaluate_usability, usable_for_query_types
from app.settings import Settings

router = APIRouter(prefix="/api/dirap", tags=["DIRAP"])

DIRAP_TASK_TYPE = "dirap_work_item"

IDEMPOTENCY_TTL = 86400  # 24 hours


def _request_hash(task_id: str, file_path: str, note: str | None) -> str:
    """Deterministic hash for source-file attachment idempotency."""
    raw = f"{task_id}|{file_path}|{note or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _claim_dirap_mutation(
    conn: aiosqlite.Connection,
    *,
    operation: str,
    scope: str,
    client_key: str | None,
    request_hash: str,
) -> tuple[IdempotencyRepository | None, dict | None, dict | None]:
    """Claim a DIRAP mutation before its first write, or return replay data."""
    if not client_key:
        return None, None, None
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor="api",
            operation=operation,
            scope=scope,
            client_key=client_key,
            request_hash=request_hash,
            ttl_seconds=IDEMPOTENCY_TTL,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if inserted:
        return repo, claim, None
    if claim["state"] == "completed":
        return repo, claim, json.loads(claim["response_json"])
    if claim["state"] == "processing":
        raise HTTPException(status_code=409, detail="DIRAP request is still processing")
    raise HTTPException(status_code=409, detail="Previous DIRAP request failed; use a new Idempotency-Key")


async def _get_task_or_404(
    conn: aiosqlite.Connection, task_id: str, require_dirap_type: bool = True
) -> dict:
    """Fetch a task and optionally enforce it is a DIRAP work item."""
    task = await TaskRepository(conn).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if require_dirap_type and task.get("task_type") != DIRAP_TASK_TYPE:
        raise HTTPException(status_code=400, detail="Task is not a DIRAP work item")
    return task


async def _get_session_title(
    conn: aiosqlite.Connection, session_id: str | None
) -> str | None:
    """Get the title of a session."""
    if not session_id:
        return None
    async with conn.execute(
        "SELECT title FROM sessions WHERE id = ?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
    return row["title"] if row else None


async def _get_source_files(
    conn: aiosqlite.Connection, task_id: str
) -> list[DirapSourceFileResponse]:
    """Get source files attached to a work item."""
    rows: list[DirapSourceFileResponse] = []
    async with conn.execute(
        "SELECT id, task_id, file_path, file_name, note, attached_at "
        "FROM dirap_source_files WHERE task_id = ? ORDER BY attached_at ASC",
        (task_id,),
    ) as cur:
        async for row in cur:
            rows.append(
                DirapSourceFileResponse(
                    id=row["id"],
                    task_id=row["task_id"],
                    file_path=row["file_path"],
                    file_name=row["file_name"],
                    note=row["note"],
                    attached_at=row["attached_at"],
                )
            )
    return rows


async def _get_audit_events(
    conn: aiosqlite.Connection,
    session_id: str | None,
    task_id: str | None = None,
    limit: int = 50,
) -> list[AuditEventResponse]:
    """Get audit events filtered by session and optionally by task target."""
    if not session_id:
        return []
    events: list[AuditEventResponse] = []
    if task_id:
        async with conn.execute(
            "SELECT id, session_id, actor, action, target, payload_json, created_at "
            "FROM audit_events "
            "WHERE session_id = ? AND (target = ? OR payload_json LIKE ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, task_id, f"%{task_id}%", limit),
        ) as cur:
            async for row in cur:
                events.append(AuditEventResponse(**dict(row)))
    else:
        async with conn.execute(
            "SELECT id, session_id, actor, action, target, payload_json, created_at "
            "FROM audit_events "
            "WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ) as cur:
            async for row in cur:
                events.append(AuditEventResponse(**dict(row)))
    return events


def _build_work_item_response(
    task: dict,
    session_title: str | None = None,
    source_files: list[DirapSourceFileResponse] | None = None,
    duplicate: bool = False,
) -> DirapWorkItemResponse:
    return DirapWorkItemResponse(
        task_id=task["id"],
        session_id=task.get("session_id") or "",
        title=task.get("title"),
        goal=task.get("description"),  # store goal in description
        status=task["status"],
        task_type=task.get("task_type", ""),
        session_title=session_title,
        workspace_path=None,  # filled by caller if needed
        source_files=source_files or [],
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        duplicate=duplicate,
    )


@router.post("/work-items", response_model=DirapWorkItemResponse, status_code=status.HTTP_201_CREATED)
async def create_work_item(
    request: DirapWorkItemCreateRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapWorkItemResponse:
    """Create a DIRAP work item from an existing session.

    Creates a task record with task_type='dirap_work_item' and stores
    the goal in the description field. Links to the session via session_id.

    Idempotency-Key is optional. If provided, the same key with the same
    payload returns the original work item; same key with different payload returns 409.
    """
    # 1. Validate session exists
    async with conn.execute(
        "SELECT id, title, workspace_path FROM sessions WHERE id = ?",
        (request.session_id,),
    ) as cur:
        session_row = await cur.fetchone()
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Create the task via TaskService for idempotency support
    from app.services.task_service import TaskService

    service = TaskService(conn)
    try:
        task, duplicate = await service.create_task(
            session_id=request.session_id,
            title=request.title,
            description=request.goal,
            task_type=DIRAP_TASK_TYPE,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # 3. Audit event
    await log_audit_event(
        conn=conn,
        session_id=request.session_id,
        actor="api",
        action="dirap.work_item.created" if not duplicate else "dirap.work_item.create_replayed",
        target=task["id"],
        payload={
            "title": request.title,
            "goal": request.goal,
            "idempotency_key": bool(idempotency_key),
            "duplicate": duplicate,
        },
    )
    await conn.commit()

    if duplicate:
        response.status_code = status.HTTP_200_OK

    return _build_work_item_response(
        task,
        session_title=session_row["title"],
        duplicate=duplicate,
    )


@router.get("/work-items", response_model=list[DirapWorkItemResponse])
async def list_work_items(
    conn: aiosqlite.Connection = Depends(get_db),
    session_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DirapWorkItemResponse]:
    """List DIRAP work items (tasks with task_type='dirap_work_item')."""
    items: list[DirapWorkItemResponse] = []

    # Fetch DIRAP tasks with optional session filter
    clauses = ["task_type = ?"]
    params: list = [DIRAP_TASK_TYPE]
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)

    where = " AND ".join(clauses)
    query = f"SELECT * FROM tasks WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with conn.execute(query, params) as cur:
        rows = await cur.fetchall()

    for row in rows:
        task = dict(row)
        source_files = await _get_source_files(conn, task["id"])
        session_title = await _get_session_title(conn, task.get("session_id"))

        # Get workspace path
        workspace_path = None
        if task.get("session_id"):
            async with conn.execute(
                "SELECT workspace_path FROM sessions WHERE id = ?",
                (task["session_id"],),
            ) as sc:
                sr = await sc.fetchone()
                if sr:
                    workspace_path = sr["workspace_path"]

        item = _build_work_item_response(task, session_title, source_files)
        item.workspace_path = workspace_path
        items.append(item)

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.work_items.listed",
        payload={"session_id": session_id, "limit": limit, "offset": offset, "count": len(items)},
    )
    await conn.commit()
    return items


@router.get("/work-items/{task_id}", response_model=DirapWorkItemDetailResponse)
async def get_work_item_package(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DirapWorkItemDetailResponse:
    """Get a full DIRAP task package.

    Returns the work item with session info, source files, and audit trail.
    """
    task = await _get_task_or_404(conn, task_id)

    # Get session info
    session_id = task.get("session_id")
    session_title = await _get_session_title(conn, session_id)
    workspace_path = None
    if session_id:
        async with conn.execute(
            "SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                workspace_path = row["workspace_path"]

    source_files = await _get_source_files(conn, task_id)
    audit_events = await _get_audit_events(conn, session_id, task_id)

    work_item = _build_work_item_response(task, session_title, source_files)
    work_item.workspace_path = workspace_path

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.work_item.viewed",
        target=task_id,
    )
    await conn.commit()

    return DirapWorkItemDetailResponse(
        work_item=work_item,
        audit_events=audit_events,
    )


@router.post(
    "/work-items/{task_id}/source-files",
    response_model=DirapSourceFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_source_file(
    task_id: str,
    request: DirapSourceFileAttachRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapSourceFileResponse:
    """Attach a workspace-scoped source file to a DIRAP work item.

    The file_path must be relative to the session's workspace.
    Validates the path via the sandbox to prevent traversal or escape.

    Supports Idempotency-Key. Same key + same payload returns the existing
    attachment (200). Same key + different payload returns 409 conflict.
    """
    # 1. Validate task
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")

    # 2. Get workspace path from session
    workspace = await get_workspace_path(session_id, conn)

    # 3. Sandbox path validation
    resolved_path = resolve_and_validate_path(workspace, request.file_path, check_binary=False)

    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found on disk")

    # 4. Compute relative path and file name
    try:
        rel_path = resolved_path.relative_to(workspace).as_posix()
    except ValueError:
        rel_path = request.file_path

    file_name = resolved_path.name

    # Claim immediately before the first database side effect.  Validation can
    # be repeated safely by competing requests; inserting the source record
    # cannot.  The legacy header remains optional for compatibility.
    claim: dict | None = None
    if idempotency_key:
        irepo = IdempotencyRepository(conn)
        req_hash = _request_hash(task_id, request.file_path, request.note)
        try:
            claim, inserted = await irepo.claim_operation(
                actor="api", operation="dirap.source_file.attach", scope=task_id,
                client_key=idempotency_key, request_hash=req_hash, ttl_seconds=IDEMPOTENCY_TTL,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not inserted:
            if claim["state"] == "completed":
                response.status_code = status.HTTP_200_OK
                return DirapSourceFileResponse(**json.loads(claim["response_json"]))
            if claim["state"] == "processing":
                raise HTTPException(status_code=409, detail="Source-file request is still processing")
            raise HTTPException(status_code=409, detail="Previous source-file request failed; use a new Idempotency-Key")

    try:
        # 5. Insert record
        file_id = f"drsrc-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await conn.execute(
            "INSERT INTO dirap_source_files (id, task_id, file_path, file_name, note, attached_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, task_id, rel_path, file_name, request.note, now),
        )
        await log_audit_event(
            conn=conn, session_id=session_id, actor="api", action="dirap.source_file.attached", target=task_id,
            payload={"file_id": file_id, "file_path": rel_path, "file_name": file_name, "note": request.note},
        )
        resp_data = {
            "id": file_id,
            "task_id": task_id,
            "file_path": rel_path,
            "file_name": file_name,
            "note": request.note,
            "attached_at": now,
        }
        if claim is not None:
            await irepo.finalize_operation(claim, response=resp_data, status_code=status.HTTP_201_CREATED, resource_id=file_id)
        else:
            await conn.commit()
        return DirapSourceFileResponse(**resp_data)
    except HTTPException:
        await conn.rollback()
        if claim is not None:
            await irepo.fail_operation(claim, "source_file_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        if claim is not None:
            await irepo.fail_operation(claim, "source_file_failed")
        raise HTTPException(status_code=500, detail="Unable to attach source file") from exc


# -----------------------------------------------------------------------------
# DIRAP v3.0 Extraction
# -----------------------------------------------------------------------------

_EXTRACTION_PREVIEW_LIMIT = 100


async def _get_source_file_or_404(
    conn: aiosqlite.Connection, task_id: str, source_file_id: str
) -> dict:
    """Fetch a source file row that belongs to the given work item."""
    async with conn.execute(
        "SELECT id, task_id, file_path, file_name, note, attached_at "
        "FROM dirap_source_files WHERE id = ? AND task_id = ?",
        (source_file_id, task_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Source file not found")
    return dict(row)


async def _mark_previous_extractions_stale(
    conn: aiosqlite.Connection,
    source_file_id: str,
    new_hash: str,
    session_id: str,
    task_id: str,
) -> int:
    """Mark fresh extractions whose source hash no longer matches as stale.

    Returns the number of extractions marked stale. Logs an audit event per
    stale marking (required: every stale marking must have an audit event).
    """
    async with conn.execute(
        "SELECT id, source_sha256 FROM dirap_extractions "
        "WHERE source_file_id = ? AND status = 'fresh' AND source_sha256 != ?",
        (source_file_id, new_hash),
    ) as cur:
        stale_rows = await cur.fetchall()

    for row in stale_rows:
        await conn.execute(
            "UPDATE dirap_extractions SET status = 'stale' WHERE id = ?",
            (row["id"],),
        )
        await log_audit_event(
            conn=conn,
            session_id=session_id,
            actor="api",
            action="dirap.extraction.staled",
            target=row["id"],
            payload={
                "source_file_id": source_file_id,
                "previous_sha256": row["source_sha256"],
                "new_sha256": new_hash,
                "reason": "source content changed",
            },
        )
    return len(stale_rows)


async def _extraction_summary(row: aiosqlite.Row) -> DirapExtractionSummaryResponse:
    return DirapExtractionSummaryResponse(
        id=row["id"],
        source_file_id=row["source_file_id"],
        source_sha256=row["source_sha256"],
        extracted_at=row["extracted_at"],
        extractor_version=row["extractor_version"],
        file_type=row["file_type"],
        status=row["status"],
        record_count=row["record_count"],
    )


async def _refresh_source_freshness(
    conn: aiosqlite.Connection,
    session_id: str,
    task_id: str,
    source: dict,
) -> tuple[Path, str, str]:
    """Re-read the source file via the sandbox and recompute its SHA-256.

    Marks every fresh extraction whose stored hash no longer matches the
    current source content as ``stale`` (one audit event per real change), so
    old results are never presented as current data.

    Raises a clear HTTP error when the file is missing, unsupported, or the
    sandbox rejects the path — it never silently keeps ``fresh`` status.
    Returns ``(resolved_path, file_type, current_hash)``.
    """
    workspace = await get_workspace_path(session_id, conn)
    resolved_path = resolve_and_validate_path(
        workspace, source["file_path"], check_binary=False
    )
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found on disk")
    file_type = file_type_for(source["file_name"])
    if file_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Supported: .txt, .md, .csv, .json, .docx",
        )
    current_hash = sha256_of_file(resolved_path)
    await _mark_previous_extractions_stale(
        conn, source["id"], current_hash, session_id, task_id
    )
    return resolved_path, file_type, current_hash


@router.post(
    "/work-items/{task_id}/source-files/{source_file_id}/extract",
    response_model=DirapExtractionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def extract_source_file(
    task_id: str,
    source_file_id: str,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DirapExtractionDetailResponse:
    """Extract an attached workspace-scoped source file into ordered records.

    - Enforces the workspace sandbox before every file read.
    - Stores SHA-256 of the source content, extractor version, timestamp,
      file type, status and ordered records with provenance.
    - Idempotent: same source hash + same extractor version reuses the
      existing fresh extraction (HTTP 200) without new rows or audit events.
    - Marks previous fresh extractions stale when the source hash changes.
    - Logs an audit event for the extraction and for every stale marking.
    """
    # 1. Validate task + source file belong together
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")
    source = await _get_source_file_or_404(conn, task_id, source_file_id)

    # 2. Resolve once, then capture one bounded immutable snapshot.  Hashing
    # and parsing must never observe different versions of the source file.
    workspace = await get_workspace_path(session_id, conn)
    resolved_path = resolve_and_validate_path(
        workspace, source["file_path"], check_binary=False
    )
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found on disk")
    file_type = file_type_for(source["file_name"])
    if file_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Supported: .txt, .md, .csv, .json, .docx",
        )
    try:
        source_snapshot = resolved_path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to read source file") from exc
    source_hash = sha256_of_bytes(source_snapshot)
    await _mark_previous_extractions_stale(
        conn, source_file_id, source_hash, session_id, task_id
    )

    # 3. Replay: reuse the existing fresh extraction for this hash + version
    async with conn.execute(
        "SELECT id, source_file_id, source_sha256, extracted_at, extractor_version, "
        "file_type, status, record_count FROM dirap_extractions "
        "WHERE source_file_id = ? AND source_sha256 = ? AND extractor_version = ? "
        "AND status = 'fresh' ORDER BY extracted_at DESC LIMIT 1",
        (source_file_id, source_hash, EXTRACTOR_VERSION),
    ) as cur:
        existing = await cur.fetchone()
    if existing is not None:
        # No new extraction, records or 'completed' audit; return current result.
        await conn.commit()
        records: list[DirapExtractionRecordResponse] = []
        async with conn.execute(
            "SELECT id, seq, content, provenance FROM dirap_extraction_records "
            "WHERE extraction_id = ? ORDER BY seq ASC LIMIT ?",
            (existing["id"], _EXTRACTION_PREVIEW_LIMIT),
        ) as cur_records:
            async for rec in cur_records:
                records.append(
                    DirapExtractionRecordResponse(
                        id=rec["id"],
                        seq=rec["seq"],
                        content=rec["content"],
                        provenance=rec["provenance"],
                    )
                )
        response.status_code = status.HTTP_200_OK
        return DirapExtractionDetailResponse(
            extraction=await _extraction_summary(existing),
            records=records,
            total_records=existing["record_count"],
        )

    # 4. Deterministic extraction of fresh content
    try:
        records = extract_bytes(source_snapshot, file_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 5. Persist extraction + ordered records
    extraction_id = f"dext-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    await conn.execute(
        "INSERT INTO dirap_extractions "
        "(id, source_file_id, source_sha256, extracted_at, extractor_version, "
        " file_type, status, record_count) VALUES (?, ?, ?, ?, ?, ?, 'fresh', ?)",
        (
            extraction_id,
            source_file_id,
            source_hash,
            now,
            EXTRACTOR_VERSION,
            file_type,
            len(records),
        ),
    )
    created_records: list[dict] = []
    for rec in records:
        record_id = f"drec-{uuid.uuid4().hex[:12]}"
        created_records.append({**rec, "id": record_id})
        await conn.execute(
            "INSERT INTO dirap_extraction_records "
            "(id, extraction_id, seq, content, provenance) VALUES (?, ?, ?, ?, ?)",
            (
                record_id,
                extraction_id,
                rec["seq"],
                rec["content"],
                rec["provenance"],
            ),
        )

    # 6. Audit event for the extraction itself
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.extraction.completed",
        target=extraction_id,
        payload={
            "source_file_id": source_file_id,
            "file_path": source["file_path"],
            "file_name": source["file_name"],
            "file_type": file_type,
            "source_sha256": source_hash,
            "extractor_version": EXTRACTOR_VERSION,
            "record_count": len(records),
        },
    )
    await conn.commit()

    return DirapExtractionDetailResponse(
        extraction=DirapExtractionSummaryResponse(
            id=extraction_id,
            source_file_id=source_file_id,
            source_sha256=source_hash,
            extracted_at=now,
            extractor_version=EXTRACTOR_VERSION,
            file_type=file_type,
            status="fresh",
            record_count=len(records),
        ),
        records=[
            DirapExtractionRecordResponse(
                id=rec["id"],
                seq=rec["seq"],
                content=rec["content"],
                provenance=rec["provenance"],
            )
            for rec in created_records[:_EXTRACTION_PREVIEW_LIMIT]
        ],
        total_records=len(records),
    )


@router.get(
    "/work-items/{task_id}/source-files/{source_file_id}/extractions",
    response_model=list[DirapExtractionSummaryResponse],
)
async def list_extractions(
    task_id: str,
    source_file_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[DirapExtractionSummaryResponse]:
    """List extraction runs for a source file (newest first).

    Refreshes freshness first: if the source content changed since an
    extraction, that extraction is marked ``stale`` (with an audit event)
    before the list is returned, so old results are never shown as fresh.
    """
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    source = await _get_source_file_or_404(conn, task_id, source_file_id)

    # Freshness refresh before listing (marks changed-hash runs stale)
    await _refresh_source_freshness(conn, session_id, task_id, source)
    await conn.commit()

    extractions: list[DirapExtractionSummaryResponse] = []
    async with conn.execute(
        "SELECT id, source_file_id, source_sha256, extracted_at, extractor_version, "
        "file_type, status, record_count FROM dirap_extractions "
        "WHERE source_file_id = ? ORDER BY extracted_at DESC",
        (source_file_id,),
    ) as cur:
        async for row in cur:
            extractions.append(await _extraction_summary(row))

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.extractions.listed",
        target=source_file_id,
        payload={"count": len(extractions)},
    )
    await conn.commit()
    return extractions


@router.get(
    "/work-items/{task_id}/source-files/{source_file_id}/extractions/{extraction_id}",
    response_model=DirapExtractionDetailResponse,
)
async def get_extraction_detail(
    task_id: str,
    source_file_id: str,
    extraction_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
    limit: int = Query(_EXTRACTION_PREVIEW_LIMIT, ge=1, le=1000),
) -> DirapExtractionDetailResponse:
    """Get one extraction run with an ordered record preview.

    Refreshes freshness first: if the source content changed since this
    extraction, it is marked ``stale`` (with an audit event) before being
    returned, so old results are never shown as fresh.
    """
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    source = await _get_source_file_or_404(conn, task_id, source_file_id)

    # Freshness refresh before returning the detail
    await _refresh_source_freshness(conn, session_id, task_id, source)
    await conn.commit()

    async with conn.execute(
        "SELECT id, source_file_id, source_sha256, extracted_at, extractor_version, "
        "file_type, status, record_count FROM dirap_extractions "
        "WHERE id = ? AND source_file_id = ?",
        (extraction_id, source_file_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    records: list[DirapExtractionRecordResponse] = []
    async with conn.execute(
        "SELECT id, seq, content, provenance FROM dirap_extraction_records "
        "WHERE extraction_id = ? ORDER BY seq ASC LIMIT ?",
        (extraction_id, limit),
    ) as cur:
        async for rec in cur:
            records.append(
                DirapExtractionRecordResponse(
                    id=rec["id"], seq=rec["seq"], content=rec["content"], provenance=rec["provenance"]
                )
            )

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.extraction.viewed",
        target=extraction_id,
        payload={"source_file_id": source_file_id},
    )
    await conn.commit()

    return DirapExtractionDetailResponse(
        extraction=await _extraction_summary(row),
        records=records,
        total_records=row["record_count"],
    )


# -----------------------------------------------------------------------------
# DIRAP v3.0 Knowledge Records
# -----------------------------------------------------------------------------

def _knowledge_request_hash(
    task_id: str, extraction_id: str, extraction_record_id: str, note: str | None
) -> str:
    """Deterministic hash for knowledge-record creation idempotency."""
    raw = f"{task_id}|{extraction_id}|{extraction_record_id}|{note or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


_KNOWLEDGE_RECORD_COLUMNS = (
    "id, task_id, extraction_id, extraction_record_id, source_file_id, "
    "source_sha256, extractor_version, provenance, content, status, note, "
    "source_verification_state, calculation_verification_state, "
    "owner_acceptance_state, authority_status, created_at, updated_at"
)


def _knowledge_from_row(
    row: aiosqlite.Row, session_id: str | None
) -> DirapKnowledgeRecordResponse:
    """Build a knowledge-record response from a dirap_knowledge_records row."""
    return DirapKnowledgeRecordResponse(
        id=row["id"],
        task_id=row["task_id"],
        session_id=session_id,
        extraction_id=row["extraction_id"],
        extraction_record_id=row["extraction_record_id"],
        source_file_id=row["source_file_id"],
        source_sha256=row["source_sha256"],
        extractor_version=row["extractor_version"],
        provenance=row["provenance"],
        content=row["content"],
        status=row["status"],
        note=row["note"],
        source_verification_state=row["source_verification_state"],
        calculation_verification_state=row["calculation_verification_state"],
        owner_acceptance_state=row["owner_acceptance_state"],
        authority_status=row["authority_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _knowledge_evidence_from_row(row: aiosqlite.Row) -> DirapKnowledgeEvidenceResponse:
    """Build an evidence response from a dirap_knowledge_evidence row."""
    return DirapKnowledgeEvidenceResponse(
        id=row["id"],
        knowledge_record_id=row["knowledge_record_id"],
        evidence_type=row["evidence_type"],
        reference=row["reference"],
        note=row["note"],
        created_at=row["created_at"],
    )


async def _get_knowledge_record_or_404(
    conn: aiosqlite.Connection, task_id: str, record_id: str
) -> aiosqlite.Row:
    """Fetch a knowledge record that belongs to the given work item."""
    async with conn.execute(
        f"SELECT {_KNOWLEDGE_RECORD_COLUMNS} FROM dirap_knowledge_records "
        "WHERE id = ? AND task_id = ?",
        (record_id, task_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Knowledge record not found")
    return row


async def _load_knowledge_evidence(
    conn: aiosqlite.Connection, record_id: str
) -> list[DirapKnowledgeEvidenceResponse]:
    """Load evidence records for a knowledge record, newest first."""
    evidence: list[DirapKnowledgeEvidenceResponse] = []
    async with conn.execute(
        "SELECT id, knowledge_record_id, evidence_type, reference, note, created_at "
        "FROM dirap_knowledge_evidence WHERE knowledge_record_id = ? "
        "ORDER BY created_at ASC, id",
        (record_id,),
    ) as cur:
        async for row in cur:
            evidence.append(_knowledge_evidence_from_row(row))
    return evidence


@router.post(
    "/work-items/{task_id}/knowledge-records",
    response_model=DirapKnowledgeRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_record(
    task_id: str,
    request: DirapKnowledgeRecordCreateRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapKnowledgeRecordResponse:
    """Create a source-grounded draft knowledge record from exactly one fresh extraction record.

    - Reuses the existing session/task/sandbox/audit systems; no parallel store.
    - Stores durable source linkage only (task, extraction, extraction record,
      source hash, extractor version, provenance) plus the extracted content —
      never the whole source file or chat history.
    - Requires the extraction to belong to this work item and be ``fresh``;
      creating from a stale extraction or a foreign ID is rejected clearly.
    - New records are always ``draft``; never claimed verified/in-use/accepted.
    - Idempotency-Key is optional: same key + same payload returns the existing
      record (200); same key + different payload returns 409.
    """
    # 0. Idempotency check (before any mutation)
    claim: dict | None = None
    if idempotency_key:
        req_hash = _knowledge_request_hash(
            task_id, request.extraction_id, request.extraction_record_id, request.note
        )
        irepo = IdempotencyRepository(conn)
        try:
            claim, inserted = await irepo.claim_operation(
                actor="api", operation="dirap.knowledge_record.create", scope=task_id,
                client_key=idempotency_key, request_hash=req_hash, ttl_seconds=IDEMPOTENCY_TTL,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not inserted:
            if claim["state"] == "completed":
                response.status_code = status.HTTP_200_OK
                return DirapKnowledgeRecordResponse(**json.loads(claim["response_json"]))
            if claim["state"] == "processing":
                raise HTTPException(status_code=409, detail="Knowledge-record request is still processing")
            raise HTTPException(status_code=409, detail="Previous knowledge-record request failed; use a new Idempotency-Key")

    # 1. Validate task + session
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")

    # 2. The extraction must exist and belong to this work item
    async with conn.execute(
        "SELECT id, source_file_id, source_sha256, extractor_version, status "
        "FROM dirap_extractions WHERE id = ?",
        (request.extraction_id,),
    ) as cur:
        extraction = await cur.fetchone()
    if extraction is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    async with conn.execute(
        "SELECT id FROM dirap_source_files WHERE id = ? AND task_id = ?",
        (extraction["source_file_id"], task_id),
    ) as cur:
        own_source = await cur.fetchone()
    if own_source is None:
        raise HTTPException(status_code=404, detail="Extraction does not belong to this work item")
    source = await _get_source_file_or_404(conn, task_id, extraction["source_file_id"])

    # 3. Refresh freshness (marks changed-hash runs stale) and re-check status:
    #    creating a knowledge record from a stale extraction must be rejected.
    await _refresh_source_freshness(conn, session_id, task_id, source)
    async with conn.execute(
        "SELECT status FROM dirap_extractions WHERE id = ?",
        (request.extraction_id,),
    ) as cur:
        current_status = await cur.fetchone()
    if current_status is None or current_status["status"] != "fresh":
        # The freshness refresh intentionally mutates stale status and audit
        # history. Persist it before returning the expected conflict.
        await conn.commit()
        if claim is not None:
            await irepo.fail_operation(claim, "knowledge_record_stale")
        raise HTTPException(
            status_code=409,
            detail="Extraction is stale; re-extract the source file before turning it into a knowledge record",
        )

    # 4. Exactly one extraction record, inside this extraction
    async with conn.execute(
        "SELECT id, seq, content, provenance FROM dirap_extraction_records "
        "WHERE id = ? AND extraction_id = ?",
        (request.extraction_record_id, request.extraction_id),
    ) as cur:
        record = await cur.fetchone()
    if record is None:
        raise HTTPException(status_code=404, detail="Extraction record not found in this extraction")

    # 5. Persist the draft knowledge record (status is always 'draft')
    record_id = f"dkr-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    await conn.execute(
        "INSERT INTO dirap_knowledge_records "
        "(id, task_id, extraction_id, extraction_record_id, source_file_id, "
        " source_sha256, extractor_version, provenance, content, status, note, "
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
        (
            record_id,
            task_id,
            request.extraction_id,
            request.extraction_record_id,
            extraction["source_file_id"],
            extraction["source_sha256"],
            extraction["extractor_version"],
            record["provenance"],
            record["content"],
            request.note,
            now,
            now,
        ),
    )

    # 6. Audit event for the successful creation
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_record.created",
        target=record_id,
        payload={
            "task_id": task_id,
            "extraction_id": request.extraction_id,
            "extraction_record_id": request.extraction_record_id,
            "source_file_id": extraction["source_file_id"],
            "source_sha256": extraction["source_sha256"],
            "extractor_version": extraction["extractor_version"],
            "provenance": record["provenance"],
            "status": "draft",
            "note": request.note,
        },
    )

    # 7. Store idempotency record (after successful mutation)
    if claim is not None:
        row = await _get_knowledge_record_or_404(conn, task_id, record_id)
        resp_data = _knowledge_from_row(row, session_id).model_dump()
        await irepo.finalize_operation(claim, response=resp_data, status_code=status.HTTP_201_CREATED, resource_id=record_id)
    else:
        await conn.commit()
    return _knowledge_from_row(
        await _get_knowledge_record_or_404(conn, task_id, record_id), session_id
    )


@router.get(
    "/work-items/{task_id}/knowledge-records",
    response_model=list[DirapKnowledgeRecordResponse],
)
async def list_knowledge_records(
    task_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[DirapKnowledgeRecordResponse]:
    """List draft knowledge records for a work item (newest first)."""
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")

    records: list[DirapKnowledgeRecordResponse] = []
    async with conn.execute(
        f"SELECT {_KNOWLEDGE_RECORD_COLUMNS} FROM dirap_knowledge_records "
        "WHERE task_id = ? ORDER BY created_at DESC",
        (task_id,),
    ) as cur:
        async for row in cur:
            records.append(_knowledge_from_row(row, session_id))

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_records.listed",
        target=task_id,
        payload={"count": len(records)},
    )
    await conn.commit()
    return records


@router.get(
    "/work-items/{task_id}/knowledge-records/search",
    response_model=DirapKnowledgeSearchResponse,
)
async def search_knowledge_records(
    task_id: str,
    q: str = Query(..., max_length=200),
    query_type: DirapUsabilityQueryType = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: aiosqlite.Connection = Depends(get_db),
) -> DirapKnowledgeSearchResponse:
    """Tìm cụm từ trong bản ghi tri thức của đúng một nhiệm vụ (chỉ đọc).

    - Route cố định ``.../search`` khai báo TRƯỚC ``/{knowledge_record_id}``
      nên không bao giờ bị hiểu nhầm ``search`` là ID bản ghi.
    - So khớp tất định (casefold + gộp khoảng trắng) trên ``content`` và
      ``provenance``; sau đó lọc theo chính sách v1 rồi MỚI phân trang.
    - Tuyệt đối chỉ đọc: không audit, không commit, không lưu kết quả tìm kiếm.
    """
    await _get_task_or_404(conn, task_id)

    query_norm = normalize_search_text(q)
    if not query_norm:
        raise HTTPException(
            status_code=422,
            detail="q không được rỗng sau khi chuẩn hóa khoảng trắng.",
        )

    cursor = await conn.execute(
        """
        SELECT id, content, provenance, status,
               source_verification_state, calculation_verification_state,
               owner_acceptance_state, authority_status
        FROM dirap_knowledge_records
        WHERE task_id = ?
        ORDER BY created_at DESC, id
        """,
        (task_id,),
    )
    rows = await cursor.fetchall()
    await cursor.close()

    records = [
        SearchRecord(
            record_id=row[0],
            content=row[1],
            provenance=row[2],
            lifecycle_state=row[3],
            source_verification_state=row[4],
            calculation_verification_state=row[5],
            owner_acceptance_state=row[6],
            authority_status=row[7],
        )
        for row in rows
    ]
    outcome = search_records(
        records, query=query_norm, query_type=query_type, limit=limit, offset=offset
    )
    return DirapKnowledgeSearchResponse(
        query_type=query_type,
        total=outcome.total,
        limit=limit,
        offset=offset,
        results=[
            DirapKnowledgeSearchResult(**asdict(item)) for item in outcome.items
        ],
    )


@router.get(
    "/work-items/{task_id}/knowledge-records/{knowledge_record_id}",
    response_model=DirapKnowledgeRecordDetailResponse,
)
async def get_knowledge_record_detail(
    task_id: str,
    knowledge_record_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DirapKnowledgeRecordDetailResponse:
    """Get one knowledge record that belongs to the work item, with its evidence."""
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    row = await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id)
    evidence = await _load_knowledge_evidence(conn, knowledge_record_id)

    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_record.viewed",
        target=knowledge_record_id,
        payload={"task_id": task_id, "source_sha256": row["source_sha256"], "status": row["status"]},
    )
    await conn.commit()

    base = _knowledge_from_row(row, session_id)
    return DirapKnowledgeRecordDetailResponse(
        **base.model_dump(),
        evidence=evidence,
    )


# -----------------------------------------------------------------------------
# DIRAP v3.0 Knowledge Review (controlled lifecycle)
# -----------------------------------------------------------------------------
#
# Allowed transitions only: draft -> review_pending -> active|rejected.
# The four verification dimensions are stored independently and are computed
# by the server from the submitted evidence references; clients can never set
# status or dimensions directly.


async def _review_transition(
    conn: aiosqlite.Connection,
    task_id: str,
    record_id: str,
    expected_status: str,
    action: str,
) -> aiosqlite.Row:
    """Load the record, enforce work-item scope and the exact allowed transition."""
    row = await _get_knowledge_record_or_404(conn, task_id, record_id)
    if row["status"] != expected_status:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot {action}: knowledge record is '{row['status']}', "
                f"expected '{expected_status}'. Allowed transitions: "
                "draft -> review_pending -> active|rejected."
            ),
        )
    return row


async def _begin_atomic_review_transition(
    conn: aiosqlite.Connection,
    task_id: str,
    record_id: str,
    expected_status: str,
    action: str,
    repo: IdempotencyRepository | None,
    claim: dict | None,
) -> aiosqlite.Row:
    """Serialize lifecycle decisions and fail a claimed loser cleanly."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        return await _review_transition(conn, task_id, record_id, expected_status, action)
    except HTTPException:
        await conn.rollback()
        if repo is not None and claim is not None:
            await repo.fail_operation(claim, "invalid_review_transition")
        raise


async def _insert_evidence(
    conn: aiosqlite.Connection,
    record_id: str,
    evidence_type: str,
    reference: str,
    note: str | None,
    now: int,
) -> str:
    evidence_id = f"kev-{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO dirap_knowledge_evidence "
        "(id, knowledge_record_id, evidence_type, reference, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (evidence_id, record_id, evidence_type, reference, note, now),
    )
    return evidence_id


@router.post(
    "/work-items/{task_id}/knowledge-records/{knowledge_record_id}/submit",
    response_model=DirapKnowledgeRecordResponse,
)
async def submit_knowledge_record(
    task_id: str,
    knowledge_record_id: str,
    request: DirapKnowledgeSubmitRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapKnowledgeRecordResponse:
    """Submit a draft for review (draft → review_pending).

    - Work-item scoped (404 for another work item's record).
    - Any other transition is rejected with 409.
    - Client cannot set status or the four verification dimensions: the server
      computes them from evidence at approve/reject time.
    - Idempotency-Key optional: same key + same payload replays (200).
    """
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")

    req_hash = hashlib.sha256(json.dumps(
        {"action": "submit", "record_id": knowledge_record_id, "note": request.note or ""}, sort_keys=True,
    ).encode()).hexdigest()
    irepo, claim, replay = await _claim_dirap_mutation(
        conn, operation="dirap.knowledge_record.submit", scope=f"{task_id}:{knowledge_record_id}",
        client_key=idempotency_key, request_hash=req_hash,
    )
    if replay is not None:
        response.status_code = status.HTTP_200_OK
        return DirapKnowledgeRecordResponse(**replay)

    row = await _begin_atomic_review_transition(
        conn, task_id, knowledge_record_id, "draft", "submit for review", irepo, claim,
    )
    now = int(time.time())
    await conn.execute(
        "UPDATE dirap_knowledge_records SET status = 'review_pending', note = COALESCE(?, note), "
        "updated_at = ? WHERE id = ?",
        (request.note, now, knowledge_record_id),
    )
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_record.submitted",
        target=knowledge_record_id,
        payload={"from": "draft", "to": "review_pending", "note": request.note},
    )

    if claim is not None and irepo is not None:
        updated = await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id)
        payload = _knowledge_from_row(updated, session_id).model_dump()
        await irepo.finalize_operation(
            claim, response=payload, status_code=status.HTTP_200_OK, resource_id=knowledge_record_id,
        )
    else:
        await conn.commit()
    return _knowledge_from_row(
        await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id), session_id
    )


@router.post(
    "/work-items/{task_id}/knowledge-records/{knowledge_record_id}/review/approve",
    response_model=DirapKnowledgeRecordResponse,
)
async def approve_knowledge_record(
    task_id: str,
    knowledge_record_id: str,
    request: DirapKnowledgeApproveRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapKnowledgeRecordResponse:
    """Approve a reviewed record (review_pending → active).

    Requires reviewer reference, source-evidence reference, authority status
    different from 'none' and an authority reference. With a calculation-
    evidence reference the calculation dimension becomes 'verified', otherwise
    it stays 'unverified'. All evidence gets its own record attached to the
    knowledge record; nothing is marked verified without a reference.
    """
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")

    authority_status = request.authority_status.strip()
    if authority_status.lower() == "none":
        raise HTTPException(
            status_code=400,
            detail="Approve requires an authority status different from 'none' with an authority reference",
        )

    req_hash = hashlib.sha256(json.dumps({
        "action": "approve", "record_id": knowledge_record_id, "reviewer": request.reviewer,
        "source_evidence_reference": request.source_evidence_reference, "authority_status": authority_status,
        "authority_reference": request.authority_reference,
        "calculation_evidence_reference": request.calculation_evidence_reference or "", "note": request.note or "",
    }, sort_keys=True).encode()).hexdigest()
    irepo, claim, replay = await _claim_dirap_mutation(
        conn, operation="dirap.knowledge_record.approve", scope=f"{task_id}:{knowledge_record_id}",
        client_key=idempotency_key, request_hash=req_hash,
    )
    if replay is not None:
        response.status_code = status.HTTP_200_OK
        return DirapKnowledgeRecordResponse(**replay)

    row = await _begin_atomic_review_transition(
        conn, task_id, knowledge_record_id, "review_pending", "approve", irepo, claim,
    )

    now = int(time.time())
    evidence_note = request.note or "approve"
    await _insert_evidence(conn, knowledge_record_id, "reviewer", request.reviewer, None, now)
    await _insert_evidence(
        conn, knowledge_record_id, "source_evidence", request.source_evidence_reference, evidence_note, now
    )
    await _insert_evidence(
        conn, knowledge_record_id, "authority_evidence", request.authority_reference, authority_status, now
    )
    calc_state = "unverified"
    if request.calculation_evidence_reference:
        calc_state = "verified"
        await _insert_evidence(
            conn,
            knowledge_record_id,
            "calculation_evidence",
            request.calculation_evidence_reference,
            evidence_note,
            now,
        )

    await conn.execute(
        "UPDATE dirap_knowledge_records SET status = 'active', "
        "source_verification_state = 'verified', "
        "calculation_verification_state = ?, "
        "owner_acceptance_state = 'accepted', authority_status = ?, updated_at = ? "
        "WHERE id = ?",
        (calc_state, authority_status, now, knowledge_record_id),
    )
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_record.accepted",
        target=knowledge_record_id,
        payload={
            "from": "review_pending",
            "to": "active",
            "reviewer": request.reviewer,
            "source_evidence_reference": request.source_evidence_reference,
            "calculation_verification_state": calc_state,
            "calculation_evidence_reference": request.calculation_evidence_reference,
            "owner_acceptance_state": "accepted",
            "authority_status": authority_status,
            "authority_reference": request.authority_reference,
            "note": request.note,
        },
    )

    if claim is not None and irepo is not None:
        updated = await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id)
        payload = _knowledge_from_row(updated, session_id).model_dump()
        await irepo.finalize_operation(
            claim, response=payload, status_code=status.HTTP_200_OK, resource_id=knowledge_record_id,
        )
    else:
        await conn.commit()
    return _knowledge_from_row(
        await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id), session_id
    )


@router.post(
    "/work-items/{task_id}/knowledge-records/{knowledge_record_id}/review/reject",
    response_model=DirapKnowledgeRecordResponse,
)
async def reject_knowledge_record(
    task_id: str,
    knowledge_record_id: str,
    request: DirapKnowledgeRejectRequest,
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DirapKnowledgeRecordResponse:
    """Reject a reviewed record (review_pending → rejected).

    Requires reviewer reference and a reason. Owner acceptance is set to
    'rejected'; source data and audit history are preserved (no deletes).
    """
    task = await _get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")

    req_hash = hashlib.sha256(json.dumps({
        "action": "reject", "record_id": knowledge_record_id,
        "reviewer": request.reviewer, "reason": request.reason,
    }, sort_keys=True).encode()).hexdigest()
    irepo, claim, replay = await _claim_dirap_mutation(
        conn, operation="dirap.knowledge_record.reject", scope=f"{task_id}:{knowledge_record_id}",
        client_key=idempotency_key, request_hash=req_hash,
    )
    if replay is not None:
        response.status_code = status.HTTP_200_OK
        return DirapKnowledgeRecordResponse(**replay)

    row = await _begin_atomic_review_transition(
        conn, task_id, knowledge_record_id, "review_pending", "reject", irepo, claim,
    )

    now = int(time.time())
    await _insert_evidence(conn, knowledge_record_id, "reviewer", request.reviewer, None, now)
    await _insert_evidence(conn, knowledge_record_id, "decision_reason", request.reason, None, now)

    await conn.execute(
        "UPDATE dirap_knowledge_records SET status = 'rejected', "
        "owner_acceptance_state = 'rejected', updated_at = ? WHERE id = ?",
        (now, knowledge_record_id),
    )
    await log_audit_event(
        conn=conn,
        session_id=session_id,
        actor="api",
        action="dirap.knowledge_record.rejected",
        target=knowledge_record_id,
        payload={
            "from": "review_pending",
            "to": "rejected",
            "reviewer": request.reviewer,
            "reason": request.reason,
            "owner_acceptance_state": "rejected",
        },
    )

    if claim is not None and irepo is not None:
        updated = await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id)
        payload = _knowledge_from_row(updated, session_id).model_dump()
        await irepo.finalize_operation(
            claim, response=payload, status_code=status.HTTP_200_OK, resource_id=knowledge_record_id,
        )
    else:
        await conn.commit()
    return _knowledge_from_row(
        await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id), session_id
    )


# -----------------------------------------------------------------------------
# DIRAP v3.0 Usability (read-only, policy v1)
# -----------------------------------------------------------------------------
#
# Tính khả dụng theo chính sách v1 cho đúng một mục đích của một bản ghi tri
# thức thuộc đúng nhiệm vụ. Hoàn toàn chỉ đọc:
#   - không đổi vòng đời, không đổi bốn chiều dữ kiện gốc;
#   - không ghi kết quả (overall_usability_state chỉ tính lúc đọc);
#   - không migration, không audit cho lần tính chính sách.


@router.get(
    "/work-items/{task_id}/knowledge-records/{knowledge_record_id}/usability",
    response_model=DirapUsabilityResponse,
)
async def get_knowledge_usability(
    task_id: str,
    knowledge_record_id: str,
    query_type: DirapUsabilityQueryType,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DirapUsabilityResponse:
    """Tính khả dụng theo chính sách v1 (chỉ đọc) cho một bản ghi tri thức.

    - ``query_type`` không hợp lệ → 422 (chuẩn FastAPI Literal).
    - Bản ghi không tồn tại hoặc thuộc nhiệm vụ khác → 404 (giống các
      endpoint tri thức hiện có, qua ``_get_knowledge_record_or_404``).
    - Không tạo audit event và không commit: đây là lần tính chính sách
      thuần đọc, không phải một sự kiện nghiệp vụ.
    """
    await _get_task_or_404(conn, task_id)
    row = await _get_knowledge_record_or_404(conn, task_id, knowledge_record_id)

    result = evaluate_usability(
        source_verification_state=row["source_verification_state"],
        calculation_verification_state=row["calculation_verification_state"],
        owner_acceptance_state=row["owner_acceptance_state"],
        authority_status=row["authority_status"],
        query_type=query_type,
    )
    usable = usable_for_query_types(
        source_verification_state=row["source_verification_state"],
        calculation_verification_state=row["calculation_verification_state"],
        owner_acceptance_state=row["owner_acceptance_state"],
        authority_status=row["authority_status"],
    )

    return DirapUsabilityResponse(
        record_id=row["id"],
        lifecycle_state=row["status"],
        query_type=query_type,
        source_verification_state=row["source_verification_state"],
        calculation_verification_state=row["calculation_verification_state"],
        owner_acceptance_state=row["owner_acceptance_state"],
        authority_status=row["authority_status"],
        overall_usability_state=result.overall_usability_state,
        policy_version="v1",
        exclusions=[
            {
                "dimension": exc.dimension,
                "required_state": exc.required_state,
                "actual_state": exc.actual_state,
                "reason": exc.reason,
            }
            for exc in result.exclusions
        ],
        usable_for_query_types=usable,
    )
