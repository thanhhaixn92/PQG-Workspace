from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.api import files as files_api
from app.db.connection import get_db_connection
from app.services.audit import log_audit_event
from app.services.sandbox import get_workspace_path
from app.services.sandbox_io import (
    MAX_FILE_SIZE, build_tree, normalized_relative_string, read_snapshot, write_bytes,
)

async def secure_get_file_tree(session_id: str, grouped: bool, settings) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
    raw_tree, truncated = build_tree(
        workspace,
        max_depth=files_api.MAX_DEPTH,
        max_entries=files_api.MAX_ENTRIES,
        hidden=set(files_api.HIDDEN_DIRS),
    )
    if not grouped:
        tree = raw_tree
    else:
        labels = {"inputs": "Tài liệu đầu vào", "working": "Tài liệu làm việc", "outputs": "Đầu ra"}
        managed_by_name = {node["name"]: node for node in raw_tree if node["name"] in labels}
        tree = [
            {
                **managed_by_name.get(folder, {"path": folder, "type": "directory", "children": []}),
                "name": label,
            }
            for folder, label in labels.items()
        ]
    return {"tree": tree, "truncated": truncated}


async def secure_get_file_content(session_id: str, path: str, settings) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
    try:
        snap = read_snapshot(workspace, path, max_size=MAX_FILE_SIZE, check_binary=True)
        content = snap.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File is binary or not valid UTF-8") from exc
    return {"content": content, "mtime": snap.mtime, "size": snap.size, "hash": snap.sha256}


async def secure_put_file_content(session_id: str, request, path: str, settings) -> dict[str, Any]:
    encoded = request.content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File content exceeds 1 MB limit")
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
    relative = normalized_relative_string(path)
    lock_key = Path(workspace) / relative
    async with files_api._lock_for(lock_key):
        current_hash: str | None = None
        current_mtime: float | None = None
        try:
            current = read_snapshot(workspace, relative, max_size=MAX_FILE_SIZE)
            current_hash = current.sha256
            current_mtime = current.mtime
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        if not request.force and (
            (request.expected_hash is not None and request.expected_hash != current_hash)
            or (
                request.expected_hash is None
                and request.expected_mtime is not None
                and current_mtime is not None
                and abs(current_mtime - request.expected_mtime) > 0.000001
            )
        ):
            raise HTTPException(
                status_code=409,
                detail={"message": "File changed on disk", "current_mtime": current_mtime, "current_hash": current_hash},
            )
        result = write_bytes(workspace, relative, encoded, create_only=False, create_parents=True)

    async with get_db_connection(settings.db_path_resolved) as db:
        await log_audit_event(
            conn=db,
            session_id=session_id,
            actor="user",
            action="file.write",
            target=relative,
            payload={"size": len(request.content)},
        )
        await db.commit()
    return {
        "status": "saved",
        "mtime": result.mtime,
        "size": len(encoded),
        "hash": hashlib.sha256(encoded).hexdigest(),
    }
