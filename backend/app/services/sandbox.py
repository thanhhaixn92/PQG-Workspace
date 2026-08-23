import os
from pathlib import Path, PureWindowsPath
from fastapi import HTTPException
from aiosqlite import Connection

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

async def get_workspace_path(session_id: str, db: Connection) -> Path:
    """Safely fetch the workspace path for a session directly from the DB."""
    async with db.execute("SELECT workspace_path, archived FROM sessions WHERE id = ?", (session_id,)) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row[1]:
            raise HTTPException(status_code=409, detail="Session is archived")
        workspace = Path(row[0]).resolve()
        if not workspace.exists() or not workspace.is_dir():
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid")
        return workspace

def resolve_and_validate_path(
    workspace: Path,
    target_path_str: str,
    check_binary: bool = False,
    max_size: int = MAX_FILE_SIZE,
) -> Path:
    """
    Strict sandbox path validation.
    Resolves the target path and ensures it does not escape the workspace.
    Optionally checks if it's a binary file or exceeds the file size limit.
    """
    try:
        workspace = Path(workspace).resolve()
        # User-controlled paths must be interpreted consistently across host OSes.
        # On POSIX, pathlib treats a backslash as an ordinary filename character;
        # accepting that would make Windows-style traversal such as ``..\\x`` pass
        # lexical validation in CI even though it escapes on Windows. Reject Windows
        # absolute/drive forms first, then normalize both separator styles before
        # applying the normal sandbox checks.
        windows_target = PureWindowsPath(target_path_str)
        if windows_target.is_absolute() or windows_target.drive:
            raise HTTPException(status_code=403, detail="Path traversal detected: absolute paths are not allowed")
        target = Path(target_path_str.replace("\\", "/"))
        if target.is_absolute():
            raise HTTPException(status_code=403, detail="Path traversal detected: absolute paths are not allowed")
        if any(part == ".." for part in target.parts):
            raise HTTPException(status_code=403, detail="Path traversal detected: target escapes workspace")
        lexical_target = workspace / target
        # Reject every existing reparse point in the original path chain.  A
        # post-approval resolve alone is insufficient on Windows because a
        # junction can be swapped between validation and open.
        current = workspace
        for part in target.parts:
            if part in ("", "."):
                continue
            current = current / part
            if current.exists() or current.is_symlink():
                stat_result = os.lstat(current)
                attributes = getattr(stat_result, "st_file_attributes", 0)
                if current.is_symlink() or attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise HTTPException(status_code=403, detail="Reparse point may escape workspace and is not allowed")
        resolved_target = lexical_target.resolve()
            
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path format")

    # Strict check: the resolved target MUST be relative to the resolved workspace
    if not resolved_target.is_relative_to(workspace):
        raise HTTPException(status_code=403, detail="Path traversal detected: Target escapes workspace")
        
    # File-specific checks (if checking for read/write text content)
    if resolved_target.exists():
        if resolved_target.is_dir():
            raise HTTPException(status_code=400, detail="Target is a directory")

        # A hard link is not a Windows reparse point: its lexical and resolved
        # paths both look safely inside the workspace even when the same inode
        # is also reachable through a sensitive path outside it. Local MVP
        # workspaces do not need hard-linked files, so fail closed on reads and
        # mutations instead of trying to infer which link is authoritative.
        try:
            if resolved_target.stat().st_nlink > 1:
                raise HTTPException(status_code=403, detail="Hard-linked files are not allowed in the workspace sandbox")
        except HTTPException:
            raise
        except OSError:
            raise HTTPException(status_code=500, detail="Failed to inspect file links")
            
        # Size limit
        try:
            size = resolved_target.stat().st_size
            if size > max_size:
                limit_label = "1 MB" if max_size == MAX_FILE_SIZE else f"{max_size} byte"
                raise HTTPException(status_code=413, detail=f"File exceeds {limit_label} limit (size: {size} bytes)")
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
