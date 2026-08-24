"""Tests for CP10 DeprecationMiddleware: X-Deprecated header and metrics."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.deprecation import metrics, is_middleware_active


@pytest.mark.asyncio
async def test_middleware_is_registered(test_app) -> None:
    assert is_middleware_active(test_app)


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_empty(client: AsyncClient) -> None:
    metrics.clear()
    resp = await client.get("/api/metrics/deprecated")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_deprecated_task_runs_latest_has_header(client: AsyncClient) -> None:
    # Create a session first.
    create = await client.post("/api/sessions", json={"title": "t"})
    assert create.status_code == 201
    sid = create.json()["id"]

    resp = await client.get(f"/api/sessions/{sid}/task-runs/latest")
    assert resp.headers.get("x-deprecated") == "true"


@pytest.mark.asyncio
async def test_deprecated_task_runs_by_id_has_header(client: AsyncClient) -> None:
    create = await client.post("/api/sessions", json={"title": "t"})
    sid = create.json()["id"]

    resp = await client.get(f"/api/sessions/{sid}/task-runs/nonexistent")
    assert resp.status_code == 404
    assert resp.headers.get("x-deprecated") == "true"


@pytest.mark.asyncio
async def test_deprecated_curate_has_header(client: AsyncClient) -> None:
    create = await client.post("/api/sessions", json={"title": "t"})
    sid = create.json()["id"]

    resp = await client.post(f"/api/sessions/{sid}/curate")
    assert resp.headers.get("x-deprecated") == "true"


@pytest.mark.asyncio
async def test_active_health_no_deprecated_header(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-deprecated") is None


@pytest.mark.asyncio
async def test_active_sessions_crud_no_deprecated_header(client: AsyncClient) -> None:
    resp = await client.post("/api/sessions", json={"title": "t2"})
    assert resp.status_code == 201
    assert resp.headers.get("x-deprecated") is None

    sid = resp.json()["id"]
    resp2 = await client.get("/api/sessions")
    assert resp2.headers.get("x-deprecated") is None

    resp3 = await client.patch(f"/api/sessions/{sid}", json={"title": "u2"})
    assert resp3.headers.get("x-deprecated") is None


@pytest.mark.asyncio
async def test_metrics_increment_on_hit(client: AsyncClient) -> None:
    metrics.clear()
    create = await client.post("/api/sessions", json={"title": "m"})
    sid = create.json()["id"]

    # Hit the deprecated endpoint 3 times.
    for _ in range(3):
        await client.get(f"/api/sessions/{sid}/task-runs/latest")

    # Curate once.
    await client.post(f"/api/sessions/{sid}/curate")

    metrics_resp = await client.get("/api/metrics/deprecated")
    data = metrics_resp.json()

    assert any(k.endswith("task-runs/latest$") for k in data)
    assert any(k.endswith("curate$") for k in data)

    for pattern, rec in data.items():
        if "task-runs/latest" in pattern:
            assert rec["hits"] == 3
        if "curate" in pattern:
            assert rec["hits"] == 1


@pytest.mark.asyncio
async def test_task_runs_by_id_404_still_has_header(client: AsyncClient) -> None:
    metrics.clear()
    create = await client.post("/api/sessions", json={"title": "404test"})
    sid = create.json()["id"]

    for _ in range(2):
        resp = await client.get(f"/api/sessions/{sid}/task-runs/does-not-exist")
        assert resp.status_code == 404
        assert resp.headers.get("x-deprecated") == "true"

    data = (await client.get("/api/metrics/deprecated")).json()
    hit = any(
        rec["hits"] == 2
        for pattern, rec in data.items()
        if "task-runs" in pattern and "latest" not in pattern
    )
    assert hit


@pytest.mark.asyncio
async def test_no_active_consumers_true_when_no_hits(client: AsyncClient) -> None:
    metrics.clear()
    from app.services.deprecation import metrics as m
    assert m.no_active_consumers(grace_hours=0) is True


@pytest.mark.asyncio
async def test_no_active_consumers_false_after_hit(client: AsyncClient) -> None:
    metrics.clear()
    create = await client.post("/api/sessions", json={"title": "active"})
    sid = create.json()["id"]
    await client.get(f"/api/sessions/{sid}/task-runs/latest")

    from app.services.deprecation import metrics as m
    assert m.no_active_consumers(grace_hours=1) is False
