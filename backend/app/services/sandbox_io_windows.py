from __future__ import annotations

import ctypes
import hashlib
import secrets
from ctypes import wintypes
from pathlib import Path

from fastapi import HTTPException

from app.services.sandbox_io import (
    MAX_FILE_SIZE,
    SandboxSnapshot,
    SandboxStat,
    _FILE_ATTRIBUTE_DIRECTORY,
    _FILE_ATTRIBUTE_REPARSE_POINT,
    _limit_error,
    _run_test_hook,
    normalize_relative_path,
)

ntdll = ctypes.WinDLL("ntdll")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

OBJ_CASE_INSENSITIVE = 0x00000040
OBJ_DONT_REPARSE = 0x00001000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
FILE_SHARE_DELETE = 0x4
FILE_CREATE = 0x2
FILE_OPEN = 0x1
FILE_OPEN_IF = 0x3
FILE_DIRECTORY_FILE = 0x00000001
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
FILE_READ_ATTRIBUTES = 0x0080
DELETE = 0x00010000
SYNCHRONIZE = 0x00100000
FILE_LIST_DIRECTORY = 0x0001
FILE_ADD_FILE = 0x0002
FILE_ADD_SUBDIRECTORY = 0x0004
FILE_TRAVERSE = 0x0020
FILE_BOTH_DIR_INFORMATION = 3
FILE_RENAME_INFORMATION = 10
FILE_DISPOSITION_INFORMATION = 13
STATUS_NO_MORE_FILES = 0x80000006
STATUS_OBJECT_NAME_NOT_FOUND = 0xC0000034
STATUS_OBJECT_PATH_NOT_FOUND = 0xC000003A
STATUS_OBJECT_NAME_COLLISION = 0xC0000035
STATUS_NOT_A_DIRECTORY = 0xC0000103
STATUS_FILE_IS_A_DIRECTORY = 0xC00000BA
STATUS_REPARSE_POINT_ENCOUNTERED = 0xC000050B
STATUS_IO_REPARSE_TAG_NOT_HANDLED = 0xC0000279
STATUS_ACCESS_DENIED = 0xC0000022
FILE_ATTRIBUTE_NORMAL = 0x00000080
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", wintypes.LPWSTR)]


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", wintypes.LPVOID),
        ("SecurityQualityOfService", wintypes.LPVOID),
    ]


class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class FILE_RENAME_INFORMATION_HEAD(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", wintypes.BOOLEAN),
        ("RootDirectory", wintypes.HANDLE),
        ("FileNameLength", wintypes.DWORD),
        ("FileName", wintypes.WCHAR * 1),
    ]


class FILE_DISPOSITION_INFORMATION_STRUCT(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOLEAN)]


class FILE_BOTH_DIR_INFORMATION_HEAD(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("FileIndex", wintypes.ULONG),
        ("CreationTime", ctypes.c_longlong),
        ("LastAccessTime", ctypes.c_longlong),
        ("LastWriteTime", ctypes.c_longlong),
        ("ChangeTime", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("AllocationSize", ctypes.c_longlong),
        ("FileAttributes", wintypes.ULONG),
        ("FileNameLength", wintypes.ULONG),
        ("EaSize", wintypes.ULONG),
        ("ShortNameLength", ctypes.c_byte),
        ("ShortName", wintypes.WCHAR * 12),
        ("FileName", wintypes.WCHAR * 1),
    ]


ntdll.NtCreateFile.argtypes = [
    ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, ctypes.POINTER(OBJECT_ATTRIBUTES),
    ctypes.POINTER(IO_STATUS_BLOCK), ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG,
    wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
]
ntdll.NtCreateFile.restype = ctypes.c_long
ntdll.NtSetInformationFile.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(IO_STATUS_BLOCK), ctypes.c_void_p, wintypes.ULONG, ctypes.c_int,
]
ntdll.NtSetInformationFile.restype = ctypes.c_long
ntdll.NtQueryDirectoryFile.argtypes = [
    wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(IO_STATUS_BLOCK),
    ctypes.c_void_p, wintypes.ULONG, ctypes.c_int, wintypes.BOOLEAN, ctypes.c_void_p, wintypes.BOOLEAN,
]
ntdll.NtQueryDirectoryFile.restype = ctypes.c_long
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
kernel32.FlushFileBuffers.restype = wintypes.BOOL
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE


def _status_code(status: int) -> int:
    return status & 0xFFFFFFFF


def _nt_success(status: int) -> bool:
    return status >= 0


def _filetime_ticks(value: wintypes.FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def _filetime_to_unix(value: wintypes.FILETIME) -> float:
    return _filetime_ticks(value) / 10_000_000 - 11644473600


def _close(handle) -> None:
    if handle and handle != INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(handle)


def _identity(info: BY_HANDLE_FILE_INFORMATION) -> tuple[int, int, int, int, int, int]:
    file_index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
    size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
    return (
        info.dwVolumeSerialNumber,
        file_index,
        size,
        _filetime_ticks(info.ftLastWriteTime),
        info.dwFileAttributes,
        info.nNumberOfLinks,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="File not found")


def _sandbox_error(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


class WindowsSandbox:
    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        handle = kernel32.CreateFileW(
            str(self.workspace),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid")
        self.root_handle = handle
        info = self._info(handle)
        if not info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY or info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            _close(handle)
            raise HTTPException(status_code=400, detail="Workspace directory does not exist or is invalid")

    def __enter__(self) -> "WindowsSandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _close(self.root_handle)

    @staticmethod
    def _info(handle) -> BY_HANDLE_FILE_INFORMATION:
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise HTTPException(status_code=500, detail="Failed to inspect workspace handle")
        return info

    def _nt_create(self, root, name: str, *, access: int, disposition: int, options: int, attributes: int = FILE_ATTRIBUTE_NORMAL):
        buffer = ctypes.create_unicode_buffer(name)
        unicode = UNICODE_STRING(len(name) * 2, (len(name) + 1) * 2, ctypes.cast(buffer, wintypes.LPWSTR))
        obj = OBJECT_ATTRIBUTES(
            ctypes.sizeof(OBJECT_ATTRIBUTES),
            root,
            ctypes.pointer(unicode),
            OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE,
            None,
            None,
        )
        io = IO_STATUS_BLOCK()
        handle = wintypes.HANDLE()
        status = ntdll.NtCreateFile(
            ctypes.byref(handle),
            access,
            ctypes.byref(obj),
            ctypes.byref(io),
            None,
            attributes,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            disposition,
            options,
            None,
            0,
        )
        if _nt_success(status):
            return handle
        code = _status_code(status)
        if code in {STATUS_OBJECT_NAME_NOT_FOUND, STATUS_OBJECT_PATH_NOT_FOUND}:
            raise _not_found()
        if code == STATUS_OBJECT_NAME_COLLISION:
            raise HTTPException(status_code=409, detail="Target already exists")
        if code in {STATUS_REPARSE_POINT_ENCOUNTERED, STATUS_IO_REPARSE_TAG_NOT_HANDLED}:
            raise _sandbox_error("Reparse/junction paths are not allowed in workspace sandbox")
        if code in {STATUS_NOT_A_DIRECTORY, STATUS_FILE_IS_A_DIRECTORY}:
            raise HTTPException(status_code=400, detail="Workspace path type mismatch")
        if code == STATUS_ACCESS_DENIED:
            raise _sandbox_error("Workspace path access denied")
        raise HTTPException(status_code=500, detail=f"Secure Windows filesystem operation failed (NTSTATUS 0x{code:08X})")

    def _open_dir_parts(self, parts: tuple[str, ...], *, create: bool = False):
        current = self.root_handle
        owned = []
        try:
            for index, part in enumerate(parts):
                handle = self._nt_create(
                    current,
                    part,
                    access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                    disposition=FILE_OPEN_IF if create else FILE_OPEN,
                    options=FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                )
                info = self._info(handle)
                if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    _close(handle)
                    raise _sandbox_error("Reparse/junction parent is not allowed in workspace sandbox")
                owned.append(handle)
                current = handle
                _run_test_hook("opened_parent", "/".join(parts[: index + 1]))
            if not owned:
                return self.root_handle, False
            for handle in owned[:-1]:
                _close(handle)
            return owned[-1], True
        except Exception:
            for handle in owned:
                _close(handle)
            raise

    def _open_file_from_parent(self, parent, name: str, *, access: int = FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE):
        handle = self._nt_create(
            parent,
            name,
            access=access,
            disposition=FILE_OPEN,
            options=FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
        )
        info = self._info(handle)
        if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            _close(handle)
            raise _sandbox_error("Reparse/symlink files are not allowed in workspace sandbox")
        if info.nNumberOfLinks > 1:
            _close(handle)
            raise _sandbox_error("Hard-linked files are not allowed in the workspace sandbox")
        return handle, info

    def _assert_parent_still_bound(self, held, parts: tuple[str, ...]) -> None:
        held_id = _identity(self._info(held))[:2]
        try:
            fresh, owned = self._open_dir_parts(parts)
        except HTTPException as exc:
            raise _sandbox_error("Workspace parent changed during filesystem operation") from exc
        try:
            fresh_id = _identity(self._info(fresh))[:2]
            if held_id != fresh_id:
                raise _sandbox_error("Workspace parent changed during filesystem operation")
        finally:
            if owned:
                _close(fresh)

    def inspect(self, relative: str, *, max_size: int | None = None, directory: bool = False) -> SandboxStat:
        parts = normalize_relative_path(relative)
        normalized = "/".join(parts) if parts else "."
        if directory or not parts:
            handle, owned = self._open_dir_parts(parts)
            try:
                info = self._info(handle)
                size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                return SandboxStat(normalized, parts[-1] if parts else ".", size, _filetime_to_unix(info.ftLastWriteTime), True, info.nNumberOfLinks)
            finally:
                if owned:
                    _close(handle)
        parent, owned = self._open_dir_parts(parts[:-1])
        try:
            handle, info = self._open_file_from_parent(parent, parts[-1])
            try:
                size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                if max_size is not None and size > max_size:
                    raise _limit_error(max_size, size)
                return SandboxStat(normalized, parts[-1], size, _filetime_to_unix(info.ftLastWriteTime), False, info.nNumberOfLinks)
            finally:
                _close(handle)
        finally:
            if owned:
                _close(parent)

    def snapshot(self, relative: str, *, max_size: int = MAX_FILE_SIZE, check_binary: bool = False) -> SandboxSnapshot:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        normalized = "/".join(parts)
        parent, owned = self._open_dir_parts(parts[:-1])
        try:
            handle, before = self._open_file_from_parent(parent, parts[-1])
            try:
                size = (before.nFileSizeHigh << 32) | before.nFileSizeLow
                if size > max_size:
                    raise _limit_error(max_size, size)
                chunks: list[bytes] = []
                total = 0
                while True:
                    buf = ctypes.create_string_buffer(min(64 * 1024, max_size + 1 - total))
                    read = wintypes.DWORD()
                    if not kernel32.ReadFile(handle, buf, len(buf), ctypes.byref(read), None):
                        raise HTTPException(status_code=500, detail="Failed to read workspace file")
                    if read.value == 0:
                        break
                    chunk = bytes(buf.raw[: read.value])
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_size:
                        raise _limit_error(max_size, total)
                data = b"".join(chunks)
                _run_test_hook("after_read", normalized)
                after = self._info(handle)
                if _identity(before) != _identity(after):
                    raise HTTPException(status_code=409, detail="File changed during secure read")
                if check_binary and b"\0" in data[:1024]:
                    raise HTTPException(status_code=400, detail="Binary files are not supported")
                return SandboxSnapshot(normalized, parts[-1], data, len(data), _filetime_to_unix(after.ftLastWriteTime), hashlib.sha256(data).hexdigest())
            finally:
                _close(handle)
        finally:
            if owned:
                _close(parent)

    def _existing_file(self, parent, name: str):
        try:
            return self._open_file_from_parent(parent, name)
        except HTTPException as exc:
            if exc.status_code == 404:
                return None
            if exc.status_code == 400:
                try:
                    handle = self._nt_create(
                        parent, name,
                        access=FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY | SYNCHRONIZE,
                        disposition=FILE_OPEN,
                        options=FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                    )
                except HTTPException:
                    raise exc
                else:
                    _close(handle)
                    raise HTTPException(status_code=400, detail="Target is a directory")
            raise

    @staticmethod
    def _write_handle(handle, data: bytes) -> None:
        if data:
            buffer = ctypes.create_string_buffer(data)
            written = wintypes.DWORD()
            if not kernel32.WriteFile(handle, buffer, len(data), ctypes.byref(written), None) or written.value != len(data):
                raise HTTPException(status_code=500, detail="Failed to write workspace file")
        if not kernel32.FlushFileBuffers(handle):
            raise HTTPException(status_code=500, detail="Failed to flush workspace file")

    def _rename_handle(self, handle, parent, name: str, *, replace: bool) -> None:
        encoded = name.encode("utf-16-le")
        offset = FILE_RENAME_INFORMATION_HEAD.FileName.offset
        buffer = ctypes.create_string_buffer(offset + len(encoded))
        head = ctypes.cast(buffer, ctypes.POINTER(FILE_RENAME_INFORMATION_HEAD)).contents
        head.ReplaceIfExists = bool(replace)
        head.RootDirectory = parent
        head.FileNameLength = len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + offset, encoded, len(encoded))
        io = IO_STATUS_BLOCK()
        status = ntdll.NtSetInformationFile(handle, ctypes.byref(io), buffer, len(buffer), FILE_RENAME_INFORMATION)
        if not _nt_success(status):
            code = _status_code(status)
            if code == STATUS_OBJECT_NAME_COLLISION:
                raise HTTPException(status_code=409, detail="Target already exists")
            raise HTTPException(status_code=500, detail=f"Secure Windows rename failed (NTSTATUS 0x{code:08X})")

    def _mark_delete(self, handle) -> None:
        info = FILE_DISPOSITION_INFORMATION_STRUCT(True)
        io = IO_STATUS_BLOCK()
        status = ntdll.NtSetInformationFile(handle, ctypes.byref(io), ctypes.byref(info), ctypes.sizeof(info), FILE_DISPOSITION_INFORMATION)
        if not _nt_success(status):
            code = _status_code(status)
            raise HTTPException(status_code=500, detail=f"Secure Windows delete failed (NTSTATUS 0x{code:08X})")

    def write_bytes(self, relative: str, data: bytes, *, create_only: bool = False, create_parents: bool = True) -> SandboxStat:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        normalized = "/".join(parts)
        parent, owned = self._open_dir_parts(parts[:-1], create=create_parents)
        temp_name = f".pqg-{secrets.token_hex(12)}.tmp"
        temp = None
        renamed = False
        try:
            existing = self._existing_file(parent, parts[-1])
            if existing is not None:
                handle, _info = existing
                _close(handle)
                if create_only:
                    raise HTTPException(status_code=409, detail="Target already exists")
            temp = self._nt_create(
                parent,
                temp_name,
                access=FILE_WRITE_DATA | FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                disposition=FILE_CREATE,
                options=FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
            )
            self._write_handle(temp, data)
            _run_test_hook("before_replace", normalized)
            self._assert_parent_still_bound(parent, parts[:-1])
            current = self._existing_file(parent, parts[-1])
            if current is not None:
                current_handle, _current_info = current
                _close(current_handle)
                if create_only:
                    raise HTTPException(status_code=409, detail="Target already exists")
            self._rename_handle(temp, parent, parts[-1], replace=not create_only)
            renamed = True
            _close(temp)
            temp = None
            final, info = self._open_file_from_parent(parent, parts[-1])
            try:
                size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                return SandboxStat(normalized, parts[-1], size, _filetime_to_unix(info.ftLastWriteTime), False, info.nNumberOfLinks)
            finally:
                _close(final)
        finally:
            if temp is not None:
                try:
                    if not renamed:
                        self._mark_delete(temp)
                except HTTPException:
                    pass
                _close(temp)
            if owned:
                _close(parent)

    def mkdir(self, relative: str, *, parents: bool = False, exist_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            return
        if parents:
            handle, owned = self._open_dir_parts(parts, create=True)
            if owned:
                _close(handle)
            return
        parent, owned = self._open_dir_parts(parts[:-1])
        try:
            handle = self._nt_create(
                parent,
                parts[-1],
                access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                disposition=FILE_OPEN_IF if exist_ok else FILE_CREATE,
                options=FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
            )
            _close(handle)
        finally:
            if owned:
                _close(parent)

    def delete(self, relative: str, *, missing_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=400, detail="Target is a directory")
        parent, owned = self._open_dir_parts(parts[:-1])
        try:
            try:
                handle, _info = self._open_file_from_parent(parent, parts[-1], access=DELETE | FILE_READ_ATTRIBUTES | SYNCHRONIZE)
            except HTTPException as exc:
                if exc.status_code == 404 and missing_ok:
                    return
                raise
            try:
                self._mark_delete(handle)
            finally:
                _close(handle)
        finally:
            if owned:
                _close(parent)

    def delete_empty_directory(self, relative: str, *, missing_ok: bool = True) -> None:
        parts = normalize_relative_path(relative)
        if not parts:
            raise HTTPException(status_code=403, detail="Workspace root cannot be removed")
        parent, owned = self._open_dir_parts(parts[:-1])
        try:
            try:
                handle = self._nt_create(
                    parent,
                    parts[-1],
                    access=DELETE | FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    disposition=FILE_OPEN,
                    options=FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                )
            except HTTPException as exc:
                if exc.status_code == 404 and missing_ok:
                    return
                raise
            try:
                self._mark_delete(handle)
            finally:
                _close(handle)
        finally:
            if owned:
                _close(parent)

    def _dir_names(self, handle) -> list[tuple[str, int]]:
        result: list[tuple[str, int]] = []
        restart = True
        while True:
            buffer = ctypes.create_string_buffer(64 * 1024)
            io = IO_STATUS_BLOCK()
            status = ntdll.NtQueryDirectoryFile(
                handle, None, None, None, ctypes.byref(io), buffer, len(buffer),
                FILE_BOTH_DIR_INFORMATION, False, None, restart,
            )
            restart = False
            code = _status_code(status)
            if code == STATUS_NO_MORE_FILES:
                break
            if not _nt_success(status):
                break
            offset = 0
            while offset < io.Information:
                base = ctypes.addressof(buffer) + offset
                entry = ctypes.cast(base, ctypes.POINTER(FILE_BOTH_DIR_INFORMATION_HEAD)).contents
                name_raw = ctypes.string_at(base + FILE_BOTH_DIR_INFORMATION_HEAD.FileName.offset, entry.FileNameLength)
                name = name_raw.decode("utf-16-le")
                if name not in {".", ".."}:
                    result.append((name, entry.FileAttributes))
                if entry.NextEntryOffset == 0:
                    break
                offset += entry.NextEntryOffset
        return sorted(result, key=lambda item: item[0].casefold())

    def _safe_child(self, parent, name: str, attrs: int):
        _run_test_hook("before_open_child", name)
        if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
            return "skip", None, None
        if attrs & _FILE_ATTRIBUTE_DIRECTORY:
            try:
                handle = self._nt_create(
                    parent, name,
                    access=FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    disposition=FILE_OPEN,
                    options=FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                )
            except HTTPException:
                return "skip", None, None
            info = self._info(handle)
            if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                _close(handle)
                return "skip", None, None
            return "dir", handle, info
        try:
            handle, info = self._open_file_from_parent(parent, name)
        except HTTPException:
            return "skip", None, None
        return "file", handle, info

    def tree(self, *, max_depth: int, max_entries: int, hidden: set[str]) -> tuple[list[dict], bool]:
        count = 0
        truncated = False

        def walk(handle, prefix: tuple[str, ...], depth: int) -> list[dict]:
            nonlocal count, truncated
            if depth > max_depth:
                return []
            dirs: list[dict] = []
            files: list[dict] = []
            for name, attrs in self._dir_names(handle):
                if count >= max_entries:
                    truncated = True
                    break
                if name in hidden or name.startswith(".DS_Store"):
                    continue
                kind, child, info = self._safe_child(handle, name, attrs)
                if child is None or info is None:
                    continue
                rel = "/".join((*prefix, name))
                count += 1
                if kind == "dir":
                    try:
                        dirs.append({"name": name, "path": rel, "type": "directory", "children": walk(child, (*prefix, name), depth + 1)})
                    finally:
                        _close(child)
                else:
                    try:
                        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                        node = {"name": name, "path": rel, "type": "file", "size": size}
                        if size > MAX_FILE_SIZE:
                            node["too_large"] = True
                        files.append(node)
                    finally:
                        _close(child)
            return dirs + files

        return walk(self.root_handle, (), 0), truncated

    def search(self, relative: str, query: str, *, limit: int = 100, hidden: set[str] | None = None) -> tuple[list[str], bool]:
        parts = normalize_relative_path(relative)
        hidden = hidden or {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
        root, owned = self._open_dir_parts(parts)
        results: list[str] = []
        truncated = False

        def walk(handle, prefix: tuple[str, ...]) -> None:
            nonlocal truncated
            for name, attrs in self._dir_names(handle):
                if len(results) >= limit:
                    truncated = True
                    return
                if name in hidden or name.startswith(".DS_Store"):
                    continue
                kind, child, info = self._safe_child(handle, name, attrs)
                if child is None or info is None:
                    continue
                if kind == "dir":
                    try:
                        walk(child, (*prefix, name))
                    finally:
                        _close(child)
                    continue
                try:
                    size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                    if size > MAX_FILE_SIZE:
                        continue
                    data = bytearray()
                    while len(data) <= MAX_FILE_SIZE:
                        buf = ctypes.create_string_buffer(min(64 * 1024, MAX_FILE_SIZE + 1 - len(data)))
                        read = wintypes.DWORD()
                        if not kernel32.ReadFile(child, buf, len(buf), ctypes.byref(read), None) or read.value == 0:
                            break
                        data.extend(buf.raw[: read.value])
                    after = self._info(child)
                    if _identity(info) != _identity(after) or len(data) > MAX_FILE_SIZE:
                        continue
                    text = bytes(data).decode("utf-8", errors="ignore")
                    rel_name = "/".join((*prefix, name))
                    for line_no, line in enumerate(text.splitlines(), start=1):
                        if query in line:
                            results.append(f"{rel_name}:{line_no}: {line.strip()}")
                            if len(results) >= limit:
                                truncated = True
                                return
                finally:
                    _close(child)

        try:
            walk(root, ())
            return results, truncated
        finally:
            if owned:
                _close(root)

    def managed_size(self, roots, *, stop_after: int | None = None) -> int:
        total = 0

        def walk(handle) -> None:
            nonlocal total
            for name, attrs in self._dir_names(handle):
                kind, child, info = self._safe_child(handle, name, attrs)
                if child is None or info is None:
                    continue
                if kind == "dir":
                    try:
                        walk(child)
                    finally:
                        _close(child)
                else:
                    try:
                        if info.nNumberOfLinks > 1:
                            raise _sandbox_error("Hard-linked files are not allowed in managed workspace roots")
                        total += (info.nFileSizeHigh << 32) | info.nFileSizeLow
                    finally:
                        _close(child)
                if stop_after is not None and total > stop_after:
                    return

        for root_name in roots:
            try:
                handle, owned = self._open_dir_parts(normalize_relative_path(root_name))
            except HTTPException as exc:
                if exc.status_code == 404:
                    continue
                raise
            try:
                walk(handle)
            finally:
                if owned:
                    _close(handle)
            if stop_after is not None and total > stop_after:
                break
        return total
