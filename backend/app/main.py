"""FastAPI application factory.

Architecture notes
-------------------
* ``lifespan`` handles startup (DB migration) and shutdown cleanup.
* CORS origins come from Settings (env-configurable, never wildcard).
* ``GET /health`` checks only the app layer (DB ping) - it does NOT
  depend on Hermes being installed or running.  Hermes unavailability
  is a runtime concern for Phase 1.
* Routes are registered inline for Phase 0 (no router needed yet).
  Phase 1 will move them to ``app/api/`` sub-modules.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.sessions import router as sessions_router
from app.api.files import router as files_router
from app.api.approvals import router as approvals_router
from app.api.skills import router as skills_router
from app.api.memory import router as memory_router
from app.api.runtime import router as runtime_router
from app.api.local_data import router as local_data_router
from app.api.n8n import router as n8n_router
from app.api.tasks import router as tasks_router
from app.api.telegram import router as telegram_router
from app.db.migrations import run_migrations
from app.dependencies import get_db, get_settings
from app.services.deprecation import DeprecationMiddleware, metrics
from app.services.hermes_client import HermesClientManager
from app.services.outbox_dispatcher import run_outbox_dispatcher_loop
from app.services.task_recovery import recover_stale_task_runs
from app.settings import Settings, get_settings as _get_settings
from app.mcp.server import setup_mcp, mcp_session_id_var

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Factory function that creates and configures the FastAPI application."""
    settings = settings_override or _get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan: run migrations on startup, clean up on shutdown."""
        logging.basicConfig(level=settings.log_level.upper())
        logger.info("Starting Hermes Local Stack backend v%s", APP_VERSION)
        logger.info("DB path: %s", settings.db_path_resolved)

        await run_migrations(settings.db_path_resolved)
        logger.info("DB ready.")
        recovered_tasks = await recover_stale_task_runs(settings.db_path_resolved)
        if recovered_tasks:
            logger.warning("Recovered %s stale task run(s).", recovered_tasks)

        # Initialize Hermes client
        client_manager = HermesClientManager(settings)
        app.state.hermes_client = client_manager

        # Outbox dispatcher background worker (if enabled)
        outbox_dispatcher_stop: asyncio.Event | None = None
        outbox_dispatcher_task: asyncio.Task[None] | None = None
        if settings.outbox_dispatcher_enabled:
            outbox_dispatcher_stop = asyncio.Event()
            outbox_dispatcher_task = asyncio.create_task(
                run_outbox_dispatcher_loop(settings, outbox_dispatcher_stop)
            )
            logger.info("Outbox dispatcher background task started (poll interval %.1fs).",
                        settings.outbox_dispatcher_poll_seconds)

        yield  # Application runs here.

        # Shutdown: stop outbox dispatcher first, then Hermes client.
        if outbox_dispatcher_stop is not None:
            outbox_dispatcher_stop.set()
        if outbox_dispatcher_task is not None:
            await outbox_dispatcher_task
            logger.info("Outbox dispatcher stopped.")
        await client_manager.stop()
        logger.info("Shutting down Hermes Local Stack backend.")

    app = FastAPI(
        title="Hermes Local Stack",
        version=APP_VERSION,
        description="Local-first AI office assistant backend.",
        lifespan=lifespan,
    )

    if settings_override:
        app.dependency_overrides[get_settings] = lambda: settings_override

    # CORS - exact origins from settings; never wildcard '*'.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Deprecation header injection for legacy routes.
    app.add_middleware(DeprecationMiddleware)

    # Include API Routers
    app.include_router(sessions_router)
    app.include_router(files_router)
    app.include_router(approvals_router)
    app.include_router(skills_router, prefix="/api/skills", tags=["skills"])
    app.include_router(memory_router, prefix="/api/memory", tags=["memory"])
    app.include_router(runtime_router)
    app.include_router(local_data_router)
    app.include_router(n8n_router)
    app.include_router(tasks_router)
    app.include_router(telegram_router)

    # MCP Integration
    setup_mcp(app)
    
    @app.middleware("http")
    async def extract_mcp_session_id(request: Request, call_next):
        """Extract session_id from header (or query) for MCP context, validate it, and enforce localhost."""
        is_mcp_route = request.url.path.startswith("/mcp") or request.url.path.startswith("/sse")
        
        if is_mcp_route:
            # 1. Localhost enforcement
            client_host = request.client.host if request.client else ""
            allowed_hosts = ("127.0.0.1", "::1", "localhost")
            if client_host not in allowed_hosts:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=403, content={"detail": "MCP access restricted to localhost"})
                
            # 2. Extract session_id
            session_id = request.headers.get("x-session-id")
            if not session_id and request.url.path.startswith("/mcp"):
                session_id = request.query_params.get("session_id")
                
            if not session_id:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Missing session_id"})
                
            # 3. Validate session_id has an active task
            settings = request.app.dependency_overrides.get(get_settings, _get_settings)()
            from app.db.connection import get_db_connection
            is_active = False
            async with get_db_connection(settings.db_path_resolved) as db:
                async with db.execute(
                    "SELECT 1 FROM task_runs WHERE session_id = ? AND status = 'running'",
                    (session_id,)
                ) as cursor:
                    if await cursor.fetchone():
                        is_active = True
                        
            if not is_active:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=403, content={"detail": "Session is not active or does not exist"})
                
            # 4. Bind session_id securely
            token = mcp_session_id_var.set(session_id)
            try:
                response = await call_next(request)
            finally:
                mcp_session_id_var.reset(token)
            return response
            
        else:
            return await call_next(request)

    # ------------------------------------------------------------------ #
    # Routes - Phase 0
    # ------------------------------------------------------------------ #

    @app.get("/api/metrics/deprecated", tags=["meta"])
    async def deprecated_route_metrics() -> dict:
        """Return hit-count metrics for deprecated legacy routes.

        Returns a dict keyed by route pattern, where each value contains
        ``hits`` (total requests) and ``last_accessed`` (Unix timestamp).
        Useful for verifying that legacy consumers have migrated before
        removing deprecated endpoints.
        """
        return metrics.snapshot()

    @app.get("/health", tags=["meta"])
    async def health(
        settings: Settings = Depends(get_settings),
        db: aiosqlite.Connection = Depends(get_db),
    ) -> dict[str, Any]:
        """Return application health.

        Checks:
        - DB connectivity (lightweight SELECT 1).
        Does NOT check Hermes availability - Hermes is not a Phase 0
        dependency and its absence must not make the health route fail.
        """
        db_ok = False
        try:
            async with db.execute("SELECT 1") as cursor:
                await cursor.fetchone()
            db_ok = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB health check failed: %s", exc)

        return {
            "status": "ok" if db_ok else "degraded",
            "version": APP_VERSION,
            "db": "ok" if db_ok else "error",
            "timestamp": int(time.time()),
        }

    return app


# Module-level app instance used by uvicorn.
app = create_app()
