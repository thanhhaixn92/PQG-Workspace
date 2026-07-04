from __future__ import annotations

import json

import pytest

from app.db.connection import get_db_connection


async def _create_session(client, title: str = "Task API") -> str:
    response = await client.post(
        "/api/sessions",
        json={"title": title, "workspace_path": "/tmp"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_public_task_create_idempotency_same_payload(client, migrated_db_path):
    session_id = await _create_session(client)
    payload = {
        "session_id": session_id,
        "title": "Draft report",
        "description": "Create report task",
        "task_type": "prompt",
    }

    first = await client.post("/api/tasks", json=payload, headers={"Idempotency-Key": "task-key-1"})
    assert first.status_code == 201
    first_data = first.json()
    assert first_data["duplicate"] is False

    second = await client.post("/api/tasks", json=payload, headers={"Idempotency-Key": "task-key-1"})
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["duplicate"] is True
    assert second_data["id"] == first_data["id"]

    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE target = ? ORDER BY rowid",
            (first_data["id"],),
        ) as cur:
            rows = await cur.fetchall()
    assert [row["action"] for row in rows] == ["task.created", "task.create_replayed"]


@pytest.mark.asyncio
async def test_public_task_create_idempotency_conflict(client):
    first = await client.post(
        "/api/tasks",
        json={"title": "First"},
        headers={"Idempotency-Key": "task-key-conflict"},
    )
    assert first.status_code == 201

    conflict = await client.post(
        "/api/tasks",
        json={"title": "Different"},
        headers={"Idempotency-Key": "task-key-conflict"},
    )
    assert conflict.status_code == 409
    assert "different payload" in conflict.json()["detail"]


@pytest.mark.asyncio
async def test_public_task_lifecycle_events_stream_and_cancel(client):
    created = await client.post("/api/tasks", json={"title": "Lifecycle"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    running = await client.post(f"/api/tasks/{task_id}/start")
    assert running.status_code == 200
    assert running.json()["status"] == "running"

    cancelled = await client.post(f"/api/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    events = await client.get(f"/api/tasks/{task_id}/events")
    assert events.status_code == 200
    event_data = events.json()
    assert [event["status"] for event in event_data] == ["running", "cancelled"]

    streamed = await client.get(f"/api/tasks/{task_id}/events/stream")
    assert streamed.status_code == 200
    assert "event: status_change" in streamed.text
    assert "event: done" in streamed.text


@pytest.mark.asyncio
async def test_public_task_cancel_terminal_returns_conflict(client):
    created = await client.post("/api/tasks", json={"title": "Cancel once"})
    task_id = created.json()["id"]
    first = await client.post(f"/api/tasks/{task_id}/cancel")
    assert first.status_code == 200

    second = await client.post(f"/api/tasks/{task_id}/cancel")
    assert second.status_code == 409
    assert "terminal" in second.json()["detail"]


@pytest.mark.asyncio
async def test_public_task_action_approval_binding_and_audit(client, migrated_db_path):
    created = await client.post("/api/tasks", json={"title": "Approval"})
    task_id = created.json()["id"]
    await client.post(f"/api/tasks/{task_id}/start")

    action_response = await client.post(
        f"/api/tasks/{task_id}/actions",
        json={
            "tool_name": "write_file",
            "description": "Write output file",
            "risk_level": "write_internal",
        },
    )
    assert action_response.status_code == 201
    action = action_response.json()
    assert action["task_id"] == task_id
    assert action["status"] == "pending"

    decision = await client.post(
        f"/api/tasks/{task_id}/actions/{action['id']}/decision",
        json={"approved": True, "output_json": json.dumps({"ok": True})},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "running"

    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT status, output_json FROM task_actions WHERE id = ?",
            (action["id"],),
        ) as cur:
            row = await cur.fetchone()
        async with db.execute(
            "SELECT action, target, payload_json FROM audit_events WHERE action LIKE 'task_action.%' ORDER BY rowid",
        ) as cur:
            audit_rows = await cur.fetchall()

    assert row["status"] == "allowed"
    assert json.loads(row["output_json"]) == {"ok": True}
    assert [audit["action"] for audit in audit_rows] == ["task_action.requested", "task_action.allowed"]
    assert audit_rows[0]["target"] == action["id"]


@pytest.mark.asyncio
async def test_legacy_session_create_does_not_use_task_api_by_default(client, migrated_db_path):
    session_id = await _create_session(client, "Legacy still works")

    async with get_db_connection(migrated_db_path) as db:
        async with db.execute("SELECT COUNT(*) AS count FROM tasks") as cur:
            row = await cur.fetchone()
        async with db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cur:
            session_row = await cur.fetchone()
    assert row["count"] == 0
    assert session_row is not None
