from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
from pathlib import Path

from fastapi import HTTPException

from app.services.sandbox_io import (
    MAX_FILE_SIZE,
    SandboxSnapshot,
    SandboxStat,
    _limit_error,
    _run_test_hook,
    normalize_relative_path,
)

_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="File not found")


def _sandbox_error(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        st.st_dev,
        st.st_ino,
        st.st_size,
        getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)),
        getattr(st, "st_ctime_ns", int(st.st_ctime * 1_000_000_000)),
    )


class PosixSandbox:
    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
        try:
            self.root_fd = os.open(self.workspace, flags)
        except OSError as exc:
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid") from exc
        root_st = os.fstat(self.root_fd)
        if not stat.S_ISDIR(root_st.st_mode):
            os.close(self.root_fd)
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid")

    def __enter__(self) -> "PosixSandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        os.close(self.root_fd)

    @staticmethod
    def _dup(fd: int) -> int:
        return os.dup(fd)

    def _open_dir_parts(self, parts: tuple[str, ...], *, create: bool = False) -> int:
        fd = self._dup(self.root_fd)
        try:
            for index, part in enumerate(parts):
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                try:
                    next_fd = os.open(part, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=fd)
                except FileNotFoundError as exc:
                    raise _not_found() from exc
                except OSError as exc:
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                        raise _sandbox_error("Workspace path escape through a reparse/symlink parent is not allowed") from exc
                    raise
                os.close(fd)
                fd = next_fd
                _run_test_hook("opened_parent", "/".join(parts[: index + 1]))
            return fd
        except Exception:
            os.close(fd)
            raise

    def _open_file_from_parent(self, parent_fd: int, name: str, *, writable: bool = False) -> int:
        flags = (os.O_RDWR if writable else os.O_RDONLY) | _O_NOFOLLOW | _O_CLOEXEC
        try:
            fd = os.open(name, flags, dir_fd=parent_fd)
        except FileNotFoundError as exc:
            raise _not_found() from exc
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise _sandbox_error("Workspace path escape through a symlink/reparse file is not allowed") from exc
            raise
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            raise HTTPException(status_code=400, detail="Target is a directory")
        if st.st_nlink > 1:
            os.close(fd)
            raise _sandbox_error("Hard-linked files are not allowed in the workspace sandbox")
        return fd

    def _open_target(self, parts: tuple[str, ...]) -> tuple[int, int]:
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        parent_fd = self._open_dir_parts(parts[:-1])
        try:
            file_fd = self._open_file_from_parent(parent_fd, parts[-1])
            return parent_fd, file_fd
        except Exception:
            os.close(parent_fd)
            raise

    def _assert_parent_still_bound(self, parent_fd: int, parent_parts: tuple[str, ...]) -> None:
        held = os.fstat(parent_fd)
        try:
            fresh_fd = self._open_dir_parts(parent_parts)
        except HTTPException as exc:
            raise _sandbox_error("Workspace parent changed during filesystem operation") from exc
        try:
            fresh = os.fstat(fresh_fd)
            if (held.st_dev, held.st_ino) != (fresh.st_dev, fresh.st_ino):
                raise _sandbox_error("Workspace parent changed during filesystem operation")
        finally:
            os.close(fresh_fd)

    def inspect(self, relative: str, *, max_size: int | None = None, directory: bool = False) -> SandboxStat:
        parts = normalize_relative_path(relative)
        normalized = "/".join(parts) if parts else "."
        if directory or not parts:
            fd = self._open_dir_parts(parts)
            try:
                st = os.fstat(fd)
                return SandboxStat(normalized, parts[-1] if parts else ".", st.st_size, st.st_mtime, True, st.st_nlink)
            finally:
                os.close(fd)
        parent_fd, file_fd = self._open_target(parts)
        try:
            st = os.fstat(file_fd)
            if max_size is not None and st.st_size > max_size:
                raise _limit_error(max_size, st.st_size)
            return SandboxStat(normalized, parts[-1], st.st_size, st.st_mtime, False, st.st_nlink)
        finally:
            os.close(file_fd)
            os.close(parent_fd)

    def snapshot(self, relative: str, *, max_size: int = MAX_FILE_SIZE, check_binary: bool = False) -> SandboxSnapshot:
        parts = normalize_relative_path(relative)
        normalized = "/".join(parts)
        parent_fd, file_fd = self._open_target(parts)
        try:
            before = os.fstat(file_fd)
            if before.st_size > max_size:
                raise _limit_error(max_size, before.st_size)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(file_fd, min(64 * 1024, max_size + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > max_size:
                    raise _limit_error(max_size, total)
            data = b"".join(chunks)
            _run_test_hook("after_read", normalized)
            after = os.fstat(file_fd)
            if _stat_identity(before) != _stat_identity(after):
                raise HTTPException(status_code=409, detail="File changed during secure read")
            if check_binary and b"\0" in data[:1024]:
                raise HTTPException(status_code=400, detail="Binary files are not supported")
            return SandboxSnapshot(
                relative_path=normalized,
                name=parts[-1],
                data=data,
                size=len(data),
                mtime=after.st_mtime,
                sha256=hashlib.sha256(data).hexdigest(),
            )
        finally:
            os.close(file_fd)
            os.close(parent_fd)

    def _inspect_existing_entry(self, parent_fd: int, name: str) -> os.stat_result | None:
        try:
            st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(st.st_mode):
            raise _sandbox_error("Workspace path escape through a symlink/reparse file is not allowed")
        if stat.S_ISDIR(st.st_mode):
            raise HTTPException(status_code=400, detail="Target is a directory")
        if not stat.S_ISREG(st.st_mode):
            raise _sandbox_error("Unsupported workspace file type")
        if st.st_nlink > 1:
            raise _sandbox_error("Hard-linked files are not allowed in the workspace sandbox")
        return st

    def write_bytes(self, relative: str, data: bytes, *, create_only: bool = False, create_parents: bool = True) -> SandboxStat:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        normalized = "/".join(parts)
        parent_fd = self._open_dir_parts(parts[:-1], create=create_parents)
        temp_name = f".pqg-{secrets.token_hex(12)}.tmp"
        temp_fd: int | None = None
        try:
            existing = self._inspect_existing_entry(parent_fd, parts[-1])
            if create_only and existing is not None:
                raise HTTPException(status_code=409, detail="Target already exists")
            temp_fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC,
                0o600,
                dir_fd=parent_fd,
            )
            view = memoryview(data)
            while view:
                written = os.write(temp_fd, view)
                view = view[written:]
            os.fsync(temp_fd)
            os.close(temp_fd)
            temp_fd = None
            _run_test_hook("before_replace", normalized)
            self._assert_parent_still_bound(parent_fd, parts[:-1])
            current = self._inspect_existing_entry(parent_fd, parts[-1])
            if create_only and current is not None:
                raise HTTPException(status_code=409, detail="Target already exists")
            os.replace(temp_name, parts[-1], src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            file_fd = self._open_file_from_parent(parent_fd, parts[-1])
            try:
                st = os.fstat(file_fd)
                return SandboxStat(normalized, parts[-1], st.st_size, st.st_mtime, False, st.st_nlink)
            finally:
                os.close(file_fd)
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Failed to write file") from exc
        finally:
            if temp_fd is not None:
                os.close(temp_fd)
            try:
                os.unlink(temp_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
            os.close(parent_fd)

    def mkdir(self, relative: str, *, parents: bool = False, exist_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            return
        if parents:
            fd = self._open_dir_parts(parts, create=True)
            os.close(fd)
            return
        parent_fd = self._open_dir_parts(parts[:-1])
        try:
            try:
                os.mkdir(parts[-1], 0o700, dir_fd=parent_fd)
            except FileExistsError:
                if not exist_ok:
                    raise HTTPException(status_code=409, detail="Target already exists")
                child_fd = self._open_dir_parts(parts)
                os.close(child_fd)
        finally:
            os.close(parent_fd)

    def delete(self, relative: str, *, missing_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        parent_fd = self._open_dir_parts(parts[:-1])
        try:
            try:
                os.unlink(parts[-1], dir_fd=parent_fd)
            except FileNotFoundError:
                if not missing_ok:
                    raise _not_found()
        finally:
            os.close(parent_fd)

    def delete_empty_directory(self, relative: str, *, missing_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=403, detail="Workspace root cannot be removed")
        parent_fd = self._open_dir_parts(parts[:-1])
        try:
            try:
                os.rmdir(parts[-1], dir_fd=parent_fd)
            except FileNotFoundError:
                if not missing_ok:
                    raise _not_found()
        finally:
            os.close(parent_fd)

    def _entries(self, dir_fd: int) -> list[str]:
        try:
            names = [entry.name for entry in os.scandir(dir_fd) if entry.name not in {".", ".."}]
        except OSError:
            return []
        return sorted(names, key=str.casefold)

    def _safe_child(self, dir_fd: int, name: str) -> tuple[str, int | None, os.stat_result | None]:
        _run_test_hook("before_open_child", name)
        try:
            fd = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOENT, errno.ENOTDIR, errno.EACCES}:
                return "skip", None, None
            return "skip", None, None
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            os.close(fd)
            try:
                dfd = os.open(name, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=dir_fd)
            except OSError:
                return "skip", None, None
            return "dir", dfd, os.fstat(dfd)
        if stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
            return "file", fd, st
        os.close(fd)
        return "skip", None, None

    def tree(self, *, max_depth: int, max_entries: int, hidden: set[str]) -> tuple[list[dict], bool]:
        count = 0
        truncated = False

        def walk(dir_fd: int, prefix: tuple[str, ...], depth: int) -> list[dict]:
            nonlocal count, truncated
            if depth > max_depth:
                return []
            dirs: list[dict] = []
            files: list[dict] = []
            for name in self._entries(dir_fd):
                if count >= max_entries:
                    truncated = True
                    break
                if name in hidden or name.startswith(".DS_Store"):
                    continue
                kind, child_fd, st = self._safe_child(dir_fd, name)
                if kind == "skip" or child_fd is None or st is None:
                    continue
                rel = "/".join((*prefix, name))
                count += 1
                if kind == "dir":
                    try:
                        node = {"name": name, "path": rel, "type": "directory", "children": walk(child_fd, (*prefix, name), depth + 1)}
                        dirs.append(node)
                    finally:
                        os.close(child_fd)
                else:
                    try:
                        node = {"name": name, "path": rel, "type": "file", "size": st.st_size}
                        if st.st_size > MAX_FILE_SIZE:
                            node["too_large"] = True
                        files.append(node)
                    finally:
                        os.close(child_fd)
            return dirs + files

        root = self._dup(self.root_fd)
        try:
            return walk(root, (), 0), truncated
        finally:
            os.close(root)

    def search(self, relative: str, query: str, *, limit: int = 100, hidden: set[str] | None = None) -> tuple[list[str], bool]:
        parts = normalize_relative_path(relative)
        hidden = hidden or {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
        root_fd = self._open_dir_parts(parts)
        results: list[str] = []
        truncated = False

        def walk(dir_fd: int, prefix: tuple[str, ...]) -> None:
            nonlocal truncated
            for name in self._entries(dir_fd):
                if len(results) >= limit:
                    truncated = True
                    return
                if name in hidden or name.startswith(".DS_Store"):
                    continue
                kind, child_fd, st = self._safe_child(dir_fd, name)
                if kind == "skip" or child_fd is None or st is None:
                    continue
                if kind == "dir":
                    try:
                        walk(child_fd, (*prefix, name))
                    finally:
                        os.close(child_fd)
                    continue
                try:
                    before = os.fstat(child_fd)
                    if before.st_size > MAX_FILE_SIZE:
                        continue
                    data = b""
                    while len(data) <= MAX_FILE_SIZE:
                        chunk = os.read(child_fd, min(64 * 1024, MAX_FILE_SIZE + 1 - len(data)))
                        if not chunk:
                            break
                        data += chunk
                    after = os.fstat(child_fd)
                    if _stat_identity(before) != _stat_identity(after) or len(data) > MAX_FILE_SIZE:
                        continue
                    text = data.decode("utf-8", errors="ignore")
                    rel_name = "/".join((*prefix, name))
                    for line_no, line in enumerate(text.splitlines(), start=1):
                        if query in line:
                            results.append(f"{rel_name}:{line_no}: {line.strip()}")
                            if len(results) >= limit:
                                truncated = True
                                return
                finally:
                    os.close(child_fd)

        try:
            walk(root_fd, ())
            return results, truncated
        finally:
            os.close(root_fd)

    def managed_size(self, roots, *, stop_after: int | None = None) -> int:
        total = 0

        def walk(dir_fd: int) -> None:
            nonlocal total
            for name in self._entries(dir_fd):
                kind, child_fd, st = self._safe_child(dir_fd, name)
                if kind == "skip" or child_fd is None or st is None:
                    continue
                if kind == "dir":
                    try:
                        walk(child_fd)
                    finally:
                        os.close(child_fd)
                else:
                    try:
                        if st.st_nlink > 1:
                            raise _sandbox_error("Hard-linked files are not allowed in managed workspace roots")
                        total += st.st_size
                        if stop_after is not None and total > stop_after:
                            return
                    finally:
                        os.close(child_fd)
                if stop_after is not None and total > stop_after:
                    return

        for root in roots:
            try:
                fd = self._open_dir_parts(normalize_relative_path(root))
            except HTTPException as exc:
                if exc.status_code == 404:
                    continue
                raise
            try:
                walk(fd)
            finally:
                os.close(fd)
            if stop_after is not None and total > stop_after:
                break
        return total
