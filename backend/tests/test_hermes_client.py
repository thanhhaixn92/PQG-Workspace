"""Tests for the HermesClient integration."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest
from app.api.approvals import pending_approvals
from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.services.event_bus import event_bus
from app.services.hermes_client import HermesClientManager
from app.settings import Settings


async def _create_test_session(db_path: Path, session_id: str, workspace: Path) -> None:
    await run_migrations(db_path)
    now = int(time.time())
    async with get_db_connection(db_path) as db:
        await db.execute(
            """
            INSERT INTO sessions (id, title, workspace_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, "Test Session", str(workspace), now, now),
        )
        await db.commit()


def _mock_settings(db_path: Path) -> Settings:
    # Use the mock_hermes script
    script_path = Path(__file__).parent / "mock_hermes.py"
    return Settings(
        db_path=str(db_path),
        hermes_executable_path=sys.executable,
        hermes_args=[str(script_path)],
        hermes_startup_timeout_seconds=5,
        hermes_request_timeout_seconds=5,
        hermes_restart_backoff_seconds=1,
    )


@pytest.mark.asyncio
async def test_lazy_spawn_and_prompt(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session_id = "test-session"
    await _create_test_session(db_path, session_id, workspace)

    mock_settings = _mock_settings(db_path)
    client = HermesClientManager(settings=mock_settings)
    try:
        # Send a prompt, which should lazily spawn the mock process.
        await client.send_prompt(session_id, "hello")

        # We should have received events on the event bus.
        queue = event_bus.get_queue(session_id)
        events = []

        await asyncio.sleep(0.1)

        while not queue.empty():
            events.append(queue.get_nowait())

        assert len(events) >= 1

        types = [e.type for e in events]
        assert "token" in types
        assert "tool_call" in types
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_read_text_file_uses_session_workspace_and_audits(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session_id = "test-session"
    await _create_test_session(db_path, session_id, workspace)
    target = workspace / "notes.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")

    client = HermesClientManager(settings=_mock_settings(db_path))
    client._acp_to_internal["acp-session"] = session_id

    response = await client.read_text_file("notes.txt", "acp-session", line=2, limit=1)

    assert response.content == "two\n"
    async with get_db_connection(db_path) as db:
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
            assert tuple(row) == ("file.read", "notes.txt")


@pytest.mark.asyncio
async def test_write_text_file_requires_approval_and_audits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session_id = "test-session"
    await _create_test_session(db_path, session_id, workspace)

    async def approve_once(approval_id: str, timeout_seconds: float = 60.0) -> str:
        pending_approvals.pop(approval_id, None)
        return "allow_once"

    monkeypatch.setattr("app.services.hermes_client.wait_for_approval", approve_once)

    client = HermesClientManager(settings=_mock_settings(db_path))
    client._acp_to_internal["acp-session"] = session_id

    await client.write_text_file("saved", "nested/output.txt", "acp-session")

    assert (workspace / "nested" / "output.txt").read_text(encoding="utf-8") == "saved"
    async with get_db_connection(db_path) as db:
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ) as cur:
            rows = [tuple(row) for row in await cur.fetchall()]
            assert any(action == "approval.requested" for action, target in rows)
            assert ("file.write", "nested/output.txt") in rows
