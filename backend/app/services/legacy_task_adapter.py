from __future__ import annotations

from typing import Optional

import aiosqlite

from app.services.task_service import TaskService


class LegacyTaskAdapter:
    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    async def on_prompt_submit(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        task_run_id: str,
        prompt: str,
        conversation_id: str | None = None,
    ) -> str:
        task, _ = await self._task_service.create_task(
            session_id=session_id,
            title=prompt[:100],
            task_type="prompt",
        )
        await db.execute(
            "UPDATE task_runs SET task_id = ? WHERE id = ?",
            (task["id"], task_run_id),
        )
        if conversation_id is not None:
            await db.execute(
                "UPDATE tasks SET conversation_id = ? WHERE id = ?",
                (conversation_id, task["id"]),
            )
        await self._task_service.start_task(task["id"], run_id=task_run_id)
        await db.commit()
        return task["id"]

    async def update_from_task_run(
        self,
        db: aiosqlite.Connection,
        task_run_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        async with db.execute(
            "SELECT task_id FROM task_runs WHERE id = ?",
            (task_run_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None or row["task_id"] is None:
            return

        task_id = row["task_id"]

        if status == "completed":
            await self._task_service.complete_task(task_id, run_id=task_run_id)
        elif status == "failed":
            await self._task_service.fail_task(task_id, error or "Unknown error", run_id=task_run_id)
        else:
            return
        await db.commit()
