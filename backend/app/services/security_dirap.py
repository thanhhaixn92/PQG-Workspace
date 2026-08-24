from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.api import dirap as dirap_api
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository
from app.services.audit import log_audit_event
from app.services.extraction import EXTRACTOR_VERSION, extract_bytes, file_type_for
from app.services.sandbox import get_workspace_path
from app.services.sandbox_io import MAX_FILE_SIZE, inspect_path, normalized_relative_string, read_snapshot


async def secure_attach_source_file(
    task_id: str,
    request,
    response,
    conn,
    settings,
    idempotency_key: str | None = None,
):
    task = await dirap_api._get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")
    workspace = await get_workspace_path(session_id, conn)
    relative = normalized_relative_string(request.file_path)
    stat_result = inspect_path(workspace, relative, max_size=MAX_FILE_SIZE)
    if stat_result.is_dir:
        raise HTTPException(status_code=400, detail="Target is a directory")
    rel_path = stat_result.relative_path
    file_name = stat_result.name

    claim: dict | None = None
    irepo: IdempotencyRepository | None = None
    if idempotency_key:
        irepo = IdempotencyRepository(conn)
        req_hash = dirap_api._request_hash(task_id, request.file_path, request.note)
        try:
            claim, inserted = await irepo.claim_operation(
                actor="api",
                operation="dirap.source_file.attach",
                scope=task_id,
                client_key=idempotency_key,
                request_hash=req_hash,
                ttl_seconds=dirap_api.IDEMPOTENCY_TTL,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not inserted:
            if claim["state"] == "completed":
                response.status_code = status.HTTP_200_OK
                return dirap_api.DirapSourceFileResponse(**json.loads(claim["response_json"]))
            if claim["state"] == "processing":
                raise HTTPException(status_code=409, detail="Source-file request is still processing")
            raise HTTPException(status_code=409, detail="Previous source-file request failed; use a new Idempotency-Key")

    try:
        file_id = f"drsrc-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await conn.execute(
            "INSERT INTO dirap_source_files (id, task_id, file_path, file_name, note, attached_at) VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, task_id, rel_path, file_name, request.note, now),
        )
        await log_audit_event(
            conn=conn,
            session_id=session_id,
            actor="api",
            action="dirap.source_file.attached",
            target=task_id,
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
        if claim is not None and irepo is not None:
            await irepo.finalize_operation(
                claim,
                response=resp_data,
                status_code=status.HTTP_201_CREATED,
                resource_id=file_id,
            )
        else:
            await conn.commit()
        return dirap_api.DirapSourceFileResponse(**resp_data)
    except HTTPException:
        await conn.rollback()
        if claim is not None and irepo is not None:
            await irepo.fail_operation(claim, "source_file_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        if claim is not None and irepo is not None:
            await irepo.fail_operation(claim, "source_file_failed")
        raise HTTPException(status_code=500, detail="Unable to attach source file") from exc


async def secure_refresh_source_freshness(conn, session_id: str, task_id: str, source: dict):
    workspace = await get_workspace_path(session_id, conn)
    file_type = file_type_for(source["file_name"])
    if file_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Supported: .txt, .md, .csv, .json, .docx",
        )
    snapshot = read_snapshot(workspace, source["file_path"], max_size=MAX_FILE_SIZE)
    await dirap_api._mark_previous_extractions_stale(
        conn,
        source["id"],
        snapshot.sha256,
        session_id,
        task_id,
    )
    return Path(workspace) / snapshot.relative_path, file_type, snapshot.sha256


async def secure_extract_source_file(task_id: str, source_file_id: str, response, conn):
    task = await dirap_api._get_task_or_404(conn, task_id)
    session_id = task.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Task has no session")
    source = await dirap_api._get_source_file_or_404(conn, task_id, source_file_id)
    workspace = await get_workspace_path(session_id, conn)
    file_type = file_type_for(source["file_name"])
    if file_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Supported: .txt, .md, .csv, .json, .docx",
        )
    snapshot = read_snapshot(workspace, source["file_path"], max_size=MAX_FILE_SIZE)
    source_hash = snapshot.sha256
    await dirap_api._mark_previous_extractions_stale(
        conn,
        source_file_id,
        source_hash,
        session_id,
        task_id,
    )

    async with conn.execute(
        "SELECT id, source_file_id, source_sha256, extracted_at, extractor_version, file_type, status, record_count "
        "FROM dirap_extractions WHERE source_file_id = ? AND source_sha256 = ? AND extractor_version = ? "
        "AND status = 'fresh' ORDER BY extracted_at DESC LIMIT 1",
        (source_file_id, source_hash, EXTRACTOR_VERSION),
    ) as cur:
        existing = await cur.fetchone()
    if existing is not None:
        await conn.commit()
        records = []
        async with conn.execute(
            "SELECT id, seq, content, provenance FROM dirap_extraction_records WHERE extraction_id = ? ORDER BY seq ASC LIMIT ?",
            (existing["id"], dirap_api._EXTRACTION_PREVIEW_LIMIT),
        ) as cur_records:
            async for rec in cur_records:
                records.append(
                    dirap_api.DirapExtractionRecordResponse(
                        id=rec["id"],
                        seq=rec["seq"],
                        content=rec["content"],
                        provenance=rec["provenance"],
                    )
                )
        response.status_code = status.HTTP_200_OK
        return dirap_api.DirapExtractionDetailResponse(
            extraction=await dirap_api._extraction_summary(existing),
            records=records,
            total_records=existing["record_count"],
        )

    try:
        records = extract_bytes(snapshot.data, file_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extraction_id = f"dext-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    await conn.execute(
        "INSERT INTO dirap_extractions "
        "(id, source_file_id, source_sha256, extracted_at, extractor_version, file_type, status, record_count) "
        "VALUES (?, ?, ?, ?, ?, ?, 'fresh', ?)",
        (extraction_id, source_file_id, source_hash, now, EXTRACTOR_VERSION, file_type, len(records)),
    )
    created_records: list[dict] = []
    for rec in records:
        record_id = f"drec-{uuid.uuid4().hex[:12]}"
        created_records.append({**rec, "id": record_id})
        await conn.execute(
            "INSERT INTO dirap_extraction_records (id, extraction_id, seq, content, provenance) VALUES (?, ?, ?, ?, ?)",
            (record_id, extraction_id, rec["seq"], rec["content"], rec["provenance"]),
        )
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
    return dirap_api.DirapExtractionDetailResponse(
        extraction=dirap_api.DirapExtractionSummaryResponse(
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
            dirap_api.DirapExtractionRecordResponse(
                id=rec["id"],
                seq=rec["seq"],
                content=rec["content"],
                provenance=rec["provenance"],
            )
            for rec in created_records[: dirap_api._EXTRACTION_PREVIEW_LIMIT]
        ],
        total_records=len(records),
    )
