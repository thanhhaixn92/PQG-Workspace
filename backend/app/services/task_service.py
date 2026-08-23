from __future__ import annotations

import hashlib
import json
from typing import Optional

from app.repositories.idempotency_repository import (
    IdempotencyConflict,
    IdempotencyFailed,
    IdempotencyInProgress,
    IdempotencyRepository,
)
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.task_repository import TaskRepository
from app.services.state_machine import TaskStateMachine


def _request_hash(
    session_id: Optional[str],
    title: Optional[str],
    description: Optional[str],
    task_type: str,
    parent_task_id: Optional[str],
) -> str:
    raw = json.dumps(
        {
            "session_id": session_id,
            "title": title,
            "description": description,
            "task_type": task_type,
            "parent_task_id": parent_task_id,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class TaskService:

    def __init__(
        self,
        db,
        task_repo: Optional[TaskRepository] = None,
        idempotency_repo: Optional[IdempotencyRepository] = None,
        outbox_repo: Optional[OutboxRepository] = None,
    ) -> None:
        self._db = db
        self._task_repo = task_repo or TaskRepository(db)
        self._idempotency = idempotency_repo or IdempotencyRepository(db)
        self._outbox = outbox_repo or OutboxRepository(db)

    async def create_task(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_type: str = "prompt",
        parent_task_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> tuple[dict, bool]:
        claim: dict | None = None
        if idempotency_key:
            req_hash = _request_hash(session_id, title, description, task_type, parent_task_id)
            claim, inserted = await self._idempotency.claim_operation(
                actor="api",
                operation="task.create",
                scope=session_id or "global",
                client_key=idempotency_key,
                request_hash=req_hash,
            )
            if not inserted:
                if claim["state"] == "completed":
                    return json.loads(claim["response_json"]), True
                if claim["state"] == "processing":
                    raise IdempotencyInProgress("A request with this Idempotency-Key is still processing")
                raise IdempotencyFailed("A previous request with this Idempotency-Key failed; use a new key to retry")

        try:
            task = await self._task_repo.create_task(
                session_id=session_id,
                title=title,
                description=description,
                task_type=task_type,
                parent_task_id=parent_task_id,
            )
            if claim is not None:
                await self._idempotency.finalize_operation(
                    claim,
                    response=task,
                    status_code=201,
                    resource_id=task["id"],
                )
        except Exception:
            if claim is not None:
                await self._db.rollback()
                await self._idempotency.fail_operation(claim)
            raise
        return task, False

    async def start_task(self, task_id: str, run_id: Optional[str] = None) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        TaskStateMachine.validate(task["status"], "running")
        updated = await self._task_repo.update_task_status(task_id, "running")
        await self._task_repo.create_event(task_id, "status_change", "running", '{"msg":"task started"}', run_id=run_id)
        return updated

    async def complete_task(self, task_id: str, result_data: Optional[str] = None, run_id: Optional[str] = None) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        TaskStateMachine.validate(task["status"], "succeeded")
        updated = await self._task_repo.update_task_status(task_id, "succeeded")
        await self._task_repo.create_event(
            task_id, "status_change", "succeeded", data_json=result_data or '{"msg":"task completed"}', run_id=run_id
        )
        await self._enqueue_terminal_notification(updated, "task.succeeded", result_data)
        return updated

    async def fail_task(self, task_id: str, error: str, run_id: Optional[str] = None) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        TaskStateMachine.validate(task["status"], "failed")
        updated = await self._task_repo.update_task_status(task_id, "failed", error=error)
        await self._task_repo.create_event(
            task_id, "status_change", "failed", data_json=json.dumps({"error": error}), run_id=run_id
        )
        await self._enqueue_terminal_notification(updated, "task.failed", json.dumps({"error": error}))
        return updated

    async def cancel_task(self, task_id: str) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        TaskStateMachine.validate(task["status"], "cancelled")
        updated = await self._task_repo.update_task_status(task_id, "cancelled")
        await self._task_repo.create_event(task_id, "status_change", "cancelled", '{"msg":"task cancelled"}')
        await self._enqueue_terminal_notification(updated, "task.cancelled", None)
        return updated

    async def request_approval(self, task_id: str, tool_name: str, description: str, risk_level: str = "write_internal") -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        TaskStateMachine.validate(task["status"], "waiting_approval")
        updated = await self._task_repo.update_task_status(task_id, "waiting_approval")
        action = await self._task_repo.create_action(
            task_id, tool_name, risk_level=risk_level, description=description
        )
        await self._task_repo.create_event(
            task_id, "approval_requested", "waiting_approval",
            data_json=json.dumps({"action_id": action["id"], "tool": tool_name}),
        )
        return updated

    async def resolve_approval(self, task_id: str, action_id: str, approved: bool, output_json: Optional[str] = None) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if approved:
            TaskStateMachine.validate(task["status"], "running")
            updated = await self._task_repo.update_task_status(task_id, "running")
            await self._task_repo.update_action_status(action_id, "allowed", output_json=output_json)
            await self._task_repo.create_event(task_id, "approval_granted", "running", json.dumps({"action_id": action_id}))
        else:
            TaskStateMachine.validate(task["status"], "failed")
            updated = await self._task_repo.update_task_status(task_id, "failed", error="Approval denied")
            await self._task_repo.update_action_status(action_id, "denied")
            await self._task_repo.create_event(task_id, "approval_denied", "failed", json.dumps({"action_id": action_id}))
        return updated

    async def request_follow_up(self, task_id: str, prompt: str) -> dict:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if TaskStateMachine.is_terminal(task["status"]):
            child = await self._task_repo.create_task(
                session_id=task["session_id"],
                title=f"Follow-up: {prompt[:50]}",
                parent_task_id=task_id,
            )
            await self._task_repo.create_event(
                task_id, "child_task_created", task["status"],
                data_json=json.dumps({"child_id": child["id"]}),
            )
            return {"action": "child_task_created", "child_task": child}
        else:
            evt = await self._task_repo.create_event(
                task_id, "follow_up", task["status"],
                data_json=json.dumps({"prompt": prompt}),
            )
            return {"action": "follow_up_event", "event": evt}

    async def get_task_with_events(self, task_id: str) -> Optional[dict]:
        task = await self._task_repo.get_task(task_id)
        if task is None:
            return None
        events = await self._task_repo.get_events(task_id)
        actions = await self._task_repo.get_actions(task_id)
        task["events"] = events
        task["actions"] = actions
        return task

    async def _enqueue_terminal_notification(
        self,
        task: dict,
        event_type: str,
        result_data: Optional[str],
    ) -> None:
        outbox_id = f"out-{task['id']}-{event_type.replace('.', '-')}"
        payload = {
            "idempotency_key": outbox_id,
            "task_id": task["id"],
            "session_id": task.get("session_id"),
            "status": task["status"],
            "event_type": event_type,
        }
        if result_data is not None:
            payload["result_data"] = result_data

        await self._outbox.insert_once(
            outbox_id=outbox_id,
            channel="n8n",
            event_type=event_type,
            payload_json=json.dumps(payload, sort_keys=True),
        )
