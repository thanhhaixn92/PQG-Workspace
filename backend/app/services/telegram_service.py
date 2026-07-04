from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional

from app.api.schemas import TelegramWebhookRequest
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.telegram_repository import TelegramRepository
from app.services.task_service import TaskService
from app.settings import Settings


class TelegramService:

    def __init__(
        self,
        db,
        settings: Settings,
        task_service: Optional[TaskService] = None,
        telegram_repo: Optional[TelegramRepository] = None,
        idempotency_repo: Optional[IdempotencyRepository] = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._task_service = task_service or TaskService(db)
        self._telegram_repo = telegram_repo or TelegramRepository(db)
        self._idempotency = idempotency_repo or IdempotencyRepository(db)

    def verify_hmac(self, body: bytes, signature: str) -> bool:
        secret = self._settings.telegram_webhook_secret
        if not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        expected_header = f"sha256={expected}"
        return hmac.compare_digest(expected_header, signature.strip())

    def check_allowlist(self, user_id: str) -> bool:
        raw = self._settings.telegram_allowlist
        if not raw:
            return True
        allowed = [uid.strip() for uid in raw.split(",") if uid.strip()]
        return user_id in allowed

    async def check_idempotency(self, message_id: str) -> Optional[dict]:
        idem_key = f"telegram-msg-{message_id}"
        row = await self._idempotency.get(idem_key)
        if row is not None:
            return json.loads(row["response_json"])
        return None

    async def process_telegram_update(self, parsed: TelegramWebhookRequest) -> tuple[dict, Optional[str]]:
        task, _ = await self._task_service.create_task(
            session_id=None,
            title=parsed.text[:200] if parsed.text else f"Telegram message {parsed.message_id}",
            description=json.dumps({
                "source": "telegram",
                "update_id": parsed.update_id,
                "message_id": parsed.message_id,
                "from_id": parsed.from_id,
                "text": parsed.text,
            }, ensure_ascii=False),
            task_type="telegram",
        )

        if parsed.message_id:
            idem_key = f"telegram-msg-{parsed.message_id}"
            response_json = json.dumps({"task_id": task["id"]})
            await self._idempotency.set(
                idem_key, response_json, 200,
                ttl_seconds=86400,
            )

        if parsed.await_callback:
            token_record = await self._telegram_repo.insert_callback_token(
                task_id=task["id"],
                action_type="approval",
                ttl_seconds=self._settings.telegram_callback_token_ttl_seconds,
            )
            return task, token_record["token"]

        return task, None

    async def consume_callback_token(self, token: str) -> dict:
        return await self._telegram_repo.consume_callback_token(token)
