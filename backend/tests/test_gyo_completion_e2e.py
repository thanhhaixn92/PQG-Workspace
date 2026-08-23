"""Real FastAPI completion path on an isolated migrated SQLite database.

This suite deliberately uses the shared ``client``/``migrated_db_path`` fixtures:
the app lifespan and every migration run against pytest's temporary database,
never the operator's ``app.db``.  It does not use a provider fake or a seeded
Action Package as evidence that a provider can generate a proposal.
"""
from __future__ import annotations

import pytest

from app.services.action_packages import execute_one_approved_package
from app.settings import Settings


@pytest.mark.asyncio
async def test_work_task_to_canonical_gyo_package_execution_uses_real_api_and_temp_db(
    client, migrated_db_path
) -> None:
    """Exercise the user-visible governed path without touching ``app.db``."""
    work_response = await client.post("/api/sessions", json={"title": "GYO completion E2E"})
    assert work_response.status_code == 201, work_response.text
    work = work_response.json()

    task_payload = {
        "session_id": work["id"],
        "title": "Chuẩn bị bản bàn giao",
        "ai_eligibility": "delegatable",
    }
    task_response = await client.post(
        "/api/workspace/tasks",
        json=task_payload,
        headers={"Idempotency-Key": "gyo-completion-task-create"},
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()

    handoff = await client.post(
        f"/api/workspace/tasks/{task['id']}/ai-jobs",
        headers={"Idempotency-Key": "gyo-completion-handoff"},
    )
    assert handoff.status_code == 201, handoff.text
    job = handoff.json()
    assert job["task_id"] == task["id"]
    assert job["conversation_id"]
    assert job["assistant_thread_id"]

    replay = await client.post(
        f"/api/workspace/tasks/{task['id']}/ai-jobs",
        headers={"Idempotency-Key": "gyo-completion-handoff"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == job["id"]
    assert replay.json()["conversation_id"] == job["conversation_id"]
    assert replay.json()["assistant_thread_id"] == job["assistant_thread_id"]

    second_task = await client.post(
        "/api/workspace/tasks",
        json={**task_payload, "title": "Tra cứu lịch sử GYO"},
        headers={"Idempotency-Key": "gyo-completion-history-task"},
    )
    assert second_task.status_code == 201, second_task.text
    second_job = await client.post(
        f"/api/workspace/tasks/{second_task.json()['id']}/ai-jobs",
        headers={"Idempotency-Key": "gyo-completion-history-handoff"},
    )
    assert second_job.status_code == 201, second_job.text

    history = await client.get(
        f"/api/assistant/works/{work['id']}/history",
        params={"limit": 1, "status": "active"},
    )
    assert history.status_code == 200, history.text
    assert history.json()["cursor_version"] == 1
    assert len(history.json()["items"]) == 1
    assert history.json()["next_cursor"]
    second_page = await client.get(
        f"/api/assistant/works/{work['id']}/history",
        params={"limit": 1, "status": "active", "cursor": history.json()["next_cursor"]},
    )
    assert second_page.status_code == 200, second_page.text
    assert {history.json()["items"][0]["id"], second_page.json()["items"][0]["id"]} == {
        job["assistant_thread_id"], second_job.json()["assistant_thread_id"],
    }
    searched = await client.get(
        f"/api/assistant/works/{work['id']}/history",
        params={"q": "GYO Thread", "include_archived": "true"},
    )
    assert searched.status_code == 200, searched.text
    assert {item["id"] for item in searched.json()["items"]} >= {
        job["assistant_thread_id"], second_job.json()["assistant_thread_id"],
    }

    pinned = await client.patch(
        f"/api/assistant/works/{work['id']}/history/{job['assistant_thread_id']}",
        json={"pinned": True},
    )
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["pinned_at"] is not None

    package_response = await client.post(
        f"/api/works/{work['id']}/action-packages",
        headers={"Idempotency-Key": "gyo-completion-package"},
        json={
            "title": "Cập nhật tiến độ bàn giao",
            "conversation_id": job["conversation_id"],
            "steps": [{
                "kind": "work_status_update",
                "input": {"work_status": "in_progress", "progress_percent": 25},
            }],
        },
    )
    assert package_response.status_code == 201, package_response.text
    package = package_response.json()

    # Provenance is intentionally grouped by semantics; a legacy ``included``
    # field may remain for compatible clients, but it is not evidence of use.
    manifest = await client.get(
        "/api/assistant/context-manifest",
        params={
            "work_id": work["id"],
            "conversation_id": job["conversation_id"],
            "package_id": package["id"],
        },
    )
    assert manifest.status_code == 200, manifest.text
    assert {"accessible", "retrieved", "used", "targeted", "excluded"} <= set(manifest.json())
    assert manifest.json()["package_id"] == package["id"]
    assert manifest.json()["targeted"]

    preflight = await client.get(f"/api/action-packages/{package['id']}/preflight")
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["valid"] is True
    assert preflight.json()["payload_hash"] == package["payload_hash"]
    assert preflight.json()["revision"] == package["revision"]

    approved = await client.post(
        f"/api/action-packages/{package['id']}/approve",
        headers={"Idempotency-Key": "gyo-completion-approve"},
        json={
            "expected_revision": preflight.json()["revision"],
            "expected_payload_hash": preflight.json()["payload_hash"],
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    settings = Settings(db_path=str(migrated_db_path), local_actor_subject="user")
    assert await execute_one_approved_package(settings, "gyo-completion-e2e-worker") is True

    executed = await client.get(f"/api/action-packages/{package['id']}")
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "succeeded"
    assert executed.json()["steps"][0]["status"] == "succeeded"

    archived = await client.patch(
        f"/api/assistant/works/{work['id']}/history/{job['assistant_thread_id']}",
        json={"archived": True},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    active_history = await client.get(f"/api/assistant/works/{work['id']}/history")
    assert job["assistant_thread_id"] not in {item["id"] for item in active_history.json()["items"]}
    archived_history = await client.get(
        f"/api/assistant/works/{work['id']}/history",
        params={"include_archived": "true"},
    )
    assert job["assistant_thread_id"] in {item["id"] for item in archived_history.json()["items"]}

    restored = await client.patch(
        f"/api/assistant/works/{work['id']}/history/{job['assistant_thread_id']}",
        json={"archived": False},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"
