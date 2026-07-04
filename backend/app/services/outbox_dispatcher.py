from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import aiosqlite

from app.db.connection import get_db_connection
from app.repositories.outbox_repository import OutboxRepository
from app.services.audit import log_audit_event
from app.settings import Settings

logger = logging.getLogger(__name__)

OutboxSender = Callable[[dict[str, Any], str], Awaitable[None] | None]


class OutboxDispatcher:
    """Claim and dispatch backend-owned notification outbox rows."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        *,
        worker_id: str,
        sender: OutboxSender,
        repository: Optional[OutboxRepository] = None,
    ) -> None:
        self._db = db
        self._worker_id = worker_id
        self._sender = sender
        self._repo = repository or OutboxRepository(db)

    async def dispatch_once(
        self,
        *,
        batch_size: int = 10,
        lease_seconds: int = 30,
    ) -> dict[str, int]:
        rows = await self._repo.claim_pending(
            self._worker_id,
            batch_size=batch_size,
            lease_seconds=lease_seconds,
        )
        result = {"claimed": len(rows), "sent": 0, "retried": 0, "dead_letter": 0}

        for row in rows:
            try:
                await self._send(row)
            except Exception as exc:
                await self._audit(row, "outbox.dispatch.error", {"error_class": exc.__class__.__name__})
                await self._repo.mark_retry(row["id"], str(exc))
                status = await self._repo.get_status(row["id"])
                if status == "dead_letter":
                    result["dead_letter"] += 1
                else:
                    result["retried"] += 1
            else:
                await self._audit(row, "outbox.dispatch.sent", {"worker_id": self._worker_id})
                await self._repo.mark_sent(row["id"])
                result["sent"] += 1
            await self._db.commit()

        return result

    async def _send(self, row: dict[str, Any]) -> None:
        payload = json.loads(row["payload_json"])
        idempotency_key = payload.get("idempotency_key") or row["id"]
        outcome = self._sender(row, idempotency_key)
        if inspect.isawaitable(outcome):
            await outcome

    async def _audit(self, row: dict[str, Any], action: str, extra: dict[str, Any]) -> None:
        payload = json.loads(row["payload_json"])
        await log_audit_event(
            self._db,
            payload.get("session_id"),
            "system",
            action,
            row["id"],
            {
                "channel": row["channel"],
                "event_type": row["event_type"],
                "attempt_count": row["attempt_count"],
                **extra,
            },
        )


def create_n8n_sender(settings: Settings) -> OutboxSender:
    """Return a sender callable that dispatches outbox rows to n8n.

    Missing n8n configuration is a dispatch failure. The dispatcher will
    retry and eventually dead-letter the row instead of marking it sent.
    """
    from app.services.n8n_webhook import trigger_n8n_webhook

    async def _sender(row: dict[str, Any], idempotency_key: str) -> None:
        payload = json.loads(row["payload_json"])
        session_id = payload.get("session_id")
        await trigger_n8n_webhook(
            settings=settings,
            session_id=session_id,
            workflow_name="notification",
            payload={
                "event_type": row["event_type"],
                "session_id": session_id,
                "task_id": payload.get("task_id"),
                "idempotency_key": idempotency_key,
            },
        )

    return _sender


def create_null_sender() -> OutboxSender:
    """Return a no-op sender for tests. Rows are claimed and marked sent."""

    async def _sender(row: dict[str, Any], idempotency_key: str) -> None:
        pass

    return _sender


async def run_outbox_dispatcher_loop(
    settings: Settings,
    stop_event: asyncio.Event,
    *,
    worker_id: str = "fastapi-backend",
    batch_size: int = 10,
    poll_seconds: float | None = None,
) -> None:
    """Poll the outbox and dispatch pending notifications until *stop_event* is set."""
    poll = poll_seconds if poll_seconds is not None else settings.outbox_dispatcher_poll_seconds
    sender = create_n8n_sender(settings)

    while not stop_event.is_set():
        try:
            async with get_db_connection(settings.db_path_resolved) as db:
                dispatcher = OutboxDispatcher(db, worker_id=worker_id, sender=sender)
                result = await dispatcher.dispatch_once(batch_size=batch_size)
                if result["claimed"]:
                    logger.info(
                        "Outbox dispatch: %d sent, %d retried, %d dead_letter",
                        result["sent"],
                        result["retried"],
                        result["dead_letter"],
                    )
        except Exception:
            logger.exception("Outbox dispatch cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll)
        except TimeoutError:
            pass
