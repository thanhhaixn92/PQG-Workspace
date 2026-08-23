"""Managed local artifacts and idempotent Markdown reports."""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import tempfile
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from app.api.schemas import (
    ArtifactResponse,
    DocumentImportResponse,
    ManagedFolderCreateRequest,
    ManagedFolderResponse,
    ManagedTextFileCreateRequest,
    ReportCreateRequest,
    ReportCreateResponse,
)
from app.dependencies import get_db
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyFailed, IdempotencyInProgress, IdempotencyRepository
from app.services.audit import log_audit_event
from app.services.sandbox import get_workspace_path, resolve_and_validate_path

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["artifacts"])


MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_MANAGED_WORKSPACE_BYTES = 100 * 1024 * 1024
MAX_OOXML_ENTRIES = 10_000
MAX_OOXML_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_OOXML_COMPRESSION_RATIO = 100
MAX_PDF_OBJECTS = 10_000
MAX_PDF_STREAMS = 5_000
MAX_PDF_DECLARED_STREAM_BYTES = 50 * 1024 * 1024
ARTIFACT_VALIDATOR_VERSION = "v1"
_ALLOWED_IMPORTS = {
    ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
}
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _report_filename(title: str, output_format: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    suffix = ".html" if output_format == "html" else ".md"
    return f"{slug[:72] or 'report'}{suffix}"


def _validate_managed_relative_path(value: str, *, allow_nested: bool = True) -> Path:
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized or len(normalized) > 500 or any(ord(char) < 32 for char in normalized):
        raise HTTPException(status_code=422, detail="Document name is empty or invalid")
    if ":" in normalized or normalized.endswith((".", " ")):
        raise HTTPException(status_code=422, detail="Document name is not valid on Windows")
    candidate = Path(normalized.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise HTTPException(status_code=403, detail="Document path must stay inside managed inputs")
    if not allow_nested and len(candidate.parts) != 1:
        raise HTTPException(status_code=422, detail="Imported file name cannot contain folders")
    for part in candidate.parts:
        if part.rstrip(". ").split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise HTTPException(status_code=422, detail="Document name is reserved on Windows")
    return candidate


def _managed_workspace_size(workspace: Path) -> int:
    total = 0
    for root_name in ("inputs", "outputs"):
        root = workspace / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
                if total > MAX_MANAGED_WORKSPACE_BYTES:
                    return total
    return total


def _validate_import_structure(path: Path, name: Path) -> str:
    """Bounded local structural validation, not malware scanning."""
    suffix = name.suffix.casefold()
    media_type = _ALLOWED_IMPORTS.get(suffix)
    if media_type is None:
        raise HTTPException(status_code=422, detail="File type is not allowed for GYO context")
    with path.open("rb") as handle:
        head = handle.read(32)
    if suffix == ".pdf" and not head.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="PDF signature is invalid")
    if suffix == ".pdf":
        # PDFs are never rendered or extracted at import time, but bound the
        # declared object/stream surface now so a later parser cannot receive
        # an arbitrarily complex document. This is structural validation, not
        # malware scanning.
        document = path.read_bytes()
        object_count = sum(1 for _ in re.finditer(rb"(?m)^\s*\d+\s+\d+\s+obj\b", document))
        stream_count = sum(1 for _ in re.finditer(rb"(?m)^\s*stream\r?$", document))
        declared_stream_bytes = 0
        for match in re.finditer(rb"/Length\s+(\d+)\b", document):
            declared_stream_bytes += int(match.group(1))
            if declared_stream_bytes > MAX_PDF_DECLARED_STREAM_BYTES:
                break
        if object_count > MAX_PDF_OBJECTS or stream_count > MAX_PDF_STREAMS or declared_stream_bytes > MAX_PDF_DECLARED_STREAM_BYTES:
            raise HTTPException(status_code=422, detail="PDF exceeds safe structural resource limits")
    if suffix == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="PNG signature is invalid")
    if suffix in {".jpg", ".jpeg"} and not head.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="JPEG signature is invalid")
    if suffix == ".webp" and not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
        raise HTTPException(status_code=422, detail="WebP signature is invalid")
    if suffix in {".docx", ".xlsx", ".pptx"}:
        if not zipfile.is_zipfile(path):
            raise HTTPException(status_code=422, detail="Office document structure is invalid")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_OOXML_ENTRIES:
                raise HTTPException(status_code=422, detail="Office document has too many entries")
            total = sum(info.file_size for info in infos)
            compressed = sum(info.compress_size for info in infos)
            if total > MAX_OOXML_UNCOMPRESSED_BYTES or (compressed and total / compressed > MAX_OOXML_COMPRESSION_RATIO):
                raise HTTPException(status_code=422, detail="Office document exceeds safe extraction limits")
            names = [info.filename for info in infos]
            if any("vbaproject.bin" in item.casefold() for item in names):
                raise HTTPException(status_code=422, detail="Macro-enabled Office content is not allowed")
            if any(name.casefold().endswith(".rels") and b"TargetMode=\"External\"" in archive.read(name) for name in names):
                raise HTTPException(status_code=422, detail="Office document has external references")
    return media_type


async def _record_validation(
    conn: aiosqlite.Connection, artifact_id: str, *, status_value: str, media_type: str | None, detail: dict[str, object]
) -> None:
    await conn.execute(
        """INSERT INTO artifact_validations (artifact_id, status, media_type, validator_version, detail_json, validated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(artifact_id) DO UPDATE SET status=excluded.status, media_type=excluded.media_type,
               validator_version=excluded.validator_version, detail_json=excluded.detail_json, validated_at=excluded.validated_at""",
        (artifact_id, status_value, media_type, ARTIFACT_VALIDATOR_VERSION, json.dumps(detail, sort_keys=True), int(time.time())),
    )


def _render_report(request: ReportCreateRequest) -> tuple[bytes, str]:
    if request.output_format == "html":
        title = html.escape(request.title)
        content = html.escape(request.content.strip())
        document = (
            "<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
            f"<title>{title}</title><style>body{{font:16px/1.6 system-ui;max-width:900px;margin:48px auto;padding:0 24px}}"
            "pre{white-space:pre-wrap;font:inherit}</style></head>"
            f"<body><h1>{title}</h1><pre>{content}</pre></body></html>\n"
        )
        return document.encode("utf-8"), "report_html"
    markdown = f"# {request.title}\n\n{request.content.strip()}\n"
    return markdown.encode("utf-8"), "report_markdown"


async def _require_active_session(conn: aiosqlite.Connection, session_id: str) -> None:
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if row[0]:
        raise HTTPException(status_code=409, detail="Session is archived")


@router.get("/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(session_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> list[ArtifactResponse]:
    await _require_active_session(conn, session_id)
    async with conn.execute(
        """SELECT artifact.*, COALESCE(validation.status, 'pending') AS validation_status, validation.media_type
           FROM artifacts artifact LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
           WHERE artifact.session_id = ? ORDER BY artifact.created_at DESC, artifact.rowid DESC""", (session_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [ArtifactResponse(**dict(row)) for row in rows]


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_content(
    session_id: str,
    artifact_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> FileResponse:
    """Open a registered managed input/output without accepting an arbitrary path."""
    await _require_active_session(conn, session_id)
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
    target = resolve_and_validate_path(workspace, relative_path, max_size=MAX_IMPORT_BYTES)
    # Never inline HTML or unknown binaries in the browser. Preview rendering is
    # deliberately outside this endpoint until it has its own sandbox.
    return FileResponse(target, media_type="application/octet-stream", filename=target.name, content_disposition_type="attachment")


@router.post("/documents/import", response_model=DocumentImportResponse, status_code=status.HTTP_201_CREATED)
async def import_document(
    session_id: str,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    file_name: Annotated[str, Header(alias="X-File-Name")],
    content_sha256: Annotated[str, Header(alias="X-Content-SHA256")],
    content_length: Annotated[int, Header(alias="Content-Length")],
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DocumentImportResponse:
    """Stream one file into managed inputs with quotas, hashing and atomic publish."""
    await _require_active_session(conn, session_id)
    safe_name = _validate_managed_relative_path(unquote(file_name), allow_nested=False)
    expected_hash = content_sha256.casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise HTTPException(status_code=422, detail="X-Content-SHA256 must be a SHA-256 hex digest")
    if content_length < 0 or content_length > MAX_IMPORT_BYTES:
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

    temp_path: Path | None = None
    published_path: Path | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        current_size = await asyncio.to_thread(_managed_workspace_size, workspace)
        if current_size + content_length > MAX_MANAGED_WORKSPACE_BYTES:
            raise HTTPException(status_code=413, detail="Managed workspace quota would exceed 100 MB")
        relative_target = Path("inputs") / safe_name
        target = resolve_and_validate_path(workspace, relative_target.as_posix(), max_size=MAX_IMPORT_BYTES)
        if target.exists():
            raise HTTPException(status_code=409, detail="A managed document with this name already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Validate again after creating the managed parent chain.
        target = resolve_and_validate_path(workspace, relative_target.as_posix(), max_size=MAX_IMPORT_BYTES)

        descriptor, temp_name = tempfile.mkstemp(prefix=".import-", suffix=".tmp", dir=target.parent)
        temp_path = Path(temp_name)
        digest = hashlib.sha256()
        received = 0
        with os.fdopen(descriptor, "wb") as handle:
            async for chunk in request.stream():
                if not chunk:
                    continue
                received += len(chunk)
                if received > MAX_IMPORT_BYTES or received > content_length:
                    raise HTTPException(status_code=413, detail="Imported file exceeded its declared size")
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if received != content_length:
            raise HTTPException(status_code=422, detail="Imported file size did not match Content-Length")
        if digest.hexdigest() != expected_hash:
            raise HTTPException(status_code=422, detail="Imported file hash did not match X-Content-SHA256")
        media_type = _validate_import_structure(temp_path, safe_name)
        target = resolve_and_validate_path(workspace, relative_target.as_posix(), max_size=MAX_IMPORT_BYTES)
        if target.exists():
            raise HTTPException(status_code=409, detail="A managed document with this name already exists")
        os.replace(temp_path, target)
        temp_path = None
        published_path = target
        artifact = {
            "id": str(uuid.uuid4()), "session_id": session_id,
            "relative_path": relative_target.as_posix(), "kind": "imported_file",
            "sha256": expected_hash, "size_bytes": received, "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""",
            artifact,
        )
        await _record_validation(conn, artifact["id"], status_value="structurally_validated", media_type=media_type, detail={"sha256": expected_hash})
        await log_audit_event(
            conn, session_id, "user", "document.imported", artifact["relative_path"],
            {"artifact_id": artifact["id"], "size_bytes": received, "sha256_prefix": expected_hash[:12]},
        )
        await repo.finalize_operation(claim, response=artifact, status_code=201, resource_id=artifact["id"])
        completed = True
        return DocumentImportResponse(**artifact, validation_status="structurally_validated", media_type=media_type)
    except HTTPException:
        await conn.rollback()
        await repo.fail_operation(claim, "import_rejected")
        raise
    except Exception as exc:
        await conn.rollback()
        await repo.fail_operation(claim, "import_failed")
        raise HTTPException(status_code=500, detail="Unable to import document") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if not completed and published_path is not None:
            published_path.unlink(missing_ok=True)


@router.post("/documents/files", response_model=DocumentImportResponse, status_code=status.HTTP_201_CREATED)
async def create_managed_text_file(
    session_id: str,
    request: ManagedTextFileCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
) -> DocumentImportResponse:
    """Create one UTF-8 text document in managed inputs using atomic publish."""
    await _require_active_session(conn, session_id)
    safe_name = _validate_managed_relative_path(request.relative_path, allow_nested=False)
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

    temp_path: Path | None = None
    published_path: Path | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        if await asyncio.to_thread(_managed_workspace_size, workspace) + len(content) > MAX_MANAGED_WORKSPACE_BYTES:
            raise HTTPException(status_code=413, detail="Managed workspace quota would exceed 100 MB")
        relative_target = Path("inputs") / safe_name
        target = resolve_and_validate_path(workspace, relative_target.as_posix())
        if target.exists():
            raise HTTPException(status_code=409, detail="A managed document with this name already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target = resolve_and_validate_path(workspace, relative_target.as_posix())
        descriptor, temp_name = tempfile.mkstemp(prefix=".create-", suffix=".tmp", dir=target.parent)
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        target = resolve_and_validate_path(workspace, relative_target.as_posix())
        if target.exists():
            raise HTTPException(status_code=409, detail="A managed document with this name already exists")
        os.replace(temp_path, target)
        temp_path = None
        published_path = target
        artifact = {
            "id": str(uuid.uuid4()), "session_id": session_id,
            "relative_path": relative_target.as_posix(), "kind": "created_text_file",
            "sha256": digest, "size_bytes": len(content), "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""",
            artifact,
        )
        # Editor-created UTF-8 content is known at the server boundary. Mark
        # only the P0 text formats usable by GYO; other extensions remain
        # pending rather than being implicitly trusted.
        media_type = _ALLOWED_IMPORTS.get(safe_name.suffix.casefold())
        validation_status = "pending"
        if safe_name.suffix.casefold() in {".txt", ".md", ".csv"}:
            validation_status = "structurally_validated"
            await _record_validation(
                conn,
                artifact["id"],
                status_value=validation_status,
                media_type=media_type,
                detail={"source": "managed_text", "bytes": len(content)},
            )
        await log_audit_event(
            conn, session_id, "user", "document.file_created", artifact["relative_path"],
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
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if not completed and published_path is not None:
            published_path.unlink(missing_ok=True)


@router.post("/documents/folders", response_model=ManagedFolderResponse, status_code=status.HTTP_201_CREATED)
async def create_managed_folder(
    session_id: str,
    request: ManagedFolderCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
) -> ManagedFolderResponse:
    """Create one top-level managed input folder; retries never create a second folder."""
    await _require_active_session(conn, session_id)
    safe_name = _validate_managed_relative_path(request.relative_path, allow_nested=False)
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

    created_path: Path | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        relative_target = Path("inputs") / safe_name
        target = workspace / relative_target
        # Validate the not-yet-created leaf and every existing parent.
        resolve_and_validate_path(workspace, (relative_target / ".validation-leaf").as_posix())
        if target.exists():
            raise HTTPException(status_code=409, detail="A managed item with this name already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        resolve_and_validate_path(workspace, (relative_target / ".validation-leaf").as_posix())
        target.mkdir()
        created_path = target
        payload = {"relative_path": relative_target.as_posix()}
        await log_audit_event(
            conn, session_id, "user", "document.folder_created", payload["relative_path"], {},
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
        if not completed and created_path is not None:
            try:
                created_path.rmdir()
            except OSError:
                pass


@router.post("/reports", response_model=ReportCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    session_id: str,
    request: ReportCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    response: Response,
    conn: aiosqlite.Connection = Depends(get_db),
) -> ReportCreateResponse:
    """Write a user-provided Markdown report to managed outputs/reports only."""
    await _require_active_session(conn, session_id)
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

    temp_path: Path | None = None
    published_path: Path | None = None
    completed = False
    try:
        workspace = await get_workspace_path(session_id, conn)
        reports_dir = workspace / "outputs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        target = reports_dir / _report_filename(request.title, request.output_format)
        if not target.resolve().is_relative_to(reports_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid report path")
        if target.exists():
            raise HTTPException(status_code=409, detail="A report with this title already exists")
        content_bytes, artifact_kind = _render_report(request)
        descriptor, temp_name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=reports_dir)
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        temp_path = None
        published_path = target
        artifact = {
            "id": str(uuid.uuid4()), "session_id": session_id,
            "relative_path": target.relative_to(workspace).as_posix(), "kind": artifact_kind,
            "sha256": hashlib.sha256(content_bytes).hexdigest(), "size_bytes": len(content_bytes),
            "created_at": int(time.time()),
        }
        await conn.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (:id, :session_id, :relative_path, :kind, :sha256, :size_bytes, :created_at)""", artifact,
        )
        await log_audit_event(
            conn, session_id, "user", "report.created", artifact["relative_path"],
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
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        # A report is only durable once its database registry and operation claim
        # are finalized.  Do not leave an unregistered file after a later failure.
        if not completed and published_path is not None:
            published_path.unlink(missing_ok=True)
