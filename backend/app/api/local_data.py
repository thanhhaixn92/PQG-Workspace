"""Local data inspection and safe backup endpoints."""
from __future__ import annotations

import sqlite3
import time
import asyncio
import hashlib
import json
import os
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_db, get_settings
from app.db.connection import get_db_connection
from app.settings import Settings
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/local-data", tags=["local-data"])


class LocalDataSummaryResponse(BaseModel):
    db_path: str
    db_size_bytes: int
    sessions_count: int
    active_sessions_count: int
    messages_count: int
    task_runs_count: int
    audit_events_count: int


class LocalDataBackupResponse(BaseModel):
    backup_path: str
    created_at: int
    sha256: str
    manifest_name: str


class LocalDataBackupInfo(BaseModel):
    name: str
    created_at: int
    size_bytes: int
    integrity_status: str
    sha256: str | None = None
    manifest_status: str = "missing"
    coverage: str = "database_only"


class RestoreReadinessResponse(LocalDataBackupInfo):
    schema_versions: int
    managed_workspace_coverage: str = "not_included"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(f"{backup_path.name}.manifest.json")


def _read_manifest(backup_path: Path) -> tuple[str, str | None]:
    manifest_path = _manifest_path(backup_path)
    if not manifest_path.exists():
        return "missing", None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = payload.get("sha256")
        if (
            payload.get("format_version") != 1
            or payload.get("backup_name") != backup_path.name
            or payload.get("coverage") != "database_only"
            or not isinstance(expected, str)
            or len(expected) != 64
            or int(payload.get("size_bytes", -1)) != backup_path.stat().st_size
        ):
            return "invalid", None
        return ("ok", expected) if _sha256_file(backup_path) == expected else ("invalid", expected)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "invalid", None


async def _count_rows(db: aiosqlite.Connection, table: str, where: str = "") -> int:
    query = f"SELECT COUNT(*) FROM {table} {where}".strip()
    async with db.execute(query) as cursor:
        row = await cursor.fetchone()
    return int(row[0])


@router.get("/summary", response_model=LocalDataSummaryResponse)
async def local_data_summary(
    settings: Settings = Depends(get_settings),
    db: aiosqlite.Connection = Depends(get_db),
) -> LocalDataSummaryResponse:
    """Return local SQLite metadata and key table counts."""
    db_path = Path(settings.db_path_resolved)
    return LocalDataSummaryResponse(
        db_path=str(db_path),
        db_size_bytes=db_path.stat().st_size if db_path.exists() else 0,
        sessions_count=await _count_rows(db, "sessions"),
        active_sessions_count=await _count_rows(db, "sessions", "WHERE archived = 0"),
        messages_count=await _count_rows(db, "chat_messages"),
        task_runs_count=await _count_rows(db, "task_runs"),
        audit_events_count=await _count_rows(db, "audit_events"),
    )


@router.post("/backup", response_model=LocalDataBackupResponse, status_code=status.HTTP_201_CREATED)
async def backup_local_data(
    settings: Settings = Depends(get_settings),
) -> LocalDataBackupResponse:
    """Create a consistent SQLite backup without overwriting existing backups."""
    db_path = Path(settings.db_path_resolved)
    if not db_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Database file not found")

    created_at = int(time.time())
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    stem = db_path.stem
    suffix = db_path.suffix or ".db"
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(created_at))
    backup_path = backup_dir / f"{stem}-{timestamp}{suffix}"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"{stem}-{timestamp}-{counter}{suffix}"
        counter += 1

    temp_path = backup_path.with_suffix(f"{backup_path.suffix}.tmp")
    manifest_path = _manifest_path(backup_path)
    manifest_temp_path = manifest_path.with_suffix(f"{manifest_path.suffix}.tmp")

    def _backup_and_check() -> None:
        source = sqlite3.connect(str(db_path), timeout=10)
        try:
            destination = sqlite3.connect(str(temp_path))
            try:
                source.backup(destination)
                check = destination.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError("SQLite backup integrity check failed")
            finally:
                destination.close()
        finally:
            source.close()
        os.replace(temp_path, backup_path)

    try:
        await asyncio.to_thread(_backup_and_check)
        digest = await asyncio.to_thread(_sha256_file, backup_path)
        manifest = {
            "format_version": 1,
            "backup_name": backup_path.name,
            "created_at": created_at,
            "size_bytes": backup_path.stat().st_size,
            "sha256": digest,
            "coverage": "database_only",
            "managed_workspace_coverage": "not_included",
        }
        manifest_temp_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(manifest_temp_path, manifest_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        manifest_temp_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Backup failed integrity check") from exc

    async with get_db_connection(settings.db_path_resolved) as db:
        await log_audit_event(db, None, "user", "local_data.backup_created", backup_path.name, {"created_at": created_at})

    return LocalDataBackupResponse(
        backup_path=str(backup_path), created_at=created_at, sha256=digest, manifest_name=manifest_path.name
    )


def _backup_directory(settings: Settings) -> Path:
    return Path(settings.db_path_resolved).parent / "backups"


def _safe_backup_path(settings: Settings, name: str) -> Path:
    if Path(name).name != name or not name.endswith(".db"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid backup name")
    target = (_backup_directory(settings) / name).resolve()
    if not target.is_relative_to(_backup_directory(settings).resolve()) or not target.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backup not found")
    return target


def _quick_check(path: Path) -> str:
    db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        row = db.execute("PRAGMA quick_check").fetchone()
        return "ok" if row and row[0] == "ok" else "invalid"
    finally:
        db.close()


@router.get("/backups", response_model=list[LocalDataBackupInfo])
async def list_local_data_backups(settings: Settings = Depends(get_settings)) -> list[LocalDataBackupInfo]:
    """List local DB-only backups; this endpoint never restores or swaps data."""
    backup_dir = _backup_directory(settings)
    if not backup_dir.exists():
        return []
    items: list[LocalDataBackupInfo] = []
    for path in sorted(backup_dir.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True):
        integrity = await asyncio.to_thread(_quick_check, path)
        manifest_status, digest = await asyncio.to_thread(_read_manifest, path)
        items.append(LocalDataBackupInfo(
            name=path.name, created_at=int(path.stat().st_mtime), size_bytes=path.stat().st_size,
            integrity_status=integrity, sha256=digest, manifest_status=manifest_status,
        ))
    return items


@router.get("/backups/{backup_name}/restore-readiness", response_model=RestoreReadinessResponse)
async def backup_restore_readiness(
    backup_name: str,
    settings: Settings = Depends(get_settings),
) -> RestoreReadinessResponse:
    """Read-only verification for a future offline maintenance restore."""
    path = _safe_backup_path(settings, backup_name)
    integrity = await asyncio.to_thread(_quick_check, path)
    if integrity != "ok":
        raise HTTPException(status.HTTP_409_CONFLICT, "Backup integrity check failed")
    manifest_status, digest = await asyncio.to_thread(_read_manifest, path)
    if manifest_status != "ok":
        raise HTTPException(status.HTTP_409_CONFLICT, "Backup manifest or hash verification failed")

    def _schema_count() -> int:
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            return int(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0])
        finally:
            db.close()

    return RestoreReadinessResponse(
        name=path.name, created_at=int(path.stat().st_mtime), size_bytes=path.stat().st_size,
        integrity_status=integrity, sha256=digest, manifest_status=manifest_status,
        schema_versions=await asyncio.to_thread(_schema_count),
    )
