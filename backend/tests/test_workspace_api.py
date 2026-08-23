"""Focused contract tests for the v2.4 user-facing Workspace task domain."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.assistant import _read_only_response
from app.db.connection import get_db_connection
from app.services.assistant_context import AssistantContextPackBuilder


class ContextCapturingGyo:
    def __init__(self) -> None:
        self.requests = []

    async def stream(self, request):
        self.requests.append(request)
        yield SimpleNamespace(type="done", data={
            "text": "Đã nhận ngữ cảnh.", "status": "completed", "model_id": "test-gyo",
            "route_mode": request.route_mode, "selection_reason": "test",
        })


@pytest.mark.asyncio
async def test_workspace_task_is_scoped_idempotent_and_legacy_tasks_remain_empty(client, migrated_db_path):
    work = await client.post("/api/sessions", json={"title": "Workspace v2.4"})
    work_id = work.json()["id"]
    payload = {"session_id": work_id, "title": "Hoàn thiện dashboard", "priority": 5, "impact": 4, "ai_eligibility": "delegatable"}
    created = await client.post("/api/workspace/tasks", json=payload, headers={"Idempotency-Key": "workspace-create-1"})
    assert created.status_code == 201, created.text
    task = created.json()
    replay = await client.post("/api/workspace/tasks", json=payload, headers={"Idempotency-Key": "workspace-create-1"})
    assert replay.status_code == 200
    assert replay.json()["id"] == task["id"]
    dashboard = await client.get("/api/workspace/today")
    assert dashboard.status_code == 200
    assert dashboard.json()["recommendation"]["id"] == task["id"]
    handoff = await client.post(f"/api/workspace/tasks/{task['id']}/ai-jobs")
    assert handoff.status_code == 201
    assert handoff.json()["status"] == "waiting_user"
    from app.db.connection import get_db_connection
    async with get_db_connection(migrated_db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM tasks") as cursor:
            assert (await cursor.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_workspace_task_rejects_archived_work_and_stale_version(client):
    work_id = (await client.post("/api/sessions", json={"title": "Archive"})).json()["id"]
    task = (await client.post("/api/workspace/tasks", json={"session_id": work_id, "title": "Task"})).json()
    updated = await client.patch(f"/api/workspace/tasks/{task['id']}", json={"status": "in_progress", "version": 1})
    assert updated.status_code == 200
    stale = await client.patch(f"/api/workspace/tasks/{task['id']}", json={"status": "done", "version": 1})
    assert stale.status_code == 409
    assert (await client.patch(f"/api/sessions/{work_id}", json={"archived": True})).status_code == 200
    rejected = await client.post("/api/workspace/tasks", json={"session_id": work_id, "title": "No write"})
    assert rejected.status_code == 409


@pytest.mark.asyncio
async def test_workspace_tasks_are_included_only_for_the_selected_work_context(client, migrated_db_path):
    selected_work = (await client.post("/api/sessions", json={"title": "Công việc được chọn"})).json()
    other_work = (await client.post("/api/sessions", json={"title": "Công việc khác"})).json()
    selected_task = await client.post(
        "/api/workspace/tasks",
        json={
            "session_id": selected_work["id"],
            "title": "Gửi báo cáo trước 16:00",
            "description": "Tổng hợp năm việc trong hôm nay.",
            "status": "ready",
            "priority": 4,
            "impact": 5,
            "due_at": 1_800_000_000,
            "estimate_minutes": 120,
            "ai_eligibility": "delegatable",
        },
    )
    assert selected_task.status_code == 201, selected_task.text
    other_task = await client.post(
        "/api/workspace/tasks",
        json={"session_id": other_work["id"], "title": "Không được lộ sang Work đã chọn"},
    )
    assert other_task.status_code == 201, other_task.text

    async with get_db_connection(migrated_db_path) as conn:
        pack = await AssistantContextPackBuilder(conn).build(selected_work["id"])

    assert "Gửi báo cáo trước 16:00" in pack.text
    assert "hạn:" in pack.text
    assert "ước lượng: 120 phút" in pack.text
    assert "Không được lộ sang Work đã chọn" not in pack.text
    assert any(
        item["kind"] == "workspace_tasks" and item["reason"] == "Việc Workspace thuộc Công việc đang chọn"
        for item in pack.included
    )

    manifest = await client.get("/api/assistant/context-manifest", params={"work_id": selected_work["id"]})
    assert manifest.status_code == 200, manifest.text
    assert any(item["kind"] == "workspace_tasks" for item in manifest.json()["included"])


@pytest.mark.asyncio
async def test_workspace_task_summary_reaches_the_gyo_provider_request(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "Work có task"})).json()
    task = await client.post(
        "/api/workspace/tasks",
        json={"session_id": work["id"], "title": "Tóm tắt việc của hôm nay", "ai_eligibility": "assistable"},
    )
    assert task.status_code == 201, task.text
    gyo = ContextCapturingGyo()

    async with get_db_connection(migrated_db_path) as conn:
        status, _, _, text, sources, *_ = await _read_only_response(
            conn, work["id"], "Hãy tóm tắt việc", gyo,
        )

    assert status == "completed"
    assert text == "Đã nhận ngữ cảnh."
    assert "Tóm tắt việc của hôm nay" in gyo.requests[0].context
    assert any(source["kind"] == "workspace_tasks" for source in sources)
