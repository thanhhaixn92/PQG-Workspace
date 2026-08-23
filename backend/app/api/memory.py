import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from aiosqlite import Connection

from app.dependencies import get_db
from app.api.schemas import MemoryEntry, MemoryEntryCreate, MemoryEntryUpdate
from app.services.audit import log_audit_event

router = APIRouter()


async def _require_active_session(db: Connection, session_id: str) -> None:
    async with db.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if row[0]:
        raise HTTPException(status_code=409, detail="Session is archived")

@router.get("", response_model=List[MemoryEntry])
async def list_global_memory(db: Connection = Depends(get_db)):
    """List all global memory entries."""
    entries = []
    async with db.execute(
        "SELECT id, session_id, key, value, kind, importance_score, last_accessed_at, created_at "
        "FROM memory_entries WHERE session_id IS NULL ORDER BY importance_score DESC"
    ) as cursor:
        async for row in cursor:
            entries.append(
                MemoryEntry(
                    id=row[0],
                    session_id=row[1],
                    key=row[2],
                    value=row[3],
                    kind=row[4],
                    importance_score=row[5],
                    last_accessed_at=row[6],
                    created_at=row[7]
                )
            )
    return entries

@router.post("", response_model=MemoryEntry)
async def create_memory(entry_in: MemoryEntryCreate, db: Connection = Depends(get_db)):
    """Create a new memory entry."""
    if entry_in.session_id:
        await _require_active_session(db, entry_in.session_id)
    entry_id = f"mem-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    
    await db.execute(
        "INSERT INTO memory_entries (id, session_id, key, value, kind, importance_score, last_accessed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entry_id, entry_in.session_id, entry_in.key, entry_in.value, entry_in.kind.value, entry_in.importance_score, None, now)
    )
    
    await log_audit_event(db, entry_in.session_id, "system", "memory.created", entry_id, entry_in.model_dump())
    await db.commit()
    
    return MemoryEntry(
        id=entry_id,
        session_id=entry_in.session_id,
        key=entry_in.key,
        value=entry_in.value,
        kind=entry_in.kind,
        importance_score=entry_in.importance_score,
        last_accessed_at=None,
        created_at=now
    )

@router.put("/{memory_id}", response_model=MemoryEntry)
async def update_memory(memory_id: str, entry_in: MemoryEntryUpdate, db: Connection = Depends(get_db)):
    """Update a memory entry."""
    async with db.execute(
        "SELECT session_id, key, value, kind, importance_score, last_accessed_at, created_at FROM memory_entries WHERE id = ?",
        (memory_id,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Memory entry not found")
            
    key = entry_in.key if entry_in.key is not None else row[1]
    value = entry_in.value if entry_in.value is not None else row[2]
    kind = entry_in.kind.value if entry_in.kind is not None else row[3]
    importance_score = entry_in.importance_score if entry_in.importance_score is not None else row[4]
    
    await db.execute(
        "UPDATE memory_entries SET key = ?, value = ?, kind = ?, importance_score = ? WHERE id = ?",
        (key, value, kind, importance_score, memory_id)
    )
    
    await log_audit_event(db, row[0], "system", "memory.updated", memory_id, entry_in.model_dump(exclude_unset=True))
    await db.commit()
    
    return MemoryEntry(
        id=memory_id,
        session_id=row[0],
        key=key,
        value=value,
        kind=kind,
        importance_score=importance_score,
        last_accessed_at=row[5],
        created_at=row[6]
    )

@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, db: Connection = Depends(get_db)):
    """Delete a memory entry."""
    async with db.execute("SELECT session_id FROM memory_entries WHERE id = ?", (memory_id,)) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Memory entry not found")
            
    await db.execute("DELETE FROM memory_entries WHERE id = ?", (memory_id,))
    
    await log_audit_event(db, row[0], "system", "memory.deleted", memory_id, {})
    await db.commit()
