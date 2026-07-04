from __future__ import annotations

import pytest

from app.db.connection import open_db
from app.repositories.task_repository import TaskRepository
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.outbox_repository import OutboxRepository


@pytest.mark.asyncio
async def test_task_repo_create_and_get(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        task = await repo.create_task(title="Test", description="Desc")
        assert task["id"].startswith("task-")
        assert task["status"] == "queued"
        assert task["session_id"] is None

        fetched = await repo.get_task(task["id"])
        assert fetched is not None
        assert fetched["title"] == "Test"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_task_repo_list(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        t1 = await repo.create_task(title="A")
        t2 = await repo.create_task(title="B")
        t3 = await repo.create_task(title="C")

        all_tasks = await repo.list_tasks()
        assert len(all_tasks) == 3

        paginated = await repo.list_tasks(limit=2)
        assert len(paginated) == 2
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_task_repo_update_status(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        task = await repo.create_task(title="Test")
        updated = await repo.update_task_status(task["id"], "running")
        assert updated["status"] == "running"

        updated2 = await repo.update_task_status(task["id"], "failed", error="Oops")
        assert updated2["status"] == "failed"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_task_repo_events(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        task = await repo.create_task(title="Test")
        evt = await repo.create_event(task["id"], "status_change", "running", data_json='{"msg":"started"}')
        assert evt["id"].startswith("evt-")
        assert evt["task_id"] == task["id"]

        events = await repo.get_events(task["id"])
        assert len(events) == 1
        assert events[0]["type"] == "status_change"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_task_repo_actions(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        task = await repo.create_task(title="Test")
        action = await repo.create_action(task["id"], "read_file", risk_level="read", description="Read a file")
        assert action["id"].startswith("act-")
        assert action["status"] == "pending"

        updated = await repo.update_action_status(action["id"], "allowed", output_json='{"ok":true}')
        assert updated["status"] == "allowed"

        actions = await repo.get_actions(task["id"])
        assert len(actions) == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_idempotency_repo_set_and_get(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = IdempotencyRepository(conn)
        key = "test-key-123"
        result = await repo.get(key)
        assert result is None

        await repo.set(key, '{"id":"x"}', 200, ttl_seconds=3600)
        result = await repo.get(key)
        assert result is not None
        assert result["response_json"] == '{"id":"x"}'
        assert result["status_code"] == 200
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_idempotency_cleanup_expired(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = IdempotencyRepository(conn)
        key = "expired-key"
        await repo.set(key, '"old"', 200, ttl_seconds=0)
        import time
        await repo._db.execute("UPDATE idempotency_records SET expires_at = ? WHERE key = ?",
                               (int(time.time()) - 10, key))

        cleaned = await repo.cleanup_expired()
        assert cleaned > 0
        result = await repo.get(key)
        assert result is None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_insert_and_claim(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert("telegram", "task.completed", '{"task_id":"t1"}')
        assert oid.startswith("out-")

        pending = await repo.get_pending_count()
        assert pending == 1

        claimed = await repo.claim_pending("worker-1", batch_size=10)
        assert len(claimed) == 1
        assert claimed[0]["id"] == oid
        assert claimed[0]["locked_by"] == "worker-1"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_insert_once_prevents_duplicate_rows(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid, inserted = await repo.insert_once(
            "out-stable-key",
            "n8n",
            "task.succeeded",
            '{"idempotency_key":"out-stable-key"}',
        )
        oid2, inserted2 = await repo.insert_once(
            "out-stable-key",
            "n8n",
            "task.succeeded",
            '{"idempotency_key":"out-stable-key"}',
        )

        assert oid == oid2 == "out-stable-key"
        assert inserted
        assert not inserted2

        claimed = await repo.claim_pending("worker-1")
        assert [row["id"] for row in claimed] == ["out-stable-key"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_mark_sent(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert("webapp", "task.completed", '{"ok":1}')
        claimed = await repo.claim_pending("w1")
        assert len(claimed) == 1

        await repo.mark_sent(oid)
        pending = await repo.get_pending_count()
        assert pending == 0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_retrying_rows_are_reclaimed_after_failure(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert("webapp", "task.failed", '{}')

        claimed = await repo.claim_pending("w1")
        assert len(claimed) == 1
        await repo.mark_retry(oid, "temporary")

        claimed2 = await repo.claim_pending("w2")
        assert len(claimed2) == 1
        assert claimed2[0]["id"] == oid
        assert claimed2[0]["locked_by"] == "w2"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_locked_rows_are_reclaimed_after_lease(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert("webapp", "task.succeeded", '{}')

        claimed = await repo.claim_pending("old-worker", lease_seconds=30)
        assert len(claimed) == 1

        claimed_too_soon = await repo.claim_pending("new-worker", lease_seconds=30)
        assert claimed_too_soon == []

        await conn.execute(
            "UPDATE notification_outbox SET locked_at = 0 WHERE id = ?",
            (oid,),
        )
        claimed_after_lease = await repo.claim_pending("new-worker", lease_seconds=30)
        assert len(claimed_after_lease) == 1
        assert claimed_after_lease[0]["id"] == oid
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_same_worker_does_not_reclaim_active_lock(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        await repo.insert("webapp", "task.succeeded", '{}')

        claimed = await repo.claim_pending("worker", lease_seconds=30)
        claimed_again = await repo.claim_pending("worker", lease_seconds=30)

        assert len(claimed) == 1
        assert claimed_again == []
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_outbox_dead_letter_on_max_attempts(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = OutboxRepository(conn)
        oid = await repo.insert("webapp", "task.failed", '{}', max_attempts=2)

        claimed = await repo.claim_pending("w1")
        await repo.mark_retry(oid, "err1")

        claimed2 = await repo.claim_pending("w1")
        await repo.mark_retry(oid, "err2")

        async with conn.execute("SELECT status FROM notification_outbox WHERE id = ?", (oid,)) as cur:
            row = await cur.fetchone()
        assert row["status"] == "dead_letter"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_task_repo_parent_task(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        repo = TaskRepository(conn)
        parent = await repo.create_task(title="Parent")
        child = await repo.create_task(title="Child", parent_task_id=parent["id"])
        assert child["parent_task_id"] == parent["id"]

        fetched = await repo.get_task(child["id"])
        assert fetched["parent_task_id"] == parent["id"]
    finally:
        await conn.close()
