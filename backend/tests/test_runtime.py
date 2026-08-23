"""Tests for runtime readiness and dev mock chat."""
from __future__ import annotations

import asyncio
import subprocess

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.api.runtime import _run_hermes_doctor_sync
from app.api.runtime import check_hermes_preflight
from app.api.model_config import get_model_config


def test_hermes_preflight_falls_back_when_doctor_json_is_unsupported(monkeypatch) -> None:
    """Hermes 0.19.x exposes provider auth status but not `doctor --json`."""
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[1:] == ["doctor", "--json"]:
            return subprocess.CompletedProcess(args, 2, "", "unrecognized arguments: --json")
        if args[1:] == ["config", "get", "model.provider"]:
            return subprocess.CompletedProcess(args, 0, "openai-codex\n", "")
        if args[1:] == ["auth", "status", "openai-codex"]:
            return subprocess.CompletedProcess(args, 0, "openai-codex: logged in\n", "")
        raise AssertionError(args)

    monkeypatch.setattr("app.api.runtime.subprocess.run", fake_run)
    assert _run_hermes_doctor_sync("hermes") is True
    assert calls == [
        ["hermes", "doctor", "--json"],
        ["hermes", "config", "get", "model.provider"],
        ["hermes", "auth", "status", "openai-codex"],
    ]


def test_explicit_nonsecret_auth_ready_setting_marks_preflight_ready(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime_explicit_auth.db"),
        hermes_executable_path="python",
        hermes_auth_ready=True,
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    preflight = check_hermes_preflight(settings)
    assert preflight.status == "ready"
    assert preflight.auth_status == "ready"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Superseded Hermes config signal; native GYO provider-profile tests cover the new contract")
async def test_model_config_uses_the_same_safe_auth_signal_as_runtime(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "model_status.db"),
        hermes_executable_path="python",
        hermes_auth_ready=True,
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    status = await get_model_config(settings)
    assert status.auth_ready is True


def test_runtime_status_missing_hermes(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_EXECUTABLE_PATH", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_missing.db"),
        hermes_executable_path="does-not-exist",
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/runtime/status")

    assert response.status_code == 200
    data = response.json()
    assert data["backend"] == "ok"
    assert data["db"]["status"] == "ok"
    assert data["hermes"]["status"] == "missing"
    assert "Không tìm thấy" in data["hermes"]["guidance"]
    serialized = str(data)
    assert "runtime_missing.db" not in serialized
    assert "executable_path" not in data["hermes"]


def test_runtime_status_mock_mode(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime_mock.db"),
        hermes_dev_mock=True,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/runtime/status")

    assert response.status_code == 200
    data = response.json()
    assert data["hermes"]["status"] == "mock"
    assert data["hermes"]["guidance"].startswith("Đang dùng Hermes dev mock")


def test_runtime_status_auth_unknown_is_not_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_AUTH_READY", raising=False)
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_auth_unknown.db"),
        hermes_executable_path="python",
        hermes_auth_ready=False,
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/runtime/status")

    assert response.status_code == 200
    data = response.json()
    assert data["hermes"]["status"] == "auth_unknown"
    assert "hermes auth" in data["hermes"]["guidance"]


def test_runtime_smoke_without_optional_integrations(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_EXECUTABLE_PATH", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_smoke.db"),
        hermes_executable_path="does-not-exist",
        hermes_dev_mock=False,
        n8n_webhook_secret="",
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.post("/api/runtime/smoke", json={})

    assert response.status_code == 200
    data = response.json()
    checks = {item["key"]: item for item in data["checks"]}
    assert checks["backend"]["status"] == "ready"
    assert checks["db"]["status"] == "ready"
    assert checks["hermes"]["status"] == "error"
    assert checks["workspace"]["status"] == "skipped"
    assert checks["n8n"]["status"] == "skipped"


def test_runtime_smoke_checks_session_workspace(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime_smoke_workspace.db"),
        hermes_dev_mock=True,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        session_resp = client.post(
            "/api/sessions",
            json={"title": "Workspace Smoke", "workspace_path": str(tmp_path)},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        response = client.post("/api/runtime/smoke", json={"session_id": session_id})

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    assert checks["hermes"]["status"] == "ready"
    assert checks["workspace"]["status"] == "ready"
    assert str(tmp_path) not in checks["workspace"]["detail"]


@pytest.mark.skip(reason="Superseded Hermes dev mock; native GYO fake-provider stream coverage is in test_gyo_provider_core")
def test_submit_prompt_with_dev_mock_streams_and_completes(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "runtime_mock_prompt.db"),
        hermes_dev_mock=True,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        session_resp = client.post(
            "/api/sessions",
            json={"title": "Mock Chat", "workspace_path": str(tmp_path)},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        prompt_resp = client.post(
            f"/api/sessions/{session_id}/prompt",
            json={"prompt": "Xin chào"},
        )
        assert prompt_resp.status_code == 202
        task_id = prompt_resp.json()["id"]

        event_names: list[str] = []
        payloads: list[str] = []
        with client.stream("GET", f"/api/sessions/{session_id}/events") as event_resp:
            for line in event_resp.iter_lines():
                if line.startswith("event: "):
                    event_names.append(line[7:])
                if line.startswith("data: "):
                    payloads.append(line[6:])
                if line.startswith("event: done"):
                    break

        assert "token" in event_names
        assert "tool_call" in event_names
        assert "done" in event_names
        assert any("Hermes dev mock" in payload for payload in payloads)

        async def check_db() -> None:
            await asyncio.sleep(0.1)
            async with aiosqlite.connect(settings.db_path_resolved) as db:
                async with db.execute(
                    "SELECT status FROM task_runs WHERE id = ?",
                    (task_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    assert row[0] == "completed"

        asyncio.run(check_db())


@pytest.mark.skip(reason="Superseded Hermes auth preflight; GYO fails safely from provider configuration")
def test_submit_prompt_blocks_when_auth_unknown(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_AUTH_READY", raising=False)
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_auth_block.db"),
        hermes_executable_path="python",
        hermes_auth_ready=False,
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        session_resp = client.post(
            "/api/sessions",
            json={"title": "Auth Block", "workspace_path": str(tmp_path)},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        prompt_resp = client.post(
            f"/api/sessions/{session_id}/prompt",
            json={"prompt": "Xin chào"},
        )

    assert prompt_resp.status_code == 503
    assert "Hermes cần đăng nhập" in prompt_resp.json()["detail"]

    async def check_db() -> None:
        async with aiosqlite.connect(settings.db_path_resolved) as db:
            async with db.execute("SELECT COUNT(*) FROM task_runs WHERE session_id = ?", (session_id,)) as cursor:
                row = await cursor.fetchone()
                assert row[0] == 0
            async with db.execute(
                "SELECT action FROM audit_events WHERE session_id = ?",
                (session_id,),
            ) as cursor:
                actions = [row[0] for row in await cursor.fetchall()]
                assert "runtime.preflight_blocked" in actions

    asyncio.run(check_db())
