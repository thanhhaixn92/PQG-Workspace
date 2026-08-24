from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.api import artifacts as artifacts_api
from app.api.schemas import DocumentImportResponse, ManagedFolderResponse, ReportCreateResponse
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository
from app.services.audit import log_audit_event
from app.services.sandbox import get_workspace_path
from app.services.sandbox_io import (
    create_directory,
    delete_empty_directory,
    delete_file,
    managed_size,
    write_bytes,
)


async def secure_create_managed_text_file(
    session_id: str,
    request,
    idempotency_key: str,
    response,
    conn,
) -> DocumentImportResponse:
    await artifacts_api._require_active_session(conn, session_id)
    safe_name = artifacts_api._validate_managed_relative_path(request.relative_path, allow_nested=False)
    content = request.content.encode("utf-8")
    if len(content) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Created text file exceeds the 1 MB editor limit")
    digest = hashlib.sha256(content).hexdigest()
    request_hash = hashlib.sha256(f"{safe_name.as_posix()}\x1f{digest}".encode("utf-8")).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor="user", operation="document.file.create", scope=session_id,
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed":
            replay = DocumentImportResponse(**json.loads(claim["response_json"]), duplicate=True)
            response.status_code = status.HTTP_200_OK
            return replay
        raise HTTPException(status_code=409, detail="File creation is already processing or previously failed")

    published_relative: str | None = None
    completed = False
    workspace = None
    try:
        workspace = await get_workspace_path(session_id, conn)
        if managed_size(workspace, stop_after=artifacts_api.MAX_MANAGED_WORKSPACE_BYTES) + len(content) > artifacts_api.MAX_MANAGED_WORKSPACE_BYTES:
            raise HTTPException(status_code=413, detail="Managed workspace quota would exceed 100 MB")
        relative_target = (Path("inputs") / safe_name).as_posix()
        write_bytes(workspace, relative_target, content, create_only=True, create_parents=True)
        published_relative = relative_target
        artifact = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "relative_path": relative_target,
            "kind": "created_text_file",
            "sha256": digest,
            "size_bytes": len(content),
            "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""",
            artifact,
        )
        media_type = artifacts_api._ALLOWED_IMPORTS.get(safe_name.suffix.casefold())
        validation_status = "pending"
        if safe_name.suffix.casefold() in {".txt", ".md", ".csv"}:
            validation_status = "structurally_validated"
            await artifacts_api._record_validation(
                conn,
                artifact["id"],
                status_value=validation_status,
                media_type=media_type,
                detail={"source": "managed_text", "bytes": len(content)},
            )
        await log_audit_event(
            conn,
            session_id,
            "user",
            "document.file_created",
            artifact["relative_path"],
            {"artifact_id": artifact["id"], "size_bytes": len(content)},
        )
        await repo.finalize_operation(claim, response=artifact, status_code=201, resource_id=artifact["id"])
        completed = True
        return DocumentImportResponse(**artifact, validation_status=validation_status, media_type=media_type)
    except HTTPException:
        await conn.rollback()
        await repo.fail_operation(claim, "file_create_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        await repo.fail_operation(claim, "file_create_failed")
        raise HTTPException(status_code=500, detail="Unable to create document") from exc
    finally:
        if not completed and published_relative is not None and workspace is not None:
            try:
                delete_file(workspace, published_relative, missing_ok=True)
            except Exception:
                pass


async def secure_create_managed_folder(
    session_id: str,
    request,
    idempotency_key: str,
    response,
    conn,
) -> ManagedFolderResponse:
    await artifacts_api._require_active_session(conn, session_id)
    safe_name = artifacts_api._validate_managed_relative_path(request.relative_path, allow_nested=False)
    request_hash = hashlib.sha256(safe_name.as_posix().encode("utf-8")).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor="user", operation="document.folder.create", scope=session_id,
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed":
            replay = ManagedFolderResponse(**json.loads(claim["response_json"]), duplicate=True)
            response.status_code = status.HTTP_200_OK
            return replay
        raise HTTPException(status_code=409, detail="Folder creation is already processing or previously failed")

    workspace = None
    relative_target: str | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        relative_target = (Path("inputs") / safe_name).as_posix()
        create_directory(workspace, "inputs", parents=True, exist_ok=True)
        create_directory(workspace, relative_target, parents=False, exist_ok=False)
        payload = {"relative_path": relative_target}
        await log_audit_event(
            conn,
            session_id,
            "user",
            "document.folder_created",
            relative_target,
            {},
        )
        await repo.finalize_operation(claim, response=payload, status_code=201, resource_id=None)
        completed = True
        return ManagedFolderResponse(**payload)
    except HTTPException:
        await conn.rollback()
        await repo.fail_operation(claim, "folder_create_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        await repo.fail_operation(claim, "folder_create_failed")
        raise HTTPException(status_code=500, detail="Unable to create folder") from exc
    finally:
        if not completed and workspace is not None and relative_target is not None:
            try:
                delete_empty_directory(workspace, relative_target, missing_ok=True)
            except Exception:
                pass


async def secure_create_report(
    session_id: str,
    request,
    idempotency_key: str,
    response,
    conn,
) -> ReportCreateResponse:
    await artifacts_api._require_active_session(conn, session_id)
    request_hash = hashlib.sha256(
        f"{request.title}\x1f{request.output_format}\x1f{request.content}".encode("utf-8")
    ).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor="user", operation="report.create", scope=session_id,
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed":
            replay = ReportCreateResponse(**json.loads(claim["response_json"]))
            replay.duplicate = True
            response.status_code = status.HTTP_200_OK
            return replay
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Report request is still processing")
        raise HTTPException(status_code=409, detail="Previous report request failed; use a new Idempotency-Key")

    workspace = None
    relative_target: str | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        content_bytes, artifact_kind = artifacts_api._render_report(request)
        filename = artifacts_api._report_filename(request.title, request.output_format)
        relative_target = (Path("outputs") / "reports" / filename).as_posix()
        write_bytes(workspace, relative_target, content_bytes, create_only=True, create_parents=True)
        artifact = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "relative_path": relative_target,
            "kind": artifact_kind,
            "sha256": hashlib.sha256(content_bytes).hexdigest(),
            "size_bytes": len(content_bytes),
            "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""",
            artifact,
        )
        await log_audit_event(
            conn,
            session_id,
            "user",
            "report.created",
            artifact["relative_path"],
            {"artifact_id": artifact["id"], "kind": artifact["kind"], "size_bytes": artifact["size_bytes"]},
        )
        await repo.finalize_operation(claim, response=artifact, status_code=201, resource_id=artifact["id"])
        completed = True
        return ReportCreateResponse(**artifact)
    except HTTPException:
        await conn.rollback()
        await repo.fail_operation(claim, "report_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        await repo.fail_operation(claim, "report_failed")
        raise HTTPException(status_code=500, detail="Unable to create report") from exc
    finally:
        if not completed and workspace is not None and relative_target is not None:
            try:
                delete_file(workspace, relative_target, missing_ok=True)
            except Exception:
                pass
