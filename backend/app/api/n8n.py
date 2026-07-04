"""Safe n8n operational status endpoints."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.approvals import register_pending_approval, wait_for_approval
from app.api.schemas import SseApprovalRequiredEvent
from app.dependencies import get_settings
from app.services.event_bus import event_bus
from app.services.n8n_webhook import trigger_n8n_webhook, validate_n8n_workflow
from app.settings import Settings

router = APIRouter(prefix="/api/n8n", tags=["n8n"])


class N8nStatusResponse(BaseModel):
    configured: bool
    webhook_base_url: str
    allowed_workflows: list[str]
    guidance: str


class N8nTestEchoRequest(BaseModel):
    session_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class N8nTestEchoResponse(BaseModel):
    status: Literal["skipped", "sent", "error"]
    workflow_name: Literal["echo"]
    message: str
    response_status: int | None = None


@router.get("/status", response_model=N8nStatusResponse)
async def n8n_status(settings: Settings = Depends(get_settings)) -> N8nStatusResponse:
    """Return n8n readiness without exposing secrets or calling external webhooks."""
    configured = bool(settings.n8n_webhook_secret)
    return N8nStatusResponse(
        configured=configured,
        webhook_base_url=settings.n8n_webhook_base_url,
        allowed_workflows=sorted(settings.n8n_allowed_workflows.keys()),
        guidance=(
            "n8n secret đã cấu hình. Webhook thật vẫn cần workflow allowlist và phê duyệt."
            if configured
            else "n8n chưa cấu hình secret; bỏ qua nếu chưa dùng tự động hóa."
        ),
    )


@router.post("/test-echo", response_model=N8nTestEchoResponse)
async def test_echo_workflow(
    request: N8nTestEchoRequest,
    settings: Settings = Depends(get_settings),
) -> N8nTestEchoResponse:
    """Safely test the allowlisted echo workflow after one-time approval."""
    try:
        validate_n8n_workflow(settings, "echo")
    except ValueError as exc:
        return N8nTestEchoResponse(status="skipped", workflow_name="echo", message=str(exc))

    if not request.session_id:
        raise HTTPException(
            status_code=400,
            detail="Cần chọn phiên trước khi test n8n echo để hiển thị phê duyệt.",
        )

    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    payload = request.payload or {
        "source": "hermes-ui-smoke",
        "timestamp": int(time.time()),
    }
    description = "Kiểm tra workflow n8n echo từ bảng tình trạng hệ thống."
    await register_pending_approval(
        approval_id=approval_id,
        session_id=request.session_id,
        action="call_n8n_webhook",
        target="echo",
        risk_level="external_or_destructive",
        description=description,
        settings=settings,
        payload={"workflow_name": "echo", "payload_top_level_keys": sorted(payload.keys())},
    )
    await event_bus.publish(
        request.session_id,
        SseApprovalRequiredEvent(
            approval_id=approval_id,
            action="call_n8n_webhook",
            target="echo",
            risk_level="external_or_destructive",
            description=description,
        ),
    )

    decision = await wait_for_approval(approval_id, timeout_seconds=settings.hermes_request_timeout_seconds)
    if decision != "allow_once":
        raise HTTPException(status_code=403, detail="Người dùng chưa phê duyệt gọi workflow n8n echo.")

    try:
        result = await trigger_n8n_webhook(
            settings=settings,
            session_id=request.session_id,
            workflow_name="echo",
            payload=payload,
        )
    except RuntimeError as exc:
        return N8nTestEchoResponse(status="error", workflow_name="echo", message=str(exc))

    return N8nTestEchoResponse(
        status="sent",
        workflow_name="echo",
        message="Đã gọi workflow n8n echo.",
        response_status=result.response_status,
    )
