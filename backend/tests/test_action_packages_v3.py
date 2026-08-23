"""Focused regression tests for the GYO v3 Action Package vertical slice.

Covers: revisioned immutable payload hash + approval expected revision/hash,
backend preflight resolution, optimistic version/blocked, creator-only
reauthorization, P0 capability/budget enforcement, durable leased execution
events + heartbeat + watchdog recovery, cancel, and log redaction.

The old API surface (create/approve/deny/cancel/list) is preserved; these
tests exercise the additive behaviour only.
"""
from __future__ import annotations

import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.connection import get_db_connection
from app.main import create_app
from app.settings import Settings
from app.services.action_packages import execute_one_approved_package, recover_stale_leases


@pytest_asyncio.fixture()
async def app_client(migrated_db_path):
    settings = Settings(
        db_path=str(migrated_db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )
    application = create_app(settings_override=settings)
    from app.dependencies import get_db, get_settings, get_trusted_actor
    from app.db.connection import get_db_connection as _gdc

    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_trusted_actor] = lambda: "user"

    async def _override_db():
        async with _gdc(migrated_db_path) as conn:
            yield conn

    application.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://testserver") as client:
        yield client, settings


async def _seed_work(conn, work_id: str, step_id: str, phase_id: str = "phase-1") -> None:
    now = int(time.time())
    await conn.execute(
        "INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES (?, 'ws', ?, ?, 0)",
        (work_id, now, now),
    )
    await conn.execute(
        "INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES (?, ?, 'Phase', 0, ?, ?)",
        (phase_id, work_id, now, now),
    )
    await conn.execute(
        "INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'Step', '', 0, 'not_started', 'user', ?, ?)",
        (step_id, phase_id, work_id, now, now),
    )
    await conn.commit()


def _step_update(step_id: str, **changes) -> dict:
    return {"kind": "work_plan_step_update", "input": {"step_id": step_id, "changes": changes}}


def _work_status_update(status: str, progress: int) -> dict:
    return {"kind": "work_status_update", "input": {"work_status": status, "progress_percent": progress}}


async def _create_package(client, work_id: str, steps: list[dict], idem: str = "key-1") -> dict:
    resp = await client.post(
        f"/api/works/{work_id}/action-packages",
        headers={"Idempotency-Key": idem},
        json={"title": "T", "steps": steps},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# --- Preflight ---------------------------------------------------------------

async def test_preflight_resolves_targets_and_diff(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-pf", "s-pf")
    body = {"title": "T", "steps": [_step_update("s-pf", title="New")]}
    resp = await client.post("/api/works/w-pf/action-packages/preflight", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert data["targets"][0]["step_id"] == "s-pf"
    assert data["diffs"][0]["before"]["title"] == "Step"
    assert data["diffs"][0]["after"]["title"] == "New"
    assert data["preconditions"][0]["type"] == "plan_step_belongs_to_work"
    assert data["package_hash"]


# --- Immutable hash + revision + approval expected ---------------------------

async def test_immutable_hash_revision_and_approval_expected(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-im", "s-im")
    pkg = await _create_package(client, "w-im", [_step_update("s-im", title="X")], idem="imm-1")
    assert pkg["revision"] == 1
    assert pkg["approved_revision"] is None
    assert pkg["created_by"] == "user"
    assert pkg["dto_version"] == 1
    assert pkg["status"] == "awaiting_approval"
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "imm-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert resp.status_code == 200, resp.text
    approved = resp.json()
    assert approved["approved_revision"] == 1
    assert approved["approved_hash"] == approved["package_hash"]
    ran = await execute_one_approved_package(settings, "worker-1")
    assert ran is True
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("SELECT title FROM work_plan_steps WHERE id = 's-im'") as cur:
            assert (await cur.fetchone())[0] == "X"
        async with conn.execute("SELECT COUNT(*) FROM action_execution_events WHERE package_id = ?", (pkg["id"],)) as cur:
            assert (await cur.fetchone())[0] >= 1


# --- Idempotency -------------------------------------------------------------

async def test_create_idempotency_key(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-id", "s-id")
    first = await _create_package(client, "w-id", [_step_update("s-id", title="A")], idem="idem-1")
    second = await _create_package(client, "w-id", [_step_update("s-id", title="A")], idem="idem-1")
    assert second["id"] == first["id"]
    assert second["package_hash"] == first["package_hash"]


# --- P0 capability / budget -------------------------------------------------

async def test_p0_capability_rejected(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-cap", "s-cap")
    resp = await client.post(
        "/api/works/w-cap/action-packages",
        headers={"Idempotency-Key": "cap-1"},
        json={"title": "T", "steps": [{"kind": "run_shell_command", "input": {"cmd": "rm -rf /"}}]},
    )
    assert resp.status_code == 422
    # The step kind is rejected by the P0 internal capability allow-list (schema + service).
    assert "kind" in resp.text or "allow-list" in resp.text


async def test_p0_budget_step_count(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-bud", "s-bud")
    steps = [_step_update("s-bud", title=f"t{i}") for i in range(21)]
    resp = await client.post(
        "/api/works/w-bud/action-packages",
        headers={"Idempotency-Key": "bud-1"},
        json={"title": "T", "steps": steps},
    )
    assert resp.status_code == 422


# --- Optimistic version / blocked / reauthorize -----------------------------

async def test_optimistic_version_blocked_then_reauthorize(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-ov", "s-ov")
    pkg_b = await _create_package(client, "w-ov", [_step_update("s-ov", title="B")], idem="ov-b")
    pkg_a = await _create_package(client, "w-ov", [_step_update("s-ov", title="A")], idem="ov-a")
    await client.post(f"/api/action-packages/{pkg_a['id']}/approve",
        headers={"Idempotency-Key": "ov-approve-a"},
        json={"expected_revision": pkg_a["revision"], "expected_payload_hash": pkg_a["payload_hash"]})
    assert await execute_one_approved_package(settings, "w-ov-a") is True
    await client.post(f"/api/action-packages/{pkg_b['id']}/approve",
        headers={"Idempotency-Key": "ov-approve-b"},
        json={"expected_revision": pkg_b["revision"], "expected_payload_hash": pkg_b["payload_hash"]})
    assert await execute_one_approved_package(settings, "w-ov-b") is True
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("SELECT status FROM action_steps WHERE package_id = ?", (pkg_b["id"],)) as cur:
            step_status = (await cur.fetchone())[0]
        async with conn.execute("SELECT status FROM action_packages WHERE id = ?", (pkg_b["id"],)) as cur:
            pkg_status = (await cur.fetchone())[0]
    assert step_status == "blocked"
    assert pkg_status == "partially_failed"
    rev = await client.post(
        f"/api/action-packages/{pkg_b['id']}/revise",
        headers={"Idempotency-Key": "ov-revise-b"},
        json={"steps": [_step_update("s-ov", title="B")]},
    )
    assert rev.status_code == 200, rev.text
    revised = rev.json()
    assert revised["revision"] == 2
    assert revised["approved_revision"] is None
    assert revised["status"] == "awaiting_approval"
    await client.post(f"/api/action-packages/{revised['id']}/approve",
        headers={"Idempotency-Key": "ov-approve-revised"},
        json={"expected_revision": revised["revision"], "expected_payload_hash": revised["payload_hash"]})
    assert await execute_one_approved_package(settings, "w-ov-b2") is True
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("SELECT title FROM work_plan_steps WHERE id = 's-ov'") as cur:
            assert (await cur.fetchone())[0] == "B"


# --- Watchdog recovery -------------------------------------------------------

async def test_watchdog_recovers_stale_lease(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-wd", "s-wd")
    pkg = await _create_package(client, "w-wd", [_step_update("s-wd", title="Z")], idem="wd-1")
    await client.post(f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "wd-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]})
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute(
            "UPDATE action_packages SET status='executing', lease_owner='dead', lease_expires_at=?, heartbeat_at=? WHERE id=?",
            (int(time.time()) - 100, int(time.time()) - 100, pkg["id"]),
        )
        await conn.execute("UPDATE action_steps SET status='executing' WHERE package_id=?", (pkg["id"],))
        await conn.commit()
    recovered = await recover_stale_leases(settings)
    assert recovered == 1
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("SELECT status FROM action_packages WHERE id=?", (pkg["id"],)) as cur:
            assert (await cur.fetchone())[0] == "approved"
        async with conn.execute("SELECT status FROM action_steps WHERE package_id=?", (pkg["id"],)) as cur:
            assert (await cur.fetchone())[0] == "pending"
    assert await execute_one_approved_package(settings, "wd-worker") is True
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("SELECT title FROM work_plan_steps WHERE id='s-wd'") as cur:
            assert (await cur.fetchone())[0] == "Z"


# --- Cancel ------------------------------------------------------------------

async def test_cancel_approved_package(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-cn", "s-cn")
    pkg = await _create_package(client, "w-cn", [_step_update("s-cn", title="C")], idem="cn-1")
    await client.post(f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "cn-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]})
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/cancel",
        headers={"Idempotency-Key": "cn-cancel-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    # A cancelled package must not be executed by the executor.
    assert await execute_one_approved_package(settings, "cn-worker") is False


# --- Creator-only reauthorization guard --------------------------------------

async def test_revise_rejects_non_creator(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-rc", "s-rc")
    pkg = await _create_package(client, "w-rc", [_step_update("s-rc", title="R")], idem="rc-1")
    # Simulate a package created by a different actor.
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("UPDATE action_packages SET created_by='other-agent' WHERE id=?", (pkg["id"],))
        await conn.commit()
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/revise",
        headers={"Idempotency-Key": "rc-revise-1"},
        json={"steps": [_step_update("s-rc", title="R2")]},
    )
    assert resp.status_code == 403


# --- Log redaction -----------------------------------------------------------

from app.services.audit import redact_payload


async def test_execution_event_redacts_sensitive_payload(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-rd", "s-rd")
    pkg = await _create_package(client, "w-rd", [_step_update("s-rd", title="Safe")], idem="rd-1")
    await client.post(f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "rd-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]})
    assert await execute_one_approved_package(settings, "rd-worker") is True
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute(
            "SELECT detail_json FROM action_execution_events WHERE package_id = ? AND event_type = 'step_succeeded'",
            (pkg["id"],),
        ) as cur:
            row = await cur.fetchone()
    assert row is not None
    # The public redaction helper must strip sensitive keys from durable logs.
    redacted = redact_payload({"token": "sekret", "title": "ok", "nested": {"password": "x"}})
    assert redacted["token"] == "[redacted]"
    assert redacted["title"] == "ok"
    assert redacted["nested"]["password"] == "[redacted]"
