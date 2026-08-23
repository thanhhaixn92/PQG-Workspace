"""Policy boundary for Memory Hub use inside a visible Work plan step."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

import aiosqlite
from fastapi import HTTPException

MemoryContextMode = Literal["off", "suggest_only", "active_work_memory"]
VALID_MEMORY_CONTEXT_MODES = {"off", "suggest_only", "active_work_memory"}


@dataclass(frozen=True)
class WorkMemoryScope:
    id: str | None
    work_id: str
    plan_step_id: str
    context_mode: MemoryContextMode
    auto_learning_enabled: bool


async def _require_active_step(conn: aiosqlite.Connection, work_id: str, plan_step_id: str) -> None:
    async with conn.execute(
        """SELECT session.archived
           FROM work_plan_steps step
           JOIN sessions session ON session.id = step.session_id
           WHERE step.id = ? AND step.session_id = ?""",
        (plan_step_id, work_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan step not found in selected Work")
    if row["archived"]:
        raise HTTPException(status_code=409, detail="Work is archived")


async def get_work_memory_scope(
    conn: aiosqlite.Connection, work_id: str, plan_step_id: str, *, require_step: bool = True,
) -> WorkMemoryScope:
    if require_step:
        await _require_active_step(conn, work_id, plan_step_id)
    async with conn.execute(
        "SELECT * FROM work_memory_scopes WHERE work_id = ? AND plan_step_id = ?",
        (work_id, plan_step_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return WorkMemoryScope(None, work_id, plan_step_id, "suggest_only", False)
    return WorkMemoryScope(
        row["id"], work_id, plan_step_id, row["context_mode"], bool(row["auto_learning_enabled"]),
    )


async def update_work_memory_scope(
    conn: aiosqlite.Connection,
    work_id: str,
    plan_step_id: str,
    *,
    context_mode: str,
    auto_learning_enabled: bool,
) -> WorkMemoryScope:
    if context_mode not in VALID_MEMORY_CONTEXT_MODES:
        raise HTTPException(status_code=422, detail="Unknown Memory Hub context mode")
    await _require_active_step(conn, work_id, plan_step_id)
    current = await get_work_memory_scope(conn, work_id, plan_step_id, require_step=False)
    now = int(time.time())
    scope_id = current.id or str(uuid.uuid4())
    await conn.execute(
        """INSERT INTO work_memory_scopes
           (id, work_id, plan_step_id, context_mode, auto_learning_enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(work_id, plan_step_id) DO UPDATE SET
             context_mode = excluded.context_mode,
             auto_learning_enabled = excluded.auto_learning_enabled,
             updated_at = excluded.updated_at""",
        (scope_id, work_id, plan_step_id, context_mode, int(auto_learning_enabled), now, now),
    )
    return WorkMemoryScope(scope_id, work_id, plan_step_id, context_mode, auto_learning_enabled)


async def scope_summary(conn: aiosqlite.Connection, scope: WorkMemoryScope) -> tuple[int, list[dict[str, object]]]:
    if scope.id is None:
        return 0, [{"kind": "memory_hub", "reason": "Chưa thiết lập phạm vi Memory Hub cho bước này"}]
    async with conn.execute(
        """SELECT lifecycle, sensitivity, kind, COUNT(*) AS total
           FROM memory_hub_records WHERE project_id = ? AND task_id = ?
           GROUP BY lifecycle, sensitivity, kind""",
        (scope.work_id, scope.id),
    ) as cur:
        rows = await cur.fetchall()
    active = 0
    excluded: list[dict[str, object]] = []
    for row in rows:
        is_eligible = row["lifecycle"] == "active" and row["sensitivity"] != "restricted" and row["kind"] != "preference"
        if is_eligible:
            active += row["total"]
        else:
            excluded.append({
                "kind": "memory_hub", "count": row["total"], "lifecycle": row["lifecycle"],
                "sensitivity": row["sensitivity"], "reason": "Chưa đủ điều kiện dùng trong chat",
            })
    return active, excluded
