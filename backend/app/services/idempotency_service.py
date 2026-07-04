from __future__ import annotations

import json
from typing import Any, Callable, Optional

from app.repositories.idempotency_repository import IdempotencyRepository


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
    ) -> tuple[Any, int, bool]:
        existing = await self._repo.get(key)
        if existing is not None:
            return json.loads(existing["response_json"]), existing["status_code"], True

        result = await operation(*(args or ()), **(kwargs or {}))
        response_json = json.dumps(result, default=str)
        status_code = 200 if result else 201
        await self._repo.set(key, response_json, status_code, ttl_seconds)
        return result, status_code, False
