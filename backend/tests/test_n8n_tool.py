import pytest
import asyncio
from app.mcp.tools import call_n8n_webhook
from app.mcp.server import mcp_session_id_var
from app.api.approvals import pending_approvals
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
    
    yield session_id, workspace, client, test_settings
    
    # Reset context
    mcp_session_id_var.reset(token)

@pytest.mark.asyncio
async def test_n8n_webhook_missing_secret(mock_session):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = None
    
    with pytest.raises(ValueError, match="not configured"):
        await call_n8n_webhook(workflow_name="echo", payload={})

@pytest.mark.asyncio
async def test_n8n_webhook_not_in_allowlist(mock_session):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = "test-secret"
    
    with pytest.raises(ValueError, match="not in the allowlist"):
        await call_n8n_webhook(workflow_name="malicious", payload={})

@pytest.mark.asyncio
async def test_n8n_webhook_allow_for_session_rejected(mock_session):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = "test-secret"
    
    async def fast_fail_delayed():
        for _ in range(30):
            await asyncio.sleep(0.1)
            if pending_approvals:
                appr_id = list(pending_approvals.keys())[0]
                resp = await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_for_session"})
                assert resp.status_code == 400
                await client.post(f"/api/approvals/{appr_id}", json={"decision": "deny"})
                return
            
    task = asyncio.create_task(fast_fail_delayed())
    
    with pytest.raises(PermissionError, match="Approval denied"):
        await call_n8n_webhook(workflow_name="echo", payload={"test": 123})
        
    await task

@pytest.mark.asyncio
async def test_n8n_webhook_success_and_audit_redaction(mock_session, monkeypatch):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = "super-secret-key"
    
    # Mock httpx.AsyncClient.post conditionally
    import httpx
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
    
    original_post = httpx.AsyncClient.post
    
    async def mock_post(self, url, *args, **kwargs):
        if "hermes-echo" in str(url):
            return MockResponse()
        return await original_post(self, url, *args, **kwargs)
        
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    
    async def approve_delayed():
        for _ in range(30):
            await asyncio.sleep(0.1)
            if pending_approvals:
                appr_id = list(pending_approvals.keys())[0]
                await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
                return
            
    task = asyncio.create_task(approve_delayed())
    
    res = await call_n8n_webhook(workflow_name="echo", payload={"secret_key": "hidden_value", "data": "test"})
    assert "Successfully triggered" in res
    assert "200" in res
    
    await task
    
    # Check audit log redaction
    from app.db.connection import get_db_connection
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT target, payload_json FROM audit_events WHERE action = 'n8n.webhook.sent'") as cur:
            rows = await cur.fetchall()
            assert len(rows) == 1
            target, payload_json = rows[0]
            assert target == "echo"
            # Ensure raw secret is not in the JSON
            assert "hidden_value" not in payload_json
            assert "super-secret-key" not in payload_json
            # Ensure top level keys are logged
            import json
            logged_payload = json.loads(payload_json)
            assert "secret_key" in logged_payload["payload_top_level_keys"]
            assert "data" in logged_payload["payload_top_level_keys"]
            assert logged_payload["response_status"] == 200

@pytest.mark.asyncio
async def test_n8n_webhook_http_error(mock_session, monkeypatch):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = "test-secret"
    
    # Mock httpx.AsyncClient.post conditionally
    import httpx
    original_post = httpx.AsyncClient.post
    
    async def mock_post(self, url, *args, **kwargs):
        if "hermes-echo" in str(url):
            raise httpx.ConnectError("Server error 500", request=httpx.Request("POST", url))
        return await original_post(self, url, *args, **kwargs)
        
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    
    async def approve_delayed():
        for _ in range(30):
            await asyncio.sleep(0.1)
            if pending_approvals:
                appr_id = list(pending_approvals.keys())[0]
                await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
                return
            
    task = asyncio.create_task(approve_delayed())
    
    with pytest.raises(RuntimeError, match="Failed to trigger webhook"):
        await call_n8n_webhook(workflow_name="echo", payload={})
        
    await task
    
    # Check error audit
    from app.db.connection import get_db_connection
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT payload_json FROM audit_events WHERE action = 'n8n.webhook.error'") as cur:
            rows = await cur.fetchall()
            assert len(rows) == 1
            import json
            logged_payload = json.loads(rows[0][0])
            assert "error_class" in logged_payload

@pytest.mark.asyncio
async def test_n8n_webhook_retry_success(mock_session, monkeypatch):
    session_id, workspace, client, settings = mock_session
    settings.n8n_webhook_secret = "test-secret"
    settings.n8n_max_retries = 2
    
    import httpx
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        
    attempts = 0
    original_post = httpx.AsyncClient.post
    
    async def mock_post(self, url, *args, **kwargs):
        nonlocal attempts
        if "hermes-echo" in str(url):
            attempts += 1
            if attempts <= 2:
                raise httpx.HTTPStatusError("503 Service Unavailable", request=None, response=httpx.Response(503, request=httpx.Request("POST", url)))
            return MockResponse()
        return await original_post(self, url, *args, **kwargs)
        
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    
    async def approve_delayed():
        from app.api.approvals import pending_approvals
        for _ in range(30):
            await asyncio.sleep(0.1)
            if pending_approvals:
                appr_id = list(pending_approvals.keys())[0]
                await client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
                return
                
    task = asyncio.create_task(approve_delayed())
    
    res = await call_n8n_webhook(workflow_name="echo", payload={})
    assert "Successfully triggered" in res
    assert attempts == 3
    
    await task

def test_n8n_compose_validation():
    import yaml
    from pathlib import Path
    compose_path = Path(__file__).parent.parent.parent / "infra" / "n8n" / "docker-compose.yml"
    assert compose_path.exists()
    
    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)
        
    n8n_service = compose["services"]["n8n"]
    
    # Check pinned image
    assert n8n_service["image"] == "n8nio/n8n:1.70.0"
    
    # Check bind to 127.0.0.1
    ports = n8n_service.get("ports", [])
    assert any(p.startswith("127.0.0.1:") for p in ports), "Must bind to localhost"
    
    # Check required environment variables
    env = n8n_service.get("environment", [])
    assert "N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:?N8N_ENCRYPTION_KEY is required}" in env
    assert "HERMES_N8N_WEBHOOK_SECRET=${HERMES_N8N_WEBHOOK_SECRET:?HERMES_N8N_WEBHOOK_SECRET is required}" in env
    
    # Check named volume
    volumes = n8n_service.get("volumes", [])
    assert any("hermes_n8n_data:/home/node/.n8n" in v for v in volumes)
