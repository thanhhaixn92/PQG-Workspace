"""API for immutable, Work-scoped action packages."""
from __future__ import annotations

import json
import hashlib
import time
import uuid
from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.api.schemas import (
    ActionPackageApproveRequest,
    ActionPackageDecisionRequest,
    ActionPackageCreateRequest,
    ActionPackagePreflightRequest,
    ActionPackagePreflightResponse,
    ActionPackageResponse,
    ActionPackageReviseRequest,
    ActionStepResponse,
)
from app.dependencies import get_db, get_trusted_actor
from app.services.action_packages import (
    ACTION_RISKS,
    APPROVAL_TTL_SECONDS,
    DTO_VERSION,
    P0_EXECUTION_BUDGETS,
    P0_INTERNAL_CAPABILITIES,
    build_resolved_payload,
    canonical_package_hash,
    canonical_payload_hash,
    resolve_preflight,
)
from app.services.audit import log_audit_event
from app.services.sandbox import get_workspace_path, resolve_and_validate_path
from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository

router = APIRouter(prefix="/api", tags=["action-packages"])


async def _validated_steps(
    conn: aiosqlite.Connection,
    work_id: str,
    request: ActionPackageCreateRequest,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for step in request.steps:
        data = step.input
        if step.kind == "work_plan_step_update":
            if set(data) != {"step_id", "changes"} or not isinstance(data.get("changes"), dict):
                raise HTTPException(status_code=422, detail="Invalid plan-step proposal input")
            step_id = data.get("step_id")
            changes = data["changes"]
            allowed = {"title", "description", "result", "status"}
            if not isinstance(step_id, str) or not step_id or not changes or not set(changes).issubset(allowed):
                raise HTTPException(status_code=422, detail="Invalid plan-step proposal input")
            if "status" in changes and changes["status"] not in {"not_started", "in_progress", "blocked", "completed"}:
                raise HTTPException(status_code=422, detail="Unsupported plan-step status")
            async with conn.execute(
                "SELECT 1 FROM work_plan_steps WHERE id = ? AND session_id = ?", (step_id, work_id)
            ) as cur:
                if await cur.fetchone() is None:
                    raise HTTPException(status_code=422, detail="Plan step is not part of selected Work")
        elif step.kind == "work_status_update":
            if set(data) != {"work_status", "progress_percent"}:
                raise HTTPException(status_code=422, detail="Invalid Work-status proposal input")
            if data.get("work_status") not in {"not_started", "in_progress", "paused"}:
                raise HTTPException(status_code=422, detail="Unsupported Work status")
            progress = data.get("progress_percent")
            if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100:
                raise HTTPException(status_code=422, detail="Progress must be an integer from 0 to 100")
        normalized.append({"kind": step.kind, "input": data})
    return normalized


async def _package(conn: aiosqlite.Connection, package_id: str) -> aiosqlite.Row:
    async with conn.execute("SELECT * FROM action_packages WHERE id = ?", (package_id,)) as cur:
        row = await cur.fetchone()
    if row is None: raise HTTPException(status_code=404, detail="Action package not found")
    return row


async def _proposal_turn_id(
    conn: aiosqlite.Connection,
    *,
    part_id: str | None,
    work_id: str,
    conversation_id: str | None,
) -> str | None:
    if not part_id:
        return None
    async with conn.execute(
        """SELECT part.turn_id, turn.work_id, turn.conversation_id
           FROM assistant_turn_parts part
           JOIN assistant_turns turn ON turn.id = part.turn_id
           WHERE part.id = ? AND part.part_type = 'action_proposal' AND turn.role = 'assistant'""",
        (part_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Source proposal part is unavailable")
    if row["work_id"] != work_id or row["conversation_id"] != conversation_id:
        raise HTTPException(status_code=422, detail="Source proposal part is outside the selected Work or conversation")
    return row["turn_id"]


async def _validated_artifact_snapshots(
    conn: aiosqlite.Connection, work_id: str, artifact_ids: list[str]
) -> list[dict[str, str]]:
    """Resolve only structurally validated, immutable artifact references."""
    if len(set(artifact_ids)) != len(artifact_ids):
        raise HTTPException(status_code=422, detail="Artifact ids must be unique")
    if not artifact_ids:
        return []
    placeholders = ", ".join("?" for _ in artifact_ids)
    async with conn.execute(
        f"""SELECT artifact.id, artifact.relative_path, artifact.sha256,
                   COALESCE(validation.status, 'pending') AS validation_status
            FROM artifacts artifact LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
            WHERE artifact.session_id = ? AND artifact.id IN ({placeholders})""",
        (work_id, *artifact_ids),
    ) as cur:
        rows = {row["id"]: row for row in await cur.fetchall()}
    if len(rows) != len(artifact_ids):
        raise HTTPException(status_code=422, detail="An artifact is outside the selected Work")
    workspace = await get_workspace_path(work_id, conn)
    snapshots: list[dict[str, str]] = []
    for artifact_id in artifact_ids:
        row = rows[artifact_id]
        if row["validation_status"] != "structurally_validated":
            raise HTTPException(status_code=422, detail="Artifact is not structurally validated")
        target = resolve_and_validate_path(workspace, row["relative_path"], max_size=10 * 1024 * 1024)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise HTTPException(status_code=409, detail="Artifact changed since validation")
        snapshots.append({"artifact_id": artifact_id, "sha256": digest, "relative_path": row["relative_path"]})
    return snapshots


async def _response(conn: aiosqlite.Connection, row: aiosqlite.Row) -> ActionPackageResponse:
    async with conn.execute("SELECT * FROM action_steps WHERE package_id = ? ORDER BY sort_order", (row["id"],)) as cur:
        steps = await cur.fetchall()
    return ActionPackageResponse(
        id=row["id"], session_id=row["session_id"], conversation_id=row["conversation_id"], title=row["title"], description=row["description"],
        package_hash=row["package_hash"], status=row["status"], approved_hash=row["approved_hash"], approved_at=row["approved_at"],
        attempt_count=row["attempt_count"], created_at=row["created_at"], updated_at=row["updated_at"],
        steps=[ActionStepResponse(
            id=step["id"], sort_order=step["sort_order"], kind=step["kind"], risk_level=step["risk_level"],
            input=json.loads(step["input_json"]), status=step["status"],
            output=json.loads(step["output_json"]) if step["output_json"] else None, error=step["error"],
            capability=step["capability"], expected_version=json.loads(step["expected_version_json"]) if step["expected_version_json"] else None,
            postcondition=json.loads(step["postcondition_json"]) if step["postcondition_json"] else None,
        ) for step in steps],
        revision=row["revision"], approved_revision=row["approved_revision"], created_by=row["created_by"], dto_version=row["dto_version"],
        capabilities=json.loads(row["capabilities_json"]) if row["capabilities_json"] else [],
        schema_version=row["schema_version"], payload_hash=row["payload_hash"],
        approved_payload_hash=row["approved_payload_hash"], expires_at=row["expires_at"],
        approval_ttl_seconds=row["approval_ttl_seconds"],
        snapshot=json.loads(row["snapshot_json"]) if row["snapshot_json"] else {},
        preconditions=json.loads(row["preconditions_json"]) if row["preconditions_json"] else [],
        budget=json.loads(row["budget_json"]) if row["budget_json"] else {},
        resolved_payload=json.loads(row["resolved_payload_json"]) if row["resolved_payload_json"] else {},
    )


@router.get("/works/{work_id}/action-packages", response_model=list[ActionPackageResponse])
async def list_work_action_packages(work_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> list[ActionPackageResponse]:
    async with conn.execute("SELECT 1 FROM sessions WHERE id = ?", (work_id,)) as cur:
        if await cur.fetchone() is None: raise HTTPException(status_code=404, detail="Work not found")
    async with conn.execute("SELECT * FROM action_packages WHERE session_id = ? ORDER BY created_at DESC", (work_id,)) as cur:
        rows = await cur.fetchall()
    return [await _response(conn, row) for row in rows]


@router.get("/action-packages/{package_id}", response_model=ActionPackageResponse)
async def get_action_package(package_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> ActionPackageResponse:
    """Canonical package state for confirmation and execution rendering."""
    return await _response(conn, await _package(conn, package_id))


@router.get("/action-packages/{package_id}/preflight", response_model=ActionPackagePreflightResponse)
async def get_canonical_action_package_preflight(
    package_id: str,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackagePreflightResponse:
    """Re-resolve the exact persisted package immediately before confirmation.

    The response is deliberately derived from the stored immutable actions and
    their current server-side targets. A stale input, target version, archived
    Work, expired package or missing binding fails closed with 409 rather than
    letting a browser reuse an old proposal preview.
    """
    package = await _package(conn, package_id)
    if package["created_by"] != actor:
        raise HTTPException(status_code=403, detail="Only the package creator may inspect this confirmation")
    if package["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="This action package is no longer awaiting confirmation")
    now = int(time.time())
    if package["expires_at"] is not None and package["expires_at"] <= now:
        raise HTTPException(status_code=409, detail="Action package has expired")
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (package["session_id"],)) as cur:
        work = await cur.fetchone()
    if work is None or work["archived"]:
        raise HTTPException(status_code=409, detail="Work is archived")
    async with conn.execute(
        "SELECT kind, input_json, expected_version_json FROM action_steps WHERE package_id = ? ORDER BY sort_order",
        (package_id,),
    ) as cur:
        step_rows = await cur.fetchall()
    try:
        steps = [{"kind": row["kind"], "input": json.loads(row["input_json"])} for row in step_rows]
        report = await resolve_preflight(conn, package["session_id"], steps)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail="Action package payload is no longer valid") from exc
    stored_versions = [
        json.loads(row["expected_version_json"]) if row["expected_version_json"] else None
        for row in step_rows
    ]
    if report["expected_versions"] != stored_versions:
        raise HTTPException(status_code=409, detail="Work data changed; review the action package again")
    payload = json.loads(package["resolved_payload_json"] or "{}")
    context = payload.get("context_snapshot", {}) if isinstance(payload, dict) else {}
    sources = context.get("sources", []) if isinstance(context, dict) else []
    artifact_ids = [item["artifact_id"] for item in sources if isinstance(item, dict) and isinstance(item.get("artifact_id"), str)]
    snapshots = await _validated_artifact_snapshots(conn, package["session_id"], artifact_ids)
    stored_preconditions = json.loads(package["preconditions_json"] or "[]")
    current_preconditions = report["preconditions"] + [{"type": "artifact_hash", **item} for item in snapshots]
    if stored_preconditions != current_preconditions:
        raise HTTPException(status_code=409, detail="Action package inputs changed; review the action package again")
    return ActionPackagePreflightResponse(
        title=package["title"], package_hash=package["package_hash"],
        targets=report["targets"], preconditions=current_preconditions, diffs=report["diffs"],
        snapshot={**report["snapshot"], "artifacts": snapshots},
        capabilities=json.loads(package["capabilities_json"] or "[]"), valid=True,
        package_id=package_id, revision=package["revision"], payload_hash=package["payload_hash"],
        expires_at=package["expires_at"],
    )


@router.post("/works/{work_id}/action-packages/preflight", response_model=ActionPackagePreflightResponse)
async def preflight_action_package(
    work_id: str,
    request: ActionPackagePreflightRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackagePreflightResponse:
    """Resolve canonical targets/diff/preconditions without persisting anything.

    This is the backend preflight the GYO v3 slice uses to show the user exactly
    what a proposed package would change before it becomes an immutable payload.
    """
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (work_id,)) as cur:
        work = await cur.fetchone()
    if work is None: raise HTTPException(status_code=404, detail="Work not found")
    if work[0]: raise HTTPException(status_code=409, detail="Work is archived")
    errors: list[str] = []
    capabilities: list[str] = []
    report: dict[str, Any] | None = None
    try:
        normalized_steps = await _validated_steps(conn, work_id, request)
        for item in normalized_steps:
            if item["kind"] not in P0_INTERNAL_CAPABILITIES:
                errors.append(f"Capability '{item['kind']}' is not permitted by the P0 internal allow-list")
            capabilities.append(item["kind"])
        if len(normalized_steps) > P0_EXECUTION_BUDGETS["max_steps"]:
            errors.append("Package exceeds the P0 step budget")
        if not errors:
            report = await resolve_preflight(conn, work_id, normalized_steps)
    except HTTPException:
        raise
    except Exception as exc:  # validation-style failure from preflight resolution
        errors.append(str(exc))
    if report is None:
        return ActionPackagePreflightResponse(
            title=request.title, package_hash="", targets=[], preconditions=[], diffs=[],
            snapshot={}, capabilities=capabilities, valid=False, errors=errors,
        )
    artifact_snapshots = await _validated_artifact_snapshots(conn, work_id, request.artifact_ids)
    report["snapshot"]["artifacts"] = artifact_snapshots
    report["preconditions"].extend({"type": "artifact_hash", **snapshot} for snapshot in artifact_snapshots)
    package_hash = canonical_package_hash(request.title, request.description, normalized_steps)
    return ActionPackagePreflightResponse(
        title=request.title, package_hash=package_hash,
        targets=report["targets"], preconditions=report["preconditions"], diffs=report["diffs"],
        snapshot=report["snapshot"], capabilities=capabilities, valid=not errors, errors=errors,
    )


@router.post("/action-packages/{package_id}/revise", response_model=ActionPackageResponse)
async def revise_action_package(
    package_id: str,
    request: ActionPackageReviseRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackageResponse:
    """Creator-only re-authorisation: bump the immutable revision and re-approve.

    Only the package creator may revise.  A revised package resets to
    ``awaiting_approval`` with a new ``revision`` and a cleared approval; the
    executor refuses to run a package whose ``approved_revision`` no longer
    matches its current ``revision`` until it is re-approved.
    """
    package = await _package(conn, package_id)
    if package["created_by"] != actor:
        raise HTTPException(status_code=403, detail="Only the package creator may revise this package")
    if package["status"] not in {"awaiting_approval", "approved", "blocked", "partially_failed", "failed"}:
        raise HTTPException(status_code=409, detail="This action package can no longer be revised")
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (package["session_id"],)) as cur:
        work = await cur.fetchone()
    if work is None or work[0]:
        raise HTTPException(status_code=409, detail="Work is archived")

    title = request.title if request.title is not None else package["title"]
    description = request.description if request.description is not None else package["description"]
    if request.steps is not None:
        fake_request = ActionPackageCreateRequest(
            title=title, description=description, conversation_id=package["conversation_id"],
            source_proposal_part_id=None, steps=request.steps,
        )
        normalized_steps = await _validated_steps(conn, package["session_id"], fake_request)
        for item in normalized_steps:
            if item["kind"] not in P0_INTERNAL_CAPABILITIES:
                raise HTTPException(status_code=422, detail=f"Capability '{item['kind']}' is not permitted by the P0 internal allow-list")
        if len(normalized_steps) > P0_EXECUTION_BUDGETS["max_steps"]:
            raise HTTPException(status_code=422, detail="Package exceeds the P0 step budget")
    else:
        normalized_steps = None

    existing_payload = json.loads(package["resolved_payload_json"]) if package["resolved_payload_json"] else {}
    existing_sources = existing_payload.get("context_snapshot", {}).get("sources", []) if isinstance(existing_payload, dict) else []
    existing_artifact_ids = [item.get("artifact_id") for item in existing_sources if isinstance(item, dict) and isinstance(item.get("artifact_id"), str)]
    existing_sources = await _validated_artifact_snapshots(conn, package["session_id"], existing_artifact_ids)
    preflight = await resolve_preflight(conn, package["session_id"], normalized_steps) if normalized_steps else None
    package_hash = canonical_package_hash(title, description, normalized_steps) if normalized_steps else package["package_hash"]
    request_hash = hashlib.sha256(json.dumps({
        "package_id": package_id, "title": title, "description": description,
        "package_hash": package_hash, "revision": package["revision"] + 1,
    }, sort_keys=True).encode("utf-8")).hexdigest()

    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor=actor, operation="action_package.revise", scope=package["session_id"],
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed" and claim["resource_id"]:
            return await _response(conn, await _package(conn, package_id))
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Revision request is still processing")
        raise HTTPException(status_code=409, detail="Previous request failed; use a new Idempotency-Key")

    now = int(time.time())
    new_revision = package["revision"] + 1
    if normalized_steps is not None:
        payload = build_resolved_payload(
            title=title, description=description,
            normalized_steps=normalized_steps,
            snapshot=preflight["snapshot"] if preflight else {},
            preconditions=preflight["preconditions"] if preflight else [],
            created_at=now, revision=new_revision, context_sources=existing_sources,
        )
        payload_hash_value = canonical_payload_hash(payload)
        expires_at = now + APPROVAL_TTL_SECONDS
    else:
        payload = None
        payload_hash_value = None
        expires_at = None
    try:
        if normalized_steps is not None:
            await conn.execute(
                """UPDATE action_packages
                   SET title = ?, description = ?, package_hash = ?, status = 'awaiting_approval',
                       approved_hash = NULL, approved_payload_hash = NULL,
                       approved_revision = NULL, approved_at = NULL, approved_by = NULL,
                       revision = ?, updated_at = ?, snapshot_json = ?, preconditions_json = ?, capabilities_json = ?,
                       resolved_payload_json = ?, payload_hash = ?, expires_at = ?, approval_ttl_seconds = ?
                   WHERE id = ? AND created_by = ? AND revision = ?""",
                (title, description, package_hash, new_revision, now,
                 json.dumps(preflight["snapshot"]) if preflight else package["snapshot_json"],
                 json.dumps(preflight["preconditions"]) if preflight else package["preconditions_json"],
                 json.dumps([item["kind"] for item in normalized_steps]),
                 json.dumps(payload), payload_hash_value, expires_at, APPROVAL_TTL_SECONDS,
                 package_id, actor, package["revision"]),
            )
        else:
            await conn.execute(
                """UPDATE action_packages
                   SET title = ?, description = ?, package_hash = ?, status = 'awaiting_approval',
                       approved_hash = NULL, approved_payload_hash = NULL,
                       approved_revision = NULL, approved_at = NULL, approved_by = NULL,
                       revision = ?, updated_at = ?
                   WHERE id = ? AND created_by = ? AND revision = ?""",
                (title, description, package_hash, new_revision, now, package_id, actor, package["revision"]),
            )
        async with conn.execute("SELECT changes()") as cur:
            if (await cur.fetchone())[0] != 1:
                raise HTTPException(status_code=409, detail="Action package changed; reload before revising")
        if normalized_steps is not None:
            await conn.execute("DELETE FROM action_attempts WHERE package_id = ?", (package_id,))
            await conn.execute("DELETE FROM action_execution_events WHERE package_id = ?", (package_id,))
            await conn.execute("DELETE FROM action_steps WHERE package_id = ?", (package_id,))
            for index, item in enumerate(normalized_steps):
                expected_version = preflight["expected_versions"][index]
                await conn.execute(
                    """INSERT INTO action_steps
                       (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at, expected_version_json, capability)
                       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), package_id, index, item["kind"], ACTION_RISKS[item["kind"]],
                     json.dumps(item["input"], sort_keys=True), now, now, json.dumps(expected_version) if expected_version else None, item["kind"]),
                )
        await log_audit_event(conn, package["session_id"], actor, "action_package.revised", package_id, {"revision": new_revision, "package_hash": package_hash}, commit=False)
        await conn.commit()
        revised = await _response(conn, await _package(conn, package_id))
        await repo.finalize_operation(claim, response=revised.model_dump(), status_code=status.HTTP_200_OK, resource_id=package_id)
        return revised
    except Exception:
        await conn.rollback()
        await repo.fail_operation(claim, "action_package_revise_failed")
        raise


@router.post("/works/{work_id}/action-packages", response_model=ActionPackageResponse, status_code=status.HTTP_201_CREATED)
async def create_action_package(
    work_id: str,
    request: ActionPackageCreateRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    http_response: Response,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackageResponse:
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (work_id,)) as cur:
        work = await cur.fetchone()
    if work is None: raise HTTPException(status_code=404, detail="Work not found")
    if work[0]: raise HTTPException(status_code=409, detail="Work is archived")
    if request.conversation_id:
        async with conn.execute("SELECT 1 FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'", (request.conversation_id, work_id)) as cur:
            if await cur.fetchone() is None: raise HTTPException(status_code=404, detail="Conversation not found in this Work")
    proposal_turn_id = await _proposal_turn_id(
        conn,
        part_id=request.source_proposal_part_id,
        work_id=work_id,
        conversation_id=request.conversation_id,
    )
    normalized_steps = await _validated_steps(conn, work_id, request)
    for item in normalized_steps:
        if item["kind"] not in P0_INTERNAL_CAPABILITIES:
            raise HTTPException(status_code=422, detail=f"Capability '{item['kind']}' is not permitted by the P0 internal allow-list")
    if len(normalized_steps) > P0_EXECUTION_BUDGETS["max_steps"]:
        raise HTTPException(status_code=422, detail="Package exceeds the P0 step budget")
    preflight = await resolve_preflight(conn, work_id, normalized_steps)
    artifact_snapshots = await _validated_artifact_snapshots(conn, work_id, request.artifact_ids)
    preflight["snapshot"]["artifacts"] = artifact_snapshots
    preflight["preconditions"].extend({"type": "artifact_hash", **snapshot} for snapshot in artifact_snapshots)
    package_hash = canonical_package_hash(request.title, request.description, normalized_steps)
    request_hash = hashlib.sha256(
        json.dumps({
            "work_id": work_id,
            "conversation_id": request.conversation_id,
            "package_hash": package_hash,
            "source_proposal_part_id": request.source_proposal_part_id,
        }, sort_keys=True).encode("utf-8")
    ).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor=actor, operation="action_package.create", scope=work_id,
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed" and claim["resource_id"]:
            http_response.status_code = status.HTTP_200_OK
            return await _response(conn, await _package(conn, claim["resource_id"]))
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Action-package request is still processing")
        raise HTTPException(status_code=409, detail="Previous request failed; use a new Idempotency-Key")

    now = int(time.time()); package_id = str(uuid.uuid4())
    capabilities = [item["kind"] for item in normalized_steps]
    payload = build_resolved_payload(
        title=request.title,
        description=request.description,
        normalized_steps=normalized_steps,
        snapshot=preflight["snapshot"],
        preconditions=preflight["preconditions"],
        created_at=now, context_sources=artifact_snapshots,
    )
    payload_hash_value = canonical_payload_hash(payload)
    expires_at = now + APPROVAL_TTL_SECONDS
    try:
        await conn.execute(
            """INSERT INTO action_packages
               (id, session_id, conversation_id, title, description, package_hash, status, created_at, updated_at,
                revision, approved_revision, created_by, dto_version, snapshot_json, preconditions_json, budget_json,
                capabilities_json, schema_version, resolved_payload_json, payload_hash, expires_at, approval_ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?, 'awaiting_approval', ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (package_id, work_id, request.conversation_id, request.title, request.description, package_hash, now, now,
             actor, DTO_VERSION, json.dumps(preflight["snapshot"]), json.dumps(preflight["preconditions"]),
             json.dumps(P0_EXECUTION_BUDGETS), json.dumps(capabilities),
             json.dumps(payload), payload_hash_value, expires_at, APPROVAL_TTL_SECONDS),
        )
        for index, item in enumerate(normalized_steps):
            expected_version = preflight["expected_versions"][index]
            await conn.execute(
                """INSERT INTO action_steps
                   (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at, expected_version_json, capability)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), package_id, index, item["kind"], ACTION_RISKS[item["kind"]],
                 json.dumps(item["input"], sort_keys=True), now, now, json.dumps(expected_version) if expected_version else None, item["kind"]),
            )
        if proposal_turn_id:
            async with conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM assistant_turn_parts WHERE turn_id = ?",
                (proposal_turn_id,),
            ) as cur:
                sort_order = (await cur.fetchone())[0]
            approval_content = {
                "title": request.title,
                "description": "Gói đề xuất đã được tạo và đang chờ quyết định của người dùng.",
                "package_id": package_id,
                "package_hash": package_hash,
                "expected_revision": 1,
                "expected_payload_hash": payload_hash_value,
                "expires_at": expires_at,
                "status": "awaiting_approval",
                "before": "Công việc chưa bị thay đổi bởi đề xuất này.",
                "after": f"{len(normalized_steps)} bước sẽ chỉ chạy sau khi package hash được duyệt.",
                "risk": "write",
                "undo": "Có thể từ chối gói trước khi chạy hoặc tạo đề xuất điều chỉnh mới sau đó.",
            }
            await conn.execute(
                "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'approval', ?, ?, ?)",
                (str(uuid.uuid4()), proposal_turn_id, json.dumps(approval_content), sort_order, now),
            )
        await log_audit_event(conn, work_id, actor, "action_package.proposed", package_id, {"package_hash": package_hash, "step_count": len(normalized_steps)}, commit=False)
        created = await _response(conn, await _package(conn, package_id))
        await repo.finalize_operation(
            claim, response=created.model_dump(), status_code=status.HTTP_201_CREATED, resource_id=package_id,
        )
        return created
    except Exception:
        await conn.rollback()
        await repo.fail_operation(claim, "action_package_create_failed")
        raise


@router.post("/action-packages/{package_id}/approve", response_model=ActionPackageResponse)
async def approve_action_package(
    package_id: str,
    approve_request: ActionPackageApproveRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackageResponse:
    package = await _package(conn, package_id)
    if package["created_by"] != actor:
        raise HTTPException(status_code=403, detail="Only the package creator may approve this package")

    request_hash = hashlib.sha256(json.dumps({
        "package_id": package_id,
        "expected_revision": approve_request.expected_revision,
        "expected_payload_hash": approve_request.expected_payload_hash,
        "actor": actor,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor=actor, operation="action_package.approve", scope=package["session_id"],
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed" and claim["resource_id"]:
            return await _response(conn, await _package(conn, package_id))
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Approval is still processing")
        raise HTTPException(status_code=409, detail="Previous request failed; use a new Idempotency-Key")

    try:
        if package["status"] != "awaiting_approval":
            raise HTTPException(status_code=409, detail="This action package can no longer be approved")
        if approve_request.expected_revision != package["revision"]:
            raise HTTPException(status_code=409, detail="Revision mismatch: package was revised since you loaded it")
        if approve_request.expected_payload_hash != package["payload_hash"]:
            raise HTTPException(status_code=409, detail="Payload hash mismatch: package content changed")
        async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (package["session_id"],)) as cur:
            work = await cur.fetchone()
        if work is None or work[0]:
            raise HTTPException(status_code=409, detail="Work is archived")
        now = int(time.time())
        if package["expires_at"] is not None and package["expires_at"] <= now:
            raise HTTPException(status_code=409, detail="Action package has expired")
        await conn.execute(
            "UPDATE action_packages SET status = 'approved', approved_hash = package_hash, approved_payload_hash = payload_hash,"
            " approved_revision = revision, approved_at = ?, approved_by = ?, updated_at = ?"
            " WHERE id = ? AND created_by = ? AND status = 'awaiting_approval' AND revision = ? AND (expires_at IS NULL OR expires_at > ?)",
            (now, actor, now, package_id, actor, approve_request.expected_revision, now),
        )
        async with conn.execute("SELECT changes()") as cur:
            changed = (await cur.fetchone())[0]
        if changed != 1:
            raise HTTPException(status_code=409, detail="Another decision already won")
        await log_audit_event(
            conn, package["session_id"], actor, "action_package.approved", package_id,
            {"package_hash": package["package_hash"], "approved_revision": package["revision"],
             "revision": package["revision"], "payload_hash": package["payload_hash"]},
            commit=False,
        )
        approved = await _response(conn, await _package(conn, package_id))
        await repo.finalize_operation(
            claim, response=approved.model_dump(), status_code=status.HTTP_200_OK, resource_id=package_id,
        )
        return approved
    except Exception:
        await conn.rollback()
        await repo.fail_operation(claim, "action_package_approve_failed")
        raise


async def _cancel_action_package(
    package_id: str,
    decision: ActionPackageDecisionRequest,
    idempotency_key: str,
    conn: aiosqlite.Connection,
    *,
    allow_approved: bool,
    actor: str,
    operation: str,
) -> ActionPackageResponse:
    package = await _package(conn, package_id)
    if package["created_by"] != actor:
        raise HTTPException(status_code=403, detail="Only the package creator may decide this package")
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (package["session_id"],)) as cur:
        work = await cur.fetchone()
    if work is None or work[0]:
        raise HTTPException(status_code=409, detail="Work is archived")
    allowed = {"draft", "awaiting_approval"} | ({"approved"} if allow_approved else set())
    if package["status"] not in allowed: raise HTTPException(status_code=409, detail="This action package can no longer be cancelled")
    if decision.expected_revision != package["revision"] or decision.expected_payload_hash != package["payload_hash"]:
        raise HTTPException(status_code=409, detail="Package content changed; reload before deciding")
    request_hash = hashlib.sha256(json.dumps({
        "package_id": package_id, "operation": operation, "revision": decision.expected_revision,
        "payload_hash": decision.expected_payload_hash, "actor": actor,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    repo = IdempotencyRepository(conn)
    try:
        claim, inserted = await repo.claim_operation(
            actor=actor, operation=f"action_package.{operation}", scope=package["session_id"],
            client_key=idempotency_key, request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not inserted:
        if claim["state"] == "completed":
            return await _response(conn, await _package(conn, package_id))
        if claim["state"] == "processing":
            raise HTTPException(status_code=409, detail="Decision is still processing")
        raise HTTPException(status_code=409, detail="Previous decision failed; use a new Idempotency-Key")
    now = int(time.time())
    placeholders = ", ".join("?" for _ in allowed)
    try:
        await conn.execute(
            f"UPDATE action_packages SET status = 'cancelled', updated_at = ? "
            f"WHERE id = ? AND created_by = ? AND status IN ({placeholders}) AND revision = ? AND payload_hash = ?",
            [now, package_id, actor, *allowed, decision.expected_revision, decision.expected_payload_hash],
        )
        async with conn.execute("SELECT changes()") as cur:
            changed = (await cur.fetchone())[0]
        if changed != 1:
            raise HTTPException(status_code=409, detail="Another decision already won")
        audit_action = "action_package.denied" if operation == "deny" else "action_package.cancelled"
        await log_audit_event(conn, package["session_id"], actor, audit_action, package_id, {"revision": package["revision"], "payload_hash": package["payload_hash"]}, commit=False)
        result = await _response(conn, await _package(conn, package_id))
        await repo.finalize_operation(claim, response=result.model_dump(), status_code=status.HTTP_200_OK, resource_id=package_id)
        return result
    except Exception:
        await conn.rollback()
        await repo.fail_operation(claim, f"action_package_{operation}_failed")
        raise


@router.post("/action-packages/{package_id}/deny", response_model=ActionPackageResponse)
async def deny_action_package(
    package_id: str,
    decision: ActionPackageDecisionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackageResponse:
    return await _cancel_action_package(package_id, decision, idempotency_key, conn, allow_approved=False, actor=actor, operation="deny")


@router.post("/action-packages/{package_id}/cancel", response_model=ActionPackageResponse)
async def cancel_action_package(
    package_id: str,
    decision: ActionPackageDecisionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> ActionPackageResponse:
    return await _cancel_action_package(package_id, decision, idempotency_key, conn, allow_approved=True, actor=actor, operation="cancel")
