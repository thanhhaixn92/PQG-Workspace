from __future__ import annotations

import time

import pytest

from app.api.assistant import _extract_learning_candidate
from app.db.connection import get_db_connection
from app.services.gyo_learning_worker import enqueue_learning_job, process_pending_learning_jobs
from app.settings import Settings


async def _work_step_scope(client):
    work = (await client.post("/api/sessions", json={"title": "Memory scope work"})).json()
    phase = (await client.post(f"/api/works/{work['id']}/plan/phases", json={"title": "Phase"})).json()
    step = (await client.post(
        f"/api/works/{work['id']}/plan/steps", json={"phase_id": phase["id"], "title": "Visible plan step"},
    )).json()
    return work, step


@pytest.mark.asyncio
async def test_visible_step_memory_policy_is_scoped_and_archive_fails_closed(client, migrated_db_path):
    work, step = await _work_step_scope(client)
    initial = await client.get(f"/api/works/{work['id']}/plan/steps/{step['id']}/memory-context")
    assert initial.status_code == 200
    assert initial.json()["context_mode"] == "suggest_only"
    assert initial.json()["auto_learning_enabled"] is False

    updated = await client.put(
        f"/api/works/{work['id']}/plan/steps/{step['id']}/memory-context",
        json={"context_mode": "active_work_memory", "auto_learning_enabled": True},
    )
    assert updated.status_code == 200
    assert updated.json()["scope_id"]
    assert updated.json()["context_mode"] == "active_work_memory"
    assert updated.json()["auto_learning_enabled"] is True
    manifest = await client.get(f"/api/assistant/context-manifest?work_id={work['id']}&plan_step_id={step['id']}")
    assert manifest.status_code == 200
    assert manifest.json()["memory_context_mode"] == "active_work_memory"
    assert manifest.json()["memory_hub_auto_injected"] is True

    async with get_db_connection(migrated_db_path) as db:
        await db.execute("UPDATE sessions SET archived = 1 WHERE id = ?", (work["id"],))
        await db.commit()
    archived = await client.get(f"/api/works/{work['id']}/plan/steps/{step['id']}/memory-context")
    assert archived.status_code == 409


@pytest.mark.asyncio
async def test_learning_job_creates_only_proposed_candidate_and_rate_limits(client, migrated_db_path):
    work, step = await _work_step_scope(client)
    policy = (await client.put(
        f"/api/works/{work['id']}/plan/steps/{step['id']}/memory-context",
        json={"context_mode": "active_work_memory", "auto_learning_enabled": True},
    )).json()
    now = int(time.time())
    candidate = {
        "kind": "memory", "plan_step_id": step["id"], "memory_kind": "lesson",
        "memory_key": "worker-scoped-lesson", "content": "Candidate only, pending review.", "confidence": 0.8,
        "sensitivity": "normal",
    }
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO assistant_threads (id, title, work_id, status, created_at, updated_at) VALUES ('scope-thread', 'Scope', ?, 'active', ?, ?)",
            (work["id"], now, now),
        )
        for turn_id in ("scope-turn-one", "scope-turn-two"):
            await db.execute(
                """INSERT INTO assistant_turns (id, thread_id, work_id, role, status, model_id, created_at, completed_at)
                   VALUES (?, 'scope-thread', ?, 'assistant', 'completed', 'test-model', ?, ?)""",
                (turn_id, work["id"], now, now),
            )
        assert await enqueue_learning_job(
            db, assistant_turn_id="scope-turn-one", work_id=work["id"], plan_step_id=step["id"],
            memory_scope_id=policy["scope_id"], candidate=candidate, now=now,
        ) == "queued"
        await db.commit()

    settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], hermes_dev_mock=False)
    assert await process_pending_learning_jobs(settings) == 1
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute("SELECT status, candidate_ref FROM gyo_learning_jobs") as cur:
            created = await cur.fetchone()
        assert created["status"] == "created"
        async with db.execute("SELECT lifecycle, task_id FROM memory_hub_records WHERE id = ?", (created["candidate_ref"],)) as cur:
            memory = await cur.fetchone()
        assert memory["lifecycle"] == "proposed"
        assert memory["task_id"] == policy["scope_id"]
        assert await enqueue_learning_job(
            db, assistant_turn_id="scope-turn-two", work_id=work["id"], plan_step_id=step["id"],
            memory_scope_id=policy["scope_id"], candidate=candidate, now=now,
        ) == "queued"
        await db.commit()
    assert await process_pending_learning_jobs(settings) == 1
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute("SELECT status, error_code FROM gyo_learning_jobs WHERE assistant_turn_id = 'scope-turn-two'") as cur:
            rate_limited = await cur.fetchone()
    assert rate_limited["status"] == "skipped"
    assert rate_limited["error_code"] == "rate_limited"


def test_learning_trailer_is_removed_before_action_proposal_and_invalid_trailer_fails_closed():
    text = (
        "Visible answer.\n"
        'DIRAP_LEARNING_CANDIDATE: {"kind":"memory","plan_step_id":"step-1","memory_kind":"lesson","memory_key":"safe","content":"Review me","confidence":0.7,"sensitivity":"normal"}\n'
        'DIRAP_ACTION_PROPOSAL: {"title":"Update","steps":[{"kind":"work_status_update","input":{"status":"in_progress"}}]}'
    )
    visible, candidate, diagnostic = _extract_learning_candidate(text)
    assert diagnostic == "valid"
    assert candidate is not None and candidate["kind"] == "memory"
    assert "DIRAP_LEARNING_CANDIDATE" not in visible
    assert "DIRAP_ACTION_PROPOSAL" in visible

    visible, candidate, diagnostic = _extract_learning_candidate("Answer\nDIRAP_LEARNING_CANDIDATE: not-json")
    assert candidate is None
    assert diagnostic == "invalid_json"
    assert visible.startswith("Answer")
