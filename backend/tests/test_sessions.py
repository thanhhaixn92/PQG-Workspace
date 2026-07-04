"""Tests for session API endpoints."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient
from app.api.sessions import _compose_hermes_prompt

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "test_sessions.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    mock_script = Path("tests/mock_hermes.py").absolute()
    settings = Settings(
        db_path=str(db_path),
        default_workspace_root=str(tmp_path / "auto_workspaces"),
        hermes_executable_path=sys.executable,
        hermes_args=[str(mock_script)],
        hermes_dev_mock=True,
    )
    app = create_app(settings_override=settings)
    app.state.test_workspace = str(workspace)
    # Use TestClient as context manager to run lifespan
    with TestClient(app) as test_client:
        yield test_client


def test_create_session(client: TestClient) -> None:
    response = client.post(
        "/api/sessions",
        json={"title": "Test Session", "workspace_path": "/tmp/test"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == "Test Session"
    assert data["workspace_path"] == "/tmp/test"
    assert "id" in data


def test_create_session_without_workspace_auto_creates_default(client: TestClient) -> None:
    response = client.post(
        "/api/sessions",
        json={"title": "Bài viết mới"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    workspace_path = Path(data["workspace_path"])
    assert workspace_path.exists()
    assert (workspace_path / "outputs").exists()
    assert "b-i-vi-t-m-i" in workspace_path.name or data["id"][:8] in workspace_path.name

    async def check_db():
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute(
                "SELECT payload_json FROM audit_events WHERE session_id = ? AND action = 'session.created'",
                (data["id"],),
            ) as cur:
                row = await cur.fetchone()
                assert row is not None
                assert "auto_created_workspace" in row[0]

    asyncio.run(check_db())


def test_list_sessions(client: TestClient) -> None:
    # Create two sessions
    client.post("/api/sessions", json={"title": "S1", "workspace_path": "/tmp"})
    client.post("/api/sessions", json={"title": "S2", "workspace_path": "/tmp"})

    response = client.get("/api/sessions")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 2
    
    titles = [s["title"] for s in data]
    assert "S1" in titles
    assert "S2" in titles


def test_rename_session_writes_audit(client: TestClient) -> None:
    resp = client.post("/api/sessions", json={"title": "Old", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    response = client.patch(f"/api/sessions/{session_id}", json={"title": "New"})
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "New"

    async def check_db():
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute(
                "SELECT action FROM audit_events WHERE session_id = ?",
                (session_id,),
            ) as cur:
                actions = [row[0] for row in await cur.fetchall()]
                assert "session.renamed" in actions

    asyncio.run(check_db())


def test_archive_session_hides_without_hard_delete(client: TestClient) -> None:
    resp = client.post("/api/sessions", json={"title": "Archive Me", "workspace_path": "/tmp"})
    session_id = resp.json()["id"]

    response = client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"

    list_response = client.get("/api/sessions")
    assert all(session["id"] != session_id for session in list_response.json())

    async def check_db():
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute("SELECT archived FROM sessions WHERE id = ?", (session_id,)) as cur:
                row = await cur.fetchone()
                assert row[0] == 1
            async with db.execute(
                "SELECT action FROM audit_events WHERE session_id = ?",
                (session_id,),
            ) as cur:
                actions = [row[0] for row in await cur.fetchall()]
                assert "session.archived" in actions

    asyncio.run(check_db())


def test_cleanup_smoke_tests_only_archives_matching_sessions(client: TestClient) -> None:
    smoke = client.post("/api/sessions", json={"title": "Smoke Test 1", "workspace_path": "/tmp"}).json()
    keep = client.post("/api/sessions", json={"title": "Real Work", "workspace_path": "/tmp"}).json()

    response = client.post("/api/sessions/cleanup-smoke-tests")
    assert response.status_code == 200, response.text
    assert response.json()["archived_count"] == 1

    sessions = client.get("/api/sessions").json()
    ids = {session["id"] for session in sessions}
    assert smoke["id"] not in ids
    assert keep["id"] in ids

    async def check_db():
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute("SELECT archived FROM sessions WHERE id = ?", (smoke["id"],)) as cur:
                assert (await cur.fetchone())[0] == 1
            async with db.execute("SELECT archived FROM sessions WHERE id = ?", (keep["id"],)) as cur:
                assert (await cur.fetchone())[0] == 0
            async with db.execute("SELECT action FROM audit_events WHERE action = 'session.cleanup_smoke_tests'") as cur:
                assert await cur.fetchone()

    asyncio.run(check_db())


def test_submit_prompt(client: TestClient) -> None:
    # 1. Create a session
    resp = client.post(
        "/api/sessions",
        json={"title": "S1", "workspace_path": client.app.state.test_workspace},
    )
    session_id = resp.json()["id"]

    # 2. Submit prompt
    prompt_resp = client.post(
        f"/api/sessions/{session_id}/prompt",
        json={"prompt": "Hello!"}
    )
    assert prompt_resp.status_code == 202, prompt_resp.text
    data = prompt_resp.json()
    assert data["status"] == "queued"
    assert data["session_id"] == session_id
    assert "id" in data
    task_id = data["id"]

    # 3. Read SSE stream and wait for background task to finish
    events = []
    with client.stream("GET", f"/api/sessions/{session_id}/events") as event_resp:
        for line in event_resp.iter_lines():
            if line.startswith("data: "):
                events.append(line[6:])
            if line.startswith("event: done") or line.startswith("event: error"):
                break
    
    assert len(events) >= 1

    async def check_db():
        # Give the background task a tiny moment to write DB
        await asyncio.sleep(0.1)
        
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute("SELECT status FROM task_runs WHERE id = ?", (task_id,)) as cur:
                row = await cur.fetchone()
                assert row[0] == "completed"
            
            async with db.execute("SELECT action FROM audit_events WHERE session_id = ?", (session_id,)) as cur:
                rows = await cur.fetchall()
                actions = [r[0] for r in rows]
                assert "task_run.completed" in actions

            async with db.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC, rowid ASC",
                (session_id,),
            ) as cur:
                rows = await cur.fetchall()
                assert rows[0] == ("user", "Hello!")
                assert rows[1][0] == "assistant"
                assert rows[1][1]
    
    asyncio.run(check_db())

    history_resp = client.get(f"/api/sessions/{session_id}/messages")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[0]["content"] == "Hello!"

    latest_task_resp = client.get(f"/api/sessions/{session_id}/task-runs/latest")
    assert latest_task_resp.status_code == 200
    latest_task = latest_task_resp.json()
    assert latest_task["id"] == task_id
    assert latest_task["status"] == "completed"

    task_detail_resp = client.get(f"/api/sessions/{session_id}/task-runs/{task_id}")
    assert task_detail_resp.status_code == 200
    task_detail = task_detail_resp.json()
    assert task_detail["id"] == task_id
    assert task_detail["session_id"] == session_id
    assert task_detail["status"] == "completed"


def test_compose_hermes_prompt_preserves_user_prompt_and_adds_guidance() -> None:
    prompt = _compose_hermes_prompt("Tạo báo cáo ngắn", "MEMORY: dùng tiếng Việt")

    assert "=== HERMES LOCAL STACK RESPONSE GUIDE ===" in prompt
    assert "Kết quả" in prompt
    assert "File đầu ra" in prompt
    assert "Cần kiểm tra" in prompt
    assert "Bước tiếp theo" in prompt
    assert "MEMORY: dùng tiếng Việt" in prompt
    assert prompt.endswith("=== USER PROMPT ===\nTạo báo cáo ngắn")


def test_submit_prompt_invalid_session(client: TestClient) -> None:
    response = client.post(
        "/api/sessions/invalid-id/prompt",
        json={"prompt": "Hello!"}
    )
    assert response.status_code == 404


def test_latest_task_run_empty_and_missing_session(client: TestClient) -> None:
    session = client.post(
        "/api/sessions",
        json={"title": "No Tasks", "workspace_path": client.app.state.test_workspace},
    ).json()

    empty_response = client.get(f"/api/sessions/{session['id']}/task-runs/latest")
    assert empty_response.status_code == 200
    assert empty_response.json() is None

    missing_response = client.get("/api/sessions/missing/task-runs/latest")
    assert missing_response.status_code == 404


def test_task_run_detail_is_session_scoped(client: TestClient) -> None:
    first = client.post(
        "/api/sessions",
        json={"title": "Task Detail 1", "workspace_path": client.app.state.test_workspace},
    ).json()
    second = client.post(
        "/api/sessions",
        json={"title": "Task Detail 2", "workspace_path": client.app.state.test_workspace},
    ).json()

    async def seed_task() -> None:
        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            await db.execute(
                """
                INSERT INTO task_runs (id, session_id, status, started_at, finished_at, error, retry_count)
                VALUES (?, ?, ?, unixepoch(), unixepoch(), NULL, 0)
                """,
                ("task-scoped", first["id"], "completed"),
            )
            await db.commit()

    asyncio.run(seed_task())

    own_response = client.get(f"/api/sessions/{first['id']}/task-runs/task-scoped")
    assert own_response.status_code == 200
    assert own_response.json()["session_id"] == first["id"]

    wrong_session_response = client.get(f"/api/sessions/{second['id']}/task-runs/task-scoped")
    assert wrong_session_response.status_code == 404


def test_list_session_audit_events(client: TestClient) -> None:
    first = client.post(
        "/api/sessions",
        json={"title": "Audit 1", "workspace_path": client.app.state.test_workspace},
    ).json()
    second = client.post(
        "/api/sessions",
        json={"title": "Audit 2", "workspace_path": client.app.state.test_workspace},
    ).json()

    client.patch(f"/api/sessions/{first['id']}", json={"title": "Audit 1 Renamed"})
    client.patch(f"/api/sessions/{second['id']}", json={"title": "Audit 2 Renamed"})

    response = client.get(f"/api/sessions/{first['id']}/audit-events?limit=10")

    assert response.status_code == 200, response.text
    events = response.json()
    actions = [event["action"] for event in events]
    assert "session.created" in actions
    assert "session.renamed" in actions
    assert all(event["session_id"] == first["id"] for event in events)


def test_list_session_audit_events_missing_session(client: TestClient) -> None:
    response = client.get("/api/sessions/missing/audit-events")
    assert response.status_code == 404


def test_submit_prompt_hermes_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Preflight pass: executable found, auth ready, not mock.
    # Mock the doctor check to return True so preflight passes.
    import sys
    monkeypatch.setenv("HERMES_AUTH_READY", "1")
    from app.api.runtime import _run_hermes_doctor_sync
    monkeypatch.setattr("app.api.runtime._run_hermes_doctor_sync", lambda _path: True)
    client.app.state.hermes_client.settings.hermes_dev_mock = False
    client.app.state.hermes_client.settings.hermes_executable_path = sys.executable
    client.app.state.hermes_client.settings.hermes_args = ["non_existent_script.py"]
    client.app.state.hermes_client.settings.hermes_startup_timeout_seconds = 1

    # 2. Create a session
    resp = client.post(
        "/api/sessions",
        json={"title": "S1", "workspace_path": client.app.state.test_workspace},
    )
    session_id = resp.json()["id"]

    # 3. Submit prompt (preflight passes; spawn fails in background)
    prompt_resp = client.post(
        f"/api/sessions/{session_id}/prompt",
        json={"prompt": "Hello!"}
    )
    assert prompt_resp.status_code == 202
    task_id = prompt_resp.json()["id"]

    # 4. Read SSE stream and wait for background task to finish
    has_error = False
    with client.stream("GET", f"/api/sessions/{session_id}/events") as event_resp:
        for line in event_resp.iter_lines():
            if line.startswith("event: error"):
                has_error = True
            if line.startswith("event: done"):
                break

    assert has_error

    async def check_db():
        # Give the background task a tiny moment to write DB
        await asyncio.sleep(0.1)

        async with aiosqlite.connect(client.app.state.hermes_client.settings.db_path_resolved) as db:
            async with db.execute("SELECT status, error FROM task_runs WHERE id = ?", (task_id,)) as cur:
                row = await cur.fetchone()
                assert row[0] == "failed"
                assert row[1] is not None

            async with db.execute("SELECT action FROM audit_events WHERE session_id = ?", (session_id,)) as cur:
                rows = await cur.fetchall()
                actions = [r[0] for r in rows]
                assert "task_run.failed" in actions
                assert "hermes.error" in actions

    asyncio.run(check_db())
