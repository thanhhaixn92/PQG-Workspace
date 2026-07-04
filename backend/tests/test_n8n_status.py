"""Tests for safe n8n status endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.approvals import pending_approvals
from app.main import create_app
from app.settings import Settings


def test_n8n_status_does_not_expose_secret(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "n8n_status.db"),
        HERMES_N8N_WEBHOOK_SECRET="super-secret-value",
        n8n_allowed_workflows={"echo": "hermes/echo", "report": "ops/report"},
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/n8n/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["allowed_workflows"] == ["echo", "report"]
    assert "super-secret-value" not in response.text
    assert "secret đã cấu hình" in data["guidance"]


def test_n8n_status_optional_when_missing_secret(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "n8n_missing.db"),
        HERMES_N8N_WEBHOOK_SECRET="",
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.get("/api/n8n/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert "echo" in data["allowed_workflows"]
    assert "bỏ qua" in data["guidance"]


def test_n8n_test_echo_skips_when_missing_secret(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "n8n_echo_missing.db"),
        HERMES_N8N_WEBHOOK_SECRET="",
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.post("/api/n8n/test-echo", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert data["workflow_name"] == "echo"
    assert "not configured" in data["message"]


def test_n8n_test_echo_requires_session_when_configured(tmp_path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "n8n_echo_requires_session.db"),
        HERMES_N8N_WEBHOOK_SECRET="super-secret-value",
        n8n_allowed_workflows={"echo": "hermes-echo"},
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)

    with TestClient(app) as client:
        response = client.post("/api/n8n/test-echo", json={})

    assert response.status_code == 400
    assert "Cần chọn phiên" in response.json()["detail"]


@pytest.mark.asyncio
async def test_n8n_test_echo_success_with_approval(client, test_app, monkeypatch, tmp_path) -> None:
    import asyncio
    import httpx
    from app.dependencies import get_settings
    from app.db.connection import get_db_connection

    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    settings.n8n_webhook_secret = "super-secret-value"
    settings.n8n_allowed_workflows = {"echo": "hermes-echo"}

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    original_post = httpx.AsyncClient.post

    async def mock_post(self, url, *args, **kwargs):
        if "headers" not in kwargs:
            return await original_post(self, url, *args, **kwargs)
        assert "super-secret-value" == kwargs["headers"]["X-Hermes-Secret"]
        assert "hermes-echo" in str(url)
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    async def approve_delayed():
        for _ in range(30):
            await asyncio.sleep(0.1)
            if pending_approvals:
                approval_id = next(iter(pending_approvals))
                await client.post(f"/api/approvals/{approval_id}", json={"decision": "allow_once"})
                return

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = await client.post(
        "/api/sessions",
        json={"title": "n8n Echo", "workspace_path": str(workspace)},
    )
    session_id = session.json()["id"]

    pending_approvals.clear()
    approval_task = asyncio.create_task(approve_delayed())
    response = await client.post(
        "/api/n8n/test-echo",
        json={"session_id": session_id, "payload": {"secret_value": "do-not-log", "visible": True}},
    )
    await approval_task

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert data["response_status"] == 200

    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute(
            "SELECT payload_json FROM audit_events WHERE action = 'n8n.webhook.sent'"
        ) as cur:
            rows = await cur.fetchall()

    assert rows
    payload_json = rows[-1][0]
    assert "super-secret-value" not in payload_json
    assert "do-not-log" not in payload_json
    assert "secret_value" in payload_json
