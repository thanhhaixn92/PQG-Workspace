"""Deprecation middleware and metrics tracking for legacy API endpoints.

Usage
-----
Add to FastAPI middleware stack in create_app()::

    from app.services.deprecation import DeprecationMiddleware
    app.add_middleware(DeprecationMiddleware)

Then query metrics at ``GET /api/metrics/deprecated``.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from threading import Lock
from typing import Any

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Deprecated route patterns – matched against request URL paths.
# Add new patterns here as endpoints are superseded.
# ---------------------------------------------------------------------------
DEPRECATED_ROUTE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^/api/sessions/[^/]+/task-runs/latest$"),
    re.compile(r"^/api/sessions/[^/]+/task-runs/[^/]+$"),
    re.compile(r"^/api/sessions/[^/]+/curate$"),
]


class DeprecationMetrics:
    """Thread-safe, in-memory metrics for deprecated-route hits."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"hits": 0, "last_accessed": 0}
        )

    def record_hit(self, route_pattern: str) -> None:
        with self._lock:
            record = self._data[route_pattern]
            record["hits"] += 1
            record["last_accessed"] = int(time.time())

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(sorted(self._data.items()))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def no_active_consumers(self, grace_hours: int = 24) -> bool:
        now = int(time.time())
        cutoff = now - (grace_hours * 3600)
        with self._lock:
            return all(
                rec["last_accessed"] < cutoff
                for rec in self._data.values()
            )


metrics = DeprecationMetrics()


class DeprecationMiddleware:
    """ASGI middleware that injects ``X-Deprecated: true`` on legacy routes.

    Also increments an in-memory hit counter keyed by the matched pattern,
    enabling operators to verify that legacy consumers have migrated.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        matched_pattern = self._match_deprecated(path)

        if matched_pattern is None:
            await self.app(scope, receive, send)
            return

        metrics.record_hit(matched_pattern)

        already_sent: list[bool] = [False]

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start" and not already_sent[0]:
                already_sent[0] = True
                headers: list[tuple[bytes, bytes]] = message.get("headers", [])
                headers = [
                    h for h in headers
                    if h[0].lower() != b"x-deprecated"
                ]
                headers.append((b"x-deprecated", b"true"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

    @staticmethod
    def _match_deprecated(path: str) -> str | None:
        for pattern in DEPRECATED_ROUTE_PATTERNS:
            if pattern.search(path):
                return pattern.pattern
        return None


def is_middleware_active(app: Any) -> bool:
    """Return True if DeprecationMiddleware is installed on *app*."""
    from fastapi import FastAPI
    if isinstance(app, FastAPI) and hasattr(app, "user_middleware"):
        return any(
            m.cls is DeprecationMiddleware
            for m in app.user_middleware
        )
    return False
