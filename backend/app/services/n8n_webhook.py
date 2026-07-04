"""Safe n8n webhook execution helpers."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.db.connection import get_db_connection
from app.services.audit import log_audit_event
from app.settings import Settings


@dataclass(frozen=True)
class N8nWebhookResult:
    workflow_name: str
    response_status: int
    message: str


def validate_n8n_workflow(settings: Settings, workflow_name: str) -> str:
    """Return the target URL for an allowlisted workflow."""
    if not settings.n8n_webhook_secret:
        raise ValueError("n8n webhook secret is not configured in backend.")

    if workflow_name not in settings.n8n_allowed_workflows:
        allowed = sorted(settings.n8n_allowed_workflows.keys())
        raise ValueError(f"Workflow '{workflow_name}' is not in the allowlist. Allowed: {allowed}")

    webhook_path = settings.n8n_allowed_workflows[workflow_name]
    return settings.n8n_webhook_base_url.rstrip("/") + "/" + webhook_path.lstrip("/")


async def trigger_n8n_webhook(
    *,
    settings: Settings,
    session_id: str | None,
    workflow_name: str,
    payload: dict[str, Any],
) -> N8nWebhookResult:
    """Call an allowlisted n8n webhook and write redacted audit metadata."""
    target_url = validate_n8n_workflow(settings, workflow_name)
    payload_size = len(json.dumps(payload, ensure_ascii=False))
    top_keys = sorted(payload.keys())

    async with httpx.AsyncClient(timeout=settings.n8n_timeout_seconds) as client:
        for attempt in range(settings.n8n_max_retries + 1):
            try:
                response = await client.post(
                    target_url,
                    json=payload,
                    headers={"X-Hermes-Secret": settings.n8n_webhook_secret},
                )
                response.raise_for_status()

                async with get_db_connection(settings.db_path_resolved) as db:
                    await log_audit_event(
                        db,
                        session_id,
                        "system",
                        "n8n.webhook.sent",
                        workflow_name,
                        {
                            "payload_size_bytes": payload_size,
                            "payload_top_level_keys": top_keys,
                            "response_status": response.status_code,
                        },
                    )
                    await db.commit()

                return N8nWebhookResult(
                    workflow_name=workflow_name,
                    response_status=response.status_code,
                    message=f"Successfully triggered workflow '{workflow_name}'. Status: {response.status_code}",
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                is_5xx = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500
                is_retryable_request = isinstance(exc, httpx.RequestError)

                if (is_5xx or is_retryable_request) and attempt < settings.n8n_max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue

                async with get_db_connection(settings.db_path_resolved) as db:
                    await log_audit_event(
                        db,
                        session_id,
                        "system",
                        "n8n.webhook.error",
                        workflow_name,
                        {
                            "payload_size_bytes": payload_size,
                            "payload_top_level_keys": top_keys,
                            "error_class": exc.__class__.__name__,
                            "attempt": attempt + 1,
                        },
                    )
                    await db.commit()
                raise RuntimeError(f"Failed to trigger webhook after {attempt + 1} attempts: {exc}") from exc
