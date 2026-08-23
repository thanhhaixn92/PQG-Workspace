import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

@pytest.mark.asyncio
async def test_context_limits_and_disabled(client: TestClient, test_app: FastAPI) -> None:
    # Helper to check audits
    async def get_audits():
        import aiosqlite
        from app.settings import Settings
        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        async with aiosqlite.connect(settings.db_path_resolved) as db:
            async with db.execute("SELECT action, target FROM audit_events") as cur:
                return await cur.fetchall()

    # 1. Create a session
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]
    
    # 2. Create one enabled skill and one disabled skill
    await client.post("/api/skills", json={"name": "S1", "content": "Enabled Skill", "enabled": True})
    await client.post("/api/skills", json={"name": "S2", "content": "Disabled Skill", "enabled": False})
    
    # 3. Create 12 memory entries (to test cap of 10)
    for i in range(12):
        await client.post("/api/memory", json={
            "key": f"k{i}",
            "value": f"v{i}",
            "kind": "preference",
            "importance_score": float(i)
        })
        
    # 4. Submit a legacy Work prompt.  It now uses the same GYO context pack
    # boundary and must not auto-inject legacy memory entries.
    resp = await client.post(f"/api/sessions/{session_id}/prompt", json={"prompt": "Hello"})
    assert resp.status_code == 202
    
    # 5. Legacy memories remain untouched; Memory Hub is opt-in per Work.
    resp = await client.get("/api/memory")
    memories = resp.json()
    
    # Order should be by importance_score DESC (so k11, k10, ... k0)
    assert memories[0]["key"] == "k11"
    
    assert all(memory["last_accessed_at"] is None for memory in memories)
    
    # Verify audit events for injection
    audits = await get_audits()
    injected_audits = [target for action, target in audits if action == "memory.injected"]
    assert injected_audits == []
    
    # Allow background task to complete
    import asyncio
    await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_curate_endpoint(client: TestClient, test_app: FastAPI) -> None:
    async def get_audits():
        import aiosqlite
        from app.settings import Settings
        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        async with aiosqlite.connect(settings.db_path_resolved) as db:
            async with db.execute("SELECT action, target FROM audit_events") as cur:
                return await cur.fetchall()
                
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]
    
    resp = await client.post(f"/api/sessions/{session_id}/curate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_proposal"
    assert data["proposal"] is None

    from app.dependencies import get_settings
    import aiosqlite
    import time
    import uuid
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    async with aiosqlite.connect(settings.db_path_resolved) as db:
        await db.execute(
            """
            INSERT INTO chat_messages (id, session_id, role, content, created_at)
            VALUES (?, ?, 'user', ?, ?)
            """,
            (
                str(uuid.uuid4()),
                session_id,
                "Tôi thích giao diện tối và ưu tiên câu trả lời ngắn gọn.",
                int(time.time()),
            ),
        )
        await db.commit()

    resp = await client.post(f"/api/sessions/{session_id}/curate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "curator_proposed"
    assert "approval_id" in data
    approval_id = data["approval_id"]
    assert "giao diện tối" in data["proposal"]["value"]
    
    # Verify approval_required is emitted and requested is audited
    audits = await get_audits()
    assert ("curator.proposed", approval_id) in audits
    assert ("approval.requested", approval_id) in audits
    
    # Deny approval
    resp = await client.post(f"/api/approvals/{approval_id}", json={"decision": "deny"})
    assert resp.status_code == 200
    audits = await get_audits()
    assert ("curator.denied", approval_id) in audits
    
    # Try accepting a non-existent one
    resp = await client.post(f"/api/approvals/appr-fake", json={"decision": "allow_once"})
    assert resp.status_code == 404
    
    # Test accepting approval
    resp = await client.post(f"/api/sessions/{session_id}/curate")
    appr_id_2 = resp.json()["approval_id"]
    resp = await client.post(f"/api/approvals/{appr_id_2}", json={"decision": "allow_once"})
    assert resp.status_code == 200
    audits = await get_audits()
    assert ("curator.accepted", appr_id_2) in audits
    assert any(action == "memory.created" for action, _ in audits)

    resp = await client.get(f"/api/sessions/{session_id}/memory")
    assert resp.status_code == 200
    memories = resp.json()
    assert any("giao diện tối" in memory["value"] for memory in memories)
