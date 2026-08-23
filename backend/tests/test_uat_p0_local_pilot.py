"""Isolated controlled-local-pilot UAT for the P0 Work-journey (handoff Milestone 1).

This test creates a brand-new isolated SQLite DB and workspace directory
(never the user's ``app.db`` / ``workspace_outputs``). It exercises the real
API surface end-to-end without Hermes, OAuth, webhooks, plugins, or any
production data:

1. Create a Work (session) with ``work_only`` scope and a goal.
2. Create at least two conversations inside that Work.
3. Send a non-destructive prompt (HERMES_DEV_MOCK path) to each conversation.
4. Add a sourced input document (inputs/), a working doc and an output doc.
5. Create an action package that updates the plan step + Work status.
6. Approve the package; confirm it executes against *this* Work only.
7. Create a report / summary artifact.
8. Re-open the same DB and confirm all state is restored (restart evidence).

Run with:
    .\\.venv\\Scripts\\python.exe -m pytest tests/test_uat_p0_local_pilot.py -q
"""

from __future__ import annotations

import asyncio
import shutil
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.main import create_app
from app.services.action_packages import execute_one_approved_package, run_action_package_executor_loop
from app.services.hermes_client import HermesClientManager
from app.services.event_bus import event_bus
from app.settings import Settings
from app.mcp.server import mcp_session_id_var
from app.mcp.tools import propose_work_update


@asynccontextmanager
async def _running_uat_client(db_path, workspace, port: int):
    """Run only the services exercised by the P0 journey for one app lifetime."""
    settings = Settings(
        db_path=str(db_path), default_workspace_root=str(workspace),
        cors_origins=["http://localhost:5173"], hermes_dev_mock=True,
        hermes_executable_path="", log_level="WARNING", outbox_dispatcher_enabled=False,
        local_actor_subject="user",
    )
    app = create_app(settings_override=settings)
    from app.dependencies import get_db, get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    async def _override_db():
        async with get_db_connection(db_path) as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_db
    client_manager = HermesClientManager(settings)
    app.state.hermes_client = client_manager
    executor_stop = asyncio.Event()
    executor_task = asyncio.create_task(run_action_package_executor_loop(settings, executor_stop))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", port)),
            base_url="http://testserver",
        ) as client:
            yield client, settings, app
    finally:
        executor_stop.set()
        await executor_task
        await client_manager.stop()


@pytest_asyncio.fixture()
async def isolated_env(tmp_path):
    """Build a fresh DB + workspace in tmp and return their paths."""
    db_path = tmp_path / "uat_app.db"
    workspace = tmp_path / "uat_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    await run_migrations(db_path)

    async with _running_uat_client(db_path, workspace, 12345) as (client, settings, app):
        yield {"client": client, "db_path": db_path, "workspace": workspace, "settings": settings, "app": app}

    # Clean up workspace files (not the user's data)
    shutil.rmtree(workspace, ignore_errors=True)


async def _create_work(client, title, goal):
    resp = await client.post(
        "/api/sessions",
        json={"title": title, "goal": goal, "data_scope": "work_only"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_conv(client, work_id, title):
    resp = await client.post(
        f"/api/works/{work_id}/conversations",
        json={"title": title, "purpose": "P0 journey conversation"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.skip(reason="Superseded Hermes ACP mock journey; native GYO proposal lifecycle is covered by focused GYO regression")
async def test_p0_work_journey_isolated(isolated_env, monkeypatch):
    client = isolated_env["client"]
    settings = isolated_env["settings"]
    app = isolated_env["app"]

    # 1. Create Work (work_only)
    work_id = await _create_work(client, "uat-codex-Pilot Work", "Hoàn thành báo cáo tổng hợp từ tài liệu đầu vào.")
    # confirm data_scope persisted
    resp = await client.get(f"/api/works/{work_id}/dashboard")
    body = resp.json()
    assert body["work"]["data_scope"] == "work_only", body

    # 2. Two conversations
    conv_a = await _create_conv(client, work_id, "Trao đổi phân tích")
    conv_b = await _create_conv(client, work_id, "Trao đổi nháp")
    convs = (await client.get(f"/api/works/{work_id}/conversations")).json()
    # Creating a Work backfills its historical/default conversation; the two
    # explicit conversations must coexist with it rather than replace it.
    assert {conv_a, conv_b}.issubset({item["id"] for item in convs}), convs

    # 3. Non-destructive prompt to each (mock Hermes, 202 Accepted)
    for cid in (conv_a, conv_b):
        r = await client.post(
            f"/api/works/{work_id}/conversations/{cid}/prompt",
            json={"prompt": "Tóm tắt ngắn gọn nội dung tài liệu đầu vào."},
        )
        assert r.status_code == 202, r.text

    # 4. Inputs / working / outputs documents via managed file API
    inputs = await client.post(
        f"/api/sessions/{work_id}/documents/files",
        headers={"Idempotency-Key": "uat-input-1"},
        json={"relative_path": "source-1.txt", "content": "Nguồn: báo cáo nội bộ 2026."},
    )
    assert inputs.status_code == 201, inputs.text
    working = await client.put(
        f"/api/sessions/{work_id}/files/content", params={"path": "working/draft-1.txt"},
        json={"content": "Nháp tổng hợp."},
    )
    assert working.status_code == 200, working.text
    output = await client.put(
        f"/api/sessions/{work_id}/files/content", params={"path": "outputs/final.txt"},
        json={"content": "Kết quả cuối."},
    )
    assert output.status_code == 200, output.text

    # file tree must show inputs/working/outputs groups, no tech files leaked
    tree = (await client.get(f"/api/sessions/{work_id}/files/tree", params={"grouped": "true"})).json()
    assert {entry["path"] for entry in tree["tree"][:3]} == {"inputs", "working", "outputs"}, tree

    # 5. Plan step + 6/7. Action package that updates plan step + Work status
    phase = await client.post(
        f"/api/works/{work_id}/plan/phases",
        json={"title": "Giai đoạn tổng hợp"},
    )
    assert phase.status_code == 201, phase.text
    phase_id = phase.json()["id"]
    step = await client.post(
        f"/api/works/{work_id}/plan/steps",
        json={"phase_id": phase_id, "title": "Tổng hợp báo cáo", "status": "not_started"},
    )
    assert step.status_code == 201, step.text
    step_id = step.json()["id"]

    class UatHermes:
        async def send_read_only_prompt(self, work_id, prompt, *, event_channel=None, assistant_turn_id=None):
            assert work_id and assistant_turn_id and event_channel
            return (
                "Đã dùng tài liệu managed để chuẩn bị đề xuất.\n"
                "DIRAP_ACTION_PROPOSAL: "
                + __import__("json").dumps({
                    "title": "Cập nhật tiến độ Work",
                    "description": "Đánh dấu bước hoàn thành và Work đang thực hiện.",
                    "conversation_id": conv_a,
                    "steps": [
                        {"kind": "work_plan_step_update", "input": {"step_id": step_id, "changes": {"status": "completed"}}},
                        {"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 50}},
                    ],
                })
            )

        def consume_read_only_parts(self, assistant_turn_id):
            return [("tool_result", {"tool_name": "managed_context", "status": "succeeded", "summary": "Đã đọc nguồn managed đã chọn."})]

    monkeypatch.setattr(
        "app.api.assistant.check_hermes_preflight",
        lambda _settings: __import__("types").SimpleNamespace(status="ready", guidance=""),
    )
    app.state.hermes_client = UatHermes()
    assistant_thread = (await client.post(
        "/api/assistant/threads",
        json={"title": "uat-codex-Assistant", "work_id": work_id, "conversation_id": conv_a},
    )).json()

    async def collect_assistant_events():
        return [event async for event in event_bus.subscribe(f"assistant:{assistant_thread['id']}")]

    stream_task = asyncio.create_task(collect_assistant_events())
    await asyncio.sleep(0)
    assistant_run = await client.post(
        f"/api/assistant/threads/{assistant_thread['id']}/runs",
        json={"prompt": "Chuẩn bị đề xuất", "attachment_artifact_ids": [inputs.json()["id"]]},
    )
    assert assistant_run.status_code == 202, assistant_run.text
    user_turn, assistant_turn = assistant_run.json()
    stream_events = await asyncio.wait_for(stream_task, timeout=2)
    terminal_event = stream_events[-1]
    assert terminal_event.type == "done"
    assert terminal_event.thread_id == assistant_thread["id"]
    assert terminal_event.assistant_turn_id == assistant_turn["id"]
    assert any(part["part_type"] == "artifact" and part["content"]["artifact_id"] == inputs.json()["id"] for part in user_turn["parts"])
    persisted_turns = (await client.get(f"/api/assistant/threads/{assistant_thread['id']}/turns")).json()
    assistant_turn = persisted_turns[-1]
    assert assistant_turn["status"] == "completed"
    part_types = {part["part_type"] for part in assistant_turn["parts"]}
    assert {"text", "source", "tool_result", "action_proposal"}.issubset(part_types)
    source_parts = [part for part in assistant_turn["parts"] if part["part_type"] == "source"]
    assert any(part["content"].get("id") == inputs.json()["id"] and part["content"].get("reason") == "Tệp đính kèm được người dùng chọn" for part in source_parts)
    proposal_part = next(part for part in assistant_turn["parts"] if part["part_type"] == "action_proposal")

    # Hermes may only return a proposal marker. The MCP call itself must not
    # mutate the step, create a package, or write a Work-mutation audit row.
    monkeypatch.setattr("app.mcp.tools.get_settings", lambda: settings)
    token = mcp_session_id_var.set(work_id)
    try:
        proposal = await propose_work_update(
            title="Cập nhật tiến độ Work",
            kind="work_plan_step_update",
            proposal_input={"step_id": step_id, "changes": {"status": "completed"}},
            conversation_id=conv_a,
        )
    finally:
        mcp_session_id_var.reset(token)
    assert proposal.startswith("DIRAP_ACTION_PROPOSAL:")
    before_package = (await client.get(f"/api/works/{work_id}/plan")).json()
    before_steps = [item for phase_item in before_package for item in phase_item["steps"]]
    assert next(item for item in before_steps if item["id"] == step_id)["status"] == "not_started"
    assert (await client.get(f"/api/works/{work_id}/action-packages")).json() == []

    package_payload = {
        "title": "Cập nhật tiến độ Work",
        "description": "Đánh dấu bước hoàn thành và Work đang thực hiện.",
        "conversation_id": conv_a,
        "source_proposal_part_id": proposal_part["id"],
        "steps": [
            {"kind": "work_plan_step_update", "input": {"step_id": step_id, "changes": {"status": "completed"}}},
            {"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 50}},
        ],
    }
    pkg = await client.post(
        f"/api/works/{work_id}/action-packages",
        json=package_payload,
        headers={"Idempotency-Key": "uat-action-package-1"},
    )
    assert pkg.status_code == 201, pkg.text
    pkg_id = pkg.json()["id"]
    assert pkg.json()["package_hash"], pkg.json()
    duplicate = await client.post(
        f"/api/works/{work_id}/action-packages",
        json=package_payload,
        headers={"Idempotency-Key": "uat-action-package-1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == pkg_id
    conflict_payload = {**package_payload, "title": "Payload khác"}
    conflict = await client.post(
        f"/api/works/{work_id}/action-packages",
        json=conflict_payload,
        headers={"Idempotency-Key": "uat-action-package-1"},
    )
    assert conflict.status_code == 409

    # 6. Approve -> executor should run it against THIS work only
    aprv = await client.post(f"/api/action-packages/{pkg_id}/approve")
    assert aprv.status_code == 200, aprv.text
    assert aprv.json()["status"] == "approved", aprv.json()

    # give the executor loop a moment (outbox disabled; executor runs in lifespan)
    for _ in range(40):
        current = (await client.get(f"/api/works/{work_id}/action-packages")).json()
        if next(item for item in current if item["id"] == pkg_id)["status"] == "succeeded":
            break
        await asyncio.sleep(0.1)

    after = (await client.get(f"/api/works/{work_id}/action-packages")).json()
    statuses = {p["id"]: p["status"] for p in after}
    assert statuses[pkg_id] == "succeeded", statuses
    plan_after = (await client.get(f"/api/works/{work_id}/plan")).json()
    assert next(item for phase_item in plan_after for item in phase_item["steps"] if item["id"] == step_id)["status"] == "completed"
    work_after = (await client.get(f"/api/works/{work_id}/dashboard")).json()["work"]
    assert work_after["work_status"] == "in_progress"
    assert work_after["progress_percent"] == 100
    assert work_after["progress_source"] == "plan_steps"
    async with get_db_connection(isolated_env["db_path"]) as conn:
        async with conn.execute("SELECT progress_percent FROM sessions WHERE id = ?", (work_id,)) as cur:
            assert (await cur.fetchone())[0] == 50
    # One attempt per action step; there are two steps and no duplicate attempt.
    assert await _count_attempts(isolated_env["db_path"], pkg_id) == 2
    async with get_db_connection(isolated_env["db_path"]) as conn:
        async with conn.execute(
            "SELECT COUNT(DISTINCT step_id) FROM action_attempts WHERE package_id = ?", (pkg_id,)
        ) as cur:
            assert (await cur.fetchone())[0] == 2
    assert await execute_one_approved_package(settings, "uat-retry-worker") is False
    assert await _count_attempts(isolated_env["db_path"], pkg_id) == 2
    refreshed_assistant = (await client.get(f"/api/assistant/threads/{assistant_thread['id']}/turns")).json()[-1]
    approvals = [part for part in refreshed_assistant["parts"] if part["part_type"] == "approval"]
    assert len(approvals) == 1 and approvals[0]["content"]["package_id"] == pkg_id

    class RetryHermes:
        fail = True

        async def send_read_only_prompt(self, work_id, prompt, *, event_channel=None, assistant_turn_id=None):
            if self.fail:
                raise RuntimeError("bounded retry failure")
            return "Retry completed from the original user turn."

    retry_hermes = RetryHermes()
    app.state.hermes_client = retry_hermes
    retry_thread = (await client.post(
        "/api/assistant/threads", json={"title": "uat-codex-Retry", "work_id": work_id, "conversation_id": conv_b},
    )).json()
    failed_run = await client.post(
        f"/api/assistant/threads/{retry_thread['id']}/runs", json={"prompt": "Retry this once"},
    )
    failed_turn_id = failed_run.json()[-1]["id"]
    failed_turns = (await client.get(f"/api/assistant/threads/{retry_thread['id']}/turns")).json()
    assert failed_turns[-1]["status"] == "failed"
    retry_hermes.fail = False
    assert (await client.post(f"/api/assistant/turns/{failed_turn_id}/retry")).status_code == 202
    retried_turns = (await client.get(f"/api/assistant/threads/{retry_thread['id']}/turns")).json()
    assert len([turn for turn in retried_turns if turn["role"] == "user"]) == 1
    assert retried_turns[-1]["status"] == "completed"

    class SlowHermes:
        cancelled: list[str] = []

        async def send_read_only_prompt(self, work_id, prompt, *, event_channel=None, assistant_turn_id=None):
            await asyncio.sleep(0.4)
            return "This late output must be discarded."

        async def cancel_read_only_turn(self, assistant_turn_id):
            self.cancelled.append(assistant_turn_id)
            return True

    slow_hermes = SlowHermes()
    app.state.hermes_client = slow_hermes
    cancel_request = asyncio.create_task(client.post(
        f"/api/assistant/threads/{retry_thread['id']}/runs", json={"prompt": "Cancel this run"},
    ))
    cancel_turn_id = None
    for _ in range(20):
        async with get_db_connection(isolated_env["db_path"]) as conn:
            async with conn.execute(
                "SELECT id FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' ORDER BY rowid DESC LIMIT 1",
                (retry_thread["id"],),
            ) as cur:
                row = await cur.fetchone()
        if row:
            cancel_turn_id = row[0]
            break
        await asyncio.sleep(0.02)
    assert cancel_turn_id
    cancelled = await client.post(f"/api/assistant/turns/{cancel_turn_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    await cancel_request
    cancelled_turns = (await client.get(f"/api/assistant/threads/{retry_thread['id']}/turns")).json()
    cancelled_turn = next(turn for turn in cancelled_turns if turn["id"] == cancel_turn_id)
    assert cancelled_turn["status"] == "cancelled"
    assert [part["part_type"] for part in cancelled_turn["parts"]] == ["error"]
    assert slow_hermes.cancelled == [cancel_turn_id]

    # 7. Report / summary artifact
    rep = await client.post(
        f"/api/sessions/{work_id}/reports",
        headers={"Idempotency-Key": "uat-report-1"},
        json={"title": "Báo cáo UAT", "content": "# Tóm tắt\nKết quả UAT pilot.", "output_format": "markdown"},
    )
    assert rep.status_code == 201, rep.text

    # summary must reflect message + artifact counts
    summary = (await client.get(f"/api/sessions/{work_id}/summary")).json()
    assert summary["artifact_count"] >= 2, summary

    # Missing n8n credentials are optional and must not trigger an external call.
    n8n = (await client.get("/api/n8n/status")).json()
    assert n8n["configured"] is False
    assert "bỏ qua" in n8n["guidance"]

    # Archive is the final mutation boundary: subsequent Work mutation fails closed.
    archived = await client.delete(f"/api/sessions/{work_id}")
    assert archived.status_code == 200, archived.text
    blocked = await client.patch(
        f"/api/works/{work_id}/plan/steps/{step_id}", json={"title": "must-not-change"}
    )
    assert blocked.status_code == 409
    assert (await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "blocked"})).status_code == 409
    assert (await client.post(f"/api/works/{work_id}/conversations", json={"title": "blocked"})).status_code == 409
    assert (await client.post(f"/api/assistant/threads/{assistant_thread['id']}/runs", json={"prompt": "blocked"})).status_code == 409
    assert (await client.post(
        f"/api/works/{work_id}/action-packages",
        json={"title": "blocked", "steps": [{"kind": "work_status_update", "input": {"work_status": "paused", "progress_percent": 50}}]},
        headers={"Idempotency-Key": "uat-archived-block"},
    )).status_code == 409

    return {"work_id": work_id, "pkg_id": pkg_id, "conv_a": conv_a, "conv_b": conv_b, "step_id": step_id}


async def test_p0_restart_recovery_isolated(tmp_path):
    """A real stop followed by a fresh app lifetime restores state once only."""
    db_path = tmp_path / "restart_app.db"
    workspace = tmp_path / "restart_workspace"
    workspace.mkdir()
    await run_migrations(db_path)

    async with _running_uat_client(db_path, workspace, 12346) as (client, _, _app):
        work_id = await _create_work(client, "uat-codex-Restart Evidence Work", "Restart evidence.")
        conversation_id = await _create_conv(client, work_id, "Restart conversation")
        package = await client.post(
            f"/api/works/{work_id}/action-packages",
            json={
                "title": "Restart package", "conversation_id": conversation_id,
                "steps": [{"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 25}}],
            },
            headers={"Idempotency-Key": "uat-restart-package"},
        )
        assert package.status_code == 201, package.text
        package_body = package.json()
        package_id = package_body["id"]
        approval = await client.post(
            f"/api/action-packages/{package_id}/approve",
            headers={"Idempotency-Key": "uat-restart-approve"},
            json={
                "expected_revision": package_body["revision"],
                "expected_payload_hash": package_body["payload_hash"],
            },
        )
        assert approval.status_code == 200, approval.text
        await asyncio.sleep(2.0)
        pre_work = (await client.get(f"/api/works/{work_id}/dashboard")).json()
        pre_packages = (await client.get(f"/api/works/{work_id}/action-packages")).json()
        pre_attempts = await _count_attempts(db_path, package_id)

    async with _running_uat_client(db_path, workspace, 12347) as (client, _, _app):
        post_work = (await client.get(f"/api/works/{work_id}/dashboard")).json()["work"]
        post_packages = (await client.get(f"/api/works/{work_id}/action-packages")).json()
        assert post_work["title"] == pre_work["work"]["title"]
        assert post_work["data_scope"] == "work_only"
        assert {p["id"]: p["status"] for p in post_packages} == {p["id"]: p["status"] for p in pre_packages}
        assert await _count_attempts(db_path, package_id) == pre_attempts
        other = await _create_work(client, "uat-codex-Other Work", "Isolation check.")
        other_packages = (await client.get(f"/api/works/{other}/action-packages")).json()
        assert not other_packages

    shutil.rmtree(workspace, ignore_errors=True)


async def _count_attempts(db_path, package_id) -> int:
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM action_attempts WHERE package_id = ?", (package_id,)
        ) as cur:
            return (await cur.fetchone())[0]
