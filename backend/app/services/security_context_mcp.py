from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Annotated, Any

from fastapi import HTTPException
from pydantic import Field

from app.api import assistant as assistant_api
from app.api.approvals import register_pending_approval, wait_for_approval
from app.db.connection import get_db_connection
from app.dependencies import get_settings
from app.services.audit import log_audit_event
from app.services.context_broker import ContextBroker, TEXT_SUFFIXES
from app.services.event_bus import event_bus
from app.services.sandbox_io import (
    MAX_FILE_SIZE,
    normalized_relative_string,
    read_snapshot,
    search_text,
    write_bytes,
)
from app.api.schemas import SseApprovalRequiredEvent

_CONTEXT_ARTIFACT_MAX_BYTES = 10 * 1024 * 1024


class SecureContextBroker(ContextBroker):
    """F7 broker with artifact hydration bound to one secure file snapshot."""

    async def _hydrate(self, work, scope, resource):
        if resource.kind != "artifact":
            return await super()._hydrate(work, scope, resource)
        relative = PurePosixPath(str(resource.locator.get("relative_path", "")))
        if (
            resource.locator.get("validation_status") != "structurally_validated"
            or not relative.parts
            or relative.parts[0] not in {"inputs", "outputs"}
            or relative.suffix.lower() not in TEXT_SUFFIXES
        ):
            return None
        try:
            snapshot = read_snapshot(
                Path(scope.workspace_path),
                relative.as_posix(),
                max_size=_CONTEXT_ARTIFACT_MAX_BYTES,
            )
            if not resource.source_hash or snapshot.sha256 != resource.source_hash:
                return None
            body = snapshot.data.decode("utf-8")
        except (HTTPException, UnicodeError, OSError):
            return None
        return body, snapshot.sha256, {}


async def secure_validated_attachments(
    conn,
    work_id: str | None,
    artifact_ids: list[str],
) -> list[dict[str, Any]]:
    if not artifact_ids:
        return []
    if not work_id:
        raise HTTPException(status_code=422, detail="Attachments require a selected Work")
    async with conn.execute(
        "SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0",
        (work_id,),
    ) as cur:
        work = await cur.fetchone()
    if work is None:
        raise HTTPException(status_code=409, detail="Work is archived or unavailable")
    workspace = Path(work["workspace_path"])
    result: list[dict[str, Any]] = []
    for artifact_id in artifact_ids:
        async with conn.execute(
            """SELECT artifact.id, artifact.relative_path, artifact.kind, artifact.sha256, artifact.size_bytes,
                      COALESCE(validation.status, 'pending') AS validation_status
               FROM artifacts artifact
               LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
               WHERE artifact.id = ? AND artifact.session_id = ?""",
            (artifact_id, work_id),
        ) as cur:
            artifact = await cur.fetchone()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Attachment artifact not found in selected Work")
        relative = PurePosixPath(artifact["relative_path"])
        validation_status = artifact["validation_status"]
        if validation_status != "structurally_validated":
            detail = {
                "pending": "Attachment has not passed structural validation",
                "rejected": "Attachment was rejected during structural validation",
                "failed": "Attachment structural validation failed",
            }.get(validation_status, "Attachment validation status is unavailable")
            raise HTTPException(status_code=422, detail=detail)
        if not relative.parts or relative.parts[0] not in {"inputs", "outputs"}:
            raise HTTPException(status_code=403, detail="Attachment is outside the managed workspace")
        if relative.suffix.lower() not in assistant_api._CONTEXT_ARTIFACT_SUFFIXES:
            raise HTTPException(
                status_code=422,
                detail="Attachment format is structurally validated but is not supported as GYO text context",
            )
        try:
            snapshot = read_snapshot(
                workspace,
                relative.as_posix(),
                max_size=_CONTEXT_ARTIFACT_MAX_BYTES,
            )
        except HTTPException as exc:
            raise HTTPException(status_code=409, detail="Attachment is no longer available") from exc
        if not artifact["sha256"] or snapshot.sha256 != artifact["sha256"]:
            raise HTTPException(status_code=409, detail="Attachment changed since it was registered")
        result.append(
            {
                "artifact_id": artifact["id"],
                "name": relative.name,
                "kind": artifact["kind"],
                "size_bytes": artifact["size_bytes"],
                "sha256": artifact["sha256"],
                "attachment": True,
            }
        )
    return result


async def _active_workspace(session_id: str, settings, *, after_approval: bool = False) -> str:
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute(
            "SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        if after_approval:
            raise PermissionError("Session is unavailable or archived")
        raise ValueError("Session not found or archived")
    return row[0]


async def secure_read_workspace_file(
    path: Annotated[str, Field(description="The path to the file relative to the workspace root.")]
) -> str:
    """Read a file from the workspace."""
    from app.mcp.server import get_mcp_session_id

    session_id = get_mcp_session_id()
    settings = get_settings()
    workspace = await _active_workspace(session_id, settings)
    try:
        snapshot = read_snapshot(workspace, path, max_size=MAX_FILE_SIZE)
        return snapshot.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Workspace file is not valid UTF-8 text") from exc


async def secure_write_workspace_file(
    path: Annotated[str, Field(description="The path to the file relative to the workspace root.")],
    content: Annotated[str, Field(description="The content to write to the file. Cannot exceed 1 MB.")],
) -> str:
    """Write content to a file in the workspace. Requires user approval."""
    import uuid
    from app.mcp.server import get_mcp_session_id

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise ValueError(f"Content size exceeds {MAX_FILE_SIZE} bytes.")
    relative = normalized_relative_string(path)
    session_id = get_mcp_session_id()
    settings = get_settings()
    await _active_workspace(session_id, settings)

    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = f"Tool wants to write to {relative}"
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="write_workspace_file",
        target=relative,
        risk_level="write_internal",
        description=description,
        settings=settings,
    )
    await event_bus.publish(
        session_id,
        SseApprovalRequiredEvent(
            approval_id=approval_id,
            action="write_workspace_file",
            target=relative,
            risk_level="write_internal",
            description=description,
        ),
    )
    decision = await wait_for_approval(approval_id)
    if decision not in {"allow_once", "allow_for_session"}:
        raise PermissionError(f"Approval denied for writing to {relative}")

    workspace = await _active_workspace(session_id, settings, after_approval=True)
    write_bytes(workspace, relative, encoded, create_only=False, create_parents=True)

    async with get_db_connection(settings.db_path_resolved) as db:
        await log_audit_event(
            db,
            session_id,
            "system",
            "file.write",
            relative,
            {"size": len(content)},
        )
        await db.commit()
    return f"Successfully wrote to {relative}"


async def secure_search_workspace(
    query: Annotated[str, Field(description="The search query.")],
    path: Annotated[
        str,
        Field(description="Directory to search in, relative to workspace root. Use '.' for root.", default="."),
    ] = ".",
) -> str:
    """Search for a string in the workspace."""
    from app.mcp.server import get_mcp_session_id

    session_id = get_mcp_session_id()
    settings = get_settings()
    workspace = await _active_workspace(session_id, settings)
    results, truncated = search_text(workspace, path, query, limit=100)
    if not results:
        return "No matches found."
    if truncated:
        results.append("... search truncated.")
    return "\n".join(results)
