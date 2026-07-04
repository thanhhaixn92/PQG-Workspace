from __future__ import annotations

import uuid
import time
from typing import Optional

import aiosqlite

class TaskRepository:

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create_task(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_type: str = "prompt",
        parent_task_id: Optional[str] = None,
    ) -> dict:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await self._db.execute(
            """INSERT INTO tasks (id, session_id, parent_task_id, title, description, status, task_type, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
            (task_id, session_id, parent_task_id, title, description, task_type, now, now),
        )
        return {
            "id": task_id,
            "session_id": session_id,
            "parent_task_id": parent_task_id,
            "title": title,
            "description": description,
            "status": "queued",
            "task_type": task_type,
            "created_at": now,
            "updated_at": now,
        }

    async def get_task(self, task_id: str) -> Optional[dict]:
        async with self._db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return dict(row)

    async def list_tasks(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses) if clauses else "1=1"
        query = f"SELECT * FROM tasks WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self._db.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def update_task_status(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> Optional[dict]:
        now = int(time.time())
        if error:
            await self._db.execute(
                "UPDATE tasks SET status = ?, updated_at = ?, description = COALESCE(?, description) WHERE id = ?",
                (status, now, error, task_id),
            )
        else:
            await self._db.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
        return await self.get_task(task_id)

    async def create_event(
        self,
        task_id: str,
        type: str,
        status: str,
        data_json: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict:
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await self._db.execute(
            """INSERT INTO task_events (id, task_id, run_id, type, status, data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, task_id, run_id, type, status, data_json, now),
        )
        return {
            "id": event_id,
            "task_id": task_id,
            "run_id": run_id,
            "type": type,
            "status": status,
            "data_json": data_json,
            "created_at": now,
        }

    async def get_events(self, task_id: str) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def create_action(
        self,
        task_id: str,
        tool_name: str,
        risk_level: str = "read",
        description: Optional[str] = None,
        input_json: Optional[str] = None,
    ) -> dict:
        action_id = f"act-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        await self._db.execute(
            """INSERT INTO task_actions (id, task_id, tool_name, risk_level, status, description, input_json, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (action_id, task_id, tool_name, risk_level, description, input_json, now),
        )
        return {
            "id": action_id,
            "task_id": task_id,
            "tool_name": tool_name,
            "risk_level": risk_level,
            "status": "pending",
            "description": description,
            "input_json": input_json,
            "output_json": None,
            "created_at": now,
            "resolved_at": None,
        }

    async def update_action_status(
        self, action_id: str, status: str, output_json: Optional[str] = None
    ) -> Optional[dict]:
        now = int(time.time())
        if output_json:
            await self._db.execute(
                "UPDATE task_actions SET status = ?, output_json = ?, resolved_at = ? WHERE id = ?",
                (status, output_json, now, action_id),
            )
        else:
            await self._db.execute(
                "UPDATE task_actions SET status = ?, resolved_at = ? WHERE id = ?",
                (status, now, action_id),
            )
        async with self._db.execute(
            "SELECT * FROM task_actions WHERE id = ?", (action_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_actions(self, task_id: str) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM task_actions WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
