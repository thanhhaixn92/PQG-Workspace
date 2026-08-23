"""Gate 1 characterization only: isolated SQLite/workspace fixtures.

These tests use the shared ``client`` fixture, whose DB is a per-test temp SQLite
file.  They never open or mutate the repository's app.db.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from pathlib import Path

import pytest

from app.db.connection import get_db_connection


async def _create_work(client, workspace: Path) -> str:
    response = await client.post(
        "/api/sessions",
        json={"title": "gate1-isolated-work", "workspace_path": str(workspace)},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _resolve_bound_thread(client, work_id: str) -> dict:
    conversations = (await client.get(f"/api/works/{work_id}/conversations")).json()
    conversation = next(item for item in conversations if item["status"] == "active")
    response = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation['id']}/assistant-thread"
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_gate1_archived_work_blocks_resolve_run_retry_and_context_manifest(
    client, migrated_db_path, tmp_path
):
    """Characterize four archive guards against one isolated archived Work."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    work_id = await _create_work(client, workspace)
    bound_thread = await _resolve_bound_thread(client, work_id)
    thread_id = bound_thread["id"]
    conversation_id = bound_thread["conversation_id"]

    # Seed a failed assistant turn in the canonical Work+Conversation scope so
    # retry reaches the archived-Work guard without relying on legacy threads.
    failed_turn_id = str(uuid.uuid4())
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at, completed_at)
               VALUES (?, ?, ?, ?, 'assistant', 'failed', 'gate1', ?, ?)""",
            (failed_turn_id, thread_id, work_id, conversation_id, now, now),
        )
        await db.commit()

    archived = await client.delete(f"/api/sessions/{work_id}")
    assert archived.status_code == 200
    assert archived.json() == {"status": "archived"}

    resolve_again = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation_id}/assistant-thread"
    )
    assert resolve_again.status_code == 409
    assert resolve_again.json()["detail"] == "Work is archived"

    run = await client.post(
        f"/api/assistant/threads/{thread_id}/runs",
        json={"prompt": "gate1"},
    )
    assert run.status_code == 409
    assert run.json()["detail"] == "Work is archived"

    retry = await client.post(f"/api/assistant/turns/{failed_turn_id}/retry", json={"mode": "auto"})
    assert retry.status_code == 409
    assert retry.json()["detail"] == "Work is archived"

    manifest = await client.get("/api/assistant/context-manifest", params={"work_id": work_id})
    assert manifest.status_code == 409
    assert manifest.json()["detail"] == "Work is archived"


@pytest.mark.asyncio
async def test_gate1_assistant_attachment_symlink_escape_is_rejected_or_runtime_skipped(
    client, migrated_db_path, tmp_path
):
    """Create a real link in a temp workspace; skip only on actual OS denial."""
    workspace = tmp_path / "workspace"
    inputs = workspace / "inputs"
    inputs.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    escaped_link = inputs / "escape.txt"
    try:
        os.symlink(outside, escaped_link)
    except OSError as exc:
        pytest.skip(f"runtime could not create temp symlink: {type(exc).__name__}: {exc}")

    work_id = await _create_work(client, workspace)
    artifact_id = str(uuid.uuid4())
    payload = outside.read_bytes()
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at)
               VALUES (?, ?, 'inputs/escape.txt', 'file', ?, ?, ?)""",
            (artifact_id, work_id, hashlib.sha256(payload).hexdigest(), len(payload), now),
        )
        await db.execute(
            """INSERT INTO artifact_validations
               (artifact_id, status, media_type, validator_version, detail_json, validated_at)
               VALUES (?, 'structurally_validated', 'text/plain', 'gate1-test', '{}', ?)""",
            (artifact_id, now),
        )
        await db.commit()

    thread = await _resolve_bound_thread(client, work_id)
    response = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "gate1", "attachment_artifact_ids": [artifact_id]},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Attachment is no longer available"
