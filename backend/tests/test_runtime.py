"""Tests for runtime readiness and dev mock chat."""
from __future__ import annotations

import asyncio

import aiosqlite
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


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
    assert data["db"]["path"].endswith("runtime_missing.db")
    assert data["hermes"]["status"] == "missing"
    assert data["hermes"]["configured"] is True
    assert data["hermes"]["executable_found"] is False
    assert data["hermes"]["auth_status"] == "unknown"
    assert isinstance(data["hermes"]["args"], list)
    assert "Không tìm thấy" in data["hermes"]["guidance"]
    assert "environment" in data


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
    assert data["hermes"]["dev_mock"] is True
    assert data["hermes"]["executable_found"] is True
    assert data["hermes"]["auth_status"] == "not_required"
    assert data["hermes"]["guidance"].startswith("Đang dùng Hermes dev mock")


def test_runtime_status_auth_unknown_is_not_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_AUTH_READY", raising=False)
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_auth_unknown.db"),
        hermes_executable_path="python",
        hermes_dev_mock=False,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/runtime/status")

    assert response.status_code == 200
    data = response.json()
    assert data["hermes"]["status"] == "auth_unknown"
    assert data["hermes"]["executable_found"] is True
    assert data["hermes"]["auth_status"] == "unknown"
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
    assert str(tmp_path) in checks["workspace"]["detail"]


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


def test_submit_prompt_blocks_when_auth_unknown(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HERMES_AUTH_READY", raising=False)
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    settings = Settings(
        db_path=str(tmp_path / "runtime_auth_block.db"),
        hermes_executable_path="python",
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
