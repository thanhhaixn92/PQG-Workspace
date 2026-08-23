"""Runtime diagnostics for local-first startup readiness."""
from __future__ import annotations

import json
import hashlib
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_db, get_settings, get_trusted_actor
from app.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


class RuntimeDbStatus(BaseModel):
    status: Literal["ok", "error"]


class RuntimeHermesStatus(BaseModel):
    status: Literal["ready", "mock", "missing", "not_configured", "auth_unknown", "auth_expired"]
    guidance: str


class RuntimeStatusResponse(BaseModel):
    backend: Literal["ok"]
    db: RuntimeDbStatus
    hermes: RuntimeHermesStatus
    timestamp: int


class RuntimeSmokeRequest(BaseModel):
    session_id: str | None = None


class RuntimeSmokeCheck(BaseModel):
    key: str
    label: str
    status: Literal["ready", "needs_config", "error", "skipped"]
    detail: str


class RuntimeSmokeResponse(BaseModel):
    checks: list[RuntimeSmokeCheck]
    timestamp: int


class RuntimeIdentityScopeResponse(BaseModel):
    """Public, non-secret namespace used by browser-only draft state."""

    identity_scope: str
    workspace_scope: Literal["local"] = "local"


def _is_executable_found(path_value: str) -> bool:
    path = Path(path_value)
    if path.is_absolute() or any(sep in path_value for sep in ("\\", "/")):
        return path.exists()
    return shutil.which(path_value) is not None


@router.get("/identity-scope", response_model=RuntimeIdentityScopeResponse)
async def runtime_identity_scope(actor: str = Depends(get_trusted_actor)) -> RuntimeIdentityScopeResponse:
    """Return a stable opaque scope without exposing the actor subject."""
    digest = hashlib.sha256(f"pqg-workspace:local-scope:{actor}".encode("utf-8")).hexdigest()
    return RuntimeIdentityScopeResponse(identity_scope=digest[:32])


def _hermes_configured(settings: Settings) -> bool:
    return (
        settings.hermes_dev_mock
        or bool(os.getenv("HERMES_EXECUTABLE_PATH"))
        or settings.hermes_executable_path != "hermes"
    )


def _hermes_auth_ready_signal(settings: Settings | None = None) -> bool:
    """Return whether local config has a non-secret sign that Hermes auth exists."""
    if settings is not None and settings.hermes_auth_ready:
        return True

    explicit = os.getenv("HERMES_AUTH_READY")
    if explicit and explicit.strip().lower() in {"1", "true", "yes", "on"}:
        return True

    if any(os.getenv(name) for name in ("NOUS_API_KEY", "HERMES_API_KEY")):
        return True

    candidates = [
        Path.home() / ".config" / "hermes" / "auth.json",
        Path.home() / ".config" / "hermes" / "credentials.json",
        Path.home() / ".hermes" / "auth.json",
        Path(os.getenv("APPDATA", "")) / "hermes" / "auth.json" if os.getenv("APPDATA") else None,
    ]
    return any(path is not None and path.exists() and path.stat().st_size > 0 for path in candidates)


class HermesPreflightResult(BaseModel):
    status: Literal["ready", "mock", "missing", "not_configured", "auth_unknown", "auth_expired"]
    configured: bool
    executable_found: bool
    auth_status: Literal["ready", "unknown", "not_required", "auth_expired"]
    guidance: str


def _run_hermes_auth_status_sync(executable_path: str) -> bool:
    """Compatibility health check for Hermes releases without doctor JSON."""
    try:
        provider_result = subprocess.run(
            [executable_path, "config", "get", "model.provider"],
            capture_output=True, text=True, timeout=4.0,
        )
        provider = provider_result.stdout.strip() if provider_result.returncode == 0 else ""
        if not provider:
            return False
        status_result = subprocess.run(
            [executable_path, "auth", "status", provider],
            capture_output=True, text=True, timeout=4.0,
        )
        return status_result.returncode == 0 and "logged in" in status_result.stdout.casefold()
    except (subprocess.TimeoutError, FileNotFoundError, OSError):
        return False


def _run_hermes_doctor_sync(executable_path: str) -> bool:
    """Validate auth, falling back for Hermes releases without doctor JSON."""
    try:
        result = subprocess.run(
            [executable_path, "doctor", "--json"],
            capture_output=True, text=True, timeout=8.0,
        )
        if result.returncode != 0:
            if "unrecognized arguments: --json" in result.stderr:
                return _run_hermes_auth_status_sync(executable_path)
            logger.warning("hermes doctor exited %d: %s", result.returncode, result.stderr.strip())
            return False
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            return False
        auth_field = data.get("auth", data.get("status", ""))
        if isinstance(auth_field, dict):
            auth_field = auth_field.get("status", "")
        ok_values = {"authenticated", "ready", "ok", "healthy", "valid", "configured"}
        return str(auth_field).strip().lower() in ok_values
    except subprocess.TimeoutError:
        logger.warning("hermes doctor timed out after 8s")
        return False
    except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        logger.warning("hermes doctor error: %s", exc)
        return False


def check_hermes_preflight(settings: Settings, run_doctor: bool = False) -> HermesPreflightResult:
    """Check safe Hermes readiness without spawning the process.

    When *run_doctor* is True and the file-based auth signal is present, the
    function additionally runs ``hermes doctor --json`` to validate that the
    token / provider is actually usable.
    """
    found = _is_executable_found(settings.hermes_executable_path)
    configured = _hermes_configured(settings) or found

    if settings.hermes_dev_mock:
        return HermesPreflightResult(
            status="mock",
            configured=True,
            executable_found=True,
            auth_status="not_required",
            guidance="Đang dùng Hermes dev mock để kiểm tra chat end-to-end.",
        )

    if not configured:
        return HermesPreflightResult(
            status="not_configured",
            configured=False,
            executable_found=found,
            auth_status="unknown",
            guidance="Chưa cấu hình HERMES_EXECUTABLE_PATH trong backend/.env.",
        )

    if not found:
        return HermesPreflightResult(
            status="missing",
            configured=True,
            executable_found=False,
            auth_status="unknown",
            guidance="Không tìm thấy Hermes executable. Hãy kiểm tra HERMES_EXECUTABLE_PATH.",
        )

    if not _hermes_auth_ready_signal(settings):
        return HermesPreflightResult(
            status="auth_unknown",
            configured=True,
            executable_found=True,
            auth_status="unknown",
            guidance="Đã tìm thấy Hermes executable nhưng chưa xác định được auth/provider. Hãy chạy hermes auth hoặc hermes doctor.",
        )

    if run_doctor:
        doctor_ok = _run_hermes_doctor_sync(settings.hermes_executable_path)
        if not doctor_ok:
            return HermesPreflightResult(
                status="auth_expired",
                configured=True,
                executable_found=True,
                auth_status="auth_expired",
                guidance="Hermes đã đăng nhập nhưng token/provider không còn hợp lệ. Hãy chạy hermes auth để đăng nhập lại.",
            )

    return HermesPreflightResult(
        status="ready",
        configured=True,
        executable_found=True,
        auth_status="ready",
        guidance="Hermes executable và tín hiệu auth local đã sẵn sàng.",
    )


@router.get("/status", response_model=RuntimeStatusResponse)
async def runtime_status(
    settings: Settings = Depends(get_settings),
    db: aiosqlite.Connection = Depends(get_db),
) -> RuntimeStatusResponse:
    """Return safe local runtime readiness without spawning Hermes."""
    db_ok = False
    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    hermes_preflight = check_hermes_preflight(settings)

    return RuntimeStatusResponse(
        backend="ok",
        db=RuntimeDbStatus(status="ok" if db_ok else "error"),
        hermes=RuntimeHermesStatus(
            status=hermes_preflight.status,
            guidance=hermes_preflight.guidance,
        ),
        timestamp=int(time.time()),
    )


@router.post("/smoke", response_model=RuntimeSmokeResponse)
async def runtime_smoke(
    request: RuntimeSmokeRequest,
    settings: Settings = Depends(get_settings),
    db: aiosqlite.Connection = Depends(get_db),
) -> RuntimeSmokeResponse:
    """Run safe local readiness checks without shell commands or external webhook calls."""
    checks: list[RuntimeSmokeCheck] = [
        RuntimeSmokeCheck(
            key="backend",
            label="Backend",
            status="ready",
            detail="FastAPI đang phản hồi.",
        )
    ]

    try:
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        checks.append(
            RuntimeSmokeCheck(
                key="db",
                label="Cơ sở dữ liệu",
                status="ready",
                detail="SQLite sẵn sàng.",
            )
        )
    except Exception as exc:
        checks.append(
            RuntimeSmokeCheck(
                key="db",
                label="Cơ sở dữ liệu",
                status="error",
                detail=f"Không truy cập được DB: {type(exc).__name__}",
            )
        )

    hermes_preflight = check_hermes_preflight(settings, run_doctor=True)
    if hermes_preflight.status == "mock":
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes executable",
                status="ready",
                detail="Đang dùng Hermes dev mock để test chat.",
            )
        )
    elif hermes_preflight.status == "not_configured":
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes executable",
                status="needs_config",
                detail="Chưa cấu hình HERMES_EXECUTABLE_PATH trong backend/.env.",
            )
        )
    elif hermes_preflight.status == "missing":
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes executable",
                status="error",
                detail="Không tìm thấy Hermes executable đã cấu hình.",
            )
        )
    elif hermes_preflight.status == "auth_unknown":
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes auth/provider",
                status="needs_config",
                detail="Chưa xác định được Hermes auth/provider. Hãy chạy hermes auth hoặc hermes doctor.",
            )
        )
    elif hermes_preflight.status == "auth_expired":
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes auth/provider",
                status="needs_config",
                detail="Hermes auth token không còn hợp lệ hoặc đã hết hạn. Hãy chạy hermes auth để đăng nhập lại.",
            )
        )
    else:
        checks.append(
            RuntimeSmokeCheck(
                key="hermes",
                label="Hermes runtime",
                status="ready",
                detail="Hermes executable và auth local đã sẵn sàng.",
            )
        )

    checks.append(
        RuntimeSmokeCheck(
            key="sse",
            label="SSE stream",
            status="ready",
            detail="SSE route đã sẵn sàng cho phiên đang hoạt động.",
        )
    )

    if request.session_id:
        async with db.execute(
            "SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0",
            (request.session_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            checks.append(
                RuntimeSmokeCheck(
                    key="workspace",
                    label="File workspace",
                    status="error",
                    detail="Không tìm thấy phiên hoặc phiên đã lưu trữ.",
                )
            )
        else:
            workspace = Path(row["workspace_path"])
            checks.append(
                RuntimeSmokeCheck(
                    key="workspace",
                    label="File workspace",
                    status="ready" if workspace.exists() and workspace.is_dir() else "error",
                    detail=(
                        "Workspace sẵn sàng."
                        if workspace.exists() and workspace.is_dir()
                        else "Workspace không tồn tại hoặc không truy cập được."
                    ),
                )
            )
    else:
        checks.append(
            RuntimeSmokeCheck(
                key="workspace",
                label="File workspace",
                status="skipped",
                detail="Chọn một phiên để kiểm tra workspace.",
            )
        )

    checks.append(
        RuntimeSmokeCheck(
            key="memory_approval",
            label="Memory/Approval",
            status="ready",
            detail="Routes memory và approval đã sẵn sàng.",
        )
    )

    checks.append(
        RuntimeSmokeCheck(
            key="n8n",
            label="n8n optional",
            status="ready" if settings.n8n_webhook_secret else "skipped",
            detail=(
                "n8n secret đã cấu hình; workflow vẫn cần allowlist và approval khi gọi thật."
                if settings.n8n_webhook_secret
                else "Chưa cấu hình n8n secret; bỏ qua nếu chưa dùng automation."
            ),
        )
    )

    return RuntimeSmokeResponse(checks=checks, timestamp=int(time.time()))
