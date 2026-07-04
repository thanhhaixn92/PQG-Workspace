import pytest
from pathlib import Path
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_skills_crud(client: TestClient, test_app) -> None:
    # Helper to check audits
    async def get_audits():
        import aiosqlite
        from app.settings import Settings
        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        async with aiosqlite.connect(settings.db_path_resolved) as db:
            async with db.execute("SELECT action, target FROM audit_events") as cur:
                return await cur.fetchall()

    # Create
    resp = await client.post("/api/skills", json={
        "name": "Test Skill",
        "description": "Test Desc",
        "content": "Do things right.",
        "enabled": True
    })
    assert resp.status_code == 200
    skill = resp.json()
    assert skill["name"] == "Test Skill"
    skill_id = skill["id"]
    
    audits = await get_audits()
    assert ("skill.created", skill_id) in audits
    
    # Duplicate name should fail
    resp = await client.post("/api/skills", json={
        "name": "Test Skill",
        "content": "Another content"
    })
    assert resp.status_code == 400
    
    # List
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    
    # Update
    resp = await client.put(f"/api/skills/{skill_id}", json={
        "enabled": False
    })
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    
    audits = await get_audits()
    assert ("skill.disabled", skill_id) in audits
    
    # Delete
    resp = await client.delete(f"/api/skills/{skill_id}")
    assert resp.status_code == 204
    
    # Verify deletion
    resp = await client.get("/api/skills")
    assert len(resp.json()) == 0
    
    audits = await get_audits()
    assert ("skill.deleted", skill_id) in audits
