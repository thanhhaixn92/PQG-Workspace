from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Optional

from app.repositories.idempotency_repository import IdempotencyConflict, IdempotencyRepository


class IdempotencyService:

    def __init__(self, db) -> None:
        self._repo = IdempotencyRepository(db)

    async def execute_idempotent(
        self,
        key: str,
        operation: Callable,
        ttl_seconds: int = 3600,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        request_hash: Optional[str] = None,
    ) -> tuple[Any, int, bool]:
        existing = await self._repo.check_key(key, request_hash=request_hash)
        if existing is not None:
            return json.loads(existing["response_json"]), existing["status_code"], True

        result = await operation(*(args or ()), **(kwargs or {}))
        response_json = json.dumps(result, default=str)
        status_code = 200 if result else 201
        await self._repo.set(key, response_json, status_code, ttl_seconds, request_hash=request_hash)
        return result, status_code, False
