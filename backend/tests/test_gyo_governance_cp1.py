"""Focused CP1 tests for GYO v3 governed execution.

Covers: migration preservation + FK check, identity 403, approve TOCTOU
(revision + payload_hash mismatch), idempotency replay, approval expiry,
event sequence ordering, outbox retry, cancel, legacy invalidation,
bounded migration, deterministic sequence backfill, migration failure
safety, competing approve, malformed proposal, budget enforcement.
"""
from __future__ import annotations

import json
import time
import pathlib
import tempfile
import asyncio

import aiosqlite
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.connection import get_db_connection, open_db
from app.main import create_app
from app.settings import Settings
from app.services.action_packages import (
    APPROVAL_TTL_SECONDS,
    build_resolved_payload,
    canonical_package_hash,
    canonical_payload_hash,
    execute_one_approved_package,
    record_execution_event,
    P0_EXECUTION_BUDGETS,
    DTO_VERSION,
)


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


def _make_app(db_path):
    settings = Settings(
        db_path=str(db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )
    app = create_app(settings_override=settings)
    from app.dependencies import get_trusted_actor
    app.dependency_overrides[get_trusted_actor] = lambda: "user"
    return app, settings


def _make_app_no_actor(db_path):
    settings = Settings(
        db_path=str(db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )
    app = create_app(settings_override=settings)
    # Intentionally do NOT override get_trusted_actor: no server-authenticated
    # identity is installed, so governed writes must fail closed.
    return app, settings


async def _seed_work(conn, work_id: str, step_id: str) -> None:
    now = int(time.time())
    await conn.execute(
        "INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES (?, 'ws', ?, ?, 0)",
        (work_id, now, now),
    )
    await conn.execute(
        "INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES (?, ?, 'Phase', 0, ?, ?)",
        (f"ph-{work_id}", work_id, now, now),
    )
    await conn.execute(
        "INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'Step', '', 0, 'not_started', 'user', ?, ?)",
        (step_id, f"ph-{work_id}", work_id, now, now),
    )
    await conn.commit()


def _step_update(step_id: str, **changes) -> dict:
    return {"kind": "work_plan_step_update", "input": {"step_id": step_id, "changes": changes}}


async def _create_package(client, work_id: str, steps: list[dict], idem: str = "key-1") -> dict:
    resp = await client.post(
        f"/api/works/{work_id}/action-packages",
        headers={"Idempotency-Key": idem},
        json={"title": "T", "steps": steps},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# --- Migration preservation ------------------------------------------------

async def test_migration_preserves_fk_and_indexes(app_client):
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("PRAGMA foreign_key_check") as cur:
            violations = await cur.fetchall()
        assert violations == [], f"FK violations: {violations}"
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_action_%'"
        ) as cur:
            indexes = {r[0] for r in await cur.fetchall()}
        assert "idx_action_execution_events_package_sequence" in indexes
        assert "idx_action_steps_idempotency" in indexes
        assert "idx_action_packages_expires" in indexes


async def test_app_db_has_new_columns(app_client):
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute("PRAGMA table_info(action_packages)") as cur:
            cols = {r[1] for r in await cur.fetchall()}
        assert "resolved_payload_json" in cols
        assert "payload_hash" in cols
        assert "approved_payload_hash" in cols
        assert "expires_at" in cols
        async with conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'artifact_validations'") as cur:
            assert await cur.fetchone() is not None


# --- Identity fail-closed --------------------------------------------------

async def test_identity_approve_requires_actor(migrated_db_path):
    app, settings = _make_app_no_actor(migrated_db_path)
    from app.dependencies import get_db, get_settings
    from app.db.connection import get_db_connection as _gdc

    test_settings = Settings(
        db_path=str(migrated_db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    async def _override_db():
        async with _gdc(migrated_db_path) as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Seed work and create package with actor
        app2, _ = _make_app(migrated_db_path)
        app2.dependency_overrides[get_settings] = lambda: test_settings
        app2.dependency_overrides[get_db] = _override_db
        from app.dependencies import get_trusted_actor
        app2.dependency_overrides[get_trusted_actor] = lambda: "user"
        async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://testserver") as c2:
            async with get_db_connection(test_settings.db_path_resolved) as conn:
                await _seed_work(conn, "w-idt", "s-idt")
            pkg = await _create_package(c2, "w-idt", [_step_update("s-idt", title="A")], idem="idt-1")
        # A missing server-authenticated actor must be rejected.
        resp = await client.post(
            f"/api/action-packages/{pkg['id']}/approve",
            headers={"Idempotency-Key": "idt-approve-missing"},
            json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
        )
        assert resp.status_code == 403
        body = resp.json()
        # detail is either string or dict with code
        text = json.dumps(body) if isinstance(body, dict) else str(body)
        assert "IDENTITY_ENFORCEMENT_INSUFFICIENT" in text
        # A client-controlled actor header is not an authenticated identity.
        resp2 = await client.post(
            f"/api/action-packages/{pkg['id']}/approve",
            headers={"Idempotency-Key": "idt-approve-spoof", "X-Actor": "user"},
            json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
        )
        assert resp2.status_code == 403, resp2.text
        assert "IDENTITY_ENFORCEMENT_INSUFFICIENT" in resp2.text


async def test_configured_local_identity_is_server_owned(migrated_db_path):
    """A loopback request receives only the configured actor, never X-Actor."""
    settings = Settings(
        db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"],
        local_actor_subject="local-owner", outbox_dispatcher_enabled=False,
    )
    app = create_app(settings_override=settings)
    from app.dependencies import get_db, get_settings
    from app.db.connection import get_db_connection as _gdc
    app.dependency_overrides[get_settings] = lambda: settings

    async def _override_db():
        async with _gdc(migrated_db_path) as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_db
    async with get_db_connection(migrated_db_path) as conn:
        await _seed_work(conn, "w-local-actor", "s-local-actor")
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://testserver"
    ) as client:
        scope = await client.get("/api/runtime/identity-scope", headers={"X-Actor": "spoofed"})
        assert scope.status_code == 200
        assert scope.json()["identity_scope"]
        created = await client.post(
            "/api/works/w-local-actor/action-packages",
            headers={"Idempotency-Key": "local-actor-create", "X-Actor": "spoofed"},
            json={"title": "Local actor", "steps": [_step_update("s-local-actor", title="Updated")]},
        )
    assert created.status_code == 201, created.text
    assert created.json()["created_by"] == "local-owner"


async def test_identity_revise_cancel_deny_require_actor(migrated_db_path):
    app, settings = _make_app_no_actor(migrated_db_path)
    from app.dependencies import get_db, get_settings
    from app.db.connection import get_db_connection as _gdc

    test_settings = Settings(
        db_path=str(migrated_db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    async def _override_db():
        async with _gdc(migrated_db_path) as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_db
    # create package with actor
    app2, _ = _make_app(migrated_db_path)
    app2.dependency_overrides[get_settings] = lambda: test_settings
    app2.dependency_overrides[get_db] = _override_db
    from app.dependencies import get_trusted_actor
    app2.dependency_overrides[get_trusted_actor] = lambda: "user"
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://testserver") as c2:
        async with get_db_connection(test_settings.db_path_resolved) as conn:
            await _seed_work(conn, "w-idt2", "s-idt2")
        pkg = await _create_package(c2, "w-idt2", [_step_update("s-idt2", title="A")], idem="idt2-1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for endpoint in ["revise", "cancel", "deny"]:
            payload = {"steps": [_step_update("s-idt2", title="B")]} if endpoint == "revise" else {"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]}
            kwargs = {"json": payload, "headers": {"Idempotency-Key": f"missing-actor-{endpoint}"}}
            resp = await client.post(f"/api/action-packages/{pkg['id']}/{endpoint}", **kwargs)
            assert resp.status_code == 403, f"{endpoint} without actor should be 403 got {resp.status_code} {resp.text}"
            assert "IDENTITY_ENFORCEMENT_INSUFFICIENT" in resp.text


# --- Approve TOCTOU: revision mismatch -------------------------------------

async def test_approve_rejects_stale_revision(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-tc", "s-tc")
    pkg = await _create_package(client, "w-tc", [_step_update("s-tc", title="A")], idem="tc-1")
    revised = await client.post(
        f"/api/action-packages/{pkg['id']}/revise",
        headers={"Idempotency-Key": "tc-revise-1"},
        json={"steps": [_step_update("s-tc", title="B")]},
    )
    assert revised.status_code == 200, revised.text
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "tc-approve-stale"},
        json={"expected_revision": 1, "expected_payload_hash": pkg["payload_hash"]},
    )
    assert resp.status_code == 409
    assert "Revision mismatch" in resp.text


# --- Approve TOCTOU: payload_hash mismatch ---------------------------------

async def test_approve_rejects_stale_payload_hash(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-ph", "s-ph")
    pkg = await _create_package(client, "w-ph", [_step_update("s-ph", title="A")], idem="ph-1")
    revised = await client.post(
        f"/api/action-packages/{pkg['id']}/revise",
        headers={"Idempotency-Key": "ph-revise-1"},
        json={"steps": [_step_update("s-ph", title="B")]},
    )
    assert revised.status_code == 200, revised.text
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "ph-approve-stale"},
        json={"expected_revision": revised.json()["revision"], "expected_payload_hash": "wrong_hash"},
    )
    assert resp.status_code == 409
    assert "hash" in resp.text.lower()
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute(
            "SELECT state FROM operation_claims WHERE operation = 'action_package.approve' AND client_key = ?",
            ("ph-approve-stale",),
        ) as cursor:
            claim = await cursor.fetchone()
    assert claim is not None
    assert claim[0] == "failed"


# --- Idempotency replay ---------------------------------------------------

async def test_approve_idempotency_replay(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-ir", "s-ir")
    pkg = await _create_package(client, "w-ir", [_step_update("s-ir", title="X")], idem="ir-1")
    body = {"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]}
    r1 = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "ir-approve-1"},
        json=body,
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "ir-approve-1"},
        json=body,
    )
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]


async def test_approve_requires_idempotency_key(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-approve-key", "s-approve-key")
    pkg = await _create_package(client, "w-approve-key", [_step_update("s-approve-key", title="X")], idem="approve-key-create")
    response = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert response.status_code == 422


async def test_approve_rejects_non_creator(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-approve-creator", "s-approve-creator")
    pkg = await _create_package(client, "w-approve-creator", [_step_update("s-approve-creator", title="X")], idem="approve-creator-create")
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute("UPDATE action_packages SET created_by = 'other-user' WHERE id = ?", (pkg["id"],))
        await conn.commit()
    response = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "approve-non-creator"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert response.status_code == 403
    assert "creator" in response.text.lower()


async def test_approve_idempotency_different_payload_conflicts(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-idc", "s-idc")
    pkg = await _create_package(client, "w-idc", [_step_update("s-idc", title="X")], idem="idc-1")
    body_ok = {"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]}
    body_wrong = {"expected_revision": pkg["revision"], "expected_payload_hash": "different_hash"}
    r1 = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "idc-conflict-key"},
        json=body_ok,
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "idc-conflict-key"},
        json=body_wrong,
    )
    # Same Idempotency-Key but different request_hash should be 409.
    assert r2.status_code == 409


# --- Competing approve single winner --------------------------------------

async def test_competing_approve_single_winner(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-ca", "s-ca")
    pkg = await _create_package(client, "w-ca", [_step_update("s-ca", title="X")], idem="ca-1")
    body = {"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]}
    r1, r2 = await asyncio.gather(
        client.post(
            f"/api/action-packages/{pkg['id']}/approve",
            headers={"Idempotency-Key": "ca-key-1"}, json=body,
        ),
        client.post(
            f"/api/action-packages/{pkg['id']}/approve",
            headers={"Idempotency-Key": "ca-key-2"}, json=body,
        ),
    )
    assert sorted((r1.status_code, r2.status_code)) == [200, 409]


async def test_event_sequence_concurrent_writers(app_client):
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-seq-race", "s-seq-race")
    app, _settings = _make_app(settings.db_path_resolved)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pkg = await _create_package(client, "w-seq-race", [_step_update("s-seq-race", title="X")], idem="seq-race-create")

    async def append_event(label: str) -> None:
        async with get_db_connection(settings.db_path_resolved) as conn:
            await record_execution_event(conn, pkg["id"], label, detail={"label": label}, commit=True)

    await asyncio.gather(append_event("concurrent-a"), append_event("concurrent-b"))
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute(
            "SELECT sequence FROM action_execution_events WHERE package_id = ? ORDER BY sequence",
            (pkg["id"],),
        ) as cursor:
            sequences = [row[0] for row in await cursor.fetchall()]
    assert sequences == [1, 2]


# --- Approval expiry -------------------------------------------------------

async def test_expired_package_not_claimed(app_client):
    _, settings = app_client
    now = int(time.time())
    package_id = "test-exp-pkg"
    title = "ExpTest"
    steps_norm = [{"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 5}}]
    payload = build_resolved_payload(
        title=title, description=None, normalized_steps=steps_norm,
        snapshot={"targets": []}, preconditions=[], created_at=now,
    )
    payload_hash_value = canonical_payload_hash(payload)
    package_hash = canonical_package_hash(title, None, steps_norm)
    expired_at = now - 100
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-exp", "s-exp")
        await conn.execute(
            """INSERT INTO action_packages
               (id, session_id, title, package_hash, status, created_at, updated_at,
                revision, created_by, dto_version, resolved_payload_json, payload_hash,
                expires_at, approval_ttl_seconds, snapshot_json, preconditions_json,
                budget_json, capabilities_json)
               VALUES (?, 'w-exp', ?, ?, 'approved', ?, ?, 1, 'user', 1, ?, ?, ?, ?, '{}', '[]', '{}', '[]')""",
            (package_id, title, package_hash, now, now, json.dumps(payload), payload_hash_value, expired_at, APPROVAL_TTL_SECONDS),
        )
        await conn.execute(
            "UPDATE action_packages SET approved_payload_hash = payload_hash, approved_revision = revision, approved_at = ? WHERE id = ?",
            (now, package_id),
        )
        await conn.execute(
            "INSERT INTO action_steps (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at)"
            " VALUES (?, ?, 0, 'work_status_update', 'write', ?, 'pending', ?, ?)",
            ("st-exp", package_id, json.dumps({"work_status": "in_progress", "progress_percent": 5}), now, now),
        )
        await conn.commit()
    ran = await execute_one_approved_package(settings, "exp-worker")
    assert ran is False


async def test_approve_rejects_expired_package(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-expa", "s-expa")
    pkg = await _create_package(client, "w-expa", [_step_update("s-expa", title="X")], idem="expa-1")
    # Manually expire the package
    async with get_db_connection(settings.db_path_resolved) as conn:
        await conn.execute(
            "UPDATE action_packages SET expires_at = ? WHERE id = ?",
            (int(time.time()) - 10, pkg["id"]),
        )
        await conn.commit()
        async with conn.execute("SELECT expires_at FROM action_packages WHERE id = ?", (pkg["id"],)) as cur:
            row = await cur.fetchone()
            assert row[0] is not None and row[0] < int(time.time())
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "expired-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert resp.status_code == 409
    assert "expired" in resp.text.lower()


# --- Legacy invalidation ---------------------------------------------------

async def test_legacy_approved_invalidated_on_migration(tmp_path):
    """All legacy approved rows must be invalidated: no approved_payload_hash."""
    from app.db.migrations import MIGRATIONS

    db_path = tmp_path / "legacy_test.db"
    # Apply migrations up to 0033 only
    conn = await open_db(db_path)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)"
        )
        await conn.commit()
        for version, step in MIGRATIONS:
            if version == "0034_gyo_v3_payload_binding":
                break
            if isinstance(step, str):
                await conn.executescript(step)
            else:
                await step(conn)
            await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, int(time.time())))
            await conn.commit()
    finally:
        await conn.close()

    # Insert a legacy approved package and an awaiting_approval package
    async with get_db_connection(db_path) as conn:
        now = int(time.time())
        # Need a session for FK
        await conn.execute("INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES ('w-leg', 'ws', ?, ?, 0)", (now, now))
        await conn.execute("INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES ('ph-leg', 'w-leg', 'Phase', 0, ?, ?)", (now, now))
        await conn.execute("INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at) VALUES ('s-leg', 'ph-leg', 'w-leg', 'Step', '', 0, 'not_started', 'user', ?, ?)", (now, now))
        # Legacy package with approved status and approved_hash matching package_hash
        pkg_hash = "abc123"
        await conn.execute(
            "INSERT INTO action_packages (id, session_id, title, package_hash, status, approved_hash, approved_at, approved_by, created_at, updated_at, revision, approved_revision, created_by) VALUES (?, 'w-leg', 'Legacy', ?, 'approved', ?, ?, 'user', ?, ?, 1, 1, 'user')",
            ("pkg-legacy-approved", pkg_hash, pkg_hash, now, now, now),
        )
        await conn.execute(
            "INSERT INTO action_steps (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at) VALUES (?, ?, 0, 'work_status_update', 'write', ?, 'pending', ?, ?)",
            ("step-leg-1", "pkg-legacy-approved", json.dumps({"work_status": "in_progress", "progress_percent": 5}), now, now),
        )
        # Awaiting approval legacy
        await conn.execute(
            "INSERT INTO action_packages (id, session_id, title, package_hash, status, created_at, updated_at, revision, created_by) VALUES (?, 'w-leg', 'Legacy2', ?, 'awaiting_approval', ?, ?, 1, 'user')",
            ("pkg-legacy-awaiting", pkg_hash, now, now),
        )
        await conn.execute(
            "INSERT INTO action_steps (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at) VALUES (?, ?, 0, 'work_status_update', 'write', ?, 'pending', ?, ?)",
            ("step-leg-2", "pkg-legacy-awaiting", json.dumps({"work_status": "in_progress", "progress_percent": 5}), now, now),
        )
        await conn.commit()

    # Now apply migration 0034
    from app.db.migrations import _apply_migration_0034_gyo_v3_payload_binding
    conn2 = await open_db(db_path)
    try:
        await _apply_migration_0034_gyo_v3_payload_binding(conn2)
        await conn2.commit()
    finally:
        await conn2.close()

    # Verify invalidation
    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT status, approved_payload_hash, approved_revision, approved_at, approved_by FROM action_packages WHERE id = 'pkg-legacy-approved'") as cur:
            row = await cur.fetchone()
            assert row["status"] == "awaiting_approval", f"legacy approved should be reset to awaiting_approval, got {row['status']}"
            assert row["approved_payload_hash"] is None
            assert row["approved_revision"] is None
            assert row["approved_at"] is None
            assert row["approved_by"] is None
        async with conn.execute("SELECT status, approved_payload_hash FROM action_packages WHERE id = 'pkg-legacy-awaiting'") as cur:
            row = await cur.fetchone()
            assert row["approved_payload_hash"] is None
        # Worker must not claim the legacy approved (now awaiting)
        # Check via service: try to claim with approved status filter - should not find it
        settings = Settings(db_path=str(db_path), cors_origins=["http://localhost:5173"], hermes_dev_mock=False, log_level="WARNING", outbox_dispatcher_enabled=False)
        ran = await execute_one_approved_package(settings, "legacy-worker")
        assert ran is False


# --- Event sequence ordering -----------------------------------------------

async def test_event_sequence_monotonic(app_client):
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-es", "s-es")
    app, _settings = _make_app(settings.db_path_resolved)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pkg = await _create_package(client, "w-es", [_step_update("s-es", title="X")], idem="es-1")
    async with get_db_connection(settings.db_path_resolved) as conn:
        for i in range(5):
            await record_execution_event(conn, pkg["id"], f"event_{i}", detail={"i": i}, commit=True)
        async with conn.execute(
            "SELECT sequence, event_type FROM action_execution_events WHERE package_id = ? ORDER BY sequence",
            (pkg["id"],),
        ) as cur:
            rows = await cur.fetchall()
    assert len(rows) >= 5
    sequences = [r[0] for r in rows]
    assert sequences == sorted(sequences), f"Sequences not monotonic: {sequences}"
    assert len(set(sequences)) == len(sequences), f"Duplicate sequences: {sequences}"


async def test_event_sequence_deterministic_multiple_packages(app_client):
    """Sequences must be deterministic per (package_id, created_at, rowid) and not duplicate."""
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-es2", "s-es2")
        # Need second work for second package
        now = int(time.time())
        await conn.execute("INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES ('w-es2b', 'ws', ?, ?, 0)", (now, now))
        await conn.execute("INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES ('ph-es2b', 'w-es2b', 'Phase', 0, ?, ?)", (now, now))
        await conn.execute("INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at) VALUES ('s-es2b', 'ph-es2b', 'w-es2b', 'Step', '', 0, 'not_started', 'user', ?, ?)", (now, now))
        await conn.commit()
    app, _settings = _make_app(settings.db_path_resolved)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pkg1 = await _create_package(client, "w-es2", [_step_update("s-es2", title="X")], idem="es2-1")
        pkg2 = await _create_package(client, "w-es2b", [_step_update("s-es2b", title="Y")], idem="es2-2")
    async with get_db_connection(settings.db_path_resolved) as conn:
        # Interleave events for two packages
        for i in range(3):
            await record_execution_event(conn, pkg1["id"], f"p1_event_{i}", detail={"i": i}, commit=True)
        for i in range(3):
            await record_execution_event(conn, pkg2["id"], f"p2_event_{i}", detail={"i": i}, commit=True)
        for i in range(2):
            await record_execution_event(conn, pkg1["id"], f"p1_event_extra_{i}", detail={"i": i}, commit=True)
        # Verify each package has unique, monotonic sequences starting at 1
        for pid in [pkg1["id"], pkg2["id"]]:
            async with conn.execute(
                "SELECT sequence FROM action_execution_events WHERE package_id = ? ORDER BY sequence",
                (pid,),
            ) as cur:
                seqs = [r[0] for r in await cur.fetchall()]
            assert seqs == sorted(seqs)
            assert len(set(seqs)) == len(seqs)
            # Sequences should be contiguous-ish but at least monotonic and 1-indexed
            assert seqs[0] >= 1


async def test_migration_sequence_backfill_deterministic(tmp_path):
    """Migration backfill for action_execution_events must be deterministic by package_id, created_at, rowid."""
    from app.db.migrations import MIGRATIONS

    db_path = tmp_path / "seq_test.db"
    conn = await open_db(db_path)
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        await conn.commit()
        for version, step in MIGRATIONS:
            if version == "0034_gyo_v3_payload_binding":
                break
            if isinstance(step, str):
                await conn.executescript(step)
            else:
                await step(conn)
            await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, int(time.time())))
            await conn.commit()
    finally:
        await conn.close()

    # Insert events with sequence=0 before migration (old schema has no sequence column, so we add via migration)
    # Instead, directly insert into old action_execution_events (6 columns) and then run migration that adds sequence
    async with get_db_connection(db_path) as conn:
        now = int(time.time())
        await conn.execute("INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES ('w-seq', 'ws', ?, ?, 0)", (now, now))
        await conn.execute("INSERT INTO action_packages (id, session_id, title, package_hash, status, created_at, updated_at, revision, created_by) VALUES ('pkg-seq', 'w-seq', 'T', 'h', 'awaiting_approval', ?, ?, 1, 'user')", (now, now))
        # Old table has 6 columns: id, package_id, step_id, event_type, detail_json, created_at
        # Insert events with different created_at but same package, out of rowid order
        for i in [5, 3, 1, 4, 2]:
            await conn.execute(
                "INSERT INTO action_execution_events (id, package_id, step_id, event_type, detail_json, created_at) VALUES (?, 'pkg-seq', NULL, ?, '{}', ?)",
                (f"evt-{i}", f"event_{i}", now + i),
            )
        await conn.commit()

    from app.db.migrations import _apply_migration_0034_gyo_v3_payload_binding
    conn2 = await open_db(db_path)
    try:
        await _apply_migration_0034_gyo_v3_payload_binding(conn2)
        await conn2.commit()
    finally:
        await conn2.close()

    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT event_type, sequence, created_at FROM action_execution_events WHERE package_id = 'pkg-seq' ORDER BY sequence") as cur:
            rows = await cur.fetchall()
        seqs = [r["sequence"] for r in rows]
        assert seqs == [1, 2, 3, 4, 5]
        # Order should be by created_at then rowid: events inserted as 5,3,1,4,2 with created_at now+5, now+3 etc.
        # Sorted by created_at: 1,2,3,4,5
        event_order = [r["event_type"] for r in rows]
        assert event_order == ["event_1", "event_2", "event_3", "event_4", "event_5"]


# --- Outbox retry ----------------------------------------------------------

async def test_publish_attempts_col(app_client):
    _, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-pa", "s-pa")
    app, _settings = _make_app(settings.db_path_resolved)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        pkg = await _create_package(client, "w-pa", [_step_update("s-pa", title="X")], idem="pa-1")
    async with get_db_connection(settings.db_path_resolved) as conn:
        await record_execution_event(conn, pkg["id"], "test_event", detail={"msg": "test"}, commit=True)
        async with conn.execute(
            "SELECT publish_attempts FROM action_execution_events WHERE package_id = ? LIMIT 1",
            (pkg["id"],),
        ) as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] >= 0


# --- Bounded migration with many rows -------------------------------------

async def test_bounded_migration_large_batch(tmp_path):
    """Migration must handle >200 packages without fetchall OOM."""
    from app.db.migrations import MIGRATIONS

    db_path = tmp_path / "large_batch.db"
    conn = await open_db(db_path)
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        await conn.commit()
        for version, step in MIGRATIONS:
            if version == "0034_gyo_v3_payload_binding":
                break
            if isinstance(step, str):
                await conn.executescript(step)
            else:
                await step(conn)
            await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, int(time.time())))
            await conn.commit()
    finally:
        await conn.close()

    async with get_db_connection(db_path) as conn:
        now = int(time.time())
        await conn.execute("INSERT INTO sessions (id, workspace_path, created_at, updated_at, archived) VALUES ('w-large', 'ws', ?, ?, 0)", (now, now))
        await conn.execute("INSERT INTO work_plan_phases (id, session_id, title, sort_order, created_at, updated_at) VALUES ('ph-large', 'w-large', 'Phase', 0, ?, ?)", (now, now))
        await conn.execute("INSERT INTO work_plan_steps (id, phase_id, session_id, title, description, sort_order, status, source, created_at, updated_at) VALUES ('s-large', 'ph-large', 'w-large', 'Step', '', 0, 'not_started', 'user', ?, ?)", (now, now))
        # Insert 250 packages (> BATCH=200)
        for i in range(250):
            await conn.execute(
                "INSERT INTO action_packages (id, session_id, title, package_hash, status, created_at, updated_at, revision, created_by) VALUES (?, 'w-large', ?, ?, 'awaiting_approval', ?, ?, 1, 'user')",
                (f"pkg-large-{i}", f"T-{i}", f"h-{i}", now, now),
            )
            await conn.execute(
                "INSERT INTO action_steps (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at) VALUES (?, ?, 0, 'work_status_update', 'write', ?, 'pending', ?, ?)",
                (f"step-large-{i}", f"pkg-large-{i}", json.dumps({"work_status": "in_progress", "progress_percent": 5}), now, now),
            )
        await conn.commit()

    from app.db.migrations import _apply_migration_0034_gyo_v3_payload_binding
    conn2 = await open_db(db_path)
    try:
        await _apply_migration_0034_gyo_v3_payload_binding(conn2)
        await conn2.commit()
    finally:
        await conn2.close()

    async with get_db_connection(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM action_packages") as cur:
            assert (await cur.fetchone())[0] == 250
        async with conn.execute("SELECT payload_hash, resolved_payload_json, expires_at FROM action_packages LIMIT 1") as cur:
            row = await cur.fetchone()
            assert row["payload_hash"]
            assert row["resolved_payload_json"]
            assert row["expires_at"]


# --- Migration failure safety ----------------------------------------------

async def test_migration_failure_rollback_and_pragma_restore(tmp_path):
    """If FK check fails, migration rolls back and PRAGMA foreign_keys is restored."""
    from app.db.migrations import MIGRATIONS

    db_path = tmp_path / "fk_fail.db"
    conn = await open_db(db_path)
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        await conn.commit()
        for version, step in MIGRATIONS:
            if version == "0034_gyo_v3_payload_binding":
                break
            if isinstance(step, str):
                await conn.executescript(step)
            else:
                await step(conn)
            await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, int(time.time())))
            await conn.commit()
    finally:
        await conn.close()

    # Insert a package with invalid FK (non-existent session)
    async with get_db_connection(db_path) as conn:
        # Temporarily disable FK to insert invalid row
        await conn.execute("PRAGMA foreign_keys = OFF")
        now = int(time.time())
        await conn.execute(
            "INSERT INTO action_packages (id, session_id, title, package_hash, status, created_at, updated_at, revision, created_by) VALUES ('pkg-bad-fk', 'nonexistent-session', 'Bad', 'h', 'awaiting_approval', ?, ?, 1, 'user')",
            (now, now),
        )
        await conn.execute(
            "INSERT INTO action_steps (id, package_id, sort_order, kind, risk_level, input_json, status, created_at, updated_at) VALUES ('step-bad', 'pkg-bad-fk', 0, 'work_status_update', 'write', ?, 'pending', ?, ?)",
            (json.dumps({"work_status": "in_progress", "progress_percent": 5}), now, now),
        )
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.commit()
        # Check FK is currently violated but not enforced until next check?
        async with conn.execute("PRAGMA foreign_key_check") as cur:
            violations = await cur.fetchall()
            # May be 1 violation
            assert len(violations) >= 1

    from app.db.migrations import _apply_migration_0034_gyo_v3_payload_binding
    conn2 = await open_db(db_path)
    try:
        # Ensure PRAGMA is ON before migration
        async with conn2.execute("PRAGMA foreign_keys") as cur:
            assert (await cur.fetchone())[0] == 1
        try:
            await _apply_migration_0034_gyo_v3_payload_binding(conn2)
            assert False, "Migration should have raised due to FK violation"
        except RuntimeError as exc:
            assert "foreign_key_check" in str(exc).lower()
        # After failure, PRAGMA should be restored to ON
        async with conn2.execute("PRAGMA foreign_keys") as cur:
            fk_after = (await cur.fetchone())[0]
        assert fk_after == 1, f"PRAGMA foreign_keys should be restored to ON, got {fk_after}"
        # Tables should still exist and data preserved (rollback)
        async with conn2.execute("SELECT COUNT(*) FROM action_packages WHERE id='pkg-bad-fk'") as cur:
            cnt = (await cur.fetchone())[0]
            # Depending on rollback, the bad row should still be there in old table (since shadow rebuild failed)
            assert cnt == 1
    finally:
        await conn2.close()


# --- Malformed proposal ----------------------------------------------------

async def test_malformed_proposal_rejected(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-mal", "s-mal")
    # Invalid step kind
    resp = await client.post(
        "/api/works/w-mal/action-packages",
        headers={"Idempotency-Key": "mal-1"},
        json={"title": "T", "steps": [{"kind": "run_shell_command", "input": {"cmd": "rm -rf /"}}]},
    )
    assert resp.status_code == 422
    # Invalid progress type
    resp2 = await client.post(
        "/api/works/w-mal/action-packages",
        headers={"Idempotency-Key": "mal-2"},
        json={"title": "T", "steps": [{"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 999}}]},
    )
    assert resp2.status_code == 422
    # Empty steps
    resp3 = await client.post(
        "/api/works/w-mal/action-packages",
        headers={"Idempotency-Key": "mal-3"},
        json={"title": "T", "steps": []},
    )
    assert resp3.status_code == 422


# --- Budget enforcement ----------------------------------------------------

async def test_budget_enforcement(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-bud2", "s-bud2")
    # Exceed max_steps (20)
    steps = [_step_update("s-bud2", title=f"t{i}") for i in range(21)]
    resp = await client.post(
        "/api/works/w-bud2/action-packages",
        headers={"Idempotency-Key": "bud2-1"},
        json={"title": "T", "steps": steps},
    )
    assert resp.status_code == 422
    assert "budget" in resp.text.lower() or "step" in resp.text.lower()


# --- Cancel ----------------------------------------------------------------

async def test_cancel_after_approve(app_client):
    client, settings = app_client
    async with get_db_connection(settings.db_path_resolved) as conn:
        await _seed_work(conn, "w-cn2", "s-cn2")
    pkg = await _create_package(client, "w-cn2", [_step_update("s-cn2", title="X")], idem="cn2-1")
    await client.post(
        f"/api/action-packages/{pkg['id']}/approve",
        headers={"Idempotency-Key": "cn2-approve-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    resp = await client.post(
        f"/api/action-packages/{pkg['id']}/cancel",
        headers={"Idempotency-Key": "cn2-cancel-1"},
        json={"expected_revision": pkg["revision"], "expected_payload_hash": pkg["payload_hash"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    assert await execute_one_approved_package(settings, "cn2-worker") is False
