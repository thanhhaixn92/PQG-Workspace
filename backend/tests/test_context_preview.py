from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_context_preview_explains_selection_without_mutating_memory(client):
    session = (await client.post("/api/sessions", json={"title": "Preview"})).json()
    draft = (await client.post("/api/skills", json={"name": "Draft", "content": "not ready"})).json()
    approved = (await client.post("/api/skills", json={"name": "Ready", "content": "use this"})).json()
    await client.post(f"/api/skills/{approved['id']}/status", json={"status": "review_pending"})
    await client.post(f"/api/skills/{approved['id']}/status", json={"status": "approved"})
    await client.put(f"/api/skills/{approved['id']}", json={"enabled": True})
    memory = (await client.post("/api/memory", json={
        "session_id": session["id"], "key": "tone", "value": "brief",
        "kind": "preference", "importance_score": 5,
    })).json()

    preview = await client.get(f"/api/context-preview?session_id={session['id']}")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    by_skill = {item["id"]: item for item in body["skills"]["items"]}
    assert by_skill[draft["id"]]["selected"] is False
    assert by_skill[draft["id"]]["reason"] == "Chưa được duyệt"
    assert by_skill[approved["id"]]["selected"] is True
    assert body["memories"]["items"][0]["id"] == memory["id"]
    assert body["memories"]["items"][0]["selected"] is True
    assert body["memory_hub_injected"] is False

    listed = await client.get(f"/api/sessions/{session['id']}/memory")
    assert next(item for item in listed.json() if item["id"] == memory["id"])["last_accessed_at"] is None
