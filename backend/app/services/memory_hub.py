"""Policy and persistence service for the Personal Memory Hub."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Iterable

import aiosqlite
from fastapi import HTTPException

from app.services.audit import log_audit_event

# GYO is the Workspace assistant identity.  It is governed exactly like the
# existing agents: task scope is mandatory and it never inherits a global
# preference or restricted record.
AGENT_ROLES = {"hermes", "gyo", "opencode", "antigravity"}
ALL_ROLES = AGENT_ROLES | {"codex", "user"}
KINDS = {"preference", "project_context", "task_continuity", "workflow_rule", "technical_decision", "lesson"}
SENSITIVITIES = {"normal", "sensitive", "restricted"}
SOURCE_TYPES = {"user_input", "agent_proposal", "legacy_memory_entries", "artifact_reference"}
ARTIFACT_EVIDENCE_TYPES = {"artifact_reference", "legacy_memory_entry"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def now() -> int:
    return int(time.time())


def _record(row: aiosqlite.Row | tuple[Any, ...]) -> dict[str, Any]:
    columns = [
        "id", "kind", "memory_key", "content", "project_id", "task_id", "session_id",
        "producer_agent", "producer_model", "producer_session", "source_type", "source_ref",
        "source_sha256", "content_sha256", "source_artifact_sha256", "confidence", "sensitivity",
        "lifecycle", "version", "supersedes_id", "verified_by", "verified_at", "activated_by",
        "activated_at", "created_at", "updated_at",
    ]
    return dict(zip(columns, row))


RECORD_SELECT = """id, kind, memory_key, content, project_id, task_id, session_id,
producer_agent, producer_model, producer_session, source_type, source_ref, source_sha256,
content_sha256, source_artifact_sha256, confidence, sensitivity, lifecycle, version,
supersedes_id, verified_by, verified_at, activated_by, activated_at, created_at, updated_at"""


def _require(condition: bool, detail: str, status_code: int = 403) -> None:
    if not condition:
        raise HTTPException(status_code=status_code, detail=detail)


def _validate_sha256(value: str | None, label: str) -> None:
    if value is None or not SHA256_RE.fullmatch(value):
        raise HTTPException(status_code=422, detail=f"{label} must be a lowercase SHA-256 hex digest")


def _validate_scope(actor: str, kind: str, project_id: str | None, task_id: str | None) -> None:
    _require(not task_id or project_id is not None, "task_id requires project_id", 422)
    if actor in AGENT_ROLES:
        _require(bool(project_id and task_id), "Agents require task-scoped memory", 422)
    if project_id is None:
        _require(kind == "preference" and actor == "user", "Global scope is reserved for user preferences", 422)


def _validate_evidence(evidence: dict[str, Any]) -> tuple[str, str, str]:
    evidence_type = evidence["evidence_type"].strip()
    reference = evidence["reference"].strip()
    supplied_hash = evidence.get("sha256")
    _require(bool(evidence_type and reference), "Evidence type and reference are required", 422)
    if evidence_type in ARTIFACT_EVIDENCE_TYPES:
        _validate_sha256(supplied_hash, "Evidence sha256")
        return evidence_type, reference, supplied_hash
    if supplied_hash is not None:
        _validate_sha256(supplied_hash, "Evidence sha256")
        return evidence_type, reference, supplied_hash
    # Non-artifact evidence is a review/user statement. Its digest describes
    # the statement only and is never represented as a source artifact hash.
    return evidence_type, reference, content_hash(reference)


async def _load_record(db: aiosqlite.Connection, record_id: str) -> dict[str, Any]:
    async with db.execute(f"SELECT {RECORD_SELECT} FROM memory_hub_records WHERE id = ?", (record_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Memory Hub record not found")
    return _record(row)


async def _insert_proposal(
    db: aiosqlite.Connection, actor: str, data: dict[str, Any], *, commit: bool
) -> dict[str, Any]:
    _require(actor in ALL_ROLES, "Unknown Memory Hub role")
    kind = data["kind"]
    sensitivity = data.get("sensitivity", "normal")
    source_type = data.get("source_type", "agent_proposal")
    if kind not in KINDS or sensitivity not in SENSITIVITIES or source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid kind, sensitivity, or source_type")
    content = data["content"].strip()
    if not content or len(content.encode("utf-8")) > 8192:
        raise HTTPException(status_code=422, detail="content must be 1..8192 UTF-8 bytes")
    if source_type == "user_input":
        _require(actor == "user", "Only user may create user_input memory", 422)
    _validate_scope(actor, kind, data.get("project_id"), data.get("task_id"))
    artifact_hash = data.get("source_artifact_sha256")
    if source_type in {"artifact_reference", "legacy_memory_entries"}:
        _validate_sha256(artifact_hash, "source_artifact_sha256")
    elif artifact_hash is not None:
        _validate_sha256(artifact_hash, "source_artifact_sha256")

    record_id, created = f"mhub-{uuid.uuid4().hex}", now()
    digest = content_hash(content)
    await db.execute(
        """INSERT INTO memory_hub_records (
            id, kind, memory_key, content, project_id, task_id, session_id, producer_agent,
            producer_model, producer_session, source_type, source_ref, source_sha256,
            content_sha256, source_artifact_sha256, confidence, sensitivity, lifecycle,
            version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', 1, ?, ?)""",
        (record_id, kind, data["memory_key"].strip(), content, data.get("project_id"), data.get("task_id"),
         data.get("session_id"), actor, data.get("producer_model"), data.get("producer_session"),
         source_type, data.get("source_ref"), digest, digest, artifact_hash,
         float(data.get("confidence", 0.5)), sensitivity, created, created),
    )
    for raw_evidence in data.get("evidence", []):
        evidence_type, reference, digest = _validate_evidence(raw_evidence)
        await db.execute(
            "INSERT INTO memory_hub_evidence (id, record_id, evidence_type, reference, sha256, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"mhubev-{uuid.uuid4().hex}", record_id, evidence_type, reference, digest, actor, created),
        )
    await log_audit_event(
        db, data.get("session_id"), actor, "memory_hub.proposed", record_id,
        {"kind": kind, "sensitivity": sensitivity, "project_id": data.get("project_id"), "task_id": data.get("task_id")},
        commit=False,
    )
    if commit:
        await db.commit()
    return await _load_record(db, record_id)


async def create_proposal(db: aiosqlite.Connection, actor: str, data: dict[str, Any]) -> dict[str, Any]:
    return await _insert_proposal(db, actor, data, commit=True)


async def get_record(
    db: aiosqlite.Connection, actor: str, record_id: str, *, project_id: str | None = None, task_id: str | None = None
) -> dict[str, Any]:
    record = await _load_record(db, record_id)
    if record["sensitivity"] == "restricted" and actor in AGENT_ROLES:
        raise HTTPException(status_code=403, detail="Restricted memory is not available to agents")
    if actor in AGENT_ROLES:
        _validate_scope(actor, record["kind"], project_id, task_id)
        _require(record["project_id"] == project_id and record["task_id"] == task_id, "Record is outside the requested scope")
    return record


async def transition(db: aiosqlite.Connection, actor: str, record_id: str, action: str, note: str | None = None) -> dict[str, Any]:
    record = await _load_record(db, record_id)
    lifecycle, timestamp = record["lifecycle"], now()
    if action == "verify":
        allowed = (actor == "user" and record["kind"] == "preference") or (
            actor == "codex" and record["kind"] != "preference" and record["sensitivity"] in {"normal", "sensitive"}
        )
        _require(allowed, "Role may not verify this Memory Hub record")
        if lifecycle != "proposed":
            raise HTTPException(status_code=409, detail="Only proposed records can be verified")
        await db.execute("UPDATE memory_hub_records SET lifecycle='verified', verified_by=?, verified_at=?, updated_at=? WHERE id=?", (actor, timestamp, timestamp, record_id))
    elif action == "activate":
        if lifecycle != "verified":
            raise HTTPException(status_code=409, detail="Only verified records can be activated")
        allowed = (actor == "user" and record["kind"] == "preference") or (
            actor == "codex" and record["kind"] != "preference" and record["sensitivity"] in {"normal", "sensitive"}
        )
        _require(allowed, "Role may not activate this Memory Hub record")
        async with db.execute(
            """SELECT id, version FROM memory_hub_records
               WHERE memory_key=? AND kind=? AND project_id IS ? AND task_id IS ? AND lifecycle='active'
               ORDER BY version DESC LIMIT 1""",
            (record["memory_key"], record["kind"], record["project_id"], record["task_id"]),
        ) as cur:
            previous = await cur.fetchone()
        version, supersedes_id = 1, None
        if previous:
            supersedes_id, version = previous[0], previous[1] + 1
            await db.execute("UPDATE memory_hub_records SET lifecycle='superseded', updated_at=? WHERE id=?", (timestamp, supersedes_id))
        await db.execute("UPDATE memory_hub_records SET lifecycle='active', version=?, supersedes_id=?, activated_by=?, activated_at=?, updated_at=? WHERE id=?", (version, supersedes_id, actor, timestamp, timestamp, record_id))
    elif action == "reject":
        allowed = actor == "codex" or (actor == "user" and record["kind"] == "preference")
        _require(allowed, "Role may not reject this Memory Hub record")
        if lifecycle not in {"proposed", "verified"}:
            raise HTTPException(status_code=409, detail="Only proposed or verified records can be rejected")
        await db.execute("UPDATE memory_hub_records SET lifecycle='rejected', updated_at=? WHERE id=?", (timestamp, record_id))
    else:
        raise HTTPException(status_code=400, detail="Unknown Memory Hub lifecycle action")
    await log_audit_event(db, record["session_id"], actor, f"memory_hub.{action}", record_id, {"note": note} if note else {}, commit=False)
    await db.commit()
    return await _load_record(db, record_id)


async def search(
    db: aiosqlite.Connection, actor: str, *, query: str | None = None, project_id: str | None = None,
    task_id: str | None = None, lifecycle: str | None = "active", sensitivity: str | None = None,
    include_global_preferences: bool = False, limit: int = 20,
) -> list[dict[str, Any]]:
    if actor in AGENT_ROLES:
        _validate_scope(actor, "technical_decision", project_id, task_id)
        _require(not include_global_preferences, "Agents may not inherit global preferences", 422)
    elif not project_id and not include_global_preferences:
        raise HTTPException(status_code=422, detail="An explicit scope or include_global_preferences is required")
    _require(not task_id or project_id is not None, "task_id requires project_id", 422)
    if actor in AGENT_ROLES and sensitivity == "restricted":
        raise HTTPException(status_code=403, detail="Restricted memory is not available to agents")
    clauses, values = [], []
    if query:
        clauses.append("r.rowid IN (SELECT rowid FROM memory_hub_fts WHERE memory_hub_fts MATCH ?)")
        values.append('"' + query.replace('"', '""') + '"')
    if project_id:
        if include_global_preferences:
            clauses.append("(r.project_id = ? OR (r.project_id IS NULL AND r.task_id IS NULL AND r.kind = 'preference'))")
        else:
            clauses.append("r.project_id = ?")
        values.append(project_id)
    elif include_global_preferences:
        clauses.append("r.project_id IS NULL AND r.task_id IS NULL AND r.kind = 'preference'")
    if task_id:
        clauses.append("r.task_id = ?"); values.append(task_id)
    permitted_lifecycles = {"active", "proposed", "verified"}
    if lifecycle and lifecycle not in permitted_lifecycles:
        raise HTTPException(status_code=422, detail="Search lifecycle must be active, proposed, or verified")
    if lifecycle in {"proposed", "verified"} and actor not in {"codex", "user"}:
        raise HTTPException(status_code=403, detail="Only Codex or user may search non-active memory")
    if lifecycle:
        clauses.append("r.lifecycle = ?"); values.append(lifecycle)
    else:
        clauses.append("r.lifecycle IN ('active', 'proposed', 'verified')")
    if sensitivity:
        _require(sensitivity in SENSITIVITIES, "Invalid sensitivity", 422)
        clauses.append("r.sensitivity = ?"); values.append(sensitivity)
    if actor in AGENT_ROLES:
        clauses.append("r.sensitivity != 'restricted'")
    where = " WHERE " + " AND ".join(clauses)
    sql = f"SELECT {RECORD_SELECT} FROM memory_hub_records r" + where + " ORDER BY r.updated_at DESC LIMIT ?"
    values.append(min(max(limit, 1), 100))
    async with db.execute(sql, values) as cur:
        return [_record(row) async for row in cur]


async def context_pack(db: aiosqlite.Connection, actor: str, project_id: str | None, task_id: str | None) -> dict[str, Any]:
    if actor in AGENT_ROLES:
        _validate_scope(actor, "technical_decision", project_id, task_id)
    elif not project_id:
        raise HTTPException(status_code=422, detail="Context packs require an explicit non-global scope")
    rows = await search(db, actor, project_id=project_id, task_id=task_id, lifecycle="active", limit=20)
    included = []
    for row in rows:
        if row["sensitivity"] == "restricted" and actor != "user":
            continue
        item = {key: row[key] for key in ("id", "kind", "memory_key", "content", "project_id", "task_id", "sensitivity", "version")}
        candidate = [*included, item]
        if len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > 8192:
            continue
        included = candidate
    used = len(json.dumps(included, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return {"project_id": project_id, "task_id": task_id, "records": included, "record_count": len(included), "bytes": used}


async def preview_legacy(db: aiosqlite.Connection, actor: str, ids: Iterable[str]) -> list[dict[str, Any]]:
    _require(actor in {"codex", "user"}, "Only Codex or user may preview legacy memory")
    selected = list(dict.fromkeys(ids))
    if not selected:
        return []
    placeholders = ",".join("?" for _ in selected)
    async with db.execute(f"SELECT id, key, value, kind, importance_score, session_id FROM memory_entries WHERE id IN ({placeholders})", selected) as cur:
        return [{"legacy_memory_id": row[0], "memory_key": row[1], "content": row[2], "kind": row[3], "confidence": min(1.0, max(0.0, float(row[4] or 0) / 10)), "session_id": row[5], "content_sha256": content_hash(row[2])} async for row in cur]


async def import_legacy(
    db: aiosqlite.Connection, actor: str, ids: Iterable[str], *, project_id: str | None, task_id: str | None
) -> list[dict[str, Any]]:
    _require(actor in {"codex", "user"}, "Only Codex or user may import legacy proposals")
    imported: list[dict[str, Any]] = []
    await db.execute("BEGIN IMMEDIATE")
    try:
        for item in await preview_legacy(db, actor, ids):
            async with db.execute("SELECT record_id FROM memory_hub_imports WHERE legacy_memory_id=? AND content_sha256=?", (item["legacy_memory_id"], item["content_sha256"])) as cur:
                existing = await cur.fetchone()
            if existing:
                imported.append(await _load_record(db, existing[0]))
                continue
            kind = item["kind"] if item["kind"] in KINDS else "project_context"
            _validate_scope(actor, kind, project_id, task_id)
            record = await _insert_proposal(db, actor, {
                "kind": kind, "memory_key": item["memory_key"], "content": item["content"],
                "project_id": project_id, "task_id": task_id, "session_id": item["session_id"],
                "source_type": "legacy_memory_entries", "source_ref": item["legacy_memory_id"],
                "source_artifact_sha256": item["content_sha256"], "confidence": item["confidence"],
                "evidence": [{"evidence_type": "legacy_memory_entry", "reference": item["legacy_memory_id"], "sha256": item["content_sha256"]}],
            }, commit=False)
            await db.execute("INSERT INTO memory_hub_imports (legacy_memory_id, content_sha256, record_id, imported_at) VALUES (?, ?, ?, ?)", (item["legacy_memory_id"], item["content_sha256"], record["id"], now()))
            imported.append(record)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return imported
