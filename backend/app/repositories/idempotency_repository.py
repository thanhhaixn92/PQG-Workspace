from __future__ import annotations

import time
from typing import Optional

import aiosqlite


class IdempotencyConflict(Exception):
    pass


class IdempotencyRepository:

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def get(self, key: str) -> Optional[dict]:
        async with self._db.execute(
            "SELECT * FROM idempotency_records WHERE key = ? AND expires_at > ?",
            (key, int(time.time())),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def check_key(
        self, key: str, request_hash: Optional[str] = None
    ) -> Optional[dict]:
        row = await self.get(key)
        if row is None:
            return None
        if request_hash is not None and row.get("request_hash") is not None and row["request_hash"] != request_hash:
            raise IdempotencyConflict(f"Idempotency key {key} already used with different payload")
        return row

    async def set(
        self,
        key: str,
        response_json: str,
        status_code: int,
        ttl_seconds: int = 3600,
        request_hash: Optional[str] = None,
    ) -> None:
        now = int(time.time())
        await self._db.execute(
            """INSERT OR REPLACE INTO idempotency_records (key, request_hash, response_json, status_code, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (key, request_hash, response_json, status_code, now, now + ttl_seconds),
        )

    async def cleanup_expired(self) -> int:
        now = int(time.time())
        async with self._db.execute(
            "DELETE FROM idempotency_records WHERE expires_at <= ?", (now,)
        ) as cur:
            return cur.rowcount
