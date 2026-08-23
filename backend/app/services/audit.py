"""Audit event logging service."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import aiosqlite

_SENSITIVE_KEYS = {"token", "secret", "authorization", "password", "prompt", "content", "output", "arguments", "payload"}


def _redact(value: Any, key: str = "") -> Any:
    if key.casefold() in _SENSITIVE_KEYS or any(part in key.casefold() for part in ("token", "secret", "authorization", "password")):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and ("Bearer " in value or "api_key=" in value.casefold()):
        return "[redacted]"
    return value


def redact_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Public redaction helper for durable execution events and versioned DTOs."""
    if payload is None:
        return None
    return _redact(payload)


async def log_audit_event(
    conn: aiosqlite.Connection,
    session_id: str | None,
    actor: str,
    action: str,
    target: str | None = None,
    payload: dict[str, Any] | None = None,
    *,
    commit: bool = True,
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
    payload_json = json.dumps(_redact(payload)) if payload is not None else None
    created_at = int(time.time())

    await conn.execute(
        """
        INSERT INTO audit_events (id, session_id, actor, action, target, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, session_id, actor, action, target, payload_json, created_at),
    )
    if commit:
        await conn.commit()
