from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.schemas import TelegramWebhookRequest, TelegramCallbackRequest, TelegramWebhookResponse, TelegramCallbackResponse
from app.dependencies import get_db, get_settings
from app.repositories.telegram_repository import TelegramCallbackTokenConflict, TelegramCallbackTokenExpired, TelegramCallbackTokenNotFound
from app.services.audit import log_audit_event
from app.services.telegram_service import TelegramService
from app.settings import Settings

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    conn=Depends(get_db),
) -> TelegramWebhookResponse:
    body = await request.body()
    signature = request.headers.get("X-HMAC-Signature", "")

    svc = TelegramService(conn, settings)
    if not svc.verify_hmac(body, signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    parsed = TelegramWebhookRequest.model_validate_json(body)
    user_id = str(parsed.from_id) if parsed.from_id else ""

    if not svc.check_allowlist(user_id):
        raise HTTPException(status_code=403, detail="Telegram user not in allowlist")

    if parsed.message_id:
        existing = await svc.check_idempotency(parsed.message_id)
        if existing:
            return TelegramWebhookResponse(
                status="duplicate",
                task_id=existing["task_id"],
                duplicate=True,
                callback_token=existing.get("callback_token"),
            )

    task, token = await svc.process_telegram_update(parsed)

    await log_audit_event(
        conn=conn,
        session_id=None,
        actor="telegram",
        action="telegram.webhook_received",
        target=task["id"],
        payload={
            "update_id": parsed.update_id,
            "message_id": parsed.message_id,
            "user_id": user_id,
            "duplicate": False,
        },
    )
    await conn.commit()

    return TelegramWebhookResponse(
        status="ok",
        task_id=task["id"],
        duplicate=False,
        callback_token=token,
    )


@router.post("/callback", response_model=TelegramCallbackResponse)
async def telegram_callback(
    request: Request,
    settings: Settings = Depends(get_settings),
    conn=Depends(get_db),
) -> TelegramCallbackResponse:
    body = await request.body()
    signature = request.headers.get("X-HMAC-Signature", "")

    svc = TelegramService(conn, settings)
    if not svc.verify_hmac(body, signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    parsed = TelegramCallbackRequest.model_validate_json(body)

    try:
        token_data = await svc.consume_callback_token(parsed.token)
    except TelegramCallbackTokenNotFound:
        raise HTTPException(status_code=404, detail="Callback token not found")
    except TelegramCallbackTokenConflict:
        raise HTTPException(status_code=409, detail="Reused callback token")
    except TelegramCallbackTokenExpired:
        raise HTTPException(status_code=410, detail="Expired callback token")

    await log_audit_event(
        conn=conn,
        session_id=None,
        actor="telegram",
        action="telegram.callback_received",
        target=token_data["task_id"],
        payload={
            "token": parsed.token,
            "action_type": token_data["action_type"],
        },
    )
    await conn.commit()

    return TelegramCallbackResponse(
        status="ok",
        action=token_data["action_type"],
        task_id=token_data["task_id"],
    )
