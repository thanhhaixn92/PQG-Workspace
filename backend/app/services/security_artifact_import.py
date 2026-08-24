from __future__ import annotations

import hashlib
import io
import json
import re
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import HTTPException, Response, status

from app.api import artifacts as artifacts_api
from app.api.schemas import DocumentImportResponse
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository
from app.services.audit import log_audit_event
from app.services.sandbox import get_workspace_path
from app.services.sandbox_io import delete_file, managed_size, read_snapshot, write_bytes


def _validate_import_bytes(content: bytes, name: Path) -> str:
    """Mirror the current structural import contract on one immutable byte snapshot."""
    suffix = name.suffix.casefold()
    media_type = artifacts_api._ALLOWED_IMPORTS.get(suffix)
    if media_type is None:
        raise HTTPException(status_code=422, detail="File type is not allowed for GYO context")
    head = content[:32]
    if suffix == ".pdf" and not head.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="PDF signature is invalid")
    if suffix == ".pdf":
        object_count = sum(1 for _ in re.finditer(rb"(?m)^\s*\d+\s+\d+\s+obj\b", content))
        stream_count = sum(1 for _ in re.finditer(rb"(?m)^\s*stream\r?$", content))
        declared_stream_bytes = 0
        for match in re.finditer(rb"/Length\s+(\d+)\b", content):
            declared_stream_bytes += int(match.group(1))
            if declared_stream_bytes > artifacts_api.MAX_PDF_DECLARED_STREAM_BYTES:
                break
        if (
            object_count > artifacts_api.MAX_PDF_OBJECTS
            or stream_count > artifacts_api.MAX_PDF_STREAMS
            or declared_stream_bytes > artifacts_api.MAX_PDF_DECLARED_STREAM_BYTES
        ):
            raise HTTPException(status_code=422, detail="PDF exceeds safe structural resource limits")
    if suffix == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="PNG signature is invalid")
    if suffix in {".jpg", ".jpeg"} and not head.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="JPEG signature is invalid")
    if suffix == ".webp" and not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
        raise HTTPException(status_code=422, detail="WebP signature is invalid")
    if suffix in {".docx", ".xlsx", ".pptx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > artifacts_api.MAX_OOXML_ENTRIES:
                    raise HTTPException(status_code=422, detail="Office document has too many entries")
                total = sum(info.file_size for info in infos)
                compressed = sum(info.compress_size for info in infos)
                if total > artifacts_api.MAX_OOXML_UNCOMPRESSED_BYTES or (
                    compressed and total / compressed > artifacts_api.MAX_OOXML_COMPRESSION_RATIO
                ):
                    raise HTTPException(status_code=422, detail="Office document exceeds safe extraction limits")
                names = [info.filename for info in infos]
                if any("vbaproject.bin" in item.casefold() for item in names):
                    raise HTTPException(status_code=422, detail="Macro-enabled Office content is not allowed")
                if any(
                    name.casefold().endswith(".rels")
                    and b"TargetMode=\"External\"" in archive.read(name)
                    for name in names
                ):
                    raise HTTPException(status_code=422, detail="Office document has external references")
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=422, detail="Office document structure is invalid") from exc
    return media_type


async def secure_get_artifact_content(session_id: str, artifact_id: str, conn) -> Response:
    await artifacts_api._require_active_session(conn, session_id)
    async with conn.execute(
        "SELECT relative_path FROM artifacts WHERE id = ? AND session_id = ?",
        (artifact_id, session_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    relative_path = row[0]
    if not relative_path.startswith(("inputs/", "outputs/")):
        raise HTTPException(status_code=403, detail="Artifact is outside the managed document roots")
    workspace = await get_workspace_path(session_id, conn)
    snapshot = read_snapshot(workspace, relative_path, max_size=artifacts_api.MAX_IMPORT_BYTES)
    filename = Path(relative_path.replace("\\", "/")).name
    return Response(
        content=snapshot.data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


async def secure_import_document(
    session_id: str,
    request,
    idempotency_key: str,
    file_name: str,
    content_sha256: str,
    content_length: int,
    response,
    conn,
) -> DocumentImportResponse:
    await artifacts_api._require_active_session(conn, session_id)
    safe_name = artifacts_api._validate_managed_relative_path(unquote(file_name), allow_nested=False)
    expected_hash = content_sha256.casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise HTTPException(status_code=422, detail="X-Content-SHA256 must be a SHA-256 hex digest")
    if content_length < 0 or content_length > artifacts_api.MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Imported file exceeds the 10 MB request limit")

    request_hash = hashlib.sha256(
        f"{safe_name.as_posix()}\x1f{content_length}\x1f{expected_hash}".encode("utf-8")
    ).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor="user", operation="document.import", scope=session_id,
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed":
            replay = DocumentImportResponse(**json.loads(claim["response_json"]), duplicate=True)
            response.status_code = status.HTTP_200_OK
            return replay
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Import request is still processing")
        raise HTTPException(status_code=409, detail="Previous import failed; use a new Idempotency-Key")

    published_relative: str | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        current_size = managed_size(
            workspace,
            stop_after=artifacts_api.MAX_MANAGED_WORKSPACE_BYTES,
        )
        if current_size + content_length > artifacts_api.MAX_MANAGED_WORKSPACE_BYTES:
            raise HTTPException(status_code=413, detail="Managed workspace quota would exceed 100 MB")

        digest = hashlib.sha256()
        received = 0
        chunks: list[bytes] = []
        async for chunk in request.stream():
            if not chunk:
                continue
            received += len(chunk)
            if received > artifacts_api.MAX_IMPORT_BYTES or received > content_length:
                raise HTTPException(status_code=413, detail="Imported file exceeded its declared size")
            digest.update(chunk)
            chunks.append(bytes(chunk))
        if received != content_length:
            raise HTTPException(status_code=422, detail="Imported file size did not match Content-Length")
        if digest.hexdigest() != expected_hash:
            raise HTTPException(status_code=422, detail="Imported file hash did not match X-Content-SHA256")
        content = b"".join(chunks)
        media_type = _validate_import_bytes(content, safe_name)

        relative_target = (Path("inputs") / safe_name).as_posix()
        write_bytes(workspace, relative_target, content, create_only=True, create_parents=True)
        published_relative = relative_target
        artifact = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "relative_path": relative_target,
            "kind": "imported_file",
            "sha256": expected_hash,
            "size_bytes": received,
            "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""",
            artifact,
        )
        await artifacts_api._record_validation(
            conn,
            artifact["id"],
            status_value="structurally_validated",
            media_type=media_type,
            detail={"sha256": expected_hash},
        )
        await log_audit_event(
            conn,
            session_id,
            "user",
            "document.imported",
            artifact["relative_path"],
            {"artifact_id": artifact["id"], "size_bytes": received, "sha256_prefix": expected_hash[:12]},
        )
        await repo.finalize_operation(claim, response=artifact, status_code=201, resource_id=artifact["id"])
        completed = True
        return DocumentImportResponse(
            **artifact,
            validation_status="structurally_validated",
            media_type=media_type,
        )
    except HTTPException:
        await conn.rollback()
        await repo.fail_operation(claim, "import_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        await repo.fail_operation(claim, "import_failed")
        raise HTTPException(status_code=500, detail="Unable to import document") from exc
    finally:
        if not completed and published_relative is not None:
            try:
                workspace = await get_workspace_path(session_id, conn)
                delete_file(workspace, published_relative, missing_ok=True)
            except Exception:
                pass
