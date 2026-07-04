"""Tests for approval API endpoints."""
from __future__ import annotations

import asyncio

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from app.api.approvals import pending_approvals
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "test_approvals.db"
    settings = Settings(
        db_path=str(db_path),
        hermes_executable_path="dummy",
        hermes_args=[],
    )
    app = create_app(settings_override=settings)
    # Clear pending approvals for tests
    pending_approvals.clear()
    
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "decision,expected_action",
    [
        ("allow_once", "approval.allowed_once"),
        ("allow_for_session", "approval.allowed_for_session"),
        ("deny", "approval.denied"),
    ],
)
def test_submit_approval(client: TestClient, decision: str, expected_action: str) -> None:
    # 1. Create a real session
    resp = client.post("/api/sessions", json={"title": "Test Session", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    # 2. Add mock pending approval
    approval_id = "test-apprv-123"
    from app.api.approvals import register_pending_approval
    from app.dependencies import get_settings
    
    override = client.app.dependency_overrides.get(get_settings)
    settings_override = override()
    
    asyncio.run(register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="execute",
        target="pytest",
        settings=settings_override
    ))

    # 3. Submit decision
    response = client.post(
        f"/api/approvals/{approval_id}",
        json={"decision": decision},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["approval_id"] == approval_id
    assert data["session_id"] == session_id
    assert data["decision"] == decision
    assert data["audit_action"] == expected_action
    
    # 4. Check decision is recorded correctly
    from app.api.approvals import pending_approvals
    assert pending_approvals[approval_id]["decision"] == decision

    # 5. Check audit log in DB
    async def check_audit() -> None:
        from app.dependencies import get_settings
        override = client.app.dependency_overrides.get(get_settings)
        settings_override = override()
        
        async with aiosqlite.connect(settings_override.db_path_resolved) as db:
            async with db.execute(
                "SELECT action, target FROM audit_events WHERE session_id = ? AND action LIKE 'approval.%' ORDER BY rowid DESC LIMIT 1",
                (session_id,)
            ) as cur:
                row = await cur.fetchone()
                assert row is not None
                assert row[0] == expected_action
                assert row[1] == approval_id

    asyncio.run(check_audit())

def test_submit_approval_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/approvals/unknown-123",
        json={"decision": "allow_once"},
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_approval_request_persisted_and_high_risk_blocks_session_allow(client: TestClient) -> None:
    resp = client.post("/api/sessions", json={"title": "Risky", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    approval_id = "appr-risky"
    from app.api.approvals import register_pending_approval
    from app.dependencies import get_settings

    settings_override = client.app.dependency_overrides[get_settings]()
    asyncio.run(register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="hermes.permission",
        target="script execution via -e/-c flag: python -c import docx",
        risk_level="external_or_destructive",
        description="Hermes wants to run a local script.",
        settings=settings_override,
    ))

    response = client.post(f"/api/approvals/{approval_id}", json={"decision": "allow_for_session"})
    assert response.status_code == 400

    async def check_db() -> None:
        async with aiosqlite.connect(settings_override.db_path_resolved) as db:
            async with db.execute(
                "SELECT action, risk_level, status FROM approval_requests WHERE id = ?",
                (approval_id,),
            ) as cur:
                row = await cur.fetchone()
                assert row == ("hermes.permission", "external_or_destructive", "pending")

    asyncio.run(check_db())


def test_approval_missing_waiter_returns_409_when_db_pending(client: TestClient) -> None:
    resp = client.post("/api/sessions", json={"title": "Restart", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    approval_id = "appr-restart"
    from app.api.approvals import register_pending_approval, pending_approvals
    from app.dependencies import get_settings

    settings_override = client.app.dependency_overrides[get_settings]()
    asyncio.run(register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="write_workspace_file",
        target="notes.md",
        settings=settings_override,
    ))
    pending_approvals.clear()

    response = client.post(f"/api/approvals/{approval_id}", json={"decision": "allow_once"})
    assert response.status_code == 409
    assert "no longer active" in response.json()["detail"]


def test_approval_timeout_marks_expired_and_audits(client: TestClient) -> None:
    resp = client.post("/api/sessions", json={"title": "Timeout", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    approval_id = "appr-timeout-db"
    from app.api.approvals import register_pending_approval, wait_for_approval
    from app.dependencies import get_settings

    settings_override = client.app.dependency_overrides[get_settings]()
    asyncio.run(register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="write_workspace_file",
        target="notes.md",
        settings=settings_override,
        timeout_seconds=1,
    ))

    decision = asyncio.run(wait_for_approval(approval_id, timeout_seconds=0.01))
    assert decision == "deny"

    async def check_db() -> None:
        async with aiosqlite.connect(settings_override.db_path_resolved) as db:
            async with db.execute(
                "SELECT status, decision FROM approval_requests WHERE id = ?",
                (approval_id,),
            ) as cur:
                row = await cur.fetchone()
                assert row == ("expired", "deny")
            async with db.execute(
                "SELECT action FROM audit_events WHERE target = ?",
                (approval_id,),
            ) as cur:
                actions = [row[0] for row in await cur.fetchall()]
                assert "approval.expired" in actions

    asyncio.run(check_db())


def test_submit_approval_does_not_signal_waiter_before_commit(client: TestClient, monkeypatch) -> None:
    resp = client.post("/api/sessions", json={"title": "Commit Gate", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    approval_id = "appr-commit-gate"
    from app.api import approvals
    from app.api.approvals import register_pending_approval
    from app.dependencies import get_settings

    settings_override = client.app.dependency_overrides[get_settings]()
    asyncio.run(register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="write_workspace_file",
        target="notes.md",
        settings=settings_override,
    ))

    original_log_audit_event = approvals.log_audit_event

    async def fail_decision_audit(*args, **kwargs):
        if kwargs.get("action") == "approval.allowed_once":
            raise RuntimeError("audit write failed")
        return await original_log_audit_event(*args, **kwargs)

    monkeypatch.setattr(approvals, "log_audit_event", fail_decision_audit)

    with pytest.raises(RuntimeError, match="audit write failed"):
        client.post(f"/api/approvals/{approval_id}", json={"decision": "allow_once"})

    pending = pending_approvals[approval_id]
    assert pending["decision"] is None
    assert pending["event"].is_set() is False

    async def check_db() -> None:
        async with aiosqlite.connect(settings_override.db_path_resolved) as db:
            async with db.execute(
                "SELECT status, decision FROM approval_requests WHERE id = ?",
                (approval_id,),
            ) as cur:
                row = await cur.fetchone()
                assert row == ("pending", None)

    asyncio.run(check_db())
