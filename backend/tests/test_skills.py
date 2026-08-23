from __future__ import annotations

import pytest


def _audit_tuples(rows: list) -> list[tuple]:
    """Convert sqlite3.Row rows to comparable (action, target) tuples."""
    return [(r["action"], r["target"]) for r in rows]


async def _fetch_audits(settings):
    from app.db.connection import open_db
    conn = await open_db(settings.db_path_resolved)
    try:
        async with conn.execute("SELECT action, target FROM audit_events ORDER BY rowid") as cur:
            return await cur.fetchall()
    finally:
        await conn.close()


async def _approve_skill(client, skill_id: str):
    review = await client.post(f"/api/skills/{skill_id}/status", json={"status": "review_pending"})
    assert review.status_code == 200
    approved = await client.post(f"/api/skills/{skill_id}/status", json={"status": "approved"})
    assert approved.status_code == 200
    return approved


class TestSkillsCRUD:

    async def test_create_skill(self, client, test_app):
        resp = await client.post("/api/skills", json={
            "name": "Test Skill",
            "description": "Test Desc",
            "content": "Do things right.",
        })
        assert resp.status_code == 200
        skill = resp.json()
        assert skill["name"] == "Test Skill"
        assert skill["status"] == "draft"
        assert skill["version"] == 1
        assert skill["enabled"] is False
        skill_id = skill["id"]

        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        audits = _audit_tuples(await _fetch_audits(settings))
        assert ("skill.created", skill_id) in audits

    async def test_legacy_enabled_flag_is_accepted_but_draft_remains_disabled(self, client):
        resp = await client.post("/api/skills", json={
            "name": "Legacy Create", "content": "Needs review", "enabled": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        assert resp.json()["enabled"] is False

    async def test_create_skill_duplicate_name(self, client, test_app):
        await client.post("/api/skills", json={"name": "Dup", "content": "First"})
        resp = await client.post("/api/skills", json={"name": "Dup", "content": "Second"})
        assert resp.status_code == 400

    async def test_list_skills(self, client, test_app):
        resp = await client.get("/api/skills")
        assert resp.status_code == 200
        before = len(resp.json())

        await client.post("/api/skills", json={"name": "S1", "content": "C1"})
        resp = await client.get("/api/skills")
        assert len(resp.json()) == before + 1

    async def test_get_skill(self, client, test_app):
        create = await client.post("/api/skills", json={"name": "GetMe", "content": "X"})
        sid = create.json()["id"]
        resp = await client.get(f"/api/skills/{sid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetMe"

    async def test_get_skill_not_found(self, client, test_app):
        resp = await client.get("/api/skills/nonexistent")
        assert resp.status_code == 404

    async def test_update_skill(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "Before", "content": "Old content",
        })
        sid = create.json()["id"]
        assert create.json()["version"] == 1

        resp = await client.put(f"/api/skills/{sid}", json={
            "name": "After", "content": "New content",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "After"
        assert updated["content"] == "New content"
        assert updated["version"] == 2

        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        audits = _audit_tuples(await _fetch_audits(settings))
        assert ("skill.updated", sid) in audits

    async def test_update_skill_not_found(self, client, test_app):
        resp = await client.put("/api/skills/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    async def test_delete_skill(self, client, test_app):
        create = await client.post("/api/skills", json={"name": "DeleteMe", "content": "X"})
        sid = create.json()["id"]

        resp = await client.delete(f"/api/skills/{sid}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/skills/{sid}")
        assert resp.status_code == 404

        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        audits = _audit_tuples(await _fetch_audits(settings))
        assert ("skill.deleted", sid) in audits

    async def test_delete_skill_not_found(self, client, test_app):
        resp = await client.delete("/api/skills/nonexistent")
        assert resp.status_code == 404


class TestSkillVersioning:

    async def test_create_snapshot_version_history(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "VersionTest", "content": "v1 content",
        })
        sid = create.json()["id"]

        # Update twice
        await client.put(f"/api/skills/{sid}", json={"content": "v2 content"})
        await client.put(f"/api/skills/{sid}", json={"content": "v3 content"})

        resp = await client.get(f"/api/skills/{sid}/versions")
        assert resp.status_code == 200
        versions = resp.json()

        # Snapshots: create (v1), update1 snapshot (v1 old state), update2 snapshot (v2 old state)
        assert len(versions) == 3
        assert versions[0]["version_number"] == 1
        assert versions[0]["content"] == "v1 content"

        versions_snapshot = versions[1]
        assert versions_snapshot["content"] == "v1 content"

        # Current skill is v3
        current = (await client.get(f"/api/skills/{sid}")).json()
        assert current["version"] == 3
        assert current["content"] == "v3 content"

    async def test_version_history_complete(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "FullHistory", "content": "v1",
        })
        sid = create.json()["id"]

        for i in range(2, 6):
            await client.put(f"/api/skills/{sid}", json={"content": f"v{i}"})

        resp = await client.get(f"/api/skills/{sid}/versions")
        # Each update snapshots the old state, plus initial create snapshot
        assert len(resp.json()) == 5

        current = (await client.get(f"/api/skills/{sid}")).json()
        assert current["version"] == 5
        assert current["content"] == "v5"


class TestSkillStatus:

    async def test_default_status_is_draft(self, client, test_app):
        resp = await client.post("/api/skills", json={
            "name": "DraftSkill", "content": "Not ready",
        })
        assert resp.json()["status"] == "draft"

    async def test_approve_skill(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "ApproveMe", "content": "Ready content",
        })
        sid = create.json()["id"]
        assert create.json()["status"] == "draft"

        resp = await _approve_skill(client, sid)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["version"] == 3

        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        audits = _audit_tuples(await _fetch_audits(settings))
        assert ("skill.status_approved", sid) in audits

    async def test_approve_already_approved_returns_400(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "AlreadyApproved", "content": "X",
        })
        sid = create.json()["id"]
        await _approve_skill(client, sid)
        resp = await client.post(f"/api/skills/{sid}/status", json={"status": "approved"})
        assert resp.status_code == 400

    async def test_revert_to_draft(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "RevertMe", "content": "Approved content",
        })
        sid = create.json()["id"]
        await _approve_skill(client, sid)

        resp = await client.post(f"/api/skills/{sid}/status", json={"status": "draft"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        assert resp.json()["version"] == 4

    async def test_status_change_snapshots_version(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "SnapshotStatus", "content": "Before approve",
        })
        sid = create.json()["id"]

        await _approve_skill(client, sid)

        versions = (await client.get(f"/api/skills/{sid}/versions")).json()
        assert len(versions) == 3  # create + submit-for-review + approve snapshots
        assert versions[1]["status"] == "draft"
        assert versions[2]["status"] == "review_pending"

    async def test_draft_cannot_be_enabled_and_content_edit_invalidates_approval(self, client):
        create = await client.post("/api/skills", json={"name": "Governed", "content": "v1"})
        sid = create.json()["id"]
        blocked = await client.put(f"/api/skills/{sid}", json={"enabled": True})
        assert blocked.status_code == 409

        await _approve_skill(client, sid)
        enabled = await client.put(f"/api/skills/{sid}", json={"enabled": True})
        assert enabled.status_code == 200
        edited = await client.put(f"/api/skills/{sid}", json={"content": "v2 needs review"})
        assert edited.status_code == 200
        assert edited.json()["status"] == "draft"
        assert edited.json()["enabled"] is False


class TestContextFiltering:

    async def test_draft_skill_excluded_from_context(self, client, test_app, migrated_db_path):
        await client.post("/api/skills", json={
            "name": "DraftSkill", "content": "Draft content",
        })

        from app.db.connection import open_db
        conn = await open_db(migrated_db_path)
        try:
            from app.services.context import _get_skills_context
            ctx = await _get_skills_context(conn)
            assert ctx == "", f"Expected empty context but got: {ctx}"
        finally:
            await conn.close()

    async def test_approved_skill_included_in_context(self, client, test_app, migrated_db_path):
        create = await client.post("/api/skills", json={
            "name": "ApprovedSkill", "content": "Approved content",
        })
        sid = create.json()["id"]
        await _approve_skill(client, sid)
        await client.put(f"/api/skills/{sid}", json={"enabled": True})

        from app.db.connection import open_db
        conn = await open_db(migrated_db_path)
        try:
            from app.services.context import _get_skills_context
            ctx = await _get_skills_context(conn)
            assert "ApprovedSkill" in ctx
            assert "Approved content" in ctx
        finally:
            await conn.close()

    async def test_disabled_approved_skill_excluded(self, client, test_app, migrated_db_path):
        create = await client.post("/api/skills", json={
            "name": "DisabledApproved", "content": "Disabled",
        })
        sid = create.json()["id"]
        await _approve_skill(client, sid)
        await client.put(f"/api/skills/{sid}", json={"enabled": False})

        from app.db.connection import open_db
        conn = await open_db(migrated_db_path)
        try:
            from app.services.context import _get_skills_context
            ctx = await _get_skills_context(conn)
            assert "DisabledApproved" not in ctx
        finally:
            await conn.close()


class TestAuditTrail:

    async def test_every_mutation_audited(self, client, test_app):
        create = await client.post("/api/skills", json={
            "name": "AuditTest", "content": "X",
        })
        sid = create.json()["id"]

        await client.put(f"/api/skills/{sid}", json={"content": "Y"})
        await _approve_skill(client, sid)
        await client.put(f"/api/skills/{sid}", json={"enabled": True})
        await client.put(f"/api/skills/{sid}", json={"enabled": False})

        from app.dependencies import get_settings
        settings = test_app.dependency_overrides.get(get_settings, get_settings)()
        audits = _audit_tuples(await _fetch_audits(settings))

        expected = [
            ("skill.created", sid),
            ("skill.updated", sid),
            ("skill.status_approved", sid),
            ("skill.enabled", sid),
            ("skill.disabled", sid),
        ]
        for exp in expected:
            assert exp in audits, f"Missing audit: {exp}"
