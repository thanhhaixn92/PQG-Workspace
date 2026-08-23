"""Regression coverage for the Work-as-project / conversation boundary."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_work_conversations_are_scoped_and_plan_is_visible(client):
    created = await client.post("/api/sessions", json={"title": "Dự án A"})
    assert created.status_code == 201, created.text
    work_id = created.json()["id"]

    conversations = await client.get(f"/api/works/{work_id}/conversations")
    assert conversations.status_code == 200
    default_conversation = conversations.json()[0]
    assert default_conversation["title"] == "Trao đổi ban đầu"

    new_conversation = await client.post(
        f"/api/works/{work_id}/conversations", json={"title": "Trao đổi phương án", "purpose": "So sánh lựa chọn"}
    )
    assert new_conversation.status_code == 201, new_conversation.text

    phase = await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "Khảo sát"})
    assert phase.status_code == 201, phase.text
    step = await client.post(
        f"/api/works/{work_id}/plan/steps", json={"phase_id": phase.json()["id"], "title": "Thu thập thông tin"}
    )
    assert step.status_code == 201, step.text
    completed = await client.patch(
        f"/api/works/{work_id}/plan/steps/{step.json()['id']}", json={"status": "completed"}
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    dashboard = await client.get(f"/api/works/{work_id}/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["work"]["id"] == work_id
    assert len(body["conversations"]) == 2
    assert body["phases"][0]["steps"][0]["title"] == "Thu thập thông tin"


@pytest.mark.asyncio
async def test_conversation_cannot_be_read_from_another_work(client):
    first = (await client.post("/api/sessions", json={"title": "A"})).json()["id"]
    second = (await client.post("/api/sessions", json={"title": "B"})).json()["id"]
    conversation = (await client.get(f"/api/works/{first}/conversations")).json()[0]["id"]
    response = await client.get(f"/api/works/{second}/conversations/{conversation}/messages")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archived_conversation_cannot_receive_another_prompt(client):
    work_id = (await client.post("/api/sessions", json={"title": "Archive conversation"})).json()["id"]
    conversation_id = (await client.get(f"/api/works/{work_id}/conversations")).json()[0]["id"]
    archived = await client.patch(
        f"/api/works/{work_id}/conversations/{conversation_id}", json={"archived": True}
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    prompt = await client.post(
        f"/api/works/{work_id}/conversations/{conversation_id}/prompt", json={"prompt": "Do not run"}
    )
    assert prompt.status_code == 409


@pytest.mark.asyncio
async def test_only_user_can_confirm_completion_after_gyo_proposal(client):
    work_id = (await client.post("/api/sessions", json={"title": "Completion"})).json()["id"]
    premature = await client.post(f"/api/works/{work_id}/confirm-completion")
    assert premature.status_code == 409
    proposal = await client.post(f"/api/works/{work_id}/completion-proposal")
    assert proposal.status_code == 200
    assert proposal.json()["work"]["work_status"] == "waiting_confirmation"
    confirmed = await client.post(f"/api/works/{work_id}/confirm-completion")
    assert confirmed.status_code == 200
    assert confirmed.json()["work"]["work_status"] == "completed"
    assert confirmed.json()["work"]["progress_percent"] == 100


@pytest.mark.asyncio
async def test_user_can_update_work_goal_and_pause_before_completion(client):
    work_id = (await client.post("/api/sessions", json={"title": "Editable work"})).json()["id"]
    updated = await client.patch(
        f"/api/works/{work_id}",
        json={"title": "Updated work", "goal": "Agree the scope", "work_status": "paused", "progress_percent": 35},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated work"
    assert updated.json()["goal"] == "Agree the scope"
    assert updated.json()["work_status"] == "paused"
    assert updated.json()["progress_percent"] == 35


@pytest.mark.asyncio
async def test_work_summary_uses_plan_progress_and_exposes_attention(client):
    work_id = (await client.post("/api/sessions", json={"title": "Server progress"})).json()["id"]
    phase = (await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "Phase"})).json()
    first = (await client.post(
        f"/api/works/{work_id}/plan/steps",
        json={"phase_id": phase["id"], "title": "Done"},
    )).json()
    second = (await client.post(
        f"/api/works/{work_id}/plan/steps",
        json={"phase_id": phase["id"], "title": "Needs input", "description": "Ask the owner"},
    )).json()
    assert (await client.patch(
        f"/api/works/{work_id}/plan/steps/{first['id']}", json={"status": "completed"}
    )).status_code == 200
    assert (await client.patch(
        f"/api/works/{work_id}/plan/steps/{second['id']}", json={"status": "blocked"}
    )).status_code == 200

    dashboard = (await client.get(f"/api/works/{work_id}/dashboard")).json()
    assert dashboard["progress_source"] == "plan_steps"
    assert dashboard["work"]["progress_source"] == "plan_steps"
    assert dashboard["work"]["progress_percent"] == 50
    assert dashboard["work"]["blocked_step_count"] == 1
    assert dashboard["work"]["next_step"]["id"] == second["id"]

    listed = (await client.get("/api/works")).json()
    summary = next(item for item in listed if item["id"] == work_id)
    assert summary["progress_percent"] == 50
    assert summary["progress_source"] == "plan_steps"
    assert summary["next_step"]["title"] == "Needs input"


@pytest.mark.asyncio
async def test_blocked_step_requires_reason_or_next_action(client):
    work_id = (await client.post("/api/sessions", json={"title": "Blocked validation"})).json()["id"]
    phase = (await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "Phase"})).json()
    step = (await client.post(
        f"/api/works/{work_id}/plan/steps", json={"phase_id": phase["id"], "title": "Step"}
    )).json()
    rejected = await client.patch(
        f"/api/works/{work_id}/plan/steps/{step['id']}", json={"status": "blocked"}
    )
    assert rejected.status_code == 422
    accepted = await client.patch(
        f"/api/works/{work_id}/plan/steps/{step['id']}",
        json={"status": "blocked", "result": "Confirm the source"},
    )
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_phase_can_be_edited_and_reordered(client):
    work_id = (await client.post("/api/sessions", json={"title": "Phase editing"})).json()["id"]
    phase = (await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "Original"})).json()
    updated = await client.patch(
        f"/api/works/{work_id}/plan/phases/{phase['id']}",
        json={"title": "Renamed", "status": "in_progress", "sort_order": 4},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Renamed"
    assert updated.json()["status"] == "in_progress"
    assert updated.json()["sort_order"] == 4


@pytest.mark.asyncio
async def test_archived_conversation_can_only_be_restored(client):
    work_id = (await client.post("/api/sessions", json={"title": "Restore conversation"})).json()["id"]
    conversation_id = (await client.get(f"/api/works/{work_id}/conversations")).json()[0]["id"]
    assert (await client.patch(
        f"/api/works/{work_id}/conversations/{conversation_id}", json={"archived": True}
    )).status_code == 200
    rename = await client.patch(
        f"/api/works/{work_id}/conversations/{conversation_id}", json={"title": "Hidden edit"}
    )
    assert rename.status_code == 409
    restored = await client.patch(
        f"/api/works/{work_id}/conversations/{conversation_id}", json={"archived": False}
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"


@pytest.mark.asyncio
async def test_archived_work_blocks_work_hub_mutations(client):
    work_id = (await client.post("/api/sessions", json={"title": "Archived Work"})).json()["id"]
    conversation_id = (await client.get(f"/api/works/{work_id}/conversations")).json()[0]["id"]
    assert (await client.patch(f"/api/sessions/{work_id}", json={"archived": True})).status_code == 200
    requests = [
        await client.patch(f"/api/works/{work_id}", json={"title": "No"}),
        await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "No"}),
        await client.post(f"/api/works/{work_id}/conversations", json={"title": "No"}),
        await client.patch(
            f"/api/works/{work_id}/conversations/{conversation_id}", json={"archived": False}
        ),
    ]
    assert [response.status_code for response in requests] == [409, 409, 409, 409]
