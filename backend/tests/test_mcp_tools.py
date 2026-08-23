import asyncio
import os
import subprocess
import pytest
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.mcp.server import mcp_session_id_var
from app.mcp.tools import (
    propose_work_update,
    save_work_context_summary,
    read_workspace_file,
    write_workspace_file,
    search_workspace,
    list_skills,
    update_memory,
    run_safe_task
)
from app.mcp.server import HERMES_MCP_TOOL_ALLOWLIST, mcp_server
from app.api.approvals import pending_approvals, wait_for_approval
from app.dependencies import get_settings
from app.db.connection import get_db_connection

@pytest.fixture
async def mock_session(client, tmp_path, test_app, monkeypatch):
    # Clear pending approvals
    pending_approvals.clear()
    
    # Patch get_settings for FastMCP tools
    test_settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    monkeypatch.setattr("app.mcp.tools.get_settings", lambda: test_settings)
    
    # Create session
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    resp = await client.post("/api/sessions", json={
        "title": "MCP Test Session",
        "workspace_path": str(workspace)
    })
    session_id = resp.json()["id"]
    
    # Create an active task_run for this session
    settings = test_settings
    async with get_db_connection(settings.db_path_resolved) as db:
        await db.execute(
            "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
            ("task-123", session_id, "running", 1000)
        )
        await db.commit()
    
    # Set context var for direct function tests
    token = mcp_session_id_var.set(session_id)
    
    yield session_id, workspace, client
    
    mcp_session_id_var.reset(token)


@pytest.mark.asyncio
async def test_hermes_mcp_surface_is_exact_allowlist():
    import app.mcp.memory_hub  # noqa: F401 - helper import must not mutate MCP registration

    tools = await mcp_server.list_tools()
    assert {tool.name for tool in tools} == HERMES_MCP_TOOL_ALLOWLIST
    assert len(tools) == 9
    for tool in tools:
        assert tool.description
        assert tool.inputSchema.get("type") == "object"
        assert "properties" in tool.inputSchema
        for property_schema in tool.inputSchema["properties"].values():
            assert property_schema.get("description")


@pytest.mark.asyncio
async def test_propose_work_update_is_read_only(mock_session, test_app):
    session_id, _workspace, _client = mock_session
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    phase_id = "phase-proposal"
    step_id = "step-proposal"
    async with get_db_connection(settings.db_path_resolved) as db:
        now = 1001
        await db.execute(
            "INSERT INTO work_plan_phases (id, session_id, title, sort_order, status, source, created_at, updated_at) VALUES (?, ?, 'Phase', 0, 'in_progress', 'user', ?, ?)",
            (phase_id, session_id, now, now),
        )
        await db.execute(
            "INSERT INTO work_plan_steps (id, phase_id, session_id, title, sort_order, status, source, created_at, updated_at) VALUES (?, ?, ?, 'Original', 0, 'not_started', 'user', ?, ?)",
            (step_id, phase_id, session_id, now, now),
        )
        await db.commit()

    result = await propose_work_update(
        title="Mark step complete",
        kind="work_plan_step_update",
        proposal_input={"step_id": step_id, "changes": {"status": "completed"}},
    )
    assert result.startswith("DIRAP_ACTION_PROPOSAL:")
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT status, title FROM work_plan_steps WHERE id = ?", (step_id,)) as cur:
            row = await cur.fetchone()
        async with db.execute("SELECT COUNT(*) FROM action_packages WHERE session_id = ?", (session_id,)) as cur:
            package_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM audit_events WHERE session_id = ? AND action LIKE 'work.%'", (session_id,)) as cur:
            mutation_audit_count = (await cur.fetchone())[0]
    assert tuple(row) == ("not_started", "Original")
    assert package_count == 0
    assert mutation_audit_count == 0


@pytest.mark.asyncio
async def test_propose_work_update_rejects_invalid_scope_and_archived_work(mock_session, test_app):
    session_id, _workspace, _client = mock_session
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    with pytest.raises(ValueError, match="not part"):
        await propose_work_update(
            title="Wrong scope",
            kind="work_plan_step_update",
            proposal_input={"step_id": "outside", "changes": {"status": "completed"}},
        )
    with pytest.raises(ValueError, match="Invalid Work-status"):
        await propose_work_update(
            title="Wrong schema",
            kind="work_status_update",
            proposal_input={"progress_percent": 10},
        )
    with pytest.raises(ValueError, match="Unsupported Work proposal kind"):
        await propose_work_update(
            title="Wrong kind",
            kind="unallowlisted_kind",  # type: ignore[arg-type]
            proposal_input={"work_status": "paused", "progress_percent": 10},
        )
    async with get_db_connection(settings.db_path_resolved) as db:
        await db.execute("UPDATE sessions SET archived = 1 WHERE id = ?", (session_id,))
        await db.commit()
    with pytest.raises(ValueError, match="archived"):
        await propose_work_update(
            title="Archived",
            kind="work_status_update",
            proposal_input={"work_status": "paused", "progress_percent": 10},
        )


@pytest.mark.asyncio
async def test_context_summary_requires_approval_and_omits_content_from_audit(mock_session, test_app, monkeypatch):
    session_id, _workspace, _client = mock_session
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    monkeypatch.setattr("app.mcp.tools.wait_for_approval", lambda _approval_id: asyncio.sleep(0, result="allow_once"))
    result = await save_work_context_summary(content="Sensitive summary text")
    assert "version 1" in result
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT COUNT(*), MAX(version) FROM work_context_summaries WHERE session_id = ?", (session_id,)) as cur:
            count, version = await cur.fetchone()
        async with db.execute("SELECT payload_json FROM audit_events WHERE session_id = ? AND action = 'work.context_summary_saved'", (session_id,)) as cur:
            audit_payload = (await cur.fetchone())[0]
    assert (count, version) == (1, 1)
    assert "Sensitive summary text" not in audit_payload


@pytest.mark.asyncio
async def test_context_summary_deny_and_archive_during_approval_fail_closed(mock_session, test_app, monkeypatch):
    session_id, _workspace, _client = mock_session
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    monkeypatch.setattr("app.mcp.tools.wait_for_approval", lambda _approval_id: asyncio.sleep(0, result="deny"))
    with pytest.raises(PermissionError, match="denied"):
        await save_work_context_summary(content="Denied")

    async def archive_then_allow(_approval_id: str) -> str:
        async with get_db_connection(settings.db_path_resolved) as db:
            await db.execute("UPDATE sessions SET archived = 1 WHERE id = ?", (session_id,))
            await db.commit()
        return "allow_once"

    monkeypatch.setattr("app.mcp.tools.wait_for_approval", archive_then_allow)
    with pytest.raises(PermissionError, match="archived after approval"):
        await save_work_context_summary(content="Archive race")
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT COUNT(*) FROM work_context_summaries WHERE session_id = ?", (session_id,)) as cur:
            assert (await cur.fetchone())[0] == 0

@pytest.mark.asyncio
async def test_read_write_workspace_file(mock_session):
    session_id, workspace, client = mock_session
    
    # Background task to approve the request
    async def approve_delayed():
        await asyncio.sleep(0.1)
        # Find pending approval
        if pending_approvals:
            appr_id = list(pending_approvals.keys())[0]
            await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
            
    task = asyncio.create_task(approve_delayed())
    
    res = await write_workspace_file(path="test.txt", content="Hello MCP")
    assert "Successfully wrote" in res
    
    # Verify file
    assert (workspace / "test.txt").read_text(encoding="utf-8") == "Hello MCP"
    
    await task
    
    # Test read
    res = await read_workspace_file(path="test.txt")
    assert res == "Hello MCP"
    
    # Test traversal rejection
    with pytest.raises(HTTPException) as exc_info:
        await write_workspace_file(path="../outside.txt", content="hack")
    assert "escapes workspace" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_write_file_deny(mock_session):
    session_id, workspace, client = mock_session
    
    async def deny_delayed():
        await asyncio.sleep(0.1)
        if pending_approvals:
            appr_id = list(pending_approvals.keys())[0]
            await client.post(f"/api/approvals/{appr_id}", json={"decision": "deny"})
            
    task = asyncio.create_task(deny_delayed())
    
    with pytest.raises(PermissionError, match="Approval denied"):
        await write_workspace_file(path="test_deny.txt", content="No")
        
    await task


@pytest.mark.asyncio
async def test_write_file_revalidates_path_after_approval(mock_session, monkeypatch, tmp_path):
    """A path swapped to a link while approval is pending must never be written."""
    _session_id, workspace, _client = mock_session
    safe_parent = workspace / "safe"
    safe_parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    async def approve_and_swap(_approval_id: str) -> str:
        safe_parent.rmdir()
        try:
            os.symlink(outside, safe_parent, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            if os.name != "nt":
                pytest.skip(f"symlink creation is unavailable: {exc}")
            junction = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(safe_parent), str(outside)],
                capture_output=True,
                text=True,
                check=False,
            )
            if junction.returncode != 0:
                pytest.skip(f"symlink/junction creation is unavailable: {exc}; {junction.stderr}")
        return "allow_once"

    monkeypatch.setattr("app.mcp.tools.wait_for_approval", approve_and_swap)

    with pytest.raises(HTTPException, match="Reparse point"):
        await write_workspace_file(path="safe/escaped.txt", content="must not escape")
    assert not (outside / "escaped.txt").exists()


@pytest.mark.asyncio
async def test_write_file_rejects_leaf_hard_link_after_approval(mock_session, monkeypatch, tmp_path):
    """A hard-linked destination substituted after approval fails closed."""
    _session_id, workspace, _client = mock_session
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside must survive", encoding="utf-8")
    destination = workspace / "leaf.txt"

    async def approve_and_substitute_leaf(_approval_id: str) -> str:
        # A hard link is available without symlink privileges.  Direct open("w")
        # would truncate outside_file; atomic replacement must not.
        os.link(outside_file, destination)
        return "allow_once"

    monkeypatch.setattr("app.mcp.tools.wait_for_approval", approve_and_substitute_leaf)
    with pytest.raises(HTTPException, match="Hard-linked"):
        await write_workspace_file(path="leaf.txt", content="safe replacement")
    assert destination.read_text(encoding="utf-8") == "outside must survive"
    assert outside_file.read_text(encoding="utf-8") == "outside must survive"


@pytest.mark.asyncio
async def test_archived_session_rejects_mcp_read_search_and_memory_mutation(mock_session, test_app):
    session_id, workspace, _ = mock_session
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    (workspace / "note.txt").write_text("private", encoding="utf-8")
    async with get_db_connection(settings.db_path_resolved) as db:
        await db.execute("UPDATE sessions SET archived = 1 WHERE id = ?", (session_id,))
        await db.commit()

    with pytest.raises(ValueError, match="archived"):
        await read_workspace_file(path="note.txt")
    with pytest.raises(ValueError, match="archived"):
        await search_workspace(query="private", path=".")
    with pytest.raises(ValueError, match="archived"):
        await update_memory(key="blocked", value="no", kind="project_fact", importance_score=5.0)
    assert not pending_approvals

@pytest.mark.asyncio
async def test_run_safe_task_allowlist(mock_session):
    session_id, workspace, client = mock_session
    
    with pytest.raises(ValueError, match="not in the allowlist"):
        await run_safe_task(task_name="hack")
        
    # Valid task but we will deny it
    async def deny_delayed():
        await asyncio.sleep(0.1)
        if pending_approvals:
            appr_id = list(pending_approvals.keys())[0]
            # Fast-fail for allow_for_session
            resp = await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_for_session"})
            assert resp.status_code == 400
            # Send proper deny
            await client.post(f"/api/approvals/{appr_id}", json={"decision": "deny"})
            
    task = asyncio.create_task(deny_delayed())
    
    with pytest.raises(PermissionError, match="Approval denied"):
        await run_safe_task(task_name="pytest")
        
    await task

@pytest.mark.asyncio
async def test_run_safe_task_error_audit(mock_session, monkeypatch, test_app):
    session_id, workspace, client = mock_session
    
    # Mock create_subprocess_exec to raise an Exception
    import asyncio
    async def mock_exec(*args, **kwargs):
        raise RuntimeError("Simulated subprocess failure")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)
    
    async def approve_delayed():
        await asyncio.sleep(0.1)
        if pending_approvals:
            appr_id = list(pending_approvals.keys())[0]
            await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
            
    task = asyncio.create_task(approve_delayed())
    
    with pytest.raises(RuntimeError, match="Simulated subprocess failure"):
        await run_safe_task(task_name="pytest")
        
    await task
    
    # Check audit log
    from app.dependencies import get_settings
    settings = test_app.dependency_overrides.get(get_settings, get_settings)()
    from app.db.connection import get_db_connection
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT action, target, payload_json FROM audit_events WHERE action = 'shell.error'") as cur:
            rows = await cur.fetchall()
            assert len(rows) > 0
            assert rows[-1][1] == "pytest" # target_str is "pytest"
            assert "Simulated subprocess failure" in rows[-1][2]

@pytest.mark.asyncio
async def test_wait_for_approval_timeout():
    # Insert a fake pending approval
    pending_approvals["appr-timeout-test"] = {
        "session_id": "sess-1",
        "action": "test",
        "target": "test",
        "event": asyncio.Event(),
        "decision": None
    }
    
    # Wait for approval with 0.1s timeout
    decision = await wait_for_approval("appr-timeout-test", timeout_seconds=0.1)
    
    assert decision == "deny"
    assert "appr-timeout-test" not in pending_approvals

@pytest.mark.asyncio
async def test_mcp_middleware_localhost_only(test_app):
    from httpx import AsyncClient, ASGITransport
    # Spoof client IP by passing client=(ip, port) to ASGITransport
    async with AsyncClient(
        transport=ASGITransport(app=test_app, client=("192.168.1.5", 50000)),
        base_url="http://testserver",
    ) as spoofed_client:
        resp = await spoofed_client.post("/mcp", headers={"x-session-id": "fake"})
        assert resp.status_code == 403
        assert "restricted to localhost" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_valid_mcp_http_boundary(client, mock_session):
    # This proves a valid app-level session passes our 401/403 middleware and
    # reaches FastMCP. The ASGI test client's ``testserver`` Host is then
    # correctly rejected by FastMCP's independent DNS-rebinding guard.
    session_id, workspace, _ = mock_session
    try:
        resp = await client.get("/sse/", headers={"x-session-id": session_id}, follow_redirects=True)
        assert resp.status_code in (200, 404, 405) # Anything but 401/403 means middleware passed
    except ValueError as e:
        assert "Request validation failed" in str(e)

@pytest.mark.asyncio
async def test_middleware_rejects_missing_session(client):
    resp = await client.post("/mcp")
    assert resp.status_code == 401
    assert "Missing session_id" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_middleware_rejects_invalid_session(client):
    resp = await client.post("/mcp", headers={"x-session-id": "fake-sess-123"})
    assert resp.status_code == 403
    assert "not active" in resp.json()["detail"]
