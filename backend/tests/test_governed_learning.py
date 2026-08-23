from __future__ import annotations

import json
import time

import pytest

from app.api.schemas import (
    CompletedRunEvidence,
    MemoryLearningCandidateCreate,
    SkillLearningCandidateCreate,
)
from app.db.connection import get_db_connection
from app.services import memory_hub
from app.services.assistant_context import AssistantContextPackBuilder
from app.services.learning import create_memory_candidate, create_skill_candidate


async def _completed_turn_evidence(client, db_path):
    work = (await client.post("/api/sessions", json={"title": "Governed learning Work"})).json()
    conversation = (await client.post(
        f"/api/works/{work['id']}/conversations", json={"title": "Learning conversation"},
    )).json()
    now = int(time.time())
    async with get_db_connection(db_path) as db:
        await db.execute(
            "INSERT INTO tasks (id, session_id, title, status, created_at, updated_at) VALUES (?, ?, ?, 'completed', ?, ?)",
            ("learning-task", work["id"], "Completed task", now, now),
        )
        await db.execute(
            "INSERT INTO assistant_threads (id, title, work_id, conversation_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            ("learning-thread", "Learning thread", work["id"], conversation["id"], now, now),
        )
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at, completed_at)
               VALUES (?, ?, ?, ?, 'assistant', 'completed', 'test-model', ?, ?)""",
            ("learning-turn", "learning-thread", work["id"], conversation["id"], now, now),
        )
        await db.execute(
            "INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("learning-artifact", work["id"], "outputs/evaluation.json", "report", "a" * 64, 10, now),
        )
        await db.commit()
    return work, conversation


@pytest.mark.asyncio
async def test_active_work_memory_is_explicit_scoped_and_manifested(client, migrated_db_path):
    work, _conversation = await _completed_turn_evidence(client, migrated_db_path)
    async with get_db_connection(migrated_db_path) as db:
        proposal = await memory_hub.create_proposal(db, "gyo", {
            "kind": "technical_decision",
            "memory_key": "learning-scope",
            "content": "Use the approved task evidence.",
            "project_id": work["id"],
            "task_id": "learning-task",
            "session_id": work["id"],
            "source_type": "agent_proposal",
            "source_ref": "assistant_turn:learning-turn",
            "evidence": [{"evidence_type": "assistant_turn", "reference": "assistant_turn:learning-turn"}],
        })
        await memory_hub.transition(db, "codex", proposal["id"], "verify")
        await memory_hub.transition(db, "codex", proposal["id"], "activate")
        global_preference = await memory_hub.create_proposal(db, "user", {
            "kind": "preference",
            "memory_key": "language",
            "content": "Never include this automatically.",
            "project_id": None,
            "task_id": None,
            "source_type": "user_input",
            "source_ref": "user",
        })
        await memory_hub.transition(db, "user", global_preference["id"], "verify")
        await memory_hub.transition(db, "user", global_preference["id"], "activate")

        default_pack = await AssistantContextPackBuilder(db).build(work["id"])
        assert proposal["id"] not in [item.get("id") for item in default_pack.included]
        assert any(item["kind"] == "memory_hub" for item in default_pack.excluded)

        scoped_pack = await AssistantContextPackBuilder(db).build(
            work["id"],
            memory_mode="active_work_memory",
            memory_project_id=work["id"],
            memory_task_id="learning-task",
        )
        assert proposal["id"] in [item.get("id") for item in scoped_pack.included]
        assert global_preference["id"] not in [item.get("id") for item in scoped_pack.included]

        missing_scope = await AssistantContextPackBuilder(db).build(
            work["id"], memory_mode="active_work_memory",
        )
        assert any("Cần phạm vi" in item["reason"] for item in missing_scope.excluded if item["kind"] == "memory_hub")


@pytest.mark.asyncio
async def test_learning_candidates_require_completed_evidence_and_remain_governed(client, migrated_db_path):
    work, _conversation = await _completed_turn_evidence(client, migrated_db_path)
    evidence = CompletedRunEvidence(
        work_id=work["id"],
        task_id="learning-task",
        assistant_turn_ids=["learning-turn"],
        artifact_ids=["learning-artifact"],
    )
    async with get_db_connection(migrated_db_path) as db:
        memory = await create_memory_candidate(db, MemoryLearningCandidateCreate(
            evidence=evidence,
            kind="lesson",
            memory_key="safe-learning",
            content="Keep candidate records pending review.",
        ))
        assert memory["lifecycle"] == "proposed"
        assert memory["producer_agent"] == "gyo"
        async with db.execute("SELECT evidence_type, reference FROM memory_hub_evidence WHERE record_id = ?", (memory["id"],)) as cur:
            evidence_rows = await cur.fetchall()
        assert ("assistant_turn", "assistant_turn:learning-turn") in [(row["evidence_type"], row["reference"]) for row in evidence_rows]
        assert ("artifact_reference", "artifact:learning-artifact") in [(row["evidence_type"], row["reference"]) for row in evidence_rows]

        skill = await create_skill_candidate(db, SkillLearningCandidateCreate(
            evidence=evidence,
            basis="user_requested",
            name="Governed learning skill",
            content="Only create a draft after explicit evidence.",
        ))
        assert skill.status == "draft"
        assert skill.enabled is False
        async with db.execute("SELECT payload_json FROM audit_events WHERE target = ?", (skill.id,)) as cur:
            audit_payload = json.loads((await cur.fetchone())[0])
        assert "Only create a draft" not in json.dumps(audit_payload)


@pytest.mark.asyncio
async def test_learning_rejects_incomplete_turn_and_insufficient_repeated_success(client, migrated_db_path):
    work, conversation = await _completed_turn_evidence(client, migrated_db_path)
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, created_at)
               VALUES ('running-turn', 'learning-thread', ?, ?, 'assistant', 'running', ?)""",
            (work["id"], conversation["id"], now),
        )
        await db.commit()
        with pytest.raises(Exception) as incomplete:
            await create_memory_candidate(db, MemoryLearningCandidateCreate(
                evidence=CompletedRunEvidence(work_id=work["id"], task_id="learning-task", assistant_turn_ids=["running-turn"]),
                kind="lesson", memory_key="bad", content="Must fail.",
            ))
        assert getattr(incomplete.value, "status_code", None) == 422

        with pytest.raises(Exception) as repeated:
            await create_skill_candidate(db, SkillLearningCandidateCreate(
                evidence=CompletedRunEvidence(work_id=work["id"], task_id="learning-task", assistant_turn_ids=["learning-turn"]),
                basis="repeated_success", name="Too early", content="Must not create.",
            ))
        assert getattr(repeated.value, "status_code", None) == 422


@pytest.mark.asyncio
async def test_learning_api_creates_only_proposed_memory_and_draft_skill(client, migrated_db_path):
    work, _conversation = await _completed_turn_evidence(client, migrated_db_path)
    evidence = {
        "work_id": work["id"],
        "task_id": "learning-task",
        "assistant_turn_ids": ["learning-turn"],
        "artifact_ids": ["learning-artifact"],
    }
    memory = await client.post("/api/gyo/learning/memory-candidates", json={
        "evidence": evidence,
        "kind": "lesson",
        "memory_key": "api-governed-learning",
        "content": "Create only a proposed record.",
    })
    assert memory.status_code == 201, memory.text
    assert memory.json()["lifecycle"] == "proposed"

    skill = await client.post("/api/gyo/learning/skill-candidates", json={
        "evidence": evidence,
        "basis": "user_requested",
        "name": "API governed learning skill",
        "content": "Create only a disabled draft.",
    })
    assert skill.status_code == 201, skill.text
    assert skill.json()["status"] == "draft"
    assert skill.json()["enabled"] is False
