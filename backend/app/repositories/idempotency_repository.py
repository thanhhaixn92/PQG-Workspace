from __future__ import annotations

import time
import hashlib
import json
from typing import Optional

import aiosqlite


class IdempotencyConflict(Exception):
    pass


class IdempotencyInProgress(Exception):
    pass


class IdempotencyFailed(Exception):
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

    @staticmethod
    def operation_identity(actor: str, operation: str, scope: str, client_key: str) -> str:
        """Return an opaque, stable identity for a caller-owned operation key."""
        raw = "\x1f".join((actor, operation, scope, client_key)).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    async def claim_operation(
        self,
        *,
        actor: str,
        operation: str,
        scope: str,
        client_key: str,
        request_hash: str,
        ttl_seconds: int = 3600,
    ) -> tuple[dict, bool]:
        """Atomically reserve an operation before its side effect begins.

        The commit is intentional: competing HTTP requests use separate SQLite
        connections and must observe ``processing`` before the first request
        performs the side effect.
        """
        now = int(time.time())
        identity = self.operation_identity(actor, operation, scope, client_key)
        # Reclaiming an expired identity and inserting its successor must be one
        # transaction. Otherwise two retries can both observe the stale row and
        # execute the protected side effect.
        await self._db.execute("BEGIN IMMEDIATE")
        try:
            await self._db.execute(
                "DELETE FROM operation_claims WHERE identity = ? AND expires_at <= ?",
                (identity, now),
            )
            await self._db.execute(
                """INSERT OR IGNORE INTO operation_claims
                   (identity, actor, operation, scope, client_key, request_hash, state,
                    response_json, status_code, created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'processing', '{}', 202, ?, ?, ?)""",
                (identity, actor, operation, scope, client_key, request_hash, now, now, now + ttl_seconds),
            )
            async with self._db.execute("SELECT changes()") as cur:
                inserted = bool((await cur.fetchone())[0])
            async with self._db.execute(
                "SELECT * FROM operation_claims WHERE identity = ?", (identity,)
            ) as cur:
                row = await cur.fetchone()
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise
        if row is None:
            raise RuntimeError("Operation claim was not persisted")
        claim = dict(row)
        if claim["request_hash"] != request_hash:
            raise IdempotencyConflict("Idempotency key already used with different payload")
        return claim, inserted

    async def finalize_operation(
        self,
        claim: dict,
        *,
        response: dict,
        status_code: int,
        resource_id: str | None = None,
    ) -> None:
        now = int(time.time())
        await self._db.execute(
            """UPDATE operation_claims
               SET state = 'completed', response_json = ?, status_code = ?, resource_id = ?,
                   error_code = NULL, updated_at = ?
               WHERE identity = ? AND state = 'processing'""",
            (json.dumps(response, default=str), status_code, resource_id, now, claim["identity"]),
        )
        async with self._db.execute("SELECT changes()") as cur:
            changed = (await cur.fetchone())[0]
        if changed != 1:
            raise IdempotencyInProgress("Operation claim is no longer owned by this request")
        await self._db.commit()

    async def fail_operation(self, claim: dict, error_code: str = "operation_failed") -> None:
        now = int(time.time())
        await self._db.execute(
            """UPDATE operation_claims
               SET state = 'failed', status_code = 500, error_code = ?, updated_at = ?
               WHERE identity = ? AND state = 'processing'""",
            (error_code, now, claim["identity"]),
        )
        await self._db.commit()
