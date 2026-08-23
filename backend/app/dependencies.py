"""FastAPI dependency providers.

Provides:
  - get_settings      - application settings (overridable in tests)
  - get_db            - per-request DB connection (overridable in tests)
  - get_trusted_actor - actor subject supplied by trusted server authentication
  - require_interactive_local_user_admin - user-only local admin boundary

All routes should declare these as FastAPI dependencies rather than
importing module-level singletons directly.  This makes test overrides
straightforward via ``app.dependency_overrides``.
"""
from __future__ import annotations

from typing import AsyncGenerator, Any
from urllib.parse import urlparse

import aiosqlite
from fastapi import Depends, HTTPException, Request

from app.db.connection import get_db_connection
from app.settings import Settings, get_settings as _get_settings

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def get_settings() -> Settings:
    """Dependency: returns the application Settings instance."""
    return _get_settings()


async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency: yields an open DB connection with PRAGMAs applied.

    Each request gets its own connection; it is closed after the request.
    ``PRAGMA foreign_keys = ON`` is set by the connection factory on
    every connection - not just during migration.
    """
    async with get_db_connection(settings.db_path_resolved) as conn:
        yield conn


def get_trusted_actor(request: Request) -> str:
    """Return the actor set by a trusted server-side authentication layer.

    ``X-Actor`` is deliberately never read here: a browser-controlled header is
    not an authenticated identity.  Until an authentication middleware sets a
    non-empty ``request.state.actor_subject``, governed writes fail closed with
    ``IDENTITY_ENFORCEMENT_INSUFFICIENT``.  Tests may override this dependency.
    """
    actor = getattr(request.state, "actor_subject", None)
    if not isinstance(actor, str) or not actor.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "IDENTITY_ENFORCEMENT_INSUFFICIENT", "message": "Authenticated actor identity required"},
        )
    return actor.strip()


def _canonical_loopback_origin(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.rstrip("/")
    parsed = urlparse(candidate)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        return None
    return candidate


def require_interactive_local_user_admin(
    request: Request,
    actor: str = Depends(get_trusted_actor),
    settings: Settings = Depends(get_settings),
) -> str:
    """Require a direct, loopback browser-originated user-admin request.

    This dependency is intentionally stricter than the general trusted actor:
    Foundation/Module administration is constitutionally user-only.  A server
    process or agent call that lacks a browser Origin fails closed even if it
    happens to originate on localhost.  The Origin must be either an exact
    configured Vite/UI origin or the loopback backend origin itself (for a
    future same-origin packaged UI).  ``Sec-Fetch-Site`` is enforced when a
    browser supplies it but is not treated as an identity source.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=403,
            detail={"code": "USER_ADMIN_LOCAL_ONLY", "message": "User administration is restricted to the local interface"},
        )

    origin = _canonical_loopback_origin(request.headers.get("origin"))
    configured_origins = {
        normalized
        for configured in settings.cors_origins
        if (normalized := _canonical_loopback_origin(configured)) is not None
    }
    host_header = request.headers.get("host")
    if host_header:
        self_origin = _canonical_loopback_origin(f"{request.url.scheme}://{host_header}")
        if self_origin is not None:
            configured_origins.add(self_origin)

    if origin is None or origin not in configured_origins:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "USER_ADMIN_INTERACTIVE_REQUIRED",
                "message": "Foundation administration requires an approved local browser Origin",
            },
        )

    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in {"same-origin", "same-site"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "USER_ADMIN_CROSS_SITE_DENIED", "message": "Cross-site administration is not allowed"},
        )
    return actor


def get_gyo_orchestrator(request: Request) -> Any:
    """Dependency: returns the native GYO provider orchestrator from app state."""
    return request.app.state.gyo_orchestrator
