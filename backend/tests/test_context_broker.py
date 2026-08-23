"""F7 regression tests for Resource Catalog + Context Broker."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.connection import get_db_connection
from app.services.context_broker import (
    BrokerScope,
    CatalogResource,
    ContextBroker,
    SENSITIVITY_CLASSES,
    TRUST_CLASSES,
)


class RecordingBroker(ContextBroker):
    """Assert the rank stage never receives denied descriptors."""

    def __init__(self, conn):
        super().__init__(conn)
        self.ranked_ids: list[str] = []

    async def discover(self, work_id, conversation_id=None, attachment_artifact_ids=None, **kwargs):
        scope = BrokerScope(
            work_id=work_id,
            conversation_id=None,
            memory_mode="suggest_only",
            memory_project_id=None,
            memory_task_id=None,
            memory_scope_id=None,
            data_scope="work_only",
            workspace_path=".",
        )
        resources = [
            CatalogResource(
                kind="work",
                resource_id=work_id,
                title="Authorized Work",
                sensitivity="internal",
                trust="canonical_user_data",
                rank_group=10,
            ),
            CatalogResource(
                kind="artifact",
                resource_id="restricted-resource-id",
                title="RESTRICTED RESOURCE TITLE",
                sensitivity="restricted",
                trust="canonical_user_data",
                rank_group=-100,
                locator={
                    "relative_path": "inputs/restricted.txt",
                    "validation_status": "structurally_validated",
                },
            ),
        ]
        return {"id": work_id}, scope, resources

    def rank(self, resources):
        self.ranked_ids = [resource.resource_id for resource in resources]
        assert "restricted-resource-id" not in self.ranked_ids
        return super().rank(resources)


@pytest.mark.asyncio
async def test_f7_security_filter_precedes_ranking_and_denied_metadata_is_not_public(migrated_db_path):
    async with get_db_connection(migrated_db_path) as db:
        broker = RecordingBroker(db)
        _work, _scope, ranked, public, denied = await broker.authorized_catalog("work-1")

    assert [resource.resource_id for resource in ranked] == ["work-1"]
    assert broker.ranked_ids == ["work-1"]
    serialized = json.dumps({"public": public, "denied": denied}, ensure_ascii=False)
    assert "restricted-resource-id" not in serialized
    assert "RESTRICTED RESOURCE TITLE" not in serialized
    assert denied == [{
        "kind": "artifact",
        "count": 1,
        "reason": "Nguồn restricted không được đưa vào catalog hoặc ngữ cảnh GYO",
    }]


@pytest.mark.asyncio
async def test_f7_catalog_filters_invalid_and_foreign_artifacts_before_context(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "F7 Work"})).json()
    other = (await client.post("/api/sessions", json={"title": "Foreign Work"})).json()
    workspace = Path(work["workspace_path"])
    other_workspace = Path(other["workspace_path"])
    workspace.joinpath("inputs").mkdir(parents=True, exist_ok=True)
    other_workspace.joinpath("inputs").mkdir(parents=True, exist_ok=True)

    safe_text = "AUTHORIZED_F7_ARTIFACT"
    denied_text = "DENIED_F7_ARTIFACT_CONTENT"
    foreign_text = "FOREIGN_F7_ARTIFACT_CONTENT"
    safe_path = workspace / "inputs" / "safe-f7.txt"
    denied_path = workspace / "inputs" / "private-f7.txt"
    foreign_path = other_workspace / "inputs" / "foreign-f7.txt"
    safe_path.write_text(safe_text, encoding="utf-8")
    denied_path.write_text(denied_text, encoding="utf-8")
    foreign_path.write_text(foreign_text, encoding="utf-8")

    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        for artifact_id, session_id, relative_path, content in (
            ("f7-safe-artifact", work["id"], "inputs/safe-f7.txt", safe_text),
            ("f7-denied-artifact", work["id"], "inputs/private-f7.txt", denied_text),
            ("f7-foreign-artifact", other["id"], "inputs/foreign-f7.txt", foreign_text),
        ):
            await db.execute(
                """INSERT INTO artifacts
                   (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
                   VALUES (?, ?, ?, 'imported_file', ?, ?, ?)""",
                (
                    artifact_id,
                    session_id,
                    relative_path,
                    hashlib.sha256(content.encode()).hexdigest(),
                    len(content.encode()),
                    now,
                ),
            )
        await db.execute(
            """INSERT INTO artifact_validations
               (artifact_id, status, media_type, validator_version, detail_json, validated_at)
               VALUES ('f7-safe-artifact', 'structurally_validated', 'text/plain', 'f7-test', '{}', ?)""",
            (now,),
        )
        await db.commit()

        pack = await ContextBroker(db).build(work["id"])

    assert safe_text in pack.text
    assert denied_text not in pack.text
    assert foreign_text not in pack.text
    assert any(item["id"] == "f7-safe-artifact" for item in pack.accessible)

    serialized = json.dumps({
        "accessible": pack.accessible,
        "included": pack.included,
        "excluded": pack.excluded,
    }, ensure_ascii=False)
    assert "f7-denied-artifact" not in serialized
    assert "private-f7.txt" not in serialized
    assert "f7-foreign-artifact" not in serialized
    assert "foreign-f7.txt" not in serialized
    assert str(workspace) not in serialized
    assert "inputs/safe-f7.txt" not in serialized
    assert any(
        item.get("kind") == "artifact"
        and item.get("reason") == "Nguồn chưa qua kiểm tra cấu trúc"
        for item in pack.excluded
    )


@pytest.mark.asyncio
async def test_f7_restricted_memory_never_enters_catalog_or_context(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "F7 Memory Work"})).json()
    phase = (await client.post(
        f"/api/works/{work['id']}/plan/phases",
        json={"title": "F7 phase"},
    )).json()
    step = (await client.post(
        f"/api/works/{work['id']}/plan/steps",
        json={"phase_id": phase["id"], "title": "F7 step"},
    )).json()
    policy = (await client.put(
        f"/api/works/{work['id']}/plan/steps/{step['id']}/memory-context",
        json={"context_mode": "active_work_memory", "auto_learning_enabled": False},
    )).json()
    scope_id = policy["scope_id"]
    assert scope_id

    allowed_content = "ALLOWED_F7_MEMORY"
    restricted_content = "RESTRICTED_F7_MEMORY_SECRET"
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        for record_id, key, content, sensitivity in (
            ("f7-memory-allowed", "allowed-memory", allowed_content, "normal"),
            ("f7-memory-restricted", "restricted-memory-key", restricted_content, "restricted"),
        ):
            digest = hashlib.sha256(content.encode()).hexdigest()
            await db.execute(
                """INSERT INTO memory_hub_records (
                       id, kind, memory_key, content, project_id, task_id, session_id,
                       producer_agent, source_type, source_sha256, content_sha256,
                       confidence, sensitivity, lifecycle, version, created_at, updated_at
                   ) VALUES (?, 'technical_decision', ?, ?, ?, ?, ?, 'codex',
                             'agent_proposal', ?, ?, 0.9, ?, 'active', 1, ?, ?)""",
                (
                    record_id,
                    key,
                    content,
                    work["id"],
                    scope_id,
                    work["id"],
                    digest,
                    digest,
                    sensitivity,
                    now,
                    now,
                ),
            )
        await db.commit()

        pack = await ContextBroker(db).build(
            work["id"],
            memory_mode="active_work_memory",
            memory_project_id=work["id"],
            memory_scope_id=scope_id,
        )

    assert allowed_content in pack.text
    assert restricted_content not in pack.text
    allowed = next(item for item in pack.accessible if item["id"] == "f7-memory-allowed")
    assert allowed["sensitivity"] == "internal"
    assert allowed["trust"] == "verified_knowledge"
    assert allowed["sensitivity"] in SENSITIVITY_CLASSES
    assert allowed["trust"] in TRUST_CLASSES

    serialized = json.dumps({
        "accessible": pack.accessible,
        "included": pack.included,
        "excluded": pack.excluded,
    }, ensure_ascii=False)
    assert "f7-memory-restricted" not in serialized
    assert "restricted-memory-key" not in serialized
    assert restricted_content not in serialized
    assert any(
        item.get("kind") == "memory_hub"
        and item.get("reason") == "Nguồn restricted không được đưa vào catalog hoặc ngữ cảnh GYO"
        for item in pack.excluded
    )


class CapturingGyo:
    def __init__(self):
        self.requests = []

    async def stream(self, request):
        self.requests.append(request)
        yield SimpleNamespace(type="token", data={"text": "F7 response"})
        yield SimpleNamespace(type="done", data={
            "text": "F7 response",
            "status": "completed",
            "model_id": "f7-fake",
            "route_mode": request.route_mode,
            "selection_reason": "f7-test",
            "structured_parts": [],
        })


@pytest.mark.asyncio
async def test_f7_provider_receives_only_broker_authorized_context(client, test_app, migrated_db_path):
    gyo = CapturingGyo()
    test_app.state.gyo_orchestrator = gyo
    work = (await client.post("/api/sessions", json={"title": "F7 Provider Work"})).json()
    conversation = (await client.get(f"/api/works/{work['id']}/conversations")).json()[0]
    thread = (await client.post(
        f"/api/assistant/works/{work['id']}/conversations/{conversation['id']}/assistant-thread"
    )).json()

    workspace = Path(work["workspace_path"])
    workspace.joinpath("inputs").mkdir(parents=True, exist_ok=True)
    allowed = "F7_PROVIDER_ALLOWED"
    denied = "F7_PROVIDER_DENIED"
    (workspace / "inputs" / "allowed.txt").write_text(allowed, encoding="utf-8")
    (workspace / "inputs" / "denied.txt").write_text(denied, encoding="utf-8")
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        for artifact_id, name, content in (
            ("f7-provider-allowed", "allowed.txt", allowed),
            ("f7-provider-denied", "denied.txt", denied),
        ):
            await db.execute(
                """INSERT INTO artifacts
                   (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
                   VALUES (?, ?, ?, 'imported_file', ?, ?, ?)""",
                (
                    artifact_id,
                    work["id"],
                    f"inputs/{name}",
                    hashlib.sha256(content.encode()).hexdigest(),
                    len(content.encode()),
                    now,
                ),
            )
        await db.execute(
            """INSERT INTO artifact_validations
               (artifact_id, status, media_type, validator_version, detail_json, validated_at)
               VALUES ('f7-provider-allowed', 'structurally_validated', 'text/plain', 'f7-test', '{}', ?)""",
            (now,),
        )
        await db.commit()

    response = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Use F7 context", "work_id": work["id"], "conversation_id": conversation["id"]},
    )
    assert response.status_code == 200, response.text
    assert gyo.requests
    provider_context = gyo.requests[-1].context
    assert allowed in provider_context
    assert denied not in provider_context
    assert "denied.txt" not in provider_context

    source_parts = [part for part in response.json()[1]["parts"] if part["part_type"] == "source"]
    source_json = json.dumps(source_parts, ensure_ascii=False)
    assert "f7-provider-allowed" in source_json
    assert "f7-provider-denied" not in source_json
    assert str(workspace) not in source_json


@pytest.mark.asyncio
async def test_f7_context_manifest_does_not_leak_denied_ids_or_raw_paths(client, migrated_db_path):
    work = (await client.post("/api/sessions", json={"title": "F7 Manifest Work"})).json()
    workspace = Path(work["workspace_path"])
    workspace.joinpath("inputs").mkdir(parents=True, exist_ok=True)
    bad = workspace / "inputs" / "manifest-denied.txt"
    bad.write_text("MANIFEST_DENIED_CONTENT", encoding="utf-8")
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO artifacts
               (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES ('f7-manifest-denied', ?, 'inputs/manifest-denied.txt', 'imported_file', ?, ?, ?)""",
            (
                work["id"],
                hashlib.sha256(b"MANIFEST_DENIED_CONTENT").hexdigest(),
                len(b"MANIFEST_DENIED_CONTENT"),
                now,
            ),
        )
        await db.commit()

    response = await client.get("/api/assistant/context-manifest", params={"work_id": work["id"]})
    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body, ensure_ascii=False)
    assert "f7-manifest-denied" not in json.dumps(body["included"], ensure_ascii=False)
    assert "f7-manifest-denied" not in json.dumps(body["retrieved"], ensure_ascii=False)
    assert "MANIFEST_DENIED_CONTENT" not in serialized
    assert str(workspace) not in serialized
