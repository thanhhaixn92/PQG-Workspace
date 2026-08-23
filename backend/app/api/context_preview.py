"""Read-only explanation of the legacy skills/memory context selection."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_db
from app.services.context import MAX_MEMORIES, MAX_MEMORY_BYTES, MAX_SKILLS, MAX_SKILL_BYTES

router = APIRouter(prefix="/api/context-preview", tags=["context-preview"])


class ContextPreviewItem(BaseModel):
    id: str
    label: str
    selected: bool
    bytes: int
    reason: str


class ContextPreviewGroup(BaseModel):
    item_limit: int
    byte_limit: int
    selected_bytes: int
    items: list[ContextPreviewItem]


class ContextPreviewResponse(BaseModel):
    session_id: str
    skills: ContextPreviewGroup
    memories: ContextPreviewGroup
    memory_hub_injected: bool = False


@router.get("", response_model=ContextPreviewResponse)
async def preview_context(
    session_id: str = Query(..., min_length=1),
    db: aiosqlite.Connection = Depends(get_db),
) -> ContextPreviewResponse:
    async with db.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cur:
        session = await cur.fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session[0]:
        raise HTTPException(status_code=409, detail="Session is archived")

    async with db.execute(
        "SELECT id, name, description, content, enabled, status FROM skills ORDER BY name ASC"
    ) as cur:
        skill_rows = await cur.fetchall()
    skill_items: list[ContextPreviewItem] = []
    skill_count = 0
    skill_bytes = 0
    for skill_id, name, description, content, enabled, status in skill_rows:
        header = f"--- Skill: {name} ---" + (f"\nDescription: {description}" if description else "")
        block_bytes = len(f"{header}\n{content}\n".encode("utf-8"))
        selected = False
        if status != "approved":
            reason = "Chưa được duyệt"
        elif not enabled:
            reason = "Đã duyệt nhưng chưa bật"
        elif skill_count >= MAX_SKILLS:
            reason = "Vượt giới hạn số kỹ năng"
        elif skill_bytes + block_bytes > MAX_SKILL_BYTES:
            reason = "Vượt giới hạn dung lượng kỹ năng"
        else:
            selected = True
            reason = "Sẽ dùng trong yêu cầu tiếp theo"
            skill_count += 1
            skill_bytes += block_bytes
        skill_items.append(ContextPreviewItem(id=skill_id, label=name, selected=selected, bytes=block_bytes, reason=reason))

    async with db.execute(
        """SELECT id, key, value, kind, importance_score FROM memory_entries
           WHERE session_id IS NULL OR session_id = ?
           ORDER BY importance_score DESC, last_accessed_at DESC""",
        (session_id,),
    ) as cur:
        memory_rows = await cur.fetchall()
    memory_items: list[ContextPreviewItem] = []
    memory_count = 0
    memory_bytes = 0
    for memory_id, key, value, kind, _score in memory_rows:
        block_bytes = len(f"[{kind}] {key}: {value}".encode("utf-8"))
        selected = False
        if memory_count >= MAX_MEMORIES:
            reason = "Vượt giới hạn số mục bộ nhớ"
        elif memory_bytes + block_bytes > MAX_MEMORY_BYTES:
            reason = "Vượt giới hạn dung lượng bộ nhớ"
        else:
            selected = True
            reason = "Sẽ dùng trong yêu cầu tiếp theo"
            memory_count += 1
            memory_bytes += block_bytes
        memory_items.append(ContextPreviewItem(id=memory_id, label=key, selected=selected, bytes=block_bytes, reason=reason))

    return ContextPreviewResponse(
        session_id=session_id,
        skills=ContextPreviewGroup(
            item_limit=MAX_SKILLS, byte_limit=MAX_SKILL_BYTES,
            selected_bytes=skill_bytes, items=skill_items,
        ),
        memories=ContextPreviewGroup(
            item_limit=MAX_MEMORIES, byte_limit=MAX_MEMORY_BYTES,
            selected_bytes=memory_bytes, items=memory_items,
        ),
    )
