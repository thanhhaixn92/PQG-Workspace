from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Iterable

from fastapi import HTTPException

MAX_FILE_SIZE = 1 * 1024 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_FILE_ATTRIBUTE_DIRECTORY = 0x0010
_TEST_HOOK: Callable[[str, str], None] | None = None
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _run_test_hook(stage: str, relative: str) -> None:
    hook = _TEST_HOOK
    if hook is not None:
        hook(stage, relative)


@dataclass(frozen=True)
class SandboxSnapshot:
    relative_path: str
    name: str
    data: bytes
    size: int
    mtime: float
    sha256: str


@dataclass(frozen=True)
class SandboxStat:
    relative_path: str
    name: str
    size: int
    mtime: float
    is_dir: bool
    nlink: int


def normalize_relative_path(value: str) -> tuple[str, ...]:
    """Normalize one workspace-relative path without touching the filesystem."""
    try:
        windows = PureWindowsPath(value)
        if windows.is_absolute() or windows.drive or value.startswith(("\\\\", "//")):
            raise HTTPException(status_code=403, detail="Path traversal detected: absolute paths are not allowed")
        candidate = PurePosixPath(value.replace("\\", "/"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid path format") from exc
    if candidate.is_absolute():
        raise HTTPException(status_code=403, detail="Path traversal detected: absolute paths are not allowed")
    parts = tuple(part for part in candidate.parts if part not in ("", "."))
    if any(part == ".." for part in parts):
        raise HTTPException(status_code=403, detail="Path traversal detected: target escapes workspace")
    for part in parts:
        if ":" in part or part.endswith((".", " ")):
            raise HTTPException(status_code=403, detail="Windows path aliases and alternate data streams are not allowed")
        if part.rstrip(". ").split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise HTTPException(status_code=403, detail="Windows reserved device names are not allowed")
    return parts


def normalized_relative_string(value: str) -> str:
    parts = normalize_relative_path(value)
    return "/".join(parts) if parts else "."


def _limit_error(max_size: int, size: int) -> HTTPException:
    label = "1 MB" if max_size == MAX_FILE_SIZE else f"{max_size} byte"
    return HTTPException(status_code=413, detail=f"File exceeds {label} limit (size: {size} bytes)")


def open_sandbox(workspace: Path | str):
    if os.name == "nt":
        from app.services.sandbox_io_windows import WindowsSandbox
        return WindowsSandbox(workspace)
    from app.services.sandbox_io_posix import PosixSandbox
    return PosixSandbox(workspace)


def read_snapshot(workspace: Path | str, relative: str, *, max_size: int = MAX_FILE_SIZE, check_binary: bool = False) -> SandboxSnapshot:
    with open_sandbox(workspace) as sandbox:
        return sandbox.snapshot(relative, max_size=max_size, check_binary=check_binary)


def inspect_path(workspace: Path | str, relative: str, *, max_size: int | None = None, directory: bool = False) -> SandboxStat:
    with open_sandbox(workspace) as sandbox:
        return sandbox.inspect(relative, max_size=max_size, directory=directory)


def write_bytes(workspace: Path | str, relative: str, data: bytes, *, create_only: bool = False, create_parents: bool = True) -> SandboxStat:
    with open_sandbox(workspace) as sandbox:
        return sandbox.write_bytes(relative, data, create_only=create_only, create_parents=create_parents)


def create_directory(workspace: Path | str, relative: str, *, parents: bool = False, exist_ok: bool = True) -> None:
    with open_sandbox(workspace) as sandbox:
        sandbox.mkdir(relative, parents=parents, exist_ok=exist_ok)


def delete_file(workspace: Path | str, relative: str, *, missing_ok: bool = True) -> None:
    with open_sandbox(workspace) as sandbox:
        sandbox.delete(relative, missing_ok=missing_ok)


def delete_empty_directory(workspace: Path | str, relative: str, *, missing_ok: bool = True) -> None:
    with open_sandbox(workspace) as sandbox:
        sandbox.delete_empty_directory(relative, missing_ok=missing_ok)


def build_tree(workspace: Path | str, *, max_depth: int, max_entries: int, hidden: set[str]) -> tuple[list[dict], bool]:
    with open_sandbox(workspace) as sandbox:
        return sandbox.tree(max_depth=max_depth, max_entries=max_entries, hidden=hidden)


def search_text(workspace: Path | str, relative: str, query: str, *, limit: int = 100, hidden: set[str] | None = None) -> tuple[list[str], bool]:
    with open_sandbox(workspace) as sandbox:
        return sandbox.search(relative, query, limit=limit, hidden=hidden)


def managed_size(workspace: Path | str, roots: Iterable[str] = ("inputs", "outputs"), *, stop_after: int | None = None) -> int:
    with open_sandbox(workspace) as sandbox:
        return sandbox.managed_size(roots, stop_after=stop_after)
