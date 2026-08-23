"""Test: GET /health endpoint.

Acceptance criteria (Phase 0):
- Returns HTTP 200.
- Body contains ``status: ok``.
- Body contains correct version string.
- Response includes ``db`` and ``timestamp`` fields.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_status_ok(client):
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok", f"Expected 'ok', got: {data}"


@pytest.mark.asyncio
async def test_health_contains_version(client):
    response = await client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] == "2.2.0"


@pytest.mark.asyncio
async def test_health_db_ok(client):
    response = await client.get("/health")
    data = response.json()
    assert data.get("db") == "ok"


@pytest.mark.asyncio
async def test_health_has_timestamp(client):
    response = await client.get("/health")
    data = response.json()
    assert "timestamp" in data
    assert isinstance(data["timestamp"], int)
    assert data["timestamp"] > 0
