import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_memory_crud_and_validation(client: TestClient, test_app) -> None:
    # Helper to check audits
    async def get_audits():
        import aiosqlite
        from app.settings import Settings
        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        async with aiosqlite.connect(settings.db_path_resolved) as db:
            async with db.execute("SELECT action, target FROM audit_events") as cur:
                return await cur.fetchall()

    # Invalid kind should be rejected
    resp = await client.post("/api/memory", json={
        "key": "test_fact",
        "value": "Test Value",
        "kind": "invalid_kind"
    })
    assert resp.status_code == 422
    
    # Valid kind
    resp = await client.post("/api/memory", json={
        "key": "test_fact",
        "value": "Test Value",
        "kind": "project_fact",
        "importance_score": 5.0
    })
    assert resp.status_code == 200
    mem_id = resp.json()["id"]
    
    audits = await get_audits()
    assert ("memory.created", mem_id) in audits
    
    # List
    resp = await client.get("/api/memory")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["importance_score"] == 5.0
    
    # Update
    resp = await client.put(f"/api/memory/{mem_id}", json={
        "importance_score": 10.0
    })
    assert resp.status_code == 200
    assert resp.json()["importance_score"] == 10.0
    
    audits = await get_audits()
    assert ("memory.updated", mem_id) in audits
    
    # Delete
    resp = await client.delete(f"/api/memory/{mem_id}")
    assert resp.status_code == 204
    
    audits = await get_audits()
    assert ("memory.deleted", mem_id) in audits
