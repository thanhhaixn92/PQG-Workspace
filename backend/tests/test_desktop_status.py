"""Tests for the bounded, read-only Desktop status contract."""
from __future__ import annotations

import pytest

from app.dependencies import get_db


@pytest.mark.asyncio
async def test_desktop_status_reports_ready_with_only_safe_fields(client):
    response = await client.get("/api/desktop/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "status": "ready",
        "api_version": "v1",
        "backend_version": "2.2.0",
        "timestamp": data["timestamp"],
    }
    assert isinstance(data["timestamp"], int)
    assert data["timestamp"] > 0
    serialized = str(data).lower()
    for forbidden in ("path", "credential", "secret", "provider", "hermes", "gyo", "db"):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_desktop_status_fails_closed_when_its_db_dependency_fails(client, test_app):
    class BrokenDb:
        def execute(self, _query):
            raise RuntimeError("database adapter unavailable")

    async def broken_db():
        yield BrokenDb()

    test_app.dependency_overrides[get_db] = broken_db
    response = await client.get("/api/desktop/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["api_version"] == "v1"
    assert data["backend_version"] == "2.2.0"
    assert "database" not in str(data).lower()


@pytest.mark.asyncio
async def test_desktop_status_allows_only_configured_loopback_cors_origin(client):
    allowed = await client.options(
        "/api/desktop/v1/status",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    foreign = await client.options(
        "/api/desktop/v1/status",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert foreign.status_code == 400
    assert "access-control-allow-origin" not in foreign.headers
