from __future__ import annotations

import pytest

from app.db.connection import open_db
from app.repositories.task_repository import TaskRepository
from app.services.idempotency_service import IdempotencyService
from app.services.state_machine import TaskStateMachine, TransitionError
from app.services.task_service import TaskService


# =========================================================================
# TaskStateMachine
# =========================================================================


class TestTaskStateMachine:

    def test_valid_transitions(self):
        TaskStateMachine.validate("queued", "running")
        TaskStateMachine.validate("queued", "cancelled")
        TaskStateMachine.validate("running", "succeeded")
        TaskStateMachine.validate("running", "failed")
        TaskStateMachine.validate("running", "waiting_approval")
        TaskStateMachine.validate("running", "cancelled")
        TaskStateMachine.validate("waiting_approval", "running")
        TaskStateMachine.validate("waiting_approval", "failed")
        TaskStateMachine.validate("waiting_approval", "cancelled")

    def test_invalid_transitions(self):
        with pytest.raises(TransitionError, match="terminal"):
            TaskStateMachine.validate("succeeded", "running")
        with pytest.raises(TransitionError, match="terminal"):
            TaskStateMachine.validate("failed", "running")
        with pytest.raises(TransitionError, match="terminal"):
            TaskStateMachine.validate("cancelled", "running")
        with pytest.raises(TransitionError, match="Invalid"):
            TaskStateMachine.validate("queued", "succeeded")
        with pytest.raises(TransitionError, match="Invalid"):
            TaskStateMachine.validate("queued", "failed")
        with pytest.raises(TransitionError, match="Invalid"):
            TaskStateMachine.validate("waiting_approval", "succeeded")
        with pytest.raises(TransitionError, match="Unknown"):
            TaskStateMachine.validate("invalid", "running")

    def test_is_terminal(self):
        assert TaskStateMachine.is_terminal("succeeded")
        assert TaskStateMachine.is_terminal("failed")
        assert TaskStateMachine.is_terminal("cancelled")
        assert not TaskStateMachine.is_terminal("queued")
        assert not TaskStateMachine.is_terminal("running")
        assert not TaskStateMachine.is_terminal("waiting_approval")


# =========================================================================
# IdempotencyService
# =========================================================================


class TestIdempotencyService:

    @pytest.mark.asyncio
    async def test_first_call_executes_second_returns_cached(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = IdempotencyService(conn)
            call_count = 0

            async def op():
                nonlocal call_count
                call_count += 1
                return {"id": "task-123"}

            result1, code1, is_dup1 = await svc.execute_idempotent("key-1", op)
            assert result1 == {"id": "task-123"}
            assert not is_dup1
            assert call_count == 1

            result2, code2, is_dup2 = await svc.execute_idempotent("key-1", op)
            assert result2 == {"id": "task-123"}
            assert is_dup2
            assert call_count == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_different_keys_not_cached(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = IdempotencyService(conn)
            call_count = 0

            async def op():
                nonlocal call_count
                call_count += 1
                return {"id": f"task-{call_count}"}

            await svc.execute_idempotent("key-a", op)
            await svc.execute_idempotent("key-b", op)
            assert call_count == 2
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_idempotency_service_request_hash_mismatch(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = IdempotencyService(conn)
            call_count = 0

            async def op_a():
                nonlocal call_count
                call_count += 1
                return {"data": "a"}

            async def op_b():
                nonlocal call_count
                call_count += 1
                return {"data": "b"}

            await svc.execute_idempotent("k", op_a, request_hash="hash-a")

            from app.repositories.idempotency_repository import IdempotencyConflict
            with pytest.raises(IdempotencyConflict):
                await svc.execute_idempotent("k", op_b, request_hash="hash-b")

            assert call_count == 1
        finally:
            await conn.close()


# =========================================================================
# TaskService
# =========================================================================


class TestTaskService:

    @pytest.mark.asyncio
    async def test_create_task(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, is_dup = await svc.create_task(title="Hello")
            assert task["status"] == "queued"
            assert not is_dup
            assert task["title"] == "Hello"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_create_task_idempotent_same_payload(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            t1, is_dup1 = await svc.create_task(title="Idem", idempotency_key="key-1")
            assert not is_dup1
            t2, is_dup2 = await svc.create_task(title="Idem", idempotency_key="key-1")
            assert is_dup2
            assert t2["id"] == t1["id"]
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_create_task_idempotent_different_payload_raises(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            await svc.create_task(title="First", idempotency_key="key-1")
            from app.repositories.idempotency_repository import IdempotencyConflict
            with pytest.raises(IdempotencyConflict):
                await svc.create_task(title="Different", idempotency_key="key-1")
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_task_lifecycle(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Lifecycle")

            running = await svc.start_task(task["id"])
            assert running["status"] == "running"

            done = await svc.complete_task(task["id"])
            assert done["status"] == "succeeded"

            events = (await svc.get_task_with_events(task["id"]))["events"]
            assert len(events) == 2
            assert events[0]["status"] == "running"
            assert events[1]["status"] == "succeeded"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_complete_task_enqueues_outbox_atomically(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Atomic")
            await svc.start_task(task["id"])
            done = await svc.complete_task(task["id"], result_data='{"ok": true}')

            async with conn.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (f"out-{task['id']}-task-succeeded",),
            ) as cur:
                row = await cur.fetchone()

            assert done["status"] == "succeeded"
            assert row is not None
            assert row["status"] == "pending"
            assert row["event_type"] == "task.succeeded"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_task_and_outbox_rollback_together(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Rollback")
            await svc.start_task(task["id"])
            await svc.complete_task(task["id"])
            await conn.rollback()

            async with conn.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (task["id"],)) as cur:
                task_count = (await cur.fetchone())[0]
            async with conn.execute(
                "SELECT COUNT(*) FROM notification_outbox WHERE id = ?",
                (f"out-{task['id']}-task-succeeded",),
            ) as cur:
                outbox_count = (await cur.fetchone())[0]

            assert task_count == 0
            assert outbox_count == 0
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_task_fail(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Fail")
            await svc.start_task(task["id"])
            failed = await svc.fail_task(task["id"], error="Something broke")
            assert failed["status"] == "failed"
            events = (await svc.get_task_with_events(task["id"]))["events"]
            assert events[-1]["status"] == "failed"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_task_cancel(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Cancel")
            cancelled = await svc.cancel_task(task["id"])
            assert cancelled["status"] == "cancelled"
            with pytest.raises(ValueError, match="terminal"):
                await svc.start_task(task["id"])
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_approval_flow(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Approve")
            await svc.start_task(task["id"])
            waiting = await svc.request_approval(task["id"], "write_file", "Write to file", risk_level="write_internal")
            assert waiting["status"] == "waiting_approval"

            actions = (await svc.get_task_with_events(task["id"]))["actions"]
            assert len(actions) == 1
            action_id = actions[0]["id"]

            resumed = await svc.resolve_approval(task["id"], action_id, approved=True)
            assert resumed["status"] == "running"

            done = await svc.complete_task(task["id"])
            assert done["status"] == "succeeded"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_approval_denied(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Deny")
            await svc.start_task(task["id"])
            await svc.request_approval(task["id"], "shell", "Run shell cmd", risk_level="external_or_destructive")
            actions = (await svc.get_task_with_events(task["id"]))["actions"]
            action_id = actions[0]["id"]

            failed = await svc.resolve_approval(task["id"], action_id, approved=False)
            assert failed["status"] == "failed"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_follow_up_active_task_creates_event(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Active")
            await svc.start_task(task["id"])
            result = await svc.request_follow_up(task["id"], "Add more detail")
            assert result["action"] == "follow_up_event"
            events = (await svc.get_task_with_events(task["id"]))["events"]
            follow_ups = [e for e in events if e["type"] == "follow_up"]
            assert len(follow_ups) == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_follow_up_completed_task_creates_child(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Done")
            await svc.start_task(task["id"])
            await svc.complete_task(task["id"])
            result = await svc.request_follow_up(task["id"], "Continue from here")
            assert result["action"] == "child_task_created"
            child = result["child_task"]
            assert child["parent_task_id"] == task["id"]
            assert child["status"] == "queued"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Bad")
            with pytest.raises(ValueError, match="Invalid transition"):
                await svc.complete_task(task["id"])
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_get_task_with_events_nonexistent(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            result = await svc.get_task_with_events("nonexistent")
            assert result is None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_cancel_running_task(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="RunningCancel")
            await svc.start_task(task["id"])
            cancelled = await svc.cancel_task(task["id"])
            assert cancelled["status"] == "cancelled"

            result = await svc.get_task_with_events(task["id"])
            events = result["events"]
            assert events[-1]["status"] == "cancelled"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_cancel_task_enqueues_outbox_atomically(self, migrated_db_path):
        conn = await open_db(migrated_db_path)
        try:
            svc = TaskService(conn)
            task, _ = await svc.create_task(title="Cancel Outbox Test")
            await svc.start_task(task["id"])
            done = await svc.cancel_task(task["id"])

            async with conn.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (f"out-{task['id']}-task-cancelled",),
            ) as cur:
                row = await cur.fetchone()

            assert done["status"] == "cancelled"
            assert row is not None
            assert row["status"] == "pending"
            assert row["event_type"] == "task.cancelled"
        finally:
            await conn.close()
