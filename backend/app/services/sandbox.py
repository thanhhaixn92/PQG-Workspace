import os
from pathlib import Path
from fastapi import HTTPException
from aiosqlite import Connection

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

async def get_workspace_path(session_id: str, db: Connection) -> Path:
    """Safely fetch the workspace path for a session directly from the DB."""
    async with db.execute("SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        workspace = Path(row[0]).resolve()
        if not workspace.exists() or not workspace.is_dir():
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid")
        return workspace

def resolve_and_validate_path(workspace: Path, target_path_str: str, check_binary: bool = False) -> Path:
    """
    Strict sandbox path validation.
    Resolves the target path and ensures it does not escape the workspace.
    Optionally checks if it's a binary file or exceeds the file size limit.
    """
    try:
        # If the target path is absolute, it must be exactly within the workspace
        # We can just join them. If target_path_str is absolute, joinpath on Windows might replace the drive.
        # It's safer to strip leading slashes or use an explicit strategy.
        # But wait, what if the user passes an absolute path like C:\Windows\System32\cmd.exe?
        # In Python, Path(workspace) / Path(absolute) evaluates to the absolute path.
        target = Path(target_path_str)
        if target.is_absolute():
            resolved_target = target.resolve()
        else:
            resolved_target = (workspace / target).resolve()
            
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid path format")

    # Strict check: the resolved target MUST be relative to the resolved workspace
    if not resolved_target.is_relative_to(workspace):
        raise HTTPException(status_code=403, detail="Path traversal detected: Target escapes workspace")
        
    # Reject symlink escapes.
    # The `resolve()` method resolves symlinks. Since we check `is_relative_to` *after* `resolve()`, 
    # any symlink that escapes the workspace will be caught. 
    # However, to be extra safe against TOCTOU on Windows junctions or edge cases:
    try:
        if resolved_target.exists():
            # os.path.realpath is another layer
            real_path = Path(os.path.realpath(resolved_target))
            if not real_path.is_relative_to(workspace):
                raise HTTPException(status_code=403, detail="Symlink traversal detected")
    except OSError:
        pass

    # File-specific checks (if checking for read/write text content)
    if resolved_target.exists():
        if resolved_target.is_dir():
            raise HTTPException(status_code=400, detail="Target is a directory")
            
        # Size limit
        try:
            size = resolved_target.stat().st_size
            if size > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail=f"File exceeds 1 MB limit (size: {size} bytes)")
        except OSError:
            raise HTTPException(status_code=500, detail="Failed to stat file")
            
        # Binary rejection
        if check_binary:
            try:
                # Naive binary check: read first 1024 bytes and look for null bytes
                with open(resolved_target, 'rb') as f:
                    chunk = f.read(1024)
                    if b'\0' in chunk:
                        raise HTTPException(status_code=400, detail="Binary files are not supported")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to read file for binary check")

    return resolved_target
