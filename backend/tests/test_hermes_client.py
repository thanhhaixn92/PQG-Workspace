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
async def test_read_only_cancel_outcomes_are_closed_and_safe(tmp_path: Path) -> None:
    client = HermesClientManager(settings=_mock_settings(tmp_path / "app.db"))
    assert await client.cancel_read_only_turn("missing") == "not_active"

    client._read_only_turn_sessions["turn"] = "internal"
    assert await client.cancel_read_only_turn("turn") == "connection_unavailable"

    class SuccessfulConnection:
        cancelled: list[str] = []
        closed: list[str] = []

        async def cancel(self, *, session_id: str) -> None:
            self.cancelled.append(session_id)

        async def close_session(self, *, session_id: str) -> None:
            self.closed.append(session_id)

    connection = SuccessfulConnection()
    client._agent_conn = connection
    assert await client.cancel_read_only_turn("turn") == "session_starting"

    client._internal_to_acp["internal"] = "acp"
    assert await client.cancel_read_only_turn("turn") == "cancelled"
    assert connection.cancelled == ["acp"]
    assert connection.closed == ["acp"]


@pytest.mark.asyncio
async def test_read_only_cancel_adapter_failure_is_non_fatal(tmp_path: Path) -> None:
    client = HermesClientManager(settings=_mock_settings(tmp_path / "app.db"))
    client._read_only_turn_sessions["turn"] = "internal"
    client._internal_to_acp["internal"] = "acp"

    class FailingConnection:
        async def cancel(self, *, session_id: str) -> None:
            raise asyncio.TimeoutError

        async def close_session(self, *, session_id: str) -> None:
            raise AssertionError("close must not run after cancel failure")

    client._agent_conn = FailingConnection()
    assert await client.cancel_read_only_turn("turn") == "adapter_failed"


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


@pytest.mark.asyncio
async def test_read_only_assistant_context_cannot_read_or_write_workspace_files(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    work_id = "selected-work"
    await _create_test_session(db_path, work_id, workspace)
    (workspace / "notes.txt").write_text("private", encoding="utf-8")

    client = HermesClientManager(settings=_mock_settings(db_path))
    internal_session_id = f"assistant-readonly:{work_id}"
    client._acp_to_internal["acp-readonly"] = internal_session_id
    client._read_only_internal_sessions.add(internal_session_id)
    client._read_only_session_work[internal_session_id] = work_id

    with pytest.raises(RuntimeError, match="File reads are not available"):
        await client.read_text_file("notes.txt", "acp-readonly")
    with pytest.raises(RuntimeError, match="File writes are not available"):
        await client.write_text_file("changed", "notes.txt", "acp-readonly")

    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "private"


@pytest.mark.asyncio
async def test_read_only_dev_mock_stream_uses_its_assistant_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    work_id = "selected-work"
    await _create_test_session(db_path, work_id, workspace)
    client = HermesClientManager(settings=Settings(db_path=str(db_path), hermes_dev_mock=True))
    channel = "assistant:thread-1"

    reply = await client.send_read_only_prompt(work_id, "hello", event_channel=channel)

    assert "phản hồi mẫu" in reply
    channel_events = []
    channel_queue = event_bus.get_queue(channel)
    while not channel_queue.empty():
        channel_events.append(channel_queue.get_nowait())
    assert {event.type for event in channel_events} >= {"token", "tool_call"}
    assert event_bus.get_queue(work_id).empty()


@pytest.mark.asyncio
async def test_synchronous_read_only_dev_mock_does_not_publish_to_work_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    work_id = "sync-selected-work"
    await _create_test_session(db_path, work_id, workspace)
    client = HermesClientManager(settings=Settings(db_path=str(db_path), hermes_dev_mock=True))

    reply = await client.send_read_only_prompt(work_id, "hello")

    assert "phản hồi mẫu" in reply
    assert event_bus.get_queue(work_id).empty()
