from __future__ import annotations

import hashlib

import pytest

from app.api.memory_hub import get_memory_hub_role


PROJECT = "dirap-v3"
TASK = "memory-hub-task"
OPERATOR_HEADERS = {"Origin": "http://localhost:5173"}


async def _as(test_app, role: str):
    async def current_role():
        return role

    test_app.dependency_overrides[get_memory_hub_role] = current_role


async def _proposal(client, **extra):
    payload = {
        "kind": "technical_decision",
        "memory_key": "python-version",
        "content": "Use Python 3.11 for this backend.",
        "project_id": PROJECT,
        "task_id": TASK,
        "evidence": [{"evidence_type": "test", "reference": "tests/test_memory_hub.py"}],
    }
    payload.update(extra)
    response = await client.post("/api/memory-hub/proposals", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def _activate_technical(client, test_app, record_id: str):
    await _as(test_app, "codex")
    assert (await client.post(f"/api/memory-hub/records/{record_id}/verify", json={})).status_code == 200
    assert (await client.post(f"/api/memory-hub/records/{record_id}/activate", json={})).status_code == 200


@pytest.mark.asyncio
async def test_memory_hub_lifecycle_and_context_pack(client, test_app):
    await _as(test_app, "hermes")
    record = await _proposal(client)
    assert record["lifecycle"] == "proposed"

    await _as(test_app, "codex")
    assert (await client.post(f"/api/memory-hub/records/{record['id']}/verify", json={})).json()["lifecycle"] == "verified"
    await _as(test_app, "hermes")
    assert (await client.post(f"/api/memory-hub/records/{record['id']}/activate", json={})).status_code == 403
    await _as(test_app, "codex")
    assert (await client.post(f"/api/memory-hub/records/{record['id']}/activate", json={})).json()["lifecycle"] == "active"

    await _as(test_app, "hermes")
    pack = (await client.post("/api/memory-hub/context-pack", json={"project_id": PROJECT, "task_id": TASK})).json()
    assert pack["record_count"] == 1
    assert pack["bytes"] <= 8192


@pytest.mark.asyncio
async def test_preference_requires_user_verify_then_activate(client, test_app):
    await _as(test_app, "user")
    preference = await _proposal(
        client,
        kind="preference",
        memory_key="language",
        content="Prefer Vietnamese.",
        project_id=None,
        task_id=None,
        source_type="user_input",
    )
    assert (await client.post(f"/api/memory-hub/records/{preference['id']}/activate", json={})).status_code == 409
    assert (await client.post(f"/api/memory-hub/records/{preference['id']}/verify", json={})).status_code == 200
    await _as(test_app, "codex")
    assert (await client.post(f"/api/memory-hub/records/{preference['id']}/activate", json={})).status_code == 403
    await _as(test_app, "user")
    assert (await client.post(f"/api/memory-hub/records/{preference['id']}/activate", json={})).status_code == 200


@pytest.mark.asyncio
async def test_scope_isolation_and_global_preference_is_explicit(client, test_app):
    await _as(test_app, "user")
    global_preference = await _proposal(
        client, kind="preference", memory_key="language", content="Vietnamese.", project_id=None, task_id=None, source_type="user_input"
    )
    await client.post(f"/api/memory-hub/records/{global_preference['id']}/verify", json={})
    await client.post(f"/api/memory-hub/records/{global_preference['id']}/activate", json={})

    await _as(test_app, "hermes")
    first = await _proposal(client, memory_key="scope-key", content="Task A", project_id="project-a", task_id="task-a")
    second = await _proposal(client, memory_key="scope-key", content="Task B", project_id="project-b", task_id="task-b")
    await _activate_technical(client, test_app, first["id"])
    await _activate_technical(client, test_app, second["id"])

    await _as(test_app, "hermes")
    assert (await client.get("/api/memory-hub/records", params={"project_id": "project-a"})).status_code == 422
    visible = await client.get("/api/memory-hub/records", params={"project_id": "project-a", "task_id": "task-a"})
    assert [item["id"] for item in visible.json()] == [first["id"]]
    assert (await client.get(f"/api/memory-hub/records/{global_preference['id']}", params={"project_id": "project-a", "task_id": "task-a"})).status_code == 403
    assert (await client.post("/api/memory-hub/proposals", json={"kind": "technical_decision", "memory_key": "bad", "content": "bad", "task_id": "task-a"})).status_code == 422

    await _as(test_app, "user")
    without_global = await client.get("/api/memory-hub/records", params={"project_id": "project-a"})
    with_global = await client.get("/api/memory-hub/records", params={"project_id": "project-a", "include_global_preferences": "true"})
    assert global_preference["id"] not in [item["id"] for item in without_global.json()]
    assert global_preference["id"] in [item["id"] for item in with_global.json()]


@pytest.mark.asyncio
async def test_search_fts_and_legacy_import_are_duplicate_safe(client, test_app, migrated_db_path):
    await _as(test_app, "hermes")
    record = await _proposal(client, content="SQLite WAL is required for durable local state.")
    await _activate_technical(client, test_app, record["id"])
    await _as(test_app, "hermes")
    found = await client.get("/api/memory-hub/records", params={"q": "SQLite WAL", "project_id": PROJECT, "task_id": TASK})
    assert found.status_code == 200 and found.json()[0]["id"] == record["id"]
    hyphenated = await client.get("/api/memory-hub/records", params={"q": "SQLite-WAL", "project_id": PROJECT, "task_id": TASK})
    assert hyphenated.status_code == 200

    from app.db.connection import get_db_connection
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("INSERT INTO memory_entries (id, session_id, key, value, kind, importance_score, created_at) VALUES ('legacy-1', NULL, 'legacy-key', 'legacy value', 'project_context', 5, 1)")
        await db.commit()
    await _as(test_app, "user")
    body = {"memory_ids": ["legacy-1"], "project_id": PROJECT}
    first = await client.post("/api/memory-hub/legacy-import", json=body)
    second = await client.post("/api/memory-hub/legacy-import", json=body)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()[0]["id"] == second.json()[0]["id"]
    await _as(test_app, "hermes")
    assert (await client.post("/api/memory-hub/legacy-import/preview", json={"memory_ids": ["legacy-1"]})).status_code == 403


@pytest.mark.asyncio
async def test_provenance_and_lifecycle_filters_fail_closed(client, test_app):
    await _as(test_app, "user")
    invalid_hash = await client.post("/api/memory-hub/proposals", json={
        "kind": "project_context", "memory_key": "artifact", "content": "artifact-backed", "project_id": PROJECT,
        "source_type": "artifact_reference", "source_artifact_sha256": "not-a-hash",
    })
    assert invalid_hash.status_code == 422
    user_input = await _proposal(client, kind="preference", memory_key="hash", content="plain user input", project_id=None, task_id=None, source_type="user_input")
    assert user_input["content_sha256"] == hashlib.sha256(b"plain user input").hexdigest()
    assert user_input["source_artifact_sha256"] is None
    assert (await client.get("/api/memory-hub/records", params={"lifecycle": "rejected", "project_id": PROJECT})).status_code == 422


@pytest.mark.asyncio
async def test_memory_hub_fails_closed_without_token(client):
    response = await client.get("/api/memory-hub/records")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_memory_hub_accepts_only_matching_keyring_token(client, test_app, monkeypatch):
    test_app.dependency_overrides.pop(get_memory_hub_role, None)
    monkeypatch.setattr("app.api.memory_hub.keyring.get_password", lambda service, role: "codex-token" if role == "codex" else None)
    accepted = await client.get("/api/memory-hub/records", params={"project_id": PROJECT}, headers={"Authorization": "Bearer codex-token"})
    rejected = await client.get("/api/memory-hub/records", params={"project_id": PROJECT}, headers={"Authorization": "Bearer wrong-token"})
    assert accepted.status_code == 200
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_token_shared_by_roles_fails_closed(client, test_app, monkeypatch):
    test_app.dependency_overrides.pop(get_memory_hub_role, None)
    monkeypatch.setattr("app.api.memory_hub.keyring.get_password", lambda service, role: "shared" if role in {"hermes", "codex"} else None)
    response = await client.get("/api/memory-hub/records", params={"project_id": PROJECT}, headers={"Authorization": "Bearer shared"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_context_cap_uses_json_bytes_and_search_hides_terminal_lifecycle(client, test_app):
    await _as(test_app, "hermes")
    active = await _proposal(client, memory_key="escapes", content='"\\' * 3500)
    rejected = await _proposal(client, memory_key="reject-me", content="do not return")
    await _as(test_app, "codex")
    for record in (active, rejected):
        await client.post(f"/api/memory-hub/records/{record['id']}/verify", json={})
    await client.post(f"/api/memory-hub/records/{active['id']}/activate", json={})
    await client.post(f"/api/memory-hub/records/{rejected['id']}/reject", json={})
    await _as(test_app, "hermes")
    pack = (await client.post("/api/memory-hub/context-pack", json={"project_id": PROJECT, "task_id": TASK})).json()
    assert pack["bytes"] <= 8192
    assert (await client.get("/api/memory-hub/records", params={"lifecycle": "rejected", "project_id": PROJECT, "task_id": TASK})).status_code == 422


@pytest.mark.asyncio
async def test_operator_requires_local_origin_and_enforces_preference_flow(client, test_app):
    missing_origin = await client.get("/api/memory-hub/operator/records")
    assert missing_origin.status_code == 403
    foreign_origin = await client.get(
        "/api/memory-hub/operator/records", headers={"Origin": "http://evil.example"}
    )
    assert foreign_origin.status_code == 403
    proxy_referer = await client.get(
        "/api/memory-hub/operator/records",
        headers={"Referer": "http://localhost:5173/review"},
        params={"project_id": PROJECT},
    )
    assert proxy_referer.status_code == 200
    foreign_referer = await client.get(
        "/api/memory-hub/operator/records", headers={"Referer": "http://evil.example/review"}
    )
    assert foreign_referer.status_code == 403
    preference = await client.post("/api/memory-hub/operator/proposals", headers=OPERATOR_HEADERS, json={
        "kind": "preference", "memory_key": "editor", "content": "Prefer concise Vietnamese.",
    })
    assert preference.status_code == 200, preference.text
    record_id = preference.json()["id"]
    review_queue = await client.get("/api/memory-hub/operator/records", headers=OPERATOR_HEADERS, params={"include_global_preferences": "true"})
    assert record_id in [item["id"] for item in review_queue.json()]
    assert (await client.post(f"/api/memory-hub/operator/records/{record_id}/activate", headers=OPERATOR_HEADERS, json={})).status_code == 409
    assert (await client.post(f"/api/memory-hub/operator/records/{record_id}/verify", headers=OPERATOR_HEADERS, json={})).status_code == 200
    assert (await client.post(f"/api/memory-hub/operator/records/{record_id}/activate", headers=OPERATOR_HEADERS, json={})).status_code == 200
    results = await client.get("/api/memory-hub/operator/records", headers=OPERATOR_HEADERS, params={"include_global_preferences": "true"})
    assert record_id in [item["id"] for item in results.json()]

    rejected = await client.post("/api/memory-hub/operator/proposals", headers=OPERATOR_HEADERS, json={
        "kind": "preference", "memory_key": "discard", "content": "Do not keep this.",
    })
    rejected_id = rejected.json()["id"]
    assert (await client.post(f"/api/memory-hub/operator/records/{rejected_id}/reject", headers=OPERATOR_HEADERS, json={})).status_code == 200
    results = await client.get("/api/memory-hub/operator/records", headers=OPERATOR_HEADERS, params={"include_global_preferences": "true"})
    assert rejected_id not in [item["id"] for item in results.json()]

    normal = await client.post("/api/memory-hub/operator/proposals", headers=OPERATOR_HEADERS, json={
        "kind": "technical_decision", "memory_key": "normal", "content": "Needs Codex review.", "project_id": PROJECT,
    })
    assert normal.status_code == 200
    assert (await client.post(f"/api/memory-hub/operator/records/{normal.json()['id']}/verify", headers=OPERATOR_HEADERS, json={})).status_code == 403
