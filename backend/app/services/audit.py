"""Audit event logging service."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import aiosqlite


async def log_audit_event(
    conn: aiosqlite.Connection,
    session_id: str | None,
    actor: str,
    action: str,
    target: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Log an event to the append-only audit_events table.
    
    Minimum Phase 1 actions:
      - session.created
      - prompt.submitted
      - task_run.started
      - task_run.completed
      - task_run.failed
      - hermes.error
    """
    event_id = str(uuid.uuid4())
    payload_json = json.dumps(payload) if payload is not None else None
    created_at = int(time.time())

    await conn.execute(
        """
        INSERT INTO audit_events (id, session_id, actor, action, target, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, session_id, actor, action, target, payload_json, created_at),
    )
    await conn.commit()
