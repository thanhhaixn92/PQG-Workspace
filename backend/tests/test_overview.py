from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_overview_returns_plain_language_counts_and_recent_work(client):
    first = await client.post("/api/sessions", json={"title": "Prepare monthly plan", "goal": "Draft priorities"})
    second = await client.post("/api/sessions", json={"title": "Review notes"})
    assert first.status_code == second.status_code == 201

    overview = await client.get("/api/overview")
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert {item["id"] for item in body["recent_work"]} == {second.json()["id"], first.json()["id"]}
    assert next(item for item in body["recent_work"] if item["id"] == first.json()["id"])["goal"] == "Draft priorities"
    assert body["active_work_count"] == 0
    assert body["pending_approval_count"] == 0
    assert body["output_count"] == 0
    assert "workspace_path" in body["recent_work"][0]  # API compatibility; UI must not display it.


@pytest.mark.asyncio
async def test_overview_counts_pending_action_packages_as_items_needing_a_decision(client):
    work = await client.post("/api/sessions", json={"title": "Plan an update"})
    proposed = await client.post(
        f"/api/works/{work.json()['id']}/action-packages",
        json={"title": "Pause this Work", "steps": [{"kind": "work_status_update", "input": {"work_status": "paused", "progress_percent": 0}}]},
        headers={"Idempotency-Key": "overview-pause-work"},
    )
    assert proposed.status_code == 201

    overview = await client.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["pending_approval_count"] == 1
    attention = overview.json()["attention_items"]
    assert len(attention) == 1
    assert attention[0]["kind"] == "approval"
    assert attention[0]["work_id"] == work.json()["id"]
    assert attention[0]["work_title"] == "Plan an update"
    assert attention[0]["title"] == "Pause this Work"
    assert attention[0]["reason"] == "Đề xuất đang chờ bạn duyệt"
    assert attention[0]["severity"] == "attention"
