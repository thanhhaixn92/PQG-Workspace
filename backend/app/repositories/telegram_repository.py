from __future__ import annotations

import time
import uuid

import aiosqlite


class TelegramCallbackTokenConflict(Exception):
    pass


class TelegramCallbackTokenExpired(Exception):
    pass


class TelegramCallbackTokenNotFound(Exception):
    pass


class TelegramRepository:

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_callback_token(
        self,
        task_id: str,
        action_type: str,
        ttl_seconds: int = 3600,
    ) -> dict:
        token = f"cb-{uuid.uuid4().hex[:20]}"
        now = int(time.time())
        expires_at = now + ttl_seconds
        await self._db.execute(
            """
            INSERT INTO telegram_callback_tokens (token, task_id, action_type, status, expires_at, created_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (token, task_id, action_type, expires_at, now),
        )
        return {
            "token": token,
            "task_id": task_id,
            "action_type": action_type,
            "status": "pending",
            "expires_at": expires_at,
            "created_at": now,
        }

    async def get_callback_token(self, token: str) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM telegram_callback_tokens WHERE token = ?",
            (token,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def consume_callback_token(self, token: str) -> dict:
        async with self._db.execute(
            "SELECT * FROM telegram_callback_tokens WHERE token = ?",
            (token,),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            raise TelegramCallbackTokenNotFound(f"Callback token not found: {token}")

        record = dict(row)
        now = int(time.time())

        if record["status"] == "used":
            raise TelegramCallbackTokenConflict(f"Callback token already used: {token}")

        if now > record["expires_at"]:
            raise TelegramCallbackTokenExpired(f"Callback token expired: {token}")

        await self._db.execute(
            "UPDATE telegram_callback_tokens SET status = 'used' WHERE token = ?",
            (token,),
        )
        return record
