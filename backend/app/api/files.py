import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import get_db_connection
from app.dependencies import get_settings
from app.settings import Settings
from app.services.sandbox import get_workspace_path, resolve_and_validate_path, MAX_FILE_SIZE
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/sessions/{session_id}/files", tags=["Files"])

HIDDEN_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
MAX_DEPTH = 6
MAX_ENTRIES = 2000

class FileContentRequest(BaseModel):
    content: str
    expected_mtime: float | None = None
    expected_hash: str | None = None
    force: bool = False


_file_locks: dict[str, asyncio.Lock] = {}


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _lock_for(path: Path) -> asyncio.Lock:
    return _file_locks.setdefault(str(path), asyncio.Lock())

def _build_tree(dir_path: Path, workspace_path: Path, current_depth: int, entries_count: list[int]) -> list[dict[str, Any]]:
    if current_depth > MAX_DEPTH:
        return []
        
    tree: list[dict[str, Any]] = []
    
    try:
        # Sort directories first, then files
        items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []

    for item in items:
        if entries_count[0] >= MAX_ENTRIES:
            break
            
        if item.name in HIDDEN_DIRS or item.name.startswith('.DS_Store'):
            continue
            
        try:
            resolved_item = item.resolve()
            if not resolved_item.is_relative_to(workspace_path):
                continue # Skip symlink escapes
        except Exception:
            continue
            
        try:
            rel_path = item.relative_to(workspace_path).as_posix()
        except ValueError:
            continue # Should not happen
            
        entries_count[0] += 1
        
        node = {
            "name": item.name,
            "path": rel_path,
        }
        
        if item.is_dir():
            node["type"] = "directory"
            node["children"] = _build_tree(item, workspace_path, current_depth + 1, entries_count)
        else:
            node["type"] = "file"
            try:
                size = item.stat().st_size
                node["size"] = size
                if size > MAX_FILE_SIZE:
                    node["too_large"] = True
            except OSError:
                node["size"] = 0
                
        tree.append(node)
        
    return tree

@router.get("/tree")
async def get_file_tree(
    session_id: str,
    grouped: bool = Query(False, description="Group files into end-user Work categories"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
        
    entries_count = [0]
    raw_tree = _build_tree(workspace, workspace, 0, entries_count)
    if not grouped:
        tree = raw_tree
    else:
        managed_names = {"inputs", "working", "outputs"}
        labels = {
            "inputs": "Tài liệu đầu vào",
            "working": "Tài liệu làm việc",
            "outputs": "Đầu ra",
        }
        managed_by_name = {node["name"]: node for node in raw_tree if node["name"] in managed_names}
        tree = [
            {
                **managed_by_name.get(folder, {"path": folder, "type": "directory", "children": []}),
                "name": label,
            }
            for folder, label in labels.items()
        ]
        # The Work-facing grouped view is deliberately limited to managed
        # roots. Legacy/root files remain available only through the compatible
        # ungrouped endpoint and never appear in the normal Work document UI.
    return {"tree": tree, "truncated": entries_count[0] >= MAX_ENTRIES}

@router.get("/content")
async def get_file_content(
    session_id: str,
    path: str = Query(..., description="Target file path relative to workspace"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
        
    target = resolve_and_validate_path(workspace, path, check_binary=True)
    
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        stat_result = target.stat()
        content = target.read_text(encoding="utf-8")
        return {"content": content, "mtime": stat_result.st_mtime, "size": stat_result.st_size, "hash": _content_hash(content)}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is binary or not valid UTF-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

@router.put("/content")
async def put_file_content(
    session_id: str,
    request: FileContentRequest,
    path: str = Query(..., description="Target file path relative to workspace"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
        
    # Validation
    target = resolve_and_validate_path(workspace, path, check_binary=False)
    
    if len(request.content.encode("utf-8")) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File content exceeds 1 MB limit")

    async with _lock_for(target):
        # Re-resolve inside the critical section so a parent junction/symlink swap
        # cannot turn a previously checked target into an escape.
        target = resolve_and_validate_path(workspace, path, check_binary=False)
        current_content: str | None = None
        current_mtime: float | None = None
        if target.exists():
            current_mtime = target.stat().st_mtime
            current_content = target.read_text(encoding="utf-8")
        current_hash = _content_hash(current_content) if current_content is not None else None
        if not request.force and (
            (request.expected_hash is not None and request.expected_hash != current_hash)
            or (request.expected_hash is None and request.expected_mtime is not None and current_mtime is not None and abs(current_mtime - request.expected_mtime) > 0.000001)
        ):
            raise HTTPException(
                status_code=409,
                detail={"message": "File changed on disk", "current_mtime": current_mtime, "current_hash": current_hash},
            )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(request.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
            stat_result = target.stat()
        except OSError as e:
            try:
                if 'tmp_name' in locals() and os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
            raise HTTPException(status_code=500, detail="Failed to write file") from e

    # Log audit event
    try:
        rel_path = target.relative_to(workspace).as_posix()
    except ValueError:
        rel_path = path

    async with get_db_connection(settings.db_path_resolved) as db:
        await log_audit_event(
            conn=db,
            session_id=session_id,
            actor="user", # UI saves are user-originated
            action="file.write",
            target=rel_path,
            payload={"size": len(request.content)}
        )

    return {"status": "saved", "mtime": stat_result.st_mtime, "size": stat_result.st_size, "hash": _content_hash(request.content)}
