from __future__ import annotations

import asyncio

import pytest

from app.db.connection import open_db
from app.repositories.outbox_repository import OutboxRepository
from app.services.outbox_dispatcher import (
    OutboxDispatcher,
    create_n8n_sender,
    create_null_sender,
    run_outbox_dispatcher_loop,
)


@pytest.mark.asyncio
async def test_dispatcher_sends_claimed_rows_with_idempotency_key(migrated_db_path):
    conn = await open_db(migrated_db_path)
    sent: list[tuple[str, str]] = []

    async def sender(row: dict, idempotency_key: str) -> None:
        sent.append((row["id"], idempotency_key))

    try:
        repo = OutboxRepository(conn)
        oid, _ = await repo.insert_once(
            "out-task-1-task-succeeded",
            "n8n",
            "task.succeeded",
            '{"idempotency_key":"out-task-1-task-succeeded","task_id":"task-1"}',
        )

        result = await OutboxDispatcher(conn, worker_id="worker-a", sender=sender).dispatch_once()

        assert result == {"claimed": 1, "sent": 1, "retried": 0, "dead_letter": 0}
        assert sent == [(oid, oid)]
        assert await repo.get_status(oid) == "sent"

        result2 = await OutboxDispatcher(conn, worker_id="worker-a", sender=sender).dispatch_once()
        assert result2["claimed"] == 0
        assert sent == [(oid, oid)]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_dispatcher_retries_then_dead_letters_after_max_attempts(migrated_db_path):
    conn = await open_db(migrated_db_path)

    async def failing_sender(row: dict, idempotency_key: str) -> None:
        raise RuntimeError("webhook down")

    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert(
            "n8n",
            "task.failed",
            '{"idempotency_key":"out-fail","task_id":"task-2"}',
            max_attempts=2,
        )
        dispatcher = OutboxDispatcher(conn, worker_id="worker-a", sender=failing_sender)

        first = await dispatcher.dispatch_once()
        second = await dispatcher.dispatch_once()

        assert first == {"claimed": 1, "sent": 0, "retried": 1, "dead_letter": 0}
        assert second == {"claimed": 1, "sent": 0, "retried": 0, "dead_letter": 1}
        assert await repo.get_status(oid) == "dead_letter"

        third = await dispatcher.dispatch_once()
        assert third["claimed"] == 0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_lifecycle_start_stop_cleanly(migrated_db_path):
    """Background dispatcher loop must start, poll, and stop without errors."""
    from app.settings import Settings

    settings = Settings(
        db_path=str(migrated_db_path),
        outbox_dispatcher_enabled=True,
        outbox_dispatcher_poll_seconds=0.1,
        n8n_webhook_secret="",
        log_level="WARNING",
    )
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_outbox_dispatcher_loop(
            settings,
            stop_event,
            worker_id="lifecycle-test",
            poll_seconds=0.1,
        )
    )

    await asyncio.sleep(0.3)
    assert not task.done(), "Dispatcher task should still be running"

    stop_event.set()
    await asyncio.wait_for(task, timeout=5.0)
    assert task.done()
    assert task.exception() is None, f"Dispatcher task raised: {task.exception()}"


@pytest.mark.asyncio
async def test_lifecycle_drains_pending_rows(migrated_db_path, monkeypatch):
    """When rows are pending, the loop must drain them."""
    import uuid
    from app.settings import Settings

    session_id = f"ses-{uuid.uuid4().hex[:8]}"

    settings = Settings(
        db_path=str(migrated_db_path),
        outbox_dispatcher_enabled=True,
        outbox_dispatcher_poll_seconds=0.1,
        n8n_webhook_secret="test-secret",
        n8n_allowed_workflows={"notification": "notification"},
        log_level="WARNING",
    )

    conn = await open_db(migrated_db_path)
    try:
        # Create a real session to satisfy FK constraints on audit_events.
        await conn.execute(
            "INSERT INTO sessions (id, title, workspace_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, "drain-test", "/tmp/drain", 1000, 1000),
        )
        repo = OutboxRepository(conn)
        oid, _ = await repo.insert_once(
            "out-drain-001",
            "n8n",
            "task.completed",
            f'{{"idempotency_key":"out-drain-001","task_id":"task-x","session_id":"{session_id}"}}',
        )
        await conn.commit()
    finally:
        await conn.close()

    async def fake_trigger_n8n_webhook(**kwargs):
        class Result:
            response_status = 200

        return Result()

    monkeypatch.setattr("app.services.n8n_webhook.trigger_n8n_webhook", fake_trigger_n8n_webhook)

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_outbox_dispatcher_loop(
            settings,
            stop_event,
            worker_id="drain-test",
            poll_seconds=0.1,
        )
    )

    await asyncio.sleep(0.3)

    stop_event.set()
    await asyncio.wait_for(task, timeout=5.0)

    conn2 = await open_db(migrated_db_path)
    try:
        repo2 = OutboxRepository(conn2)
        status = await repo2.get_status(oid)
        assert status == "sent", f"Expected 'sent', got {status!r}"
    finally:
        await conn2.close()


@pytest.mark.asyncio
async def test_n8n_sender_missing_secret_retries_not_sent(migrated_db_path):
    """Runtime n8n sender must not mark rows sent when n8n is not configured."""
    from app.settings import Settings

    settings = Settings(
        db_path=str(migrated_db_path),
        n8n_webhook_secret="",
        log_level="WARNING",
    )

    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert(
            "n8n",
            "task.completed",
            '{"idempotency_key":"out-missing-secret","task_id":"task-x"}',
            max_attempts=2,
        )
        await conn.commit()

        dispatcher = OutboxDispatcher(conn, worker_id="worker-a", sender=create_n8n_sender(settings))

        first = await dispatcher.dispatch_once()
        assert first == {"claimed": 1, "sent": 0, "retried": 1, "dead_letter": 0}
        assert await repo.get_status(oid) == "retrying"

        second = await dispatcher.dispatch_once()
        assert second == {"claimed": 1, "sent": 0, "retried": 0, "dead_letter": 1}
        assert await repo.get_status(oid) == "dead_letter"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_n8n_sender_missing_notification_workflow_retries_not_sent(migrated_db_path):
    """Runtime n8n sender must not mark rows sent when notification is not allowlisted."""
    from app.settings import Settings

    settings = Settings(
        db_path=str(migrated_db_path),
        n8n_webhook_secret="test-secret",
        n8n_allowed_workflows={"echo": "echo"},
        log_level="WARNING",
    )

    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert(
            "n8n",
            "task.completed",
            '{"idempotency_key":"out-missing-workflow","task_id":"task-x"}',
            max_attempts=1,
        )
        await conn.commit()

        result = await OutboxDispatcher(
            conn,
            worker_id="worker-a",
            sender=create_n8n_sender(settings),
        ).dispatch_once()

        assert result == {"claimed": 1, "sent": 0, "retried": 0, "dead_letter": 1}
        assert await repo.get_status(oid) == "dead_letter"
    finally:
        await conn.close()
