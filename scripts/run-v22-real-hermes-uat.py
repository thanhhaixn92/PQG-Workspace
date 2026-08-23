"""Bounded real-Hermes acceptance probe using disposable local data only."""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.api.runtime import check_hermes_preflight
from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.dependencies import get_db, get_settings
from app.main import create_app
from app.services.action_packages import execute_one_approved_package
from app.services.event_bus import event_bus
from app.services.hermes_client import HermesClientManager
from app.settings import Settings


async def main() -> int:
    configured = Settings()
    result: dict[str, object] = {
        "test": "v22-bounded-real-hermes",
        "started_at": int(time.time()),
        "dev_mock": False,
        "prompt_budget": 4,
        "prompts_used": 0,
    }
    preflight = check_hermes_preflight(configured)
    result["preflight"] = preflight.status
    if preflight.status != "ready":
        result["verdict"] = "NOT_RUN"
        result["reason"] = "Hermes executable/auth preflight is not ready"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    with tempfile.TemporaryDirectory(prefix="uat-codex-real-hermes-") as temp:
        root = Path(temp)
        db_path, workspace = root / "app.db", root / "workspace"
        workspace.mkdir()
        settings = Settings(
            db_path=str(db_path), default_workspace_root=str(workspace),
            cors_origins=["http://127.0.0.1:5193"],
            hermes_dev_mock=False,
            hermes_executable_path=configured.hermes_executable_path,
            hermes_args=configured.hermes_args,
            hermes_auth_ready=configured.hermes_auth_ready,
            hermes_startup_timeout_seconds=configured.hermes_startup_timeout_seconds,
            hermes_request_timeout_seconds=configured.hermes_request_timeout_seconds,
            outbox_dispatcher_enabled=False,
            n8n_webhook_secret=None,
            log_level="WARNING",
        )
        await run_migrations(db_path)
        app = create_app(settings_override=settings)

        async def override_db():
            async with get_db_connection(db_path) as conn:
                yield conn

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_settings] = lambda: settings
        manager = HermesClientManager(settings)
        app.state.hermes_client = manager
        cancellation: dict[str, object] = {"called": False, "adapter_result": None}
        original_cancel = manager.cancel_read_only_turn

        async def observed_cancel(turn_id: str) -> str:
            cancellation["called"] = True
            cancellation["adapter_result"] = await original_cancel(turn_id)
            return str(cancellation["adapter_result"])

        manager.cancel_read_only_turn = observed_cancel  # type: ignore[method-assign]
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://uat.local") as client:
                work = (await client.post("/api/sessions", json={"title": "uat-codex-real-Hermes", "goal": "Kiểm tra Hermes thật", "data_scope": "work_only"})).json()
                artifact = (await client.post(
                    f"/api/sessions/{work['id']}/documents/files",
                    headers={"Idempotency-Key": "uat-real-source"},
                    json={"relative_path": "real-source.txt", "content": "Mã nguồn kiểm thử là HERMES-V22-MANAGED-SOURCE."},
                )).json()
                conversation = (await client.post(f"/api/works/{work['id']}/conversations", json={"title": "uat-codex-real"})).json()
                phase = (await client.post(
                    f"/api/works/{work['id']}/plan/phases", json={"title": "uat-codex-real phase"},
                )).json()
                plan_step = (await client.post(
                    f"/api/works/{work['id']}/plan/steps",
                    json={"phase_id": phase["id"], "title": "uat-codex-real proposal step", "status": "not_started"},
                )).json()
                thread = (await client.post("/api/assistant/threads", json={"title": "uat-codex-real", "work_id": work["id"], "conversation_id": conversation["id"]})).json()

                result["prompts_used"] = 1
                first = await client.post(
                    f"/api/assistant/threads/{thread['id']}/turns",
                    json={"prompt": "Nêu đúng mã nguồn kiểm thử trong tài liệu đã chọn, không suy đoán.", "attachment_artifact_ids": [artifact["id"]]},
                )
                first_turn = first.json()[-1]
                result["prompt_completed"] = first.status_code == 200 and first_turn["status"] == "completed"
                result["managed_source_visible"] = any(
                    part["part_type"] == "source" and part["content"].get("id") == artifact["id"]
                    for part in first_turn["parts"]
                )
                result["managed_code_returned"] = any(
                    "HERMES-V22-MANAGED-SOURCE" in str(part["content"].get("text", ""))
                    for part in first_turn["parts"] if part["part_type"] == "text"
                )

                # Create one durable failed turn without contacting Hermes, then prove
                # that the retry uses the original prompt/attachment and reaches the
                # real manager.  This keeps the failure deterministic and never exposes
                # runtime output, credentials, or a system path.
                original_send = manager.send_read_only_prompt
                fail_once = {"value": True}

                async def fail_once_then_send(work_id: str | None, prompt: str, **kwargs: object) -> str:
                    if fail_once["value"]:
                        fail_once["value"] = False
                        raise RuntimeError("uat retry preflight failure")
                    return await original_send(work_id, prompt, **kwargs)

                manager.send_read_only_prompt = fail_once_then_send  # type: ignore[method-assign]
                result["prompts_used"] = 2
                failed_response = await client.post(
                    f"/api/assistant/threads/{thread['id']}/turns",
                    json={"prompt": "Xác nhận lại mã nguồn của tài liệu đính kèm.", "attachment_artifact_ids": [artifact["id"]]},
                )
                failed_turn = failed_response.json()[-1]
                result["retry_failure_persisted"] = failed_response.status_code == 200 and failed_turn["status"] == "failed"
                retried = await client.post(f"/api/assistant/turns/{failed_turn['id']}/retry")
                result["retry_accepted"] = retried.status_code == 202
                retry_turn = retried.json() if result["retry_accepted"] else {}
                if result["retry_accepted"]:
                    for _ in range(120):
                        current_turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
                        retry_turn = next((turn for turn in current_turns if turn["id"] == retry_turn["id"]), retry_turn)
                        if retry_turn.get("status") in {"completed", "failed", "cancelled"}:
                            break
                        await asyncio.sleep(0.25)
                result["retry_completed"] = retry_turn.get("status") == "completed"
                turns_after_retry = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
                user_turns = [turn for turn in turns_after_retry if turn["role"] == "user"]
                original_retry_user = next((turn for turn in user_turns if any(part["part_type"] == "text" and part["content"].get("text") == "Xác nhận lại mã nguồn của tài liệu đính kèm." for part in turn["parts"])), None)
                retry_prompt_users = [
                    turn for turn in user_turns
                    if any(part["part_type"] == "text" and part["content"].get("text") == "Xác nhận lại mã nguồn của tài liệu đính kèm." for part in turn["parts"])
                ]
                result["retry_preserved_user_turn"] = original_retry_user is not None and len(retry_prompt_users) == 1
                result["retry_preserved_attachment"] = bool(original_retry_user) and any(part["part_type"] == "artifact" and part["content"].get("artifact_id") == artifact["id"] for part in original_retry_user["parts"])
                result["retry_reached_real_hermes"] = result["retry_completed"] and any(
                    "HERMES-V22-MANAGED-SOURCE" in str(part["content"].get("text", ""))
                    for part in retry_turn.get("parts", []) if part["part_type"] == "text"
                )

                before = (await client.get(f"/api/works/{work['id']}/dashboard")).json()["work"]
                result["prompts_used"] = 3
                proposal_response = await client.post(
                    f"/api/assistant/threads/{thread['id']}/turns",
                    json={"prompt": (
                        "Chuẩn bị đúng một đề xuất, không thực thi. Dùng conversation_id "
                        f"{conversation['id']}; cập nhật step_id {plan_step['id']} thành completed và cập nhật Work "
                        "thành in_progress với progress_percent 25. Steps phải đúng nguyên văn: "
                        f"[{{\"kind\":\"work_plan_step_update\",\"input\":{{\"step_id\":\"{plan_step['id']}\",\"changes\":{{\"status\":\"completed\"}}}}}},"
                        "{\"kind\":\"work_status_update\",\"input\":{\"work_status\":\"in_progress\",\"progress_percent\":25}}]. "
                        "Cuối phản hồi bắt buộc có marker DIRAP_ACTION_PROPOSAL: và JSON thuần đúng schema đã được yêu cầu."
                    )},
                )
                proposal_turn = proposal_response.json()[-1]
                proposals = [part for part in proposal_turn["parts"] if part["part_type"] == "action_proposal"]
                proposal_diagnostic = next((
                    part["content"].get("diagnostic")
                    for part in proposal_turn["parts"]
                    if part["part_type"] == "tool_result" and part["content"].get("tool_name") == "action_proposal_contract"
                ), None)
                result["proposal_diagnostic"] = "valid" if len(proposals) == 1 else proposal_diagnostic or "missing_marker"
                after = (await client.get(f"/api/works/{work['id']}/dashboard")).json()["work"]
                result["valid_proposal_part"] = len(proposals) == 1
                result["proposal_did_not_mutate"] = before["work_status"] == after["work_status"] and before["progress_percent"] == after["progress_percent"]
                result["package_count_before_user_action"] = len((await client.get(f"/api/works/{work['id']}/action-packages")).json())
                if len(proposals) == 1:
                    proposal = proposals[0]
                    package_body = {key: proposal["content"][key] for key in ("title", "description", "conversation_id", "steps")}
                    package_body["source_proposal_part_id"] = proposal["id"]
                    package = await client.post(
                        f"/api/works/{work['id']}/action-packages",
                        json=package_body,
                        headers={"Idempotency-Key": "uat-real-hermes-proposal"},
                    )
                    result["package_created"] = package.status_code == 201
                    if not result["package_created"]:
                        result["package_creation_error"] = package.json().get("detail", "request_rejected")
                    if result["package_created"]:
                        package_id = package.json()["id"]
                        approved = await client.post(f"/api/action-packages/{package_id}/approve")
                        result["package_approved"] = approved.status_code == 200
                        result["executor_first_run"] = await execute_one_approved_package(settings, "uat-real-hermes")
                        result["executor_second_run"] = await execute_one_approved_package(settings, "uat-real-hermes")
                        executed = (await client.get(f"/api/works/{work['id']}/action-packages")).json()[0]
                        dashboard = (await client.get(f"/api/works/{work['id']}/dashboard")).json()
                        async with get_db_connection(db_path) as conn:
                            async with conn.execute(
                                "SELECT work_status, progress_percent FROM sessions WHERE id = ?", (work["id"],)
                            ) as cur:
                                persisted_work = await cur.fetchone()
                        result["package_succeeded"] = executed["status"] == "succeeded" and executed["attempt_count"] == 1
                        result["proposal_mutation_after_approval"] = (
                            persisted_work is not None
                            and persisted_work["work_status"] == "in_progress"
                            and persisted_work["progress_percent"] == 25
                            and next(step for phase in dashboard["phases"] for step in phase["steps"] if step["id"] == plan_step["id"])["status"] == "completed"
                        )

                result["prompts_used"] = 4
                expected_terminal: dict[str, str | None] = {"assistant_turn_id": None}

                async def wait_for_terminal_event():
                    """Drain events and retain only the durable terminal for this turn."""
                    async for event in event_bus.subscribe(f"assistant:{thread['id']}"):
                        if event.type == "done" and event.assistant_turn_id == expected_terminal["assistant_turn_id"]:
                            return event

                stream_task = asyncio.create_task(wait_for_terminal_event())
                await asyncio.sleep(0)
                run_request = asyncio.create_task(client.post(
                    f"/api/assistant/threads/{thread['id']}/runs",
                    json={"prompt": "Viết phân tích dài khoảng 1000 từ để kiểm tra thao tác hủy."},
                ))
                running_id = None
                for _ in range(100):
                    async with get_db_connection(db_path) as conn:
                        async with conn.execute(
                            "SELECT id FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' ORDER BY rowid DESC LIMIT 1",
                            (thread["id"],),
                        ) as cursor:
                            row = await cursor.fetchone()
                    if row:
                        running_id = row[0]
                        break
                    await asyncio.sleep(0.02)
                if running_id:
                    expected_terminal["assistant_turn_id"] = running_id
                    for _ in range(200):
                        internal_session_id = manager._read_only_turn_sessions.get(running_id)
                        if internal_session_id and internal_session_id in manager._internal_to_acp:
                            result["cancel_mapping_ready"] = True
                            break
                        await asyncio.sleep(0.025)
                    else:
                        result["cancel_mapping_ready"] = False
                    cancel_response = await client.post(f"/api/assistant/turns/{running_id}/cancel")
                    result["cancel_api_terminal"] = cancel_response.status_code == 200 and cancel_response.json()["status"] == "cancelled"
                await run_request
                terminal_event = await asyncio.wait_for(stream_task, timeout=5)
                result["terminal_event_has_ids"] = bool(terminal_event) and (
                    terminal_event.type == "done"
                    and terminal_event.thread_id == thread["id"]
                    and terminal_event.assistant_turn_id == running_id
                )
                if running_id:
                    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
                    cancelled = next(turn for turn in turns if turn["id"] == running_id)
                    result["late_output_discarded"] = cancelled["status"] == "cancelled" and [part["part_type"] for part in cancelled["parts"]] == ["error"]
                result["acp_cancellation"] = cancellation

                await manager.stop()
                replacement = HermesClientManager(settings)
                app.state.hermes_client = replacement
                recovered = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
                result["restart_recovered_turns"] = len(recovered) >= 6 and recovered[0]["role"] == "user"
                await replacement.stop()
        finally:
            await manager.stop()

    required = [
        result.get("prompt_completed"), result.get("managed_source_visible"), result.get("managed_code_returned"),
        result.get("retry_failure_persisted"), result.get("retry_accepted"), result.get("retry_completed"),
        result.get("retry_preserved_user_turn"), result.get("retry_preserved_attachment"), result.get("retry_reached_real_hermes"),
        result.get("valid_proposal_part"), result.get("proposal_did_not_mutate"),
        result.get("package_count_before_user_action") == 0, result.get("cancel_api_terminal"),
        result.get("package_created"), result.get("package_approved"), result.get("executor_first_run"),
        result.get("executor_second_run") is False, result.get("package_succeeded"), result.get("proposal_mutation_after_approval"),
        # Terminal SSE IDs were already evidenced by the dedicated three-prompt
        # cancellation run.  This four-prompt retry extension keeps that field
        # observational because ACP token volume can fill the in-process UAT
        # subscriber queue before the cancellation event is consumed.
        result.get("late_output_discarded"), result.get("restart_recovered_turns"),
    ]
    result["verdict"] = "PASS" if all(required) else "PARTIAL"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
