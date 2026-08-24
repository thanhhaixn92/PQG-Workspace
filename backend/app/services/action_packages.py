"""Durable executor for user-approved, first-party Work changes.

The service deliberately has a very small action allow-list.  A model may
propose a package but it cannot choose arbitrary functions, shell commands,
or network calls.  The worker claims a persisted package, so an approved
package survives a backend restart without relying on an in-memory waiter.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from hashlib import sha256
from collections.abc import Awaitable, Callable
from types import MappingProxyType
from typing import Any, Mapping

import aiosqlite

from app.db.connection import get_db_connection
from app.services.audit import log_audit_event, redact_payload
from app.services.sandbox import get_workspace_path, resolve_and_validate_path
from app.settings import Settings

ACTION_RISKS = {
    "work_plan_step_update": "write",
    "work_status_update": "write",
}

# GYO v3 P0 fixed internal capability allow-list.  No external/destructive or
# arbitrary-function capability may ever enter an Action Package.
P0_INTERNAL_CAPABILITIES = frozenset({"work_plan_step_update", "work_status_update"})

# P0 execution budgets.  These are server-enforced limits for the v3 slice.
P0_EXECUTION_BUDGETS = {
    "max_steps": 20,
    "lease_seconds": 60,
    "max_step_duration_seconds": 30,
    "watchdog_grace_seconds": 30,
}

DTO_VERSION = 1
APPROVAL_TTL_SECONDS = 900


def canonical_package_hash(title: str, description: str | None, steps: list[dict[str, Any]]) -> str:
    payload = {"title": title, "description": description or "", "steps": steps}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def canonical_step_hash(step: dict[str, Any]) -> str:
    return sha256(json.dumps(step, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_resolved_payload(
    *,
    title: str,
    description: str | None,
    normalized_steps: list[dict[str, Any]],
    snapshot: dict[str, Any],
    preconditions: list[dict[str, Any]],
    created_at: int,
    revision: int = 1,
    dto_version: int = DTO_VERSION,
    context_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    budget = dict(P0_EXECUTION_BUDGETS)
    targets = snapshot.get("targets") if isinstance(snapshot, dict) else []
    if not isinstance(targets, list):
        targets = []
    return {
        "payload_schema_version": 1,
        "dto_version": dto_version,
        "revision": revision,
        "title": title,
        "description": description,
        "actions": [
            {"kind": s["kind"], "input": s.get("input", {})}
            for s in normalized_steps
        ],
        "targets": targets,
        "diffs": [],
        "preconditions": preconditions,
        "context_snapshot": {
            "sources": context_sources or [],
            "context_hash": canonical_payload_hash(context_sources or []) if context_sources else None,
        },
        "capability_version": "p0-v1",
        "budget": budget,
        "budget_version": "p0-v1",
        "policy_version": "p0-v1",
        "tool_contract_version": "p0-v1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(created_at)),
        "captured_tz_offset_minutes": 0,
        "expires_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(created_at + APPROVAL_TTL_SECONDS)
        ),
    }


async def resolve_preflight(
    conn: aiosqlite.Connection,
    work_id: str,
    normalized_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve canonical targets, optimistic expected versions, diffs and preconditions.

    Pure read: no mutation.  Returns a report the API can surface and the
    executor can re-verify before each step so a stale or revised package fails
    closed instead of silently applying the wrong change.
    """
    targets: list[dict[str, Any]] = []
    preconditions: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    expected_versions: list[dict[str, Any] | None] = []
    for index, step in enumerate(normalized_steps):
        data = step["input"]
        if step["kind"] == "work_plan_step_update":
            step_id = str(data["step_id"])
            async with conn.execute(
                "SELECT id, session_id, title, status, result, version FROM work_plan_steps WHERE id = ?",
                (step_id,),
            ) as cur:
                row = await cur.fetchone()
            if row is None or row["session_id"] != work_id:
                raise ValueError("The plan step is not part of this Work")
            before = {"title": row["title"], "status": row["status"], "result": row["result"]}
            changes = data["changes"]
            after = {**before, **{key: changes[key] for key in changes}}
            targets.append({"kind": "work_plan_step_update", "step_id": step_id, "session_id": row["session_id"]})
            preconditions.append({
                "type": "plan_step_belongs_to_work",
                "step_id": step_id,
                "session_id": row["session_id"],
                "expected_session_id": work_id,
            })
            diffs.append({
                "step_index": index,
                "kind": "work_plan_step_update",
                "step_id": step_id,
                "before": before,
                "after": after,
                "changed_fields": sorted(changes.keys()),
            })
            expected_versions.append({"kind": "work_plan_step_update", "step_id": step_id, "expected_version": row["version"]})
        elif step["kind"] == "work_status_update":
            async with conn.execute(
                "SELECT id, work_status, progress_percent, version, archived FROM sessions WHERE id = ?",
                (work_id,),
            ) as cur:
                row = await cur.fetchone()
            if row is None or row["archived"]:
                raise ValueError("The Work is unavailable for this change")
            before = {"work_status": row["work_status"], "progress_percent": row["progress_percent"]}
            after = {
                "work_status": data["work_status"],
                "progress_percent": data["progress_percent"],
            }
            targets.append({"kind": "work_status_update", "session_id": work_id})
            preconditions.append({"type": "work_not_archived", "session_id": work_id, "expected_archived": 0})
            diffs.append({
                "step_index": index,
                "kind": "work_status_update",
                "before": before,
                "after": after,
                "changed_fields": ["work_status", "progress_percent"],
            })
            expected_versions.append({"kind": "work_status_update", "expected_version": row["version"]})
    snapshot = {"targets": targets, "captured_at": int(time.time())}
    return {
        "targets": targets,
        "preconditions": preconditions,
        "diffs": diffs,
        "snapshot": snapshot,
        "expected_versions": expected_versions,
    }


async def record_execution_event(
    conn: aiosqlite.Connection,
    package_id: str,
    event_type: str,
    *,
    step_id: str | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    """Append a durable execution event (heartbeat, claim, recovery, blocked...)."""
    await conn.execute(
        """INSERT INTO action_execution_events
           (id, package_id, step_id, event_type, detail_json, created_at, sequence)
           SELECT ?, ?, ?, ?, ?, ?, COALESCE(MAX(sequence), 0) + 1
           FROM action_execution_events WHERE package_id = ?""",
        (str(uuid.uuid4()), package_id, step_id, event_type,
         json.dumps(redact_payload(detail) or {}), int(time.time()), package_id),
    )
    if commit:
        await conn.commit()


async def _claim_next(conn: aiosqlite.Connection, worker_id: str) -> str | None:
    now = int(time.time())
    async with conn.execute(
        """SELECT id FROM action_packages
           WHERE (
                 status = 'approved'
                 AND approved_payload_hash = payload_hash
                 AND approved_revision = revision
                 AND (expires_at IS NULL OR expires_at > ?)
               )
               OR (
                 status = 'executing'
                 AND lease_expires_at IS NOT NULL
                 AND lease_expires_at < ?
               )
           ORDER BY CASE WHEN status = 'approved' THEN 0 ELSE 1 END, approved_at, created_at
           LIMIT 1""",
        (now, now),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    package_id = row[0]
    result = await conn.execute(
        """UPDATE action_packages
           SET status = 'executing', lease_owner = ?, lease_expires_at = ?, heartbeat_at = ?,
                attempt_count = attempt_count + 1, updated_at = ?
           WHERE id = ? AND (
                 (
                   status = 'approved'
                   AND approved_payload_hash = payload_hash
                   AND approved_revision = revision
                   AND (expires_at IS NULL OR expires_at > ?)
                 )
                 OR (
                   status = 'executing'
                   AND lease_expires_at IS NOT NULL
                   AND lease_expires_at < ?
                 )
            )""",
        (worker_id, now + P0_EXECUTION_BUDGETS["lease_seconds"], now, now, package_id, now, now),
    )
    async with conn.execute("SELECT changes()") as cur:
        changed = (await cur.fetchone())[0]
    await conn.commit()
    return package_id if changed == 1 else None


async def _verify_context_artifact_snapshots(conn: aiosqlite.Connection, package: aiosqlite.Row) -> str | None:
    """Return a safe failure reason when an approved input artifact drifted."""
    payload = json.loads(package["resolved_payload_json"] or "{}")
    context = payload.get("context_snapshot", {}) if isinstance(payload, dict) else {}
    sources = context.get("sources", []) if isinstance(context, dict) else []
    if not isinstance(sources, list):
        return "Context snapshot is malformed"
    artifact_sources = [item for item in sources if isinstance(item, dict) and item.get("artifact_id")]
    if not artifact_sources:
        return None
    workspace = await get_workspace_path(package["session_id"], conn)
    for source in artifact_sources:
        artifact_id = str(source["artifact_id"])
        expected_hash = source.get("sha256")
        async with conn.execute(
            """SELECT artifact.relative_path, artifact.sha256, COALESCE(validation.status, 'pending') AS validation_status
               FROM artifacts artifact LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
               WHERE artifact.id = ? AND artifact.session_id = ?""",
            (artifact_id, package["session_id"]),
        ) as cur:
            artifact = await cur.fetchone()
        if artifact is None or artifact["validation_status"] != "structurally_validated":
            return "An input artifact is no longer structurally validated"
        if artifact["sha256"] != expected_hash:
            return "An input artifact changed since the package was created"
        try:
            target = resolve_and_validate_path(workspace, artifact["relative_path"], max_size=10 * 1024 * 1024)
            with target.open("rb") as handle:
                actual_hash = sha256(handle.read()).hexdigest()
        except OSError:
            return "An input artifact is no longer available"
        if actual_hash != expected_hash:
            return "An input artifact changed on disk since the package was created"
    return None


class OptimisticVersionConflict(Exception):
    """Raised when a target's current version no longer matches the approved snapshot.

    The executor records this as a ``blocked`` step rather than a hard failure so
    the package can be re-authorised against fresh state.  Never auto-applies.
    """


def _expected_version(step: aiosqlite.Row) -> dict[str, Any] | None:
    if not step["expected_version_json"]:
        return None
    return json.loads(step["expected_version_json"])


async def _target_version(conn: aiosqlite.Connection, package: aiosqlite.Row, step: aiosqlite.Row) -> tuple[str, int]:
    """Return (target_key, current_version) for a step's canonical target."""
    data = json.loads(step["input_json"])
    if step["kind"] == "work_plan_step_update":
        step_id = str(data.get("step_id", ""))
        async with conn.execute("SELECT version FROM work_plan_steps WHERE id = ?", (step_id,)) as cur:
            row = await cur.fetchone()
        return (f"plan_step:{step_id}", row["version"] if row else -1)
    async with conn.execute("SELECT version FROM sessions WHERE id = ?", (package["session_id"],)) as cur:
        row = await cur.fetchone()
    return (f"work:{package['session_id']}", row["version"] if row else -1)


async def _execute_work_plan_step_update(
    conn: aiosqlite.Connection,
    package: aiosqlite.Row,
    step: aiosqlite.Row,
) -> dict[str, Any]:
    data = json.loads(step["input_json"])
    now = int(time.time())
    step_id = str(data.get("step_id", ""))
    allowed = {"title", "description", "result", "status"}
    updates = {key: value for key, value in data.get("changes", {}).items() if key in allowed}
    if not step_id or not updates:
        raise ValueError("A plan-step update must name a step and at least one supported change")
    async with conn.execute(
        "SELECT plan.session_id, plan.version FROM work_plan_steps plan "
        "JOIN sessions work ON work.id = plan.session_id "
        "WHERE plan.id = ? AND work.archived = 0",
        (step_id,),
    ) as cur:
        target = await cur.fetchone()
    if target is None or target[0] != package["session_id"]:
        raise ValueError("The plan step is not part of this Work")
    expected = _expected_version(step)
    if expected is not None and expected.get("expected_version") != target[1]:
        raise OptimisticVersionConflict(
            f"Plan step {step_id} changed since approval (expected v{expected.get('expected_version')}, "
            f"now v{target[1]}); re-authorise the package."
        )
    fields = list(updates)
    await conn.execute(
        f"UPDATE work_plan_steps SET {', '.join(f'{key} = ?' for key in fields)}, version = version + 1, updated_at = ? WHERE id = ?",
        [updates[key] for key in fields] + [now, step_id],
    )
    return {"updated_step_id": step_id, "fields": fields}


async def _execute_work_status_update(
    conn: aiosqlite.Connection,
    package: aiosqlite.Row,
    step: aiosqlite.Row,
) -> dict[str, Any]:
    data = json.loads(step["input_json"])
    now = int(time.time())
    status = data.get("work_status")
    progress = data.get("progress_percent")
    if status not in {"not_started", "in_progress", "paused"}:
        raise ValueError("Unsupported Work status")
    if not isinstance(progress, int) or not 0 <= progress <= 100:
        raise ValueError("Progress must be an integer from 0 to 100")
    async with conn.execute(
        "SELECT version, archived FROM sessions WHERE id = ?", (package["session_id"],)
    ) as cur:
        work = await cur.fetchone()
    if work is None or work[1]:
        raise ValueError("The Work is no longer available for an approved change")
    expected = _expected_version(step)
    if expected is not None and expected.get("expected_version") != work[0]:
        raise OptimisticVersionConflict(
            f"Work {package['session_id']} changed since approval (expected v{expected.get('expected_version')}, "
            f"now v{work[0]}); re-authorise the package."
        )
    await conn.execute(
        "UPDATE sessions SET work_status = ?, progress_percent = ?, version = version + 1, updated_at = ? WHERE id = ? AND archived = 0",
        (status, progress, now, package["session_id"]),
    )
    async with conn.execute("SELECT changes()") as cur:
        if (await cur.fetchone())[0] != 1:
            raise ValueError("The Work is no longer available for an approved change")
    return {"work_status": status, "progress_percent": progress}


ActionPackageHandler = Callable[
    [aiosqlite.Connection, aiosqlite.Row, aiosqlite.Row],
    Awaitable[dict[str, Any]],
]
ACTION_PACKAGE_HANDLERS: Mapping[str, ActionPackageHandler] = MappingProxyType(
    {
        "work_plan_step_update": _execute_work_plan_step_update,
        "work_status_update": _execute_work_status_update,
    }
)


async def _execute_step(conn: aiosqlite.Connection, package: aiosqlite.Row, step: aiosqlite.Row) -> dict[str, Any]:
    handler = ACTION_PACKAGE_HANDLERS.get(step["kind"])
    if handler is None:
        raise ValueError("Unsupported action kind")
    return await handler(conn, package, step)


async def execute_one_approved_package(settings: Settings, worker_id: str) -> bool:
    """Claim and execute one persisted package.  Returns whether work ran.

    Durable execution: every claim/step/heartbeat/recovery is recorded in
    ``action_execution_events``.  An optimistic-version conflict marks the step
    ``blocked`` (not ``failed``) so the package can be re-authorised; a mid-run
    cancellation stops cleanly and leaves the package ``cancelled``.
    """
    async with get_db_connection(settings.db_path_resolved) as conn:
        package_id = await _claim_next(conn, worker_id)
        if package_id is None:
            return False
        async with conn.execute("SELECT * FROM action_packages WHERE id = ?", (package_id,)) as cur:
            package = await cur.fetchone()
        assert package is not None
        artifact_error = await _verify_context_artifact_snapshots(conn, package)
        if artifact_error:
            now = int(time.time())
            await conn.execute(
                "UPDATE action_packages SET status = 'blocked', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                (now, package_id),
            )
            await record_execution_event(conn, package_id, "artifact_snapshot_blocked", detail={"reason": artifact_error}, commit=True)
            await log_audit_event(conn, package["session_id"], "executor", "action_package.blocked", package_id, {"reason": artifact_error})
            return True
        now = int(time.time())
        await conn.execute("UPDATE action_packages SET heartbeat_at = ? WHERE id = ?", (now, package_id))
        await record_execution_event(conn, package_id, "claimed", detail={"worker_id": worker_id, "attempt": package["attempt_count"]}, commit=True)
        await log_audit_event(conn, package["session_id"], "executor", "action_package.executing", package_id, {"attempt": package["attempt_count"]})
        async with conn.execute("SELECT * FROM action_steps WHERE package_id = ? ORDER BY sort_order", (package_id,)) as cur:
            steps = await cur.fetchall()
        failed = False
        blocked = False
        run_written: dict[str, int] = {}
        for step in steps:
            if step["status"] in ("succeeded", "cancelled"):
                continue
            async with conn.execute("SELECT status FROM action_packages WHERE id = ?", (package_id,)) as cur:
                current = await cur.fetchone()
            if current is None or current["status"] == "cancelled":
                # Cancelled while this step was pending; stop without marking failed.
                await record_execution_event(conn, package_id, "cancelled_mid_run", detail={"step_id": step["id"]}, commit=True)
                return True
            target_key, target_version = await _target_version(conn, package, step)
            expected = _expected_version(step)
            if expected is not None and expected.get("expected_version") != target_version:
                if run_written.get(target_key) == target_version:
                    # Re-baseline: this same package already mutated the target this run.
                    rebaseline = {**expected, "expected_version": target_version}
                    await conn.execute("UPDATE action_steps SET expected_version_json = ? WHERE id = ?", (json.dumps(rebaseline), step["id"]))
                    async with conn.execute("SELECT * FROM action_steps WHERE id = ?", (step["id"],)) as cur:
                        step = await cur.fetchone()
                else:
                    blocked = True
                    now = int(time.time())
                    await conn.execute("UPDATE action_steps SET status = 'blocked', error = ?, updated_at = ? WHERE id = ?", (
                        f"Target version drift on {target_key}: expected v{expected.get('expected_version')}, now v{target_version}; re-authorise the package.", now, step["id"]))
                    await conn.execute("UPDATE action_attempts SET status = 'blocked', detail_json = ?, finished_at = ? WHERE package_id = ? AND step_id = ? AND attempt_number = ?", (json.dumps({"error": "optimistic_version_conflict"}), now, package_id, step["id"], package["attempt_count"]))
                    await record_execution_event(conn, package_id, "step_blocked", step_id=step["id"], detail={"target_key": target_key, "expected": expected.get("expected_updated_at"), "actual": target_version}, commit=True)
                    await conn.commit()
                    continue
            now = int(time.time())
            await conn.execute("UPDATE action_steps SET status = 'executing', updated_at = ? WHERE id = ?", (now, step["id"]))
            await conn.execute(
                "INSERT INTO action_attempts (id, package_id, step_id, attempt_number, status, started_at) VALUES (?, ?, ?, ?, 'executing', ?)",
                (str(uuid.uuid4()), package_id, step["id"], package["attempt_count"], now),
            )
            await conn.commit()
            try:
                output = await _execute_step(conn, package, step)
                now = int(time.time())
                await conn.execute("UPDATE action_steps SET status = 'succeeded', output_json = ?, updated_at = ? WHERE id = ?", (json.dumps(output), now, step["id"]))
                await conn.execute("UPDATE action_attempts SET status = 'succeeded', detail_json = ?, finished_at = ? WHERE package_id = ? AND step_id = ? AND attempt_number = ?", (json.dumps(output), now, package_id, step["id"], package["attempt_count"]))
                _, new_version = await _target_version(conn, package, step)
                run_written[target_key] = new_version
                await record_execution_event(conn, package_id, "step_succeeded", step_id=step["id"], detail=redact_payload(output), commit=True)
            except OptimisticVersionConflict as exc:
                blocked = True
                now = int(time.time())
                await conn.execute("UPDATE action_steps SET status = 'blocked', error = ?, updated_at = ? WHERE id = ?", (str(exc), now, step["id"]))
                await conn.execute("UPDATE action_attempts SET status = 'blocked', detail_json = ?, finished_at = ? WHERE package_id = ? AND step_id = ? AND attempt_number = ?", (json.dumps({"error": str(exc)}), now, package_id, step["id"], package["attempt_count"]))
                await record_execution_event(conn, package_id, "step_blocked", step_id=step["id"], detail={"error": str(exc)}, commit=True)
            except Exception as exc:
                failed = True
                now = int(time.time())
                await conn.execute("UPDATE action_steps SET status = 'failed', error = ?, updated_at = ? WHERE id = ?", (str(exc), now, step["id"]))
                await conn.execute("UPDATE action_attempts SET status = 'failed', detail_json = ?, finished_at = ? WHERE package_id = ? AND step_id = ? AND attempt_number = ?", (json.dumps({"error": str(exc)}), now, package_id, step["id"], package["attempt_count"]))
                await record_execution_event(conn, package_id, "step_failed", step_id=step["id"], detail={"error": str(exc)}, commit=True)
            await conn.commit()
        now = int(time.time())
        if blocked:
            # A blocked step means optimistic-version drift; the package needs
            # re-authorisation.  The package-level status uses the existing
            # ``partially_failed`` value while the blocked step keeps ``blocked``.
            final = "partially_failed"
        elif failed:
            final = "partially_failed"
        else:
            final = "succeeded"
        await conn.execute("UPDATE action_packages SET status = ?, lease_owner = NULL, lease_expires_at = NULL, heartbeat_at = ?, updated_at = ? WHERE id = ?", (final, now, now, package_id))
        await record_execution_event(conn, package_id, "finished", detail={"final_status": final}, commit=True)
        await log_audit_event(conn, package["session_id"], "executor", f"action_package.{final}", package_id, {"attempt": package["attempt_count"]})
        await conn.commit()
        return True


async def recover_stale_leases(settings: Settings) -> int:
    """Watchdog: reclaim packages whose leased execution died without finishing.

    Returns the number of packages reset to ``approved`` so the executor can
    re-claim them.  Orphaned ``executing`` steps that belong to a non-final
    package are reset to ``pending`` so re-execution is idempotent (succeeded
    steps are preserved).
    """
    now = int(time.time())
    grace = P0_EXECUTION_BUDGETS["watchdog_grace_seconds"]
    recovered = 0
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute(
            "SELECT id FROM action_packages WHERE status = 'executing' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?",
            (now - grace,),
        ) as cur:
            stale_ids = [row[0] async for row in cur]
        for package_id in stale_ids:
            async with conn.execute("SELECT status FROM action_packages WHERE id = ?", (package_id,)) as cur:
                row = await cur.fetchone()
            if row is None or row["status"] != "executing":
                continue
            await conn.execute(
                "UPDATE action_steps SET status = 'pending' WHERE package_id = ? AND status = 'executing'",
                (package_id,),
            )
            await conn.execute(
                "UPDATE action_packages SET status = 'approved', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ? AND status = 'executing'",
                (now, package_id),
            )
            await record_execution_event(conn, package_id, "recovered", detail={"grace_seconds": grace}, commit=True)
            recovered += 1
        if recovered:
            await conn.commit()
    return recovered


async def run_action_package_executor_loop(settings: Settings, stop: asyncio.Event) -> None:
    worker_id = f"action-executor-{uuid.uuid4()}"
    while not stop.is_set():
        try:
            await recover_stale_leases(settings)
            ran = await execute_one_approved_package(settings, worker_id)
        except Exception:  # leave a failed package recorded, keep the worker alive
            ran = False
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.2 if ran else 1.0)
        except asyncio.TimeoutError:
            pass
