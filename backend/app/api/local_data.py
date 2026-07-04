"""Local data inspection and safe backup endpoints."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_db, get_settings
from app.settings import Settings

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

    source = sqlite3.connect(str(db_path), timeout=10)
    try:
        destination = sqlite3.connect(str(backup_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    return LocalDataBackupResponse(backup_path=str(backup_path), created_at=created_at)
