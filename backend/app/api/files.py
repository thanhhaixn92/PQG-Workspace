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
    force: bool = False

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
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    async with get_db_connection(settings.db_path_resolved) as db:
        workspace = await get_workspace_path(session_id, db)
        
    entries_count = [0]
    tree = _build_tree(workspace, workspace, 0, entries_count)
    
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
        return {"content": content, "mtime": stat_result.st_mtime, "size": stat_result.st_size}
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

    if target.exists() and request.expected_mtime is not None and not request.force:
        current_mtime = target.stat().st_mtime
        if abs(current_mtime - request.expected_mtime) > 0.000001:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "File changed on disk",
                    "current_mtime": current_mtime,
                    "expected_mtime": request.expected_mtime,
                },
            )
        
    # Write file
    try:
        # Create parent directories if they don't exist
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(request.content, encoding="utf-8")
        stat_result = target.stat()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {e}")

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

    return {"status": "saved", "mtime": stat_result.st_mtime, "size": stat_result.st_size}
