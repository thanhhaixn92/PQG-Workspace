"""Read-only status contract for the first-party PQG Desktop client."""
from __future__ import annotations

import logging
import time
from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_db
from app.version import APP_VERSION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/desktop/v1", tags=["desktop"])


class DesktopStatusResponse(BaseModel):
    """Non-sensitive readiness information for a loopback Desktop integration."""

    status: Literal["ready", "degraded"]
    api_version: Literal["v1"] = "v1"
    backend_version: str
    timestamp: int


@router.get("/status", response_model=DesktopStatusResponse)
async def desktop_status(
    db: aiosqlite.Connection = Depends(get_db),
) -> DesktopStatusResponse:
    """Report whether the backend can serve Desktop requests without exposing internals.

    This endpoint performs no mutation and deliberately returns no paths,
    credentials, provider state, user data, or GYO/Hermes runtime details.
    """
    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - status must fail closed for any DB adapter failure.
        logger.warning("Desktop status database check failed: %s", type(exc).__name__)
        return DesktopStatusResponse(
            status="degraded",
            backend_version=APP_VERSION,
            timestamp=int(time.time()),
        )
    return DesktopStatusResponse(
        status="ready",
        backend_version=APP_VERSION,
        timestamp=int(time.time()),
    )
