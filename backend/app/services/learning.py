"""Governed learning candidate creation for the Workspace Assistant.

This module is deliberately not an autonomous learner.  A caller must submit
explicit identifiers for completed Assistant turns and (optionally) managed
artifacts.  It never reads or persists raw transcripts, activates Memory Hub
records, enables Skills, or changes a Work.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import aiosqlite
from fastapi import HTTPException

from app.api.schemas import (
    CompletedRunEvidence,
    MemoryLearningCandidateCreate,
    SkillCreate,
    SkillLearningCandidateCreate,
)
from app.api.skills import create_draft_skill_candidate
from app.services import memory_hub


@dataclass(frozen=True)
class VerifiedLearningEvidence:
    work_id: str
    task_id: str
    turn_ids: list[str]
    artifact_ids: list[str]
    artifact_hashes: dict[str, str]
    model_id: str | None
    conversation_id: str | None


def _digest_reference(reference: str) -> str:
    return hashlib.sha256(reference.encode("utf-8")).hexdigest()


async def _verified_completed_evidence(
    db: aiosqlite.Connection,
    evidence: CompletedRunEvidence,
) -> VerifiedLearningEvidence:
    """Validate identifier-only evidence against durable, local state."""
    async with db.execute(
        "SELECT id FROM sessions WHERE id = ? AND archived = 0",
        (evidence.work_id,),
    ) as cur:
        if await cur.fetchone() is None:
            raise HTTPException(status_code=409, detail="Learning candidates require an active Work")

    async with db.execute(
        "SELECT id FROM tasks WHERE id = ? AND session_id = ?",
        (evidence.task_id, evidence.work_id),
    ) as cur:
        scoped_entity = await cur.fetchone()
    if scoped_entity is None:
        # New Workspace UI scopes Memory to a visible plan step.  Its opaque
        # scope id remains compatible with the existing governed evidence
        # contract without exposing operational tasks to the user.
        async with db.execute(
            "SELECT id FROM work_memory_scopes WHERE id = ? AND work_id = ?",
            (evidence.task_id, evidence.work_id),
        ) as cur:
            scoped_entity = await cur.fetchone()
    if scoped_entity is None:
        raise HTTPException(status_code=422, detail="Learning evidence task is outside the selected Work")

    placeholders = ",".join("?" for _ in evidence.assistant_turn_ids)
    async with db.execute(
        f"""SELECT id, model_id, conversation_id FROM assistant_turns
            WHERE id IN ({placeholders}) AND work_id = ?
              AND role = 'assistant' AND status = 'completed'""",
        (*evidence.assistant_turn_ids, evidence.work_id),
    ) as cur:
        rows = await cur.fetchall()
    by_id = {row["id"]: row for row in rows}
    missing = [turn_id for turn_id in evidence.assistant_turn_ids if turn_id not in by_id]
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Every learning evidence turn must be a completed Assistant turn in the selected Work",
        )

    artifact_hashes: dict[str, str] = {}
    if evidence.artifact_ids:
        placeholders = ",".join("?" for _ in evidence.artifact_ids)
        async with db.execute(
            f"SELECT id, sha256 FROM artifacts WHERE session_id = ? AND id IN ({placeholders})",
            (evidence.work_id, *evidence.artifact_ids),
        ) as cur:
            artifact_hashes = {row["id"]: row["sha256"] for row in await cur.fetchall()}
        missing_artifacts = [artifact_id for artifact_id in evidence.artifact_ids if artifact_id not in artifact_hashes]
        if missing_artifacts:
            raise HTTPException(status_code=422, detail="Learning evidence artifact is outside the selected Work")

    first = by_id[evidence.assistant_turn_ids[0]]
    return VerifiedLearningEvidence(
        work_id=evidence.work_id,
        task_id=evidence.task_id,
        turn_ids=list(evidence.assistant_turn_ids),
        artifact_ids=list(evidence.artifact_ids),
        artifact_hashes=artifact_hashes,
        model_id=first["model_id"],
        conversation_id=first["conversation_id"],
    )


def _memory_evidence(verified: VerifiedLearningEvidence) -> list[dict[str, str]]:
    # References are durable IDs/hashes only.  Do not put turn text, provider
    # output, raw paths, or request metadata into Memory Hub evidence.
    result = [
        {
            "evidence_type": "assistant_turn",
            "reference": f"assistant_turn:{turn_id}",
            "sha256": _digest_reference(f"assistant_turn:{turn_id}"),
        }
        for turn_id in verified.turn_ids
    ]
    result.extend(
        {
            "evidence_type": "artifact_reference",
            "reference": f"artifact:{artifact_id}",
            "sha256": verified.artifact_hashes[artifact_id],
        }
        for artifact_id in verified.artifact_ids
    )
    return result


async def create_memory_candidate(
    db: aiosqlite.Connection,
    request: MemoryLearningCandidateCreate,
) -> dict[str, Any]:
    """Create exactly one task-scoped Memory Hub proposal, never an active record."""
    verified = await _verified_completed_evidence(db, request.evidence)
    record = await memory_hub._insert_proposal(  # noqa: SLF001 - service boundary owns lifecycle validation
        db,
        "gyo",
        {
            "kind": request.kind,
            "memory_key": request.memory_key,
            "content": request.content,
            "project_id": verified.work_id,
            "task_id": verified.task_id,
            "session_id": verified.work_id,
            "producer_model": verified.model_id,
            "producer_session": verified.conversation_id,
            "source_type": "agent_proposal",
            "source_ref": ",".join(f"assistant_turn:{turn_id}" for turn_id in verified.turn_ids),
            "confidence": request.confidence,
            "sensitivity": request.sensitivity,
            "evidence": _memory_evidence(verified),
        },
        commit=True,
    )
    # Defensive invariant: a future Memory Hub implementation must not turn a
    # learning candidate into an implicit approval.
    if record["lifecycle"] != "proposed":
        raise RuntimeError("Learning candidate unexpectedly bypassed Memory Hub approval")
    return record


async def create_skill_candidate(
    db: aiosqlite.Connection,
    request: SkillLearningCandidateCreate,
):
    """Create a disabled Skill draft from explicit completed-run evidence."""
    verified = await _verified_completed_evidence(db, request.evidence)
    if request.basis == "repeated_success" and len(verified.turn_ids) < 2:
        raise HTTPException(
            status_code=422,
            detail="A repeated-success Skill candidate requires two completed Assistant turns",
        )
    skill = await create_draft_skill_candidate(
        db,
        SkillCreate(
            name=request.name,
            description=request.description,
            content=request.content,
            enabled=False,
            status="draft",
        ),
        actor="gyo",
        provenance={
            "basis": request.basis,
            "work_id": verified.work_id,
            "task_id": verified.task_id,
            "assistant_turn_ids": verified.turn_ids,
            "artifact_ids": verified.artifact_ids,
            "artifact_sha256": [verified.artifact_hashes[item] for item in verified.artifact_ids],
        },
    )
    if skill.status != "draft" or skill.enabled:
        raise RuntimeError("Learning candidate unexpectedly bypassed Skill approval")
    return skill
