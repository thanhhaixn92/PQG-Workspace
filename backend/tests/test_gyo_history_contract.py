"""Focused Work-scoped GYO history, provenance and canonical-preflight tests."""
from __future__ import annotations

import time

import pytest

from app.db.connection import get_db_connection


@pytest.mark.asyncio
async def test_work_history_is_cursor_scoped_searchable_and_mutable(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "History work"})).json()
    other = (await client.post("/api/sessions", json={"title": "Other work"})).json()
    conversation = (await client.post(f"/api/works/{work['id']}/conversations", json={"title": "GYO history"})).json()
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        for thread_id, title, work_id, conversation_id in (
            ("hist-a", "Needle A", work["id"], conversation["id"]),
            ("hist-b", "Needle B", work["id"], conversation["id"]),
            ("hist-other", "Needle other", other["id"], None),
        ):
            await db.execute(
                """INSERT INTO assistant_threads (id, title, work_id, conversation_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (thread_id, title, work_id, conversation_id, now, now),
            )
        await db.commit()
    first = await client.get(f"/api/assistant/works/{work['id']}/history", params={"q": "needle", "limit": 1})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["cursor_version"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] != "hist-other"
    assert body["next_cursor"]
    second = await client.get(
        f"/api/assistant/works/{work['id']}/history", params={"cursor": body["next_cursor"], "q": "needle"}
    )
    assert second.status_code == 200
    assert {item["id"] for item in second.json()["items"]} == {"hist-a"}
    pinned = await client.patch(f"/api/assistant/works/{work['id']}/history/hist-a", json={"pinned": True})
    assert pinned.status_code == 200 and pinned.json()["pinned_at"] is not None
    archived = await client.patch(f"/api/assistant/works/{work['id']}/history/hist-a", json={"archived": True})
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    hidden = await client.get(f"/api/assistant/works/{work['id']}/history")
    assert "hist-a" not in {item["id"] for item in hidden.json()["items"]}
    restored = await client.patch(f"/api/assistant/works/{work['id']}/history/hist-a", json={"archived": False})
    assert restored.status_code == 200 and restored.json()["status"] == "active"


@pytest.mark.asyncio
async def test_canonical_package_preflight_and_context_provenance(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "Preflight work"})).json()
    conversation = (await client.post(f"/api/works/{work['id']}/conversations", json={"title": "Conversation"})).json()
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES ('phase-pf', ?, 'P', 0, ?, ?)",
            (work["id"], now, now),
        )
        await db.execute(
            """INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at)
               VALUES ('step-pf', 'phase-pf', ?, 'Before', '', 0, 'not_started', 'user', ?, ?)""",
            (work["id"], now, now),
        )
        await db.commit()
    created = await client.post(
        f"/api/works/{work['id']}/action-packages",
        headers={"Idempotency-Key": "history-preflight-create"},
        json={"title": "Update", "conversation_id": conversation["id"], "steps": [
            {"kind": "work_plan_step_update", "input": {"step_id": "step-pf", "changes": {"title": "After"}}}
        ]},
    )
    assert created.status_code == 201, created.text
    package = created.json()
    preflight = await client.get(f"/api/action-packages/{package['id']}/preflight")
    assert preflight.status_code == 200, preflight.text
    checked = preflight.json()
    assert checked["valid"] is True
    assert checked["package_id"] == package["id"]
    assert checked["revision"] == package["revision"]
    assert checked["payload_hash"] == package["payload_hash"]
    manifest = await client.get(
        "/api/assistant/context-manifest",
        params={"work_id": work["id"], "conversation_id": conversation["id"], "package_id": package["id"]},
    )
    assert manifest.status_code == 200, manifest.text
    data = manifest.json()
    assert data["retrieved"] == data["included"]
    assert any(item["kind"] == "work_plan_step_update" for item in data["targeted"])
    # Mutating the target invalidates the confirmation preflight.
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("UPDATE work_plan_steps SET title = 'Changed', version = version + 1 WHERE id = 'step-pf'")
        await db.commit()
    stale = await client.get(f"/api/action-packages/{package['id']}/preflight")
    assert stale.status_code == 409
