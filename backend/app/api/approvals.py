import asyncio
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import ApprovalDecisionResponse, ApprovalRequest
from app.db.connection import get_db_connection
from app.dependencies import get_settings
from app.services.audit import log_audit_event
from app.settings import Settings

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])

# Active in-process waiters. Durable request state is stored in approval_requests.
pending_approvals: dict[str, dict] = {}


EXTERNAL_OR_DESTRUCTIVE_ACTIONS = {
    "run_safe_task",
    "call_n8n_webhook",
}


def _is_external_or_destructive(data: dict) -> bool:
    if data.get("risk_level") == "external_or_destructive":
        return True
    if data.get("action") in EXTERNAL_OR_DESTRUCTIVE_ACTIONS:
        return True
    text = f"{data.get('action', '')} {data.get('target', '')} {data.get('description', '')}".lower()
    return any(
        marker in text
        for marker in (
            "script execution",
            "terminal",
            "shell",
            "python -c",
            "powershell",
            "cmd.exe",
            "execution via",
        )
    )


async def _apply_curator_memory_if_needed(
    db,
    session_id: str | None,
    approval_id: str,
    pending_data: dict,
) -> None:
    """Apply an approved curator proposal to memory entries."""
    if pending_data.get("action") != "update_memory" or not session_id:
        return

    payload = pending_data.get("payload") or {}
    kind = payload.get("kind")
    key = payload.get("key")
    value = payload.get("value")
    importance_score = float(payload.get("importance_score", 5.0))
    if not kind or not key or not value:
        return

    now = int(time.time())
    async with db.execute(
        "SELECT id FROM memory_entries WHERE session_id = ? AND key = ?",
        (session_id, key),
    ) as cur:
        row = await cur.fetchone()

    if row:
        memory_id = row[0]
        await db.execute(
            """
            UPDATE memory_entries
            SET value = ?, kind = ?, importance_score = ?
            WHERE id = ?
            """,
            (value, kind, importance_score, memory_id),
        )
        audit_action = "memory.updated"
    else:
        import uuid

        memory_id = f"mem-{uuid.uuid4().hex[:12]}"
        await db.execute(
            """
            INSERT INTO memory_entries (
                id, session_id, key, value, kind, importance_score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (memory_id, session_id, key, value, kind, importance_score, now),
        )
        audit_action = "memory.created"

    await log_audit_event(
        conn=db,
        session_id=session_id,
        actor="system",
        action=audit_action,
        target=memory_id,
        payload={"approval_id": approval_id, "key": key, "kind": kind},
    )


async def register_pending_approval(
    approval_id: str,
    session_id: str | None,
    action: str,
    target: str,
    settings: Settings,
    risk_level: str = "write_internal",
    description: str | None = None,
    timeout_seconds: float | None = None,
    payload: dict | None = None,
) -> None:
    """Register a new pending approval and log the audit event."""
    now = int(time.time())
    expires_at = now + int(timeout_seconds or settings.hermes_request_timeout_seconds or 60)
    pending_approvals[approval_id] = {
        "session_id": session_id,
        "action": action,
        "target": target,
        "risk_level": risk_level,
        "description": description,
        "payload": payload,
        "db_path": settings.db_path_resolved,
        "event": asyncio.Event(),
        "decision": None
    }
    
    async with get_db_connection(settings.db_path_resolved) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO approval_requests (
                id, session_id, action, target, risk_level, description,
                status, decision, created_at, resolved_at, expires_at, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL, ?, ?)
            """,
            (
                approval_id,
                session_id,
                action,
                target,
                risk_level,
                description,
                now,
                expires_at,
                json.dumps(payload, ensure_ascii=False) if payload is not None else None,
            ),
        )
        await log_audit_event(
            conn=db,
            session_id=session_id,
            actor="system",
            action="approval.requested",
            target=approval_id,
            payload={
                "action": action,
                "target": target,
                "risk_level": risk_level,
                "description": description,
                "expires_at": expires_at,
                "payload": payload,
            }
        )
        await db.commit()


async def _mark_approval_resolved(
    db_path,
    approval_id: str,
    status: str,
    decision: str | None,
    session_id: str | None,
    audit_action: str | None = None,
    payload: dict | None = None,
) -> None:
    now = int(time.time())
    async with get_db_connection(db_path) as db:
        await db.execute(
            """
            UPDATE approval_requests
            SET status = ?, decision = ?, resolved_at = ?
            WHERE id = ?
            """,
            (status, decision, now, approval_id),
        )
        if audit_action:
            await log_audit_event(
                conn=db,
                session_id=session_id,
                actor="system" if status == "expired" else "user",
                action=audit_action,
                target=approval_id,
                payload=payload or {},
            )
        await db.commit()

async def wait_for_approval(approval_id: str, timeout_seconds: float = 60.0) -> str:
    """Wait for an approval decision with a timeout.
    Returns the decision ('allow_once', 'allow_for_session', 'deny').
    If timeout occurs, returns 'deny' and cleans up.
    """
    if approval_id not in pending_approvals:
        return "deny"
        
    event = pending_approvals[approval_id]["event"]
    try:
        # async timeout wrapper
        async with asyncio.timeout(timeout_seconds):
            await event.wait()
    except TimeoutError:
        # On timeout, clean up and return deny
        pending_data = pending_approvals.pop(approval_id, None)
        if pending_data and pending_data.get("db_path"):
            await _mark_approval_resolved(
                pending_data["db_path"],
                approval_id,
                "expired",
                "deny",
                pending_data.get("session_id"),
                "approval.expired",
                {
                    "action": pending_data.get("action"),
                    "target": pending_data.get("target"),
                    "risk_level": pending_data.get("risk_level"),
                },
            )
        return "deny"
        
    # Once event is set, the decision should be stored by submit_approval
    # The submit_approval route should NOT delete from pending_approvals, 
    # instead it sets the decision and triggers the event, then wait_for_approval deletes it.
    if approval_id in pending_approvals:
        decision = pending_approvals[approval_id].get("decision", "deny")
        db_path = pending_approvals[approval_id].get("db_path")
        session_id = pending_approvals[approval_id].get("session_id")
        del pending_approvals[approval_id]
        if db_path and decision is None:
            await _mark_approval_resolved(db_path, approval_id, "denied", "deny", session_id)
        return decision
        
    return "deny"



@router.post("/{approval_id}")
async def submit_approval(
    approval_id: str,
    request_data: ApprovalRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ApprovalDecisionResponse:
    """Submit a decision for a pending approval."""
    # In a real flow, we'd validate against the ACP task state.
    # For Phase 2, we just record the decision and emit the audit log.
    
    if approval_id not in pending_approvals:
        async with get_db_connection(settings.db_path_resolved) as db:
            async with db.execute(
                "SELECT status FROM approval_requests WHERE id = ?",
                (approval_id,),
            ) as cur:
                row = await cur.fetchone()
        if row and row[0] == "pending":
            raise HTTPException(status_code=409, detail="Approval expired or no longer active")
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
        
        
    pending_data = pending_approvals[approval_id]
    session_id = pending_data.get("session_id")
    pending_action = pending_data.get("action")
    
    # 2. Early rejection of allow_for_session for external/destructive actions
    if request_data.decision == "allow_for_session" and _is_external_or_destructive(pending_data):
        raise HTTPException(status_code=400, detail="allow_for_session is not permitted for external_or_destructive tasks.")
    
    if request_data.decision == "allow_once":
        action = "approval.allowed_once"
        if pending_action == "update_memory":
            action = "curator.accepted"
        elif pending_action == "mcp.update_memory":
            action = "mcp.memory.accepted"
    elif request_data.decision == "allow_for_session":
        action = "approval.allowed_for_session"
        if pending_action == "update_memory":
            action = "curator.accepted"
        elif pending_action == "mcp.update_memory":
            action = "mcp.memory.accepted"
    else:
        action = "approval.denied"
        if pending_action == "update_memory":
            action = "curator.denied"
        elif pending_action == "mcp.update_memory":
            action = "mcp.memory.denied"

    async with get_db_connection(settings.db_path_resolved) as db:
        if request_data.decision in ("allow_once", "allow_for_session"):
            await _apply_curator_memory_if_needed(db, session_id, approval_id, pending_data)
        await db.execute(
            """
            UPDATE approval_requests
            SET status = ?, decision = ?, resolved_at = ?
            WHERE id = ?
            """,
            ("resolved", request_data.decision, int(time.time()), approval_id),
        )
        await log_audit_event(
            conn=db,
            session_id=session_id,
            actor="user",
            action=action,
            target=approval_id,
            payload=request_data.model_dump()
        )
        await db.commit()

    # Notify waiters only after durable state and audit rows have been committed.
    pending_data["decision"] = request_data.decision
    if "event" in pending_data:
        pending_data["event"].set()

    return ApprovalDecisionResponse(
        status="recorded",
        approval_id=approval_id,
        session_id=session_id,
        decision=request_data.decision,
        audit_action=action,
    )
