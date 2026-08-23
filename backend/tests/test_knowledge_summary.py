from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_knowledge_summary_scopes_work_sources_and_reuses_context_policy(client):
    work = (await client.post("/api/sessions", json={"title": "Knowledge summary"})).json()
    skill = (await client.post(
        "/api/skills",
        json={"name": "Review me", "content": "Only after approval"},
    )).json()
    moved = await client.post(
        f"/api/skills/{skill['id']}/status", json={"status": "review_pending"}
    )
    assert moved.status_code == 200
    memory = await client.post(
        "/api/memory",
        json={
            "session_id": work["id"],
            "key": "Local preference",
            "value": "Keep it scoped",
            "kind": "preference",
            "importance_score": 0.5,
        },
    )
    assert memory.status_code == 200

    response = await client.get("/api/knowledge/summary", params={"work_id": work["id"]})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["work_id"] == work["id"]
    assert body["counts_by_source"]["skills"] == 1
    assert body["counts_by_source"]["memory"] == 1
    assert body["counts_by_source"]["knowledge"] == 0
    assert body["counts_by_lifecycle"]["review_pending"] == 1
    assert body["pending_review_count"] == 1
    assert body["context_included_count"] >= 1
    assert body["context_excluded_count"] >= 1
    assert body["last_updated_at"] is not None


@pytest.mark.asyncio
async def test_knowledge_summary_rejects_unknown_work(client):
    response = await client.get("/api/knowledge/summary", params={"work_id": "missing"})
    assert response.status_code == 404
