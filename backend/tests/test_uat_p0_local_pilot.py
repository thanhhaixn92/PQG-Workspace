"""Deterministic current-GYO controlled-local-pilot acceptance journey.

This test uses only a fresh temporary SQLite database and workspace. It drives
the current durable Assistant/GYO API with an injected provider-neutral adapter;
there is no Hermes/ACP acceptance path, real provider, credential, network, or
user data involved.

The single journey proves:

create Work -> two conversations -> current GYO durable stream -> persisted
text/source/action proposal -> no proposal-time mutation -> immutable Action
Package -> canonical preflight -> exact-binding approval -> exactly-once
execution -> report artifact -> reopen the same isolated DB -> durable state.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.main import create_app
from app.services.action_packages import execute_one_approved_package
from app.services.event_bus import event_bus
from app.services.gyo_orchestrator import GyoEvent, GyoProviderHealth
from app.settings import Settings


class OfflineGyoAdapter:
    """One deterministic current-GYO provider seam with zero network access."""

    def __init__(self) -> None:
        self.response_text = ""
        self.requests: list[Any] = []

    async def health_check(self, _profile, _credential) -> GyoProviderHealth:
        return GyoProviderHealth("ready", "Offline deterministic P0 adapter is ready.")

    async def stream(self, request, _profile, _model, credential, cancel_event):
        assert credential == "offline-p0-test-credential"
        assert not cancel_event.is_set()
        self.requests.append(request)
        yield GyoEvent("token", {"text": self.response_text})


async def _seed_offline_gyo(db_path) -> None:
    """Create an enabled model profile only inside the disposable P0 database."""
    async with get_db_connection(db_path) as conn:
        await conn.execute(
            """INSERT INTO ai_provider_profiles
               (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at)
               VALUES ('p0-offline-provider', 'P0 Offline Provider', 'openai_responses', NULL,
                       'provider:p0-offline-provider', 1, 1, 1)"""
        )
        await conn.execute(
            """INSERT INTO ai_model_profiles
               (id, provider_profile_id, display_name, model_identifier, tier,
                capabilities_json, priority, enabled, is_default, created_at, updated_at)
               VALUES ('p0-offline-model', 'p0-offline-provider', 'P0 Offline Model',
                       'p0-offline-model', 'balanced', '[\"chat\"]', 1, 1, 1, 1, 1)"""
        )
        await conn.commit()


@asynccontextmanager
async def _running_uat_client(db_path, workspace, adapter: OfflineGyoAdapter, port: int):
    settings = Settings(
        db_path=str(db_path),
        default_workspace_root=str(workspace),
        cors_origins=["http://localhost:5173"],
        outbox_dispatcher_enabled=False,
        model_fallback_enabled=False,
        local_actor_subject="user",
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)
    from app.dependencies import get_db, get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    async def _override_db():
        async with get_db_connection(db_path) as conn:
            yield conn

    app.dependency_overrides[get_db] = _override_db
    app.state.gyo_orchestrator.providers["openai_responses"] = adapter
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", port)),
            base_url="http://testserver",
        ) as client:
            yield client, settings, app
    finally:
        await app.state.gyo_orchestrator.stop()


async def _create_work(client: AsyncClient, title: str, goal: str) -> str:
    response = await client.post(
        "/api/sessions",
        json={"title": title, "goal": goal, "data_scope": "work_only"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _create_conversation(client: AsyncClient, work_id: str, title: str) -> str:
    response = await client.post(
        f"/api/works/{work_id}/conversations",
        json={"title": title, "purpose": "P0 native GYO journey"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _count_attempts(db_path, package_id: str) -> int:
    async with get_db_connection(db_path) as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM action_attempts WHERE package_id = ?", (package_id,)
        ) as cur:
            return (await cur.fetchone())[0]


async def _assistant_turn(client: AsyncClient, thread_id: str, turn_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/assistant/threads/{thread_id}/turns")
    assert response.status_code == 200, response.text
    return next(turn for turn in response.json() if turn["id"] == turn_id)


@pytest.mark.asyncio
async def test_p0_native_gyo_integrated_journey_isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "p0_native_gyo.db"
    workspace = tmp_path / "p0_native_gyo_workspace"
    workspace.mkdir()
    await run_migrations(db_path)
    await _seed_offline_gyo(db_path)

    # The registry requires a credential to dispatch, but this deterministic
    # sentinel never leaves process memory and the injected adapter performs no
    # network operation.
    monkeypatch.setattr(
        "app.services.gyo_registry.keyring.get_password",
        lambda *_args: "offline-p0-test-credential",
    )
    adapter = OfflineGyoAdapter()

    try:
        async with _running_uat_client(db_path, workspace, adapter, 12345) as (client, settings, _app):
            # 1. Create one work_only Work and two explicit conversations.
            work_id = await _create_work(
                client,
                "uat-p0-Native GYO Work",
                "Hoàn thành báo cáo tổng hợp từ tài liệu đầu vào.",
            )
            dashboard = (await client.get(f"/api/works/{work_id}/dashboard")).json()
            assert dashboard["work"]["data_scope"] == "work_only"
            conv_a = await _create_conversation(client, work_id, "Trao đổi phân tích")
            conv_b = await _create_conversation(client, work_id, "Trao đổi kiểm tra")
            conversations = (await client.get(f"/api/works/{work_id}/conversations")).json()
            assert {conv_a, conv_b}.issubset({item["id"] for item in conversations})

            # 2. Register a validated managed source and a plan target.
            source_response = await client.post(
                f"/api/sessions/{work_id}/documents/files",
                headers={"Idempotency-Key": "p0-native-source"},
                json={"relative_path": "source-1.txt", "content": "Nguồn kiểm soát cho hành trình native GYO."},
            )
            assert source_response.status_code == 201, source_response.text
            source = source_response.json()
            assert source["validation_status"] == "structurally_validated"

            phase = await client.post(
                f"/api/works/{work_id}/plan/phases",
                json={"title": "Giai đoạn tổng hợp"},
            )
            assert phase.status_code == 201, phase.text
            step = await client.post(
                f"/api/works/{work_id}/plan/steps",
                json={
                    "phase_id": phase.json()["id"],
                    "title": "Tổng hợp báo cáo",
                    "status": "not_started",
                },
            )
            assert step.status_code == 201, step.text
            step_id = step.json()["id"]

            # 3. Current durable Assistant/GYO run. The offline adapter returns
            # visible text plus the same action-proposal marker real providers
            # must satisfy; the API owns parsing, scope, persistence and SSE.
            adapter.response_text = (
                "Đã đọc nguồn được người dùng chọn và chuẩn bị đề xuất.\n"
                "DIRAP_ACTION_PROPOSAL: "
                + json.dumps(
                    {
                        "title": "Cập nhật tiến độ Work",
                        "description": "Đánh dấu bước hoàn thành và Work đang thực hiện.",
                        "steps": [
                            {
                                "kind": "work_plan_step_update",
                                "input": {"step_id": step_id, "changes": {"status": "completed"}},
                            },
                            {
                                "kind": "work_status_update",
                                "input": {"work_status": "in_progress", "progress_percent": 50},
                            },
                        ],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            thread_response = await client.post(
                f"/api/assistant/works/{work_id}/conversations/{conv_a}/assistant-thread"
            )
            assert thread_response.status_code == 200, thread_response.text
            thread_id = thread_response.json()["id"]

            async def collect_events():
                return [event async for event in event_bus.subscribe(f"assistant:{thread_id}")]

            stream_task = asyncio.create_task(collect_events())
            await asyncio.sleep(0)
            run_response = await client.post(
                f"/api/assistant/threads/{thread_id}/runs",
                json={
                    "prompt": "Dùng nguồn đã chọn để đề xuất cập nhật tiến độ.",
                    "work_id": work_id,
                    "conversation_id": conv_a,
                    "attachment_artifact_ids": [source["id"]],
                    "model_profile_id": "p0-offline-model",
                    "route_mode": "manual",
                },
            )
            assert run_response.status_code == 202, run_response.text
            run_turns = run_response.json()
            assistant_turn_id = next(turn["id"] for turn in run_turns if turn["role"] == "assistant")
            stream_events = await asyncio.wait_for(stream_task, timeout=2)
            assert any(event.type == "token" and event.assistant_turn_id == assistant_turn_id for event in stream_events)
            assert stream_events[-1].type == "done"
            assert stream_events[-1].assistant_turn_id == assistant_turn_id
            assert len(adapter.requests) == 1
            assert adapter.requests[0].work_id == work_id
            assert adapter.requests[0].assistant_turn_id == assistant_turn_id
            assert "## source-1.txt" in adapter.requests[0].context
            assert "Nguồn kiểm soát cho hành trình native GYO." in adapter.requests[0].context

            persisted = await _assistant_turn(client, thread_id, assistant_turn_id)
            assert persisted["status"] == "completed"
            part_types = {part["part_type"] for part in persisted["parts"]}
            assert {"text", "source", "action_proposal"}.issubset(part_types)
            source_parts = [part for part in persisted["parts"] if part["part_type"] == "source"]
            assert any(
                part["content"].get("id") == source["id"]
                and part["content"].get("reason") == "Tệp đính kèm được người dùng chọn"
                for part in source_parts
            )
            proposal_part = next(part for part in persisted["parts"] if part["part_type"] == "action_proposal")
            proposal = proposal_part["content"]
            assert proposal["work_id"] == work_id
            assert proposal["conversation_id"] == conv_a

            # 4. A proposal is read-only. No Work mutation or package exists yet.
            plan_before = (await client.get(f"/api/works/{work_id}/plan")).json()
            step_before = next(
                item
                for phase_item in plan_before
                for item in phase_item["steps"]
                if item["id"] == step_id
            )
            assert step_before["status"] == "not_started"
            assert (await client.get(f"/api/works/{work_id}/action-packages")).json() == []

            # Cross-Work source selection fails closed before another GYO run can
            # be created or a foreign source can enter model-visible context.
            other_work = await _create_work(client, "uat-p0-Other Work", "Isolation check")
            other_source_response = await client.post(
                f"/api/sessions/{other_work}/documents/files",
                headers={"Idempotency-Key": "p0-native-other-source"},
                json={"relative_path": "foreign.txt", "content": "Không thuộc Work chính."},
            )
            assert other_source_response.status_code == 201, other_source_response.text
            foreign_run = await client.post(
                f"/api/assistant/threads/{thread_id}/runs",
                json={
                    "prompt": "Không được dùng nguồn Work khác.",
                    "attachment_artifact_ids": [other_source_response.json()["id"]],
                },
            )
            assert foreign_run.status_code == 404
            assert len(adapter.requests) == 1

            # 5. Create an immutable package from the persisted proposal part.
            package_payload = {
                "title": proposal["title"],
                "description": proposal.get("description"),
                "conversation_id": conv_a,
                "source_proposal_part_id": proposal_part["id"],
                "steps": proposal["steps"],
            }
            package_response = await client.post(
                f"/api/works/{work_id}/action-packages",
                json=package_payload,
                headers={"Idempotency-Key": "p0-native-package"},
            )
            assert package_response.status_code == 201, package_response.text
            package = package_response.json()
            package_id = package["id"]
            duplicate = await client.post(
                f"/api/works/{work_id}/action-packages",
                json=package_payload,
                headers={"Idempotency-Key": "p0-native-package"},
            )
            assert duplicate.status_code == 200, duplicate.text
            assert duplicate.json()["id"] == package_id
            conflict = await client.post(
                f"/api/works/{work_id}/action-packages",
                json={**package_payload, "title": "Payload khác"},
                headers={"Idempotency-Key": "p0-native-package"},
            )
            assert conflict.status_code == 409

            # 6. Canonical preflight immediately precedes exact-binding approval.
            preflight_response = await client.get(f"/api/action-packages/{package_id}/preflight")
            assert preflight_response.status_code == 200, preflight_response.text
            preflight = preflight_response.json()
            assert preflight["valid"] is True
            assert preflight["package_id"] == package_id
            assert preflight["revision"] == package["revision"]
            assert preflight["payload_hash"] == package["payload_hash"]
            approval = await client.post(
                f"/api/action-packages/{package_id}/approve",
                headers={"Idempotency-Key": "p0-native-approve"},
                json={
                    "expected_revision": preflight["revision"],
                    "expected_payload_hash": preflight["payload_hash"],
                },
            )
            assert approval.status_code == 200, approval.text
            assert approval.json()["status"] == "approved"

            # 7. Execute the approved package exactly once. A second worker pass
            # must find no claimable approved package and create no attempts.
            assert await execute_one_approved_package(settings, "p0-native-worker") is True
            attempts_after_first = await _count_attempts(db_path, package_id)
            assert attempts_after_first == len(package_payload["steps"])
            assert await execute_one_approved_package(settings, "p0-native-worker-repeat") is False
            assert await _count_attempts(db_path, package_id) == attempts_after_first

            terminal_packages = (await client.get(f"/api/works/{work_id}/action-packages")).json()
            terminal_package = next(item for item in terminal_packages if item["id"] == package_id)
            assert terminal_package["status"] == "succeeded"
            plan_after = (await client.get(f"/api/works/{work_id}/plan")).json()
            step_after = next(
                item
                for phase_item in plan_after
                for item in phase_item["steps"]
                if item["id"] == step_id
            )
            assert step_after["status"] == "completed"
            work_after = (await client.get(f"/api/works/{work_id}/dashboard")).json()["work"]
            assert work_after["work_status"] == "in_progress"
            assert work_after["progress_percent"] == 100
            assert work_after["progress_source"] == "plan_steps"
            assert (await client.get(f"/api/works/{other_work}/action-packages")).json() == []

            # 8. Create and read a managed report artifact before restart.
            report_response = await client.post(
                f"/api/sessions/{work_id}/reports",
                headers={"Idempotency-Key": "p0-native-report"},
                json={
                    "title": "Báo cáo P0 Native GYO",
                    "content": "Kết quả hành trình current GYO đã được áp dụng qua Action Package.",
                    "output_format": "markdown",
                },
            )
            assert report_response.status_code == 201, report_response.text
            report = report_response.json()
            report_content = await client.get(f"/api/sessions/{work_id}/artifacts/{report['id']}/content")
            assert report_content.status_code == 200
            assert b"P0 Native GYO" in report_content.content

            expected = {
                "work_id": work_id,
                "conv_a": conv_a,
                "conv_b": conv_b,
                "thread_id": thread_id,
                "assistant_turn_id": assistant_turn_id,
                "package_id": package_id,
                "step_id": step_id,
                "report_id": report["id"],
                "attempt_count": attempts_after_first,
            }

        # 9. A fresh app/client over the same isolated DB/workspace must recover
        # the durable Work, conversation, GYO, package, execution and artifact.
        restart_adapter = OfflineGyoAdapter()
        async with _running_uat_client(db_path, workspace, restart_adapter, 12346) as (client, _settings, _app):
            recovered_dashboard = (await client.get(f"/api/works/{expected['work_id']}/dashboard")).json()["work"]
            assert recovered_dashboard["data_scope"] == "work_only"
            assert recovered_dashboard["work_status"] == "in_progress"
            assert recovered_dashboard["progress_percent"] == 100

            recovered_conversations = (await client.get(
                f"/api/works/{expected['work_id']}/conversations"
            )).json()
            recovered_ids = {item["id"] for item in recovered_conversations}
            assert {expected["conv_a"], expected["conv_b"]}.issubset(recovered_ids)

            recovered_turn = await _assistant_turn(
                client, expected["thread_id"], expected["assistant_turn_id"]
            )
            assert recovered_turn["status"] == "completed"
            assert {"text", "source", "action_proposal"}.issubset(
                {part["part_type"] for part in recovered_turn["parts"]}
            )

            recovered_packages = (await client.get(
                f"/api/works/{expected['work_id']}/action-packages"
            )).json()
            recovered_package = next(
                item for item in recovered_packages if item["id"] == expected["package_id"]
            )
            assert recovered_package["status"] == "succeeded"
            assert await _count_attempts(db_path, expected["package_id"]) == expected["attempt_count"]

            recovered_plan = (await client.get(f"/api/works/{expected['work_id']}/plan")).json()
            recovered_step = next(
                item
                for phase_item in recovered_plan
                for item in phase_item["steps"]
                if item["id"] == expected["step_id"]
            )
            assert recovered_step["status"] == "completed"

            artifacts = (await client.get(f"/api/sessions/{expected['work_id']}/artifacts")).json()
            assert expected["report_id"] in {item["id"] for item in artifacts}
            recovered_report = await client.get(
                f"/api/sessions/{expected['work_id']}/artifacts/{expected['report_id']}/content"
            )
            assert recovered_report.status_code == 200
            assert b"P0 Native GYO" in recovered_report.content
            assert restart_adapter.requests == []
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
