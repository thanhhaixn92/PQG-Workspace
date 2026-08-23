"""Focused regression tests for the GYO Assistant control plane."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import time
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.db.connection import get_db_connection
from app.services.action_packages import execute_one_approved_package
from app.services.marketplace_catalog import canonical_catalog_payload, ingest_verified_catalog
from app.api.assistant import (
    _extract_action_proposal,
    _normalize_cancel_outcome,
    _proposal_contract_diagnostic,
    _proposal_contract_reason_code,
)


class FakeGyo:
    """Small stream-only fake; it never invokes an external model runtime."""

    def __init__(
        self,
        *,
        text: str = "Phản hồi GYO chỉ đọc.",
        structured_parts=None,
        status: str = "completed",
        provider_profile_id: str | None = None,
        model_profile_id: str | None = None,
        selection_reason: str = "test",
    ):
        self.text = text
        self.structured_parts = structured_parts or []
        self.status = status
        self.provider_profile_id = provider_profile_id
        self.model_profile_id = model_profile_id
        self.selection_reason = selection_reason
        self.requests = []
        self.cancel_outcome = "cancelled"

    async def stream(self, request):
        self.requests.append(request)
        if self.status == "completed" and self.text:
            yield SimpleNamespace(type="token", data={"text": self.text})
        yield SimpleNamespace(type="done", data={
            "text": self.text,
            "status": self.status,
            "model_id": "fake-gyo-model",
            "provider_profile_id": self.provider_profile_id,
            "model_profile_id": self.model_profile_id,
            "route_mode": request.route_mode,
            "selection_reason": self.selection_reason,
            "structured_parts": self.structured_parts,
        })

    async def cancel(self, assistant_turn_id: str) -> str:
        return self.cancel_outcome


def _e2_runner_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run-package-e2-bounded-real-provider.py"
    spec = importlib.util.spec_from_file_location("e2_bounded_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def resolve_bound_thread(client, work_id: str) -> dict:
    """Create no legacy thread: resolve the Work's active Conversation first."""
    conversations = (await client.get(f"/api/works/{work_id}/conversations")).json()
    conversation = next(item for item in conversations if item["status"] == "active")
    response = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation['id']}/assistant-thread"
    )
    assert response.status_code == 200
    thread = response.json()
    assert thread["work_id"] == work_id
    assert thread["conversation_id"] == conversation["id"]
    return thread


@pytest.mark.asyncio
async def test_package_a_bound_thread_resolver_is_idempotent_and_global_thread_cannot_create_work_turn(client):
    """New Work turns may only originate from the canonical bound-thread resolver."""
    work = (await client.post("/api/sessions", json={"title": "Package A scope"})).json()
    conversation = (await client.get(f"/api/works/{work['id']}/conversations")).json()[0]

    first, second = await asyncio.gather(
        client.post(f"/api/assistant/works/{work['id']}/conversations/{conversation['id']}/assistant-thread"),
        client.post(f"/api/assistant/works/{work['id']}/conversations/{conversation['id']}/assistant-thread"),
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["work_id"] == work["id"]
    assert first.json()["conversation_id"] == conversation["id"]

    global_thread = (await client.post("/api/assistant/threads", json={"title": "Global"})).json()
    for path in ("turns", "runs"):
        rejected = await client.post(
            f"/api/assistant/threads/{global_thread['id']}/{path}",
            json={"prompt": "must fail closed", "work_id": work["id"], "conversation_id": conversation["id"]},
        )
        assert rejected.status_code in {409, 422}

    missing_conversation = await client.post(
        "/api/assistant/threads", json={"title": "Invalid Work thread", "work_id": work["id"]},
    )
    assert missing_conversation.status_code == 422


def test_proposal_contract_diagnostic_is_safe_and_deterministic():
    assert _proposal_contract_diagnostic("Chỉ giải thích") == "missing_marker"
    assert _proposal_contract_reason_code("Chỉ giải thích") == "marker_missing"
    assert _proposal_contract_diagnostic("DIRAP_ACTION_PROPOSAL: {") == "invalid_json"
    assert _proposal_contract_reason_code("DIRAP_ACTION_PROPOSAL: {") == "json_syntax"
    assert _proposal_contract_diagnostic('DIRAP_ACTION_PROPOSAL: {"title":"x","steps":[]}') == "invalid_schema"
    assert _proposal_contract_reason_code('DIRAP_ACTION_PROPOSAL: {"title":"x","steps":[]}') == "steps_invalid"
    assert _proposal_contract_diagnostic(
        'DIRAP_ACTION_PROPOSAL: {"title":"x","steps":[]}\nDIRAP_ACTION_PROPOSAL: {"title":"y","steps":[]}'
    ) == "invalid_json"
    assert _proposal_contract_reason_code(
        'DIRAP_ACTION_PROPOSAL: {"title":"x","steps":[]}\nDIRAP_ACTION_PROPOSAL: {"title":"y","steps":[]}'
    ) == "multiple_markers"
    text, proposal, diagnostic = _extract_action_proposal(
        'Sẽ chuẩn bị.\nDIRAP_ACTION_PROPOSAL: ```json\n{"title":"Cập nhật Work","description":"Có thể hoàn tác","conversation_id":"foreign-conversation","source_proposal_part_id":"model-controlled","steps":[{"kind":"work_status_update","input":{"work_status":"in_progress","progress_percent":25}}]}\n```',
        work_id="w1", conversation_id="c1",
    )
    assert text == "Sẽ chuẩn bị."
    assert diagnostic == "valid"
    assert proposal is not None and proposal["work_id"] == "w1"
    assert proposal["conversation_id"] == "c1"
    assert "source_proposal_part_id" not in proposal


def test_e2_runner_contract_diagnostics_are_redacted_and_action_scoped():
    runner = _e2_runner_module()
    persisted = runner._e2_contract_diagnostics({
        "status": "completed",
        "parts": [{
            "part_type": "tool_result",
            "content": {
                "tool_name": "action_proposal_contract",
                "diagnostic": "invalid_json",
                "reason_code": "json_syntax",
                "summary": "raw provider output must not be copied",
            },
        }],
    })
    assert persisted == [{"diagnostic": "invalid_json", "reason_code": "json_syntax"}]
    assert runner._e2_contract_diagnostics({"status": "completed", "parts": []}) == [{
        "diagnostic": "missing_marker",
        "reason_code": "marker_missing",
        "source": "e2_runner_inference",
    }]


@pytest.mark.asyncio
async def test_action_proposal_prompt_keeps_work_conversation_scope_server_bound(client, test_app):
    """A provider is not asked to invent identifiers it cannot see."""
    gyo = FakeGyo(text="Phản hồi chỉ đọc.")
    test_app.state.gyo_orchestrator = gyo
    work_id = (await client.post("/api/sessions", json={"title": "Prompt scope"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    response = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Đặt tiến độ thành 1%", "conversation_id": thread["conversation_id"]},
    )

    assert response.status_code == 200
    provider_prompt = gyo.requests[-1].prompt
    assert "Phạm vi Công việc/Phiên trao đổi do server gắn" in provider_prompt
    assert "không thêm work_id hoặc conversation_id" in provider_prompt
    assert '"work_status":"in_progress"' in provider_prompt
    assert thread["conversation_id"] not in provider_prompt


@pytest.mark.asyncio
async def test_invalid_proposal_persists_only_allowlisted_reason_code(client, test_app):
    test_app.state.gyo_orchestrator = FakeGyo(text="DIRAP_ACTION_PROPOSAL: {")
    work_id = (await client.post("/api/sessions", json={"title": "Invalid proposal"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    response = await client.post(f"/api/assistant/threads/{thread['id']}/turns", json={"prompt": "Bắt đầu"})

    assert response.status_code == 200
    parts = response.json()[1]["parts"]
    contract = next(part["content"] for part in parts if part["part_type"] == "tool_result")
    assert contract == {
        "tool_name": "action_proposal_contract",
        "status": "failed",
        "diagnostic": "invalid_json",
        "reason_code": "json_syntax",
        "summary": "Đề xuất không được lưu vì sai contract (invalid_json).",
    }


def test_cancel_outcome_normalizes_gyo_adapters_fail_closed():
    assert _normalize_cancel_outcome("cancelled") == "cancelled"
    assert _normalize_cancel_outcome("not_active") == "not_active"
    assert _normalize_cancel_outcome(True) == "cancelled"
    assert _normalize_cancel_outcome(False) == "adapter_failed"
    assert _normalize_cancel_outcome("unexpected") == "adapter_failed"


@pytest.mark.asyncio
async def test_assistant_home_is_read_scoped_and_work_scope_is_explicit(client, test_app):
    gyo = FakeGyo(text="Đây là phản hồi GYO chỉ đọc.")
    test_app.state.gyo_orchestrator = gyo
    work_id = (await client.post("/api/sessions", json={"title": "Kế hoạch A", "goal": "Hoàn tất việc A"})).json()["id"]
    thread = await client.post("/api/assistant/threads", json={"title": "Trợ lý hôm nay"})
    assert thread.status_code == 201
    home_turns = await client.post(f"/api/assistant/threads/{thread.json()['id']}/turns", json={"prompt": "Tôi có gì?"})
    assert home_turns.status_code == 200
    assert "chọn một Công việc" in home_turns.json()[1]["parts"][0]["content"]["text"]
    scoped_thread = await resolve_bound_thread(client, work_id)
    scoped = await client.post(f"/api/assistant/threads/{scoped_thread['id']}/turns", json={"prompt": "Xem việc", "conversation_id": scoped_thread["conversation_id"]})
    assert scoped.status_code == 200
    assert scoped.json()[1]["status"] == "completed"
    assert scoped.json()[1]["model_id"] == "fake-gyo-model"
    assert scoped.json()[1]["parts"][0]["content"]["text"] == "Đây là phản hồi GYO chỉ đọc."
    assert scoped.json()[1]["parts"][1]["content"]["kind"] == "work"
    assert gyo.requests[-1].route_mode == "auto"
    manifest = await client.get("/api/assistant/context-manifest", params={"work_id": work_id})
    assert manifest.status_code == 200
    assert manifest.json()["memory_hub_auto_injected"] is False
    assert any(item["kind"] == "memory_hub" for item in manifest.json()["excluded"])
    assert any(item["kind"] == "approved_library" for item in manifest.json()["excluded"])


@pytest.mark.asyncio
async def test_work_scoped_assistant_reports_unavailable_gyo_without_fake_success(client):
    work_id = (await client.post("/api/sessions", json={"title": "GYO chưa sẵn sàng"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    response = await client.post(f"/api/assistant/threads/{thread['id']}/turns", json={"prompt": "Tóm tắt"})

    assert response.status_code == 200
    assistant_turn = response.json()[1]
    assert assistant_turn["status"] == "failed"
    assert assistant_turn["model_id"] == "gyo-unavailable"
    assert assistant_turn["parts"][0]["part_type"] == "error"
    assert "chưa sẵn sàng" in assistant_turn["parts"][0]["content"]["message"]

    retried = await client.post(f"/api/assistant/turns/{assistant_turn['id']}/retry", json={"mode": "auto"})
    assert retried.status_code == 202
    assert retried.json()["status"] == "running"
    turns = await client.get(f"/api/assistant/threads/{thread['id']}/turns")
    assert [turn["role"] for turn in turns.json()] == ["user", "assistant", "assistant"]
    assert turns.json()[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_retry_same_model_reuses_last_actual_model_without_duplicate_user_turn(client, test_app, migrated_db_path):
    gyo = FakeGyo(status="failed", text="", provider_profile_id="retry-provider", model_profile_id="retry-model")
    test_app.state.gyo_orchestrator = gyo
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES ('retry-provider', 'Retry provider', 'openai_responses', NULL, 'provider:retry', 1, 1, 1)")
        await db.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES ('retry-model', 'retry-provider', 'Retry model', 'retry-model', 'balanced', '[\"chat\"]', 1, 1, 1, 1, 1)")
        await db.commit()
    work_id = (await client.post("/api/sessions", json={"title": "Retry same"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    first = await client.post(f"/api/assistant/threads/{thread['id']}/turns", json={"prompt": "Giữ nguyên model", "work_id": work_id})
    assert first.status_code == 200
    failed_turn_id = first.json()[1]["id"]
    retried = await client.post(f"/api/assistant/turns/{failed_turn_id}/retry", json={"mode": "same_model"})
    assert retried.status_code == 202
    assert gyo.requests[-1].route_mode == "manual"
    assert gyo.requests[-1].model_profile_id == "retry-model"
    history = await client.get(f"/api/assistant/threads/{thread['id']}/turns")
    assert len([turn for turn in history.json() if turn["role"] == "user"]) == 1


@pytest.mark.asyncio
async def test_read_only_assistant_run_is_persisted_and_scoped_before_it_completes(client, test_app):
    gyo = FakeGyo(
        text="Phản hồi chỉ đọc đã hoàn tất.",
        structured_parts=[("tool_result", {"tool_name": "safe_lookup", "status": "succeeded", "summary": "Đã tra cứu nguồn đã lọc.", "arguments": {"secret": "not persisted"}})],
    )
    test_app.state.gyo_orchestrator = gyo
    work_id = (await client.post("/api/sessions", json={"title": "Luồng GYO"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    created = await client.post(
        f"/api/assistant/threads/{thread['id']}/runs",
        json={"prompt": "Tóm tắt", "work_id": work_id},
    )

    assert created.status_code == 202
    assert [turn["role"] for turn in created.json()] == ["user", "assistant"]
    turns = await client.get(f"/api/assistant/threads/{thread['id']}/turns")
    assert turns.status_code == 200
    assert turns.json()[-1]["status"] == "completed"
    assert turns.json()[-1]["parts"][0]["content"]["text"] == "Phản hồi chỉ đọc đã hoàn tất."
    tool_part = next(part for part in turns.json()[-1]["parts"] if part["part_type"] == "tool_result")
    assert tool_part["content"] == {"tool_name": "safe_lookup", "status": "succeeded", "summary": "Đã tra cứu nguồn đã lọc."}
    assert gyo.requests[-1].event_channel == f"assistant:{thread['id']}"
    assert gyo.requests[-1].assistant_turn_id == turns.json()[-1]["id"]


@pytest.mark.asyncio
async def test_assistant_allows_only_one_running_response_and_blocks_archive(client, migrated_db_path):
    work_id = (await client.post("/api/sessions", json={"title": "Một phản hồi tại một thời điểm"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)",
            ("running-turn", thread["id"], work_id, thread["conversation_id"], now),
        )
        await db.commit()

    second = await client.post(f"/api/assistant/threads/{thread['id']}/runs", json={"prompt": "Gửi tiếp"})
    assert second.status_code == 409
    archived = await client.patch(f"/api/assistant/threads/{thread['id']}", json={"archived": True})
    assert archived.status_code == 409


@pytest.mark.asyncio
async def test_cancelling_running_assistant_turn_is_durable_and_audited(client, test_app, migrated_db_path):
    test_app.state.gyo_orchestrator = FakeGyo()
    work_id = (await client.post("/api/sessions", json={"title": "Hủy phản hồi"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)",
            ("cancel-turn", thread["id"], work_id, thread["conversation_id"], now),
        )
        await db.commit()

    cancelled = await client.post("/api/assistant/turns/cancel-turn/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["parts"][0]["part_type"] == "error"
    assert "Nội dung đến muộn" in cancelled.json()["parts"][0]["content"]["message"]
    repeated = await client.post("/api/assistant/turns/cancel-turn/cancel")
    assert repeated.status_code == 409
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT action, payload_json FROM audit_events WHERE target = ? ORDER BY created_at, rowid",
            ("cancel-turn",),
        ) as cur:
            events = await cur.fetchall()
        assert [event["action"] for event in events] == [
            "assistant.turn.cancelled",
            "assistant.turn.cancel_compute",
        ]
        assert json.loads(events[-1]["payload_json"])["outcome"] in {
            "cancelled", "not_active", "connection_unavailable", "adapter_failed", "unsupported",
        }


@pytest.mark.asyncio
async def test_assistant_persists_manual_model_provenance_once(client, test_app, migrated_db_path):
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES (?, ?, 'openai_compatible', ?, ?, 1, ?, ?)",
            ("provider-manual", "Manual", "http://127.0.0.1:1234/v1", "test:manual", now, now),
        )
        await db.execute(
            "INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, 'balanced', '[]', 100, 1, 0, ?, ?)",
            ("manual-model", "provider-manual", "Manual model", "manual-model-id", now, now),
        )
        await db.commit()
    gyo = FakeGyo(
        provider_profile_id="provider-manual",
        model_profile_id="manual-model",
        selection_reason="manual_pin",
    )
    test_app.state.gyo_orchestrator = gyo
    work_id = (await client.post("/api/sessions", json={"title": "Chọn mô hình"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    response = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Trả lời", "model_profile_id": "manual-model", "route_mode": "manual"},
    )

    assert response.status_code == 200
    assert gyo.requests[-1].model_profile_id == "manual-model"
    assert gyo.requests[-1].route_mode == "manual"
    assistant_turn_id = response.json()[1]["id"]
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT provider_profile_id, model_profile_id, route_mode, selection_reason, fallback_from_model_profile_id FROM assistant_run_metadata WHERE assistant_turn_id = ?",
            (assistant_turn_id,),
        ) as cur:
            metadata = await cur.fetchone()
    assert dict(metadata) == {
        "provider_profile_id": "provider-manual",
        "model_profile_id": "manual-model",
        "route_mode": "manual",
        "selection_reason": "manual_pin",
        "fallback_from_model_profile_id": None,
    }


@pytest.mark.asyncio
async def test_assistant_persists_cancelled_gyo_provenance_once(client, test_app, migrated_db_path):
    test_app.state.gyo_orchestrator = FakeGyo(text="", status="cancelled", selection_reason="cancelled_test")
    work_id = (await client.post("/api/sessions", json={"title": "GYO cancel provenance"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    created = await client.post(f"/api/assistant/threads/{thread['id']}/runs", json={"prompt": "Dừng"})
    assert created.status_code == 202
    assistant_turn_id = created.json()[1]["id"]
    turns = await client.get(f"/api/assistant/threads/{thread['id']}/turns")
    assert turns.json()[-1]["status"] == "cancelled"
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT route_mode, selection_reason FROM assistant_run_metadata WHERE assistant_turn_id = ?",
            (assistant_turn_id,),
        ) as cur:
            metadata = await cur.fetchone()
    assert dict(metadata) == {"route_mode": "auto", "selection_reason": "cancelled_test"}


@pytest.mark.asyncio
async def test_cancelled_assistant_turn_discards_a_late_completion(client, migrated_db_path):
    from app.api.assistant import _run_read_only_turn
    from app.settings import Settings

    work_id = (await client.post("/api/sessions", json={"title": "Bỏ kết quả đến muộn"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)",
            ("late-turn", thread["id"], work_id, thread["conversation_id"], now),
        )
        await db.commit()

    assert (await client.post("/api/assistant/turns/late-turn/cancel")).status_code == 200
    settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False)
    await _run_read_only_turn(
        assistant_id="late-turn",
        thread_id=thread["id"],
        work_id=work_id,
        conversation_id=thread["conversation_id"],
        prompt="Kết quả này không được phép lưu",
        gyo_orchestrator=None,
        settings=settings,
    )

    turn = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()[0]
    assert turn["status"] == "cancelled"
    assert len(turn["parts"]) == 1


@pytest.mark.asyncio
async def test_cancelled_dispatched_turn_persists_late_routing_once_without_output(client, migrated_db_path):
    """A cancel wins visible state; a late terminal may add only safe provenance."""
    from app.api.assistant import _run_read_only_turn
    from app.settings import Settings

    class DelayedTerminalGyo:
        def __init__(self) -> None:
            self.release = asyncio.Event()
            self.started = asyncio.Event()

        async def stream(self, request):
            self.started.set()
            await self.release.wait()
            yield SimpleNamespace(type="token", data={"text": "late provider text"})
            yield SimpleNamespace(type="done", data={
                "text": "late provider text", "status": "completed", "model_id": "manual-model-id",
                "provider_profile_id": "late-provider", "model_profile_id": "late-model",
                "route_mode": "manual", "selection_reason": "manual_selection", "fallback_chain": [],
                "structured_parts": [],
            })

        async def cancel(self, _assistant_turn_id: str) -> str:
            return "cancelled"

    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES ('late-provider', 'Late provider', 'openai_compatible', 'http://127.0.0.1:1234/v1', 'test:late', 1, ?, ?)",
            (now, now),
        )
        await db.execute(
            "INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES ('late-model', 'late-provider', 'Late model', 'manual-model-id', 'balanced', '[\"chat\"]', 1, 1, 0, ?, ?)",
            (now, now),
        )
        await db.commit()
    work_id = (await client.post("/api/sessions", json={"title": "Late provenance"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO assistant_turns (id, thread_id, work_id, role, status, model_id, created_at) VALUES ('late-provenance-turn', ?, ?, 'assistant', 'running', 'gyo', ?)",
            (thread["id"], work_id, now),
        )
        await db.commit()

    gyo = DelayedTerminalGyo()
    settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False)
    run_task = asyncio.create_task(_run_read_only_turn(
        assistant_id="late-provenance-turn", thread_id=thread["id"], work_id=work_id,
        conversation_id=None, prompt="no persisted late text", gyo_orchestrator=gyo,
        settings=settings, model_profile_id="late-model", route_mode="manual",
    ))
    await asyncio.wait_for(gyo.started.wait(), timeout=1)
    assert (await client.post("/api/assistant/turns/late-provenance-turn/cancel")).status_code == 200
    gyo.release.set()
    await asyncio.wait_for(run_task, timeout=1)

    # Replaying a terminal completion cannot create another provenance row or visible text.
    await _run_read_only_turn(
        assistant_id="late-provenance-turn", thread_id=thread["id"], work_id=work_id,
        conversation_id=None, prompt="no persisted late text", gyo_orchestrator=gyo,
        settings=settings, model_profile_id="late-model", route_mode="manual",
    )
    turn = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()[0]
    assert turn["status"] == "cancelled"
    assert [part["part_type"] for part in turn["parts"]] == ["error"]
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute(
            "SELECT provider_profile_id, model_profile_id, route_mode, selection_reason, fallback_chain_json, COUNT(*) OVER () AS total FROM assistant_run_metadata WHERE assistant_turn_id = 'late-provenance-turn'",
        ) as cur:
            metadata = await cur.fetchone()
    metadata_dict = dict(metadata)
    assert {key: value for key, value in metadata_dict.items() if key != "fallback_chain_json"} == {
        "provider_profile_id": "late-provider", "model_profile_id": "late-model",
        "route_mode": "manual", "selection_reason": "manual_selection", "total": 1,
    }
    assert json.loads(metadata_dict["fallback_chain_json"]) == [{
        "provider_profile_id": "late-provider", "model_profile_id": "late-model", "outcome": "cancelled",
    }]


@pytest.mark.asyncio
async def test_cancelled_dispatched_turn_persists_selected_routing_without_terminal(client, test_app, migrated_db_path):
    """A selected route is durable even if the adapter never emits a terminal event."""
    class NoTerminalGyo:
        async def cancel_with_selected_routing(self, assistant_turn_id: str):
            assert assistant_turn_id == "no-terminal-turn"
            return "cancelled", {
                "provider_profile_id": "no-terminal-provider", "model_profile_id": "no-terminal-model",
                "route_mode": "manual", "selection_reason": "manual_selection", "fallback_chain": [],
            }

    test_app.state.gyo_orchestrator = NoTerminalGyo()
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES ('no-terminal-provider', 'No terminal provider', 'openai_responses', NULL, 'test:no-terminal', 1, ?, ?)", (now, now))
        await db.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES ('no-terminal-model', 'no-terminal-provider', 'No terminal model', 'no-terminal-model-id', 'balanced', '[\"chat\"]', 1, 1, 0, ?, ?)", (now, now))
        await db.commit()
    work_id = (await client.post("/api/sessions", json={"title": "No terminal provenance"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("INSERT INTO assistant_turns (id, thread_id, work_id, role, status, model_id, created_at) VALUES ('no-terminal-turn', ?, ?, 'assistant', 'running', 'gyo', ?)", (thread["id"], work_id, now))
        await db.commit()

    cancelled = await client.post("/api/assistant/turns/no-terminal-turn/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["routing"]["attempts"][0]["outcome"] == "cancelled"
    turn = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()[0]
    assert turn["status"] == "cancelled"
    assert [part["part_type"] for part in turn["parts"]] == ["error"]
    async with get_db_connection(migrated_db_path) as db:
        async with db.execute("SELECT provider_profile_id, model_profile_id, route_mode, selection_reason, fallback_chain_json, COUNT(*) OVER () AS total FROM assistant_run_metadata WHERE assistant_turn_id = 'no-terminal-turn'") as cur:
            metadata = dict(await cur.fetchone())
    assert metadata["provider_profile_id"] == "no-terminal-provider"
    assert metadata["model_profile_id"] == "no-terminal-model"
    assert metadata["route_mode"] == "manual"
    assert metadata["selection_reason"] == "manual_selection"
    assert metadata["total"] == 1
    assert json.loads(metadata["fallback_chain_json"]) == [{"provider_profile_id": "no-terminal-provider", "model_profile_id": "no-terminal-model", "outcome": "cancelled"}]


@pytest.mark.asyncio
async def test_assistant_thread_history_is_opt_in_and_can_be_restored(client):
    work_id = (await client.post("/api/sessions", json={"title": "Lịch sử trao đổi"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)

    archived = await client.patch(f"/api/assistant/threads/{thread['id']}", json={"archived": True})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert not any(item["id"] == thread["id"] for item in (await client.get("/api/assistant/threads")).json())

    history = await client.get("/api/assistant/threads", params={"include_archived": "true"})
    assert history.status_code == 200
    assert any(item["id"] == thread["id"] and item["status"] == "archived" for item in history.json())

    restored = await client.patch(f"/api/assistant/threads/{thread['id']}", json={"archived": False})
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"


@pytest.mark.asyncio
async def test_work_data_scope_is_explicit_and_persisted(client):
    created = await client.post(
        "/api/sessions",
        json={"title": "Phạm vi đã chọn", "data_scope": "approved_library"},
    )
    assert created.status_code == 201
    work_id = created.json()["id"]
    assert created.json()["data_scope"] == "approved_library"

    updated = await client.patch(f"/api/works/{work_id}", json={"data_scope": "work_only"})
    assert updated.status_code == 200
    assert updated.json()["data_scope"] == "work_only"
    manifest = await client.get("/api/assistant/context-manifest", params={"work_id": work_id})
    assert any(item["kind"] == "approved_library" for item in manifest.json()["excluded"])


@pytest.mark.asyncio
async def test_context_manifest_is_versioned_scoped_and_excludes_memory_hub(client, migrated_db_path):
    work = (await client.post(
        "/api/sessions", json={"title": "Context Work", "goal": "Use selected evidence", "data_scope": "approved_library"},
    )).json()
    conversation = (await client.post(
        f"/api/works/{work['id']}/conversations", json={"title": "Context conversation"},
    )).json()
    now = int(time.time())
    async with get_db_connection(migrated_db_path) as db:
        await db.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, created_at, conversation_id) VALUES (?, ?, 'user', ?, ?, ?)",
            ("context-message", work["id"], "Evidence in selected conversation", now, conversation["id"]),
        )
        await db.execute(
            "INSERT INTO skills (id, name, normalized_name, description, content, enabled, status, version, updated_at) VALUES (?, ?, ?, ?, ?, 1, 'approved', 1, ?)",
            ("context-skill", "Approved context skill", "approved context skill", "Safe skill", "Skill evidence", now),
        )
        await db.commit()

    response = await client.get(
        "/api/assistant/context-manifest",
        params={"work_id": work["id"], "conversation_id": conversation["id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] and body["generated_at"]
    assert 0 < body["byte_count"] <= body["byte_limit"] == 12_000
    assert body["from_message_id"] == body["through_message_id"] == "context-message"
    assert any(item["kind"] == "conversation" for item in body["included"])
    assert any(item["kind"] == "skill" and item["id"] == "context-skill" for item in body["included"])
    assert any(item["kind"] == "memory_hub" for item in body["excluded"])


@pytest.mark.asyncio
async def test_assistant_attachments_are_scoped_ordered_and_preserved_on_retry(client, test_app, migrated_db_path):
    gyo = FakeGyo()
    test_app.state.gyo_orchestrator = gyo
    work = (await client.post("/api/sessions", json={"title": "Attachment Work"})).json()
    other = (await client.post("/api/sessions", json={"title": "Other Work"})).json()
    attachments = []
    async with get_db_connection(migrated_db_path) as db:
        for index, name in enumerate(("first.txt", "second.bin")):
            target = __import__("pathlib").Path(work["workspace_path"]) / "inputs" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            content = b"selected evidence" if name.endswith(".txt") else b"\x00\x01"
            target.write_bytes(content)
            artifact_id = f"attachment-{index}"
            attachments.append(artifact_id)
            await db.execute(
                "INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at) VALUES (?, ?, ?, 'imported_file', ?, ?, ?)",
                (artifact_id, work["id"], f"inputs/{name}", hashlib.sha256(content).hexdigest(), len(content), int(time.time()) + index),
            )
            await db.execute(
                """INSERT INTO artifact_validations
                   (artifact_id, status, media_type, validator_version, detail_json, validated_at)
                   VALUES (?, 'structurally_validated', 'text/plain', 'test', '{}', ?)""",
                (artifact_id, int(time.time()) + index),
            )
        # Keep the selected attachments outside the general latest-20 query.
        # Explicit attachment priority must not depend on artifact recency.
        for index in range(21):
            content = f"newer artifact {index}".encode()
            name = f"newer-{index}.txt"
            target = __import__("pathlib").Path(work["workspace_path"]) / "inputs" / name
            target.write_bytes(content)
            await db.execute(
                "INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at) VALUES (?, ?, ?, 'imported_file', ?, ?, ?)",
                (
                    f"newer-artifact-{index}", work["id"], f"inputs/{name}",
                    hashlib.sha256(content).hexdigest(), len(content), int(time.time()) + 10 + index,
                ),
            )
        other_target = __import__("pathlib").Path(other["workspace_path"]) / "inputs" / "other.txt"
        other_target.parent.mkdir(parents=True, exist_ok=True)
        other_target.write_text("outside scope", encoding="utf-8")
        await db.execute(
            "INSERT INTO artifacts (id, session_id, relative_path, kind, sha256, size_bytes, created_at) VALUES ('other-artifact', ?, 'inputs/other.txt', 'imported_file', ?, 13, ?)",
            (other["id"], hashlib.sha256(b"outside scope").hexdigest(), int(time.time())),
        )
        await db.commit()
    thread = await resolve_bound_thread(client, work["id"])
    response = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Use attachments", "attachment_artifact_ids": [attachments[0], attachments[0]]},
    )
    assert response.status_code == 200
    user_parts = response.json()[0]["parts"]
    # The request contract de-duplicates selected artifact ids before a turn is
    # persisted, so a retry cannot accidentally widen its context.
    assert [part["content"].get("artifact_id") for part in user_parts[1:]] == [attachments[0]]
    sources = response.json()[1]["parts"]
    assert any(part["part_type"] == "source" and part["content"].get("id") == attachments[0] for part in sources)
    assert not any(part["part_type"] == "source" and part["content"].get("id") == attachments[1] for part in sources)
    assert gyo.requests[-1].attachment_count == 1
    binary_context = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Binary context must fail", "attachment_artifact_ids": [attachments[1]]},
    )
    assert binary_context.status_code == 422
    assert binary_context.json()["detail"] == "Attachment format is structurally validated but is not supported as GYO text context"
    wrong_scope = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Wrong scope", "attachment_artifact_ids": ["other-artifact"]},
    )
    assert wrong_scope.status_code == 404

    failed_id = response.json()[1]["id"]
    async with get_db_connection(migrated_db_path) as db:
        await db.execute("UPDATE assistant_turns SET status = 'failed' WHERE id = ?", (failed_id,))
        await db.commit()
    retried = await client.post(f"/api/assistant/turns/{failed_id}/retry", json={"mode": "auto"})
    assert retried.status_code == 202
    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assert len([turn for turn in turns if turn["role"] == "user"]) == 1


@pytest.mark.asyncio
async def test_model_proposal_is_inert_until_idempotent_package_creation(client, test_app):
    test_app.state.gyo_orchestrator = FakeGyo(
        text=(
            "Tôi đã chuẩn bị thay đổi để bạn xem.\n"
            'DIRAP_ACTION_PROPOSAL: {"title":"Bắt đầu Work","description":"Đề xuất an toàn",'
            '"steps":[{"kind":"work_status_update","input":{"work_status":"in_progress","progress_percent":20}}]}'
        ),
    )
    work_id = (await client.post("/api/sessions", json={"title": "Proposal Work"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    turns = await client.post(f"/api/assistant/threads/{thread['id']}/turns", json={"prompt": "Bắt đầu"})
    proposal = next(part for part in turns.json()[1]["parts"] if part["part_type"] == "action_proposal")
    assert (await client.get(f"/api/works/{work_id}/action-packages")).json() == []

    payload = {key: proposal["content"][key] for key in ("title", "description", "conversation_id", "steps")}
    payload["source_proposal_part_id"] = proposal["id"]
    first = await client.post(
        f"/api/works/{work_id}/action-packages", json=payload, headers={"Idempotency-Key": f"proposal-{proposal['id']}"},
    )
    replay = await client.post(
        f"/api/works/{work_id}/action-packages", json=payload, headers={"Idempotency-Key": f"proposal-{proposal['id']}"},
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    refreshed_turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    approval_parts = [part for part in refreshed_turns[1]["parts"] if part["part_type"] == "approval"]
    assert len(approval_parts) == 1
    assert approval_parts[0]["content"]["package_id"] == first.json()["id"]
    assert approval_parts[0]["content"]["package_hash"] == first.json()["package_hash"]
    changed = {**payload, "title": "Different"}
    conflict = await client.post(
        f"/api/works/{work_id}/action-packages", json=changed, headers={"Idempotency-Key": f"proposal-{proposal['id']}"},
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_approved_action_package_survives_worker_restart_and_runs_once(client, migrated_db_path):
    from app.settings import Settings
    test_settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False)
    work_id = (await client.post("/api/sessions", json={"title": "Hành động bền vững"})).json()["id"]
    phase = await client.post(f"/api/works/{work_id}/plan/phases", json={"title": "Pha 1"})
    plan_step = await client.post(f"/api/works/{work_id}/plan/steps", json={"phase_id": phase.json()["id"], "title": "Cũ"})
    proposed = await client.post(
        f"/api/works/{work_id}/action-packages",
        json={"title": "Đổi tên bước", "steps": [{"kind": "work_plan_step_update", "input": {"step_id": plan_step.json()["id"], "changes": {"title": "Mới", "status": "in_progress"}}}]},
        headers={"Idempotency-Key": "assistant-actions-restart"},
    )
    assert proposed.status_code == 201, proposed.text
    package = proposed.json()
    package_id = package["id"]
    approved = await client.post(
        f"/api/action-packages/{package_id}/approve",
        json={"expected_revision": package["revision"], "expected_payload_hash": package["payload_hash"]},
        headers={"Idempotency-Key": "assistant-actions-restart-approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved_hash"] == approved.json()["package_hash"]

    # A fresh executor instance represents the backend after an approval/restart boundary.
    assert await execute_one_approved_package(test_settings, "restart-worker") is True
    assert await execute_one_approved_package(test_settings, "restart-worker") is False
    packages = await client.get(f"/api/works/{work_id}/action-packages")
    assert packages.json()[0]["status"] == "succeeded"
    dashboard = await client.get(f"/api/works/{work_id}/dashboard")
    assert dashboard.json()["phases"][0]["steps"][0]["title"] == "Mới"


@pytest.mark.asyncio
async def test_expired_action_lease_is_reclaimed_after_worker_restart(client, migrated_db_path):
    from app.settings import Settings

    test_settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False)
    work_id = (await client.post("/api/sessions", json={"title": "Khôi phục gói hành động"})).json()["id"]
    proposed = await client.post(
        f"/api/works/{work_id}/action-packages",
        json={"title": "Tái chạy an toàn", "steps": [{"kind": "work_status_update", "input": {"work_status": "in_progress", "progress_percent": 25}}]},
        headers={"Idempotency-Key": "assistant-actions-reclaim"},
    )
    package = proposed.json()
    package_id = package["id"]
    assert (await client.post(
        f"/api/action-packages/{package_id}/approve",
        json={"expected_revision": package["revision"], "expected_payload_hash": package["payload_hash"]},
        headers={"Idempotency-Key": "assistant-actions-reclaim-approve"},
    )).status_code == 200

    # Simulate a process stopping after it acquired the lease but before it could finish.
    async with get_db_connection(test_settings.db_path_resolved) as db:
        await db.execute(
            "UPDATE action_packages SET status = 'executing', lease_owner = 'old-worker', lease_expires_at = ?, attempt_count = 1 WHERE id = ?",
            (int(time.time()) - 1, package_id),
        )
        await db.commit()

    assert await execute_one_approved_package(test_settings, "new-worker") is True
    packages = await client.get(f"/api/works/{work_id}/action-packages")
    assert packages.json()[0]["status"] == "succeeded"
    assert packages.json()[0]["attempt_count"] == 2


@pytest.mark.asyncio
async def test_action_package_has_single_approval_winner(client):
    work_id = (await client.post("/api/sessions", json={"title": "Một quyết định"})).json()["id"]
    proposed = await client.post(f"/api/works/{work_id}/action-packages", json={"title": "Pause", "steps": [{"kind": "work_status_update", "input": {"work_status": "paused", "progress_percent": 10}}]}, headers={"Idempotency-Key": "assistant-actions-single-winner"})
    package = proposed.json()
    package_id = package["id"]
    decision = {"expected_revision": package["revision"], "expected_payload_hash": package["payload_hash"]}
    first, second = await asyncio.gather(
        client.post(f"/api/action-packages/{package_id}/approve", json=decision, headers={"Idempotency-Key": "single-winner-approve"}),
        client.post(f"/api/action-packages/{package_id}/deny", json=decision, headers={"Idempotency-Key": "single-winner-deny"}),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]


@pytest.mark.asyncio
async def test_marketplace_never_enables_without_isolation(client, migrated_db_path):
    from app.settings import Settings
    test_settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False)
    now = int(time.time())
    manifest = {"name": "Ví dụ", "permissions": ["file:managed"], "network_domains": []}
    async with get_db_connection(test_settings.db_path_resolved) as db:
        await db.execute("INSERT INTO marketplace_packages (package_id, version, catalog_name, publisher, manifest_json, package_hash, signature_valid, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)", ("sample.plugin", "1.0.0", "dirap", "DIRAP", json.dumps(manifest), "abc", now))
        await db.commit()
    catalog = await client.get("/api/marketplace/catalog")
    assert catalog.status_code == 200 and catalog.json()[0]["signature_valid"] is True
    installed = await client.post("/api/marketplace/sample.plugin/1.0.0/install")
    assert installed.status_code == 200
    assert installed.json()["install_state"] == "cannot_run_safely"
    enabled = await client.post("/api/marketplace/sample.plugin/enable")
    assert enabled.status_code == 409


@pytest.mark.asyncio
async def test_signed_catalog_and_rollback_keep_plugin_disabled(client, migrated_db_path):
    from app.settings import Settings
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    import base64
    settings = Settings(
        db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"], outbox_dispatcher_enabled=False,
        marketplace_catalog_public_keys={"dirap": base64.b64encode(public_key).decode()},
    )
    packages = [
        {"package_id": "sample.plugin", "version": "1.0.0", "package_hash": "a" * 64, "manifest": {"name": "Sample", "publisher": "DIRAP", "entrypoint": "main", "permissions": [], "network_domains": [], "dependencies": [], "changelog": "v1"}},
        {"package_id": "sample.plugin", "version": "2.0.0", "package_hash": "b" * 64, "manifest": {"name": "Sample", "publisher": "DIRAP", "entrypoint": "main", "permissions": [], "network_domains": [], "dependencies": [], "changelog": "v2"}},
    ]
    signature = base64.b64encode(private_key.sign(canonical_catalog_payload("dirap", packages))).decode()
    async with get_db_connection(settings.db_path_resolved) as db:
        assert await ingest_verified_catalog(db, settings, "dirap", packages, signature) == 2
    assert (await client.post("/api/marketplace/sample.plugin/1.0.0/install")).status_code == 200
    assert (await client.post("/api/marketplace/sample.plugin/2.0.0/install")).status_code == 200
    rollback = await client.post("/api/marketplace/sample.plugin/rollback")
    assert rollback.status_code == 200
    assert rollback.json()["version"] == "1.0.0"
    assert rollback.json()["install_state"] == "cannot_run_safely"


async def _archive_work(db_path: str, work_id: str) -> None:
    from app.db.connection import get_db_connection
    async with get_db_connection(db_path) as db:
        await db.execute("UPDATE sessions SET archived = 1 WHERE id = ?", (work_id,))
        await db.commit()


async def _archive_conversation(db_path: str, conversation_id: str) -> None:
    from app.db.connection import get_db_connection
    async with get_db_connection(db_path) as db:
        await db.execute("UPDATE conversations SET status = 'archived' WHERE id = ?", (conversation_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_resolve_thread_rejects_archived_work(client, migrated_db_path):
    """Archived Work → 409 + 0 assistant thread mới tại resolver."""
    work_id = (await client.post("/api/sessions", json={"title": "Archived Work Resolver"})).json()["id"]
    conversation = (await client.post(
        f"/api/works/{work_id}/conversations", json={"title": "Active Conv"}
    )).json()

    await _archive_work(migrated_db_path, work_id)

    # Count threads before
    before = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    count_before = len(before)

    response = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation['id']}/assistant-thread"
    )
    assert response.status_code == 409
    assert "archived" in response.json()["detail"].lower()

    # Verify 0 new thread created
    after = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    assert len(after) == count_before


@pytest.mark.asyncio
async def test_resolve_thread_rejects_archived_conversation(client, migrated_db_path):
    """Archived Conversation → 409 + 0 assistant thread mới tại resolver."""
    work_id = (await client.post("/api/sessions", json={"title": "Work With Archived Conv"})).json()["id"]
    conversation = (await client.post(
        f"/api/works/{work_id}/conversations", json={"title": "Archived Conv"}
    )).json()

    await _archive_conversation(migrated_db_path, conversation["id"])

    before = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    count_before = len(before)

    response = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation['id']}/assistant-thread"
    )
    assert response.status_code == 409
    assert "archived" in response.json()["detail"].lower()

    after = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    assert len(after) == count_before


@pytest.mark.asyncio
async def test_resolve_thread_rejects_work_not_found(client):
    """Work không tồn tại → 404 + 0 assistant thread mới."""
    fake_work_id = "00000000-0000-0000-0000-000000000000"
    fake_conv_id = "00000000-0000-0000-0000-000000000000"

    before = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    count_before = len(before)

    response = await client.post(
        f"/api/assistant/works/{fake_work_id}/conversations/{fake_conv_id}/assistant-thread"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    after = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    assert len(after) == count_before


@pytest.mark.asyncio
async def test_resolve_thread_rejects_conversation_not_in_work(client, migrated_db_path):
    """Conversation không thuộc Work → 404 + 0 assistant thread mới."""
    work_a = (await client.post("/api/sessions", json={"title": "Work A Resolver"})).json()
    work_b = (await client.post("/api/sessions", json={"title": "Work B Resolver"})).json()
    conv_b = (await client.post(
        f"/api/works/{work_b['id']}/conversations", json={"title": "Conv B"}
    )).json()

    before = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    count_before = len(before)

    # Try to resolve conv_b under work_a
    response = await client.post(
        f"/api/assistant/works/{work_a['id']}/conversations/{conv_b['id']}/assistant-thread"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    after = (await client.get("/api/assistant/threads", params={"include_archived": "true"})).json()
    assert len(after) == count_before


async def _archive_thread(db_path: str, thread_id: str) -> None:
    from app.db.connection import get_db_connection
    async with get_db_connection(db_path) as db:
        await db.execute("UPDATE assistant_threads SET status = 'archived' WHERE id = ?", (thread_id,))
        await db.commit()


async def _resolve_target_conversation_thread(client, work_id: str, conversation_id: str) -> dict:
    """Resolve only the explicitly supplied active Work/Conversation tuple."""
    response = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation_id}/assistant-thread"
    )
    assert response.status_code == 200
    thread = response.json()
    assert thread["work_id"] == work_id
    assert thread["conversation_id"] == conversation_id
    assert thread["status"] == "active"
    return thread


async def _assistant_mutation_snapshot(db_path: str, work_id: str) -> tuple[int, int, int]:
    """Count only rows a rejected assistant mutation could have created."""
    from app.db.connection import get_db_connection
    async with get_db_connection(db_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM assistant_turns WHERE work_id = ?", (work_id,)
        ) as cur:
            turns = (await cur.fetchone())[0]
        async with db.execute(
            """SELECT COUNT(*) FROM assistant_run_metadata AS metadata
               JOIN assistant_turns AS turn ON turn.id = metadata.assistant_turn_id
               WHERE turn.work_id = ?""",
            (work_id,),
        ) as cur:
            run_metadata = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE session_id = ?", (work_id,)
        ) as cur:
            audit_events = (await cur.fetchone())[0]
    return turns, run_metadata, audit_events


async def _create_failed_scoped_retry_pair(
    db_path: str, *, thread_id: str, work_id: str, conversation_id: str
) -> str:
    """Create the exact persisted prerequisite for an auto-mode retry."""
    from app.db.connection import get_db_connection
    now = int(time.time())
    user_turn_id = str(__import__("uuid").uuid4())
    failed_turn_id = str(__import__("uuid").uuid4())
    async with get_db_connection(db_path) as db:
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, created_at, completed_at)
               VALUES (?, ?, ?, ?, 'user', 'completed', ?, ?)""",
            (user_turn_id, thread_id, work_id, conversation_id, now, now),
        )
        await db.execute(
            """INSERT INTO assistant_turn_parts
               (id, turn_id, part_type, content_json, sort_order, created_at)
               VALUES (?, ?, 'text', ?, 0, ?)""",
            (str(__import__("uuid").uuid4()), user_turn_id, json.dumps({"text": "Retry target"}), now),
        )
        await db.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at, completed_at, error)
               VALUES (?, ?, ?, ?, 'assistant', 'failed', 'gyo', ?, ?, 'failed for archived-conversation retry')""",
            (failed_turn_id, thread_id, work_id, conversation_id, now, now),
        )
        await db.commit()
    return failed_turn_id


async def _create_active_turn(db_path: str, thread_id: str, role: str = "assistant", status: str = "failed") -> str:
    from app.db.connection import get_db_connection
    turn_id = str(__import__("uuid").uuid4())
    async with get_db_connection(db_path) as db:
        await db.execute(
            "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, NULL, NULL, ?, ?, 'gyo', ?)",
            (turn_id, thread_id, role, status, int(__import__("time").time())),
        )
        await db.commit()
    return turn_id


@pytest.mark.asyncio
async def test_create_turn_rejects_archived_thread(client, migrated_db_path):
    """Archived thread → create_turn 409 + 0 turn mới."""
    work_id = (await client.post("/api/sessions", json={"title": "Turn Archived"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    await _archive_thread(migrated_db_path, thread["id"])

    resp = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Must fail"},
    )
    assert resp.status_code == 409

    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assert len(turns) == 0


@pytest.mark.asyncio
async def test_create_run_rejects_archived_thread(client, migrated_db_path):
    """Archived thread → create_run 409 + 0 turn mới."""
    work_id = (await client.post("/api/sessions", json={"title": "Run Archived"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    await _archive_thread(migrated_db_path, thread["id"])

    resp = await client.post(
        f"/api/assistant/threads/{thread['id']}/runs",
        json={"prompt": "Must fail"},
    )
    assert resp.status_code == 409

    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assert len(turns) == 0


@pytest.mark.asyncio
async def test_retry_rejects_archived_thread(client, migrated_db_path):
    """Archived thread → retry 409 + 0 turn mới."""
    work_id = (await client.post("/api/sessions", json={"title": "Retry Archived"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    turn_id = await _create_active_turn(migrated_db_path, thread["id"], role="assistant", status="failed")
    await _archive_thread(migrated_db_path, thread["id"])

    resp = await client.post(f"/api/assistant/turns/{turn_id}/retry")
    assert resp.status_code == 409

    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assert len(turns) == 1  # only the original failed turn


@pytest.mark.asyncio
async def test_create_turn_rejects_archived_conversation(client, migrated_db_path):
    """The exact archived Conversation tuple rejects create_turn before writes."""
    work_id = (await client.post("/api/sessions", json={"title": "Conv Archived Turn"})).json()["id"]
    conv = (await client.post(f"/api/works/{work_id}/conversations", json={"title": "Archived"})).json()
    thread = await _resolve_target_conversation_thread(client, work_id, conv["id"])
    await _archive_conversation(migrated_db_path, conv["id"])
    before = await _assistant_mutation_snapshot(migrated_db_path, work_id)

    resp = await client.post(
        f"/api/assistant/threads/{thread['id']}/turns",
        json={"prompt": "Must fail", "work_id": work_id, "conversation_id": conv["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Conversation is archived"
    assert await _assistant_mutation_snapshot(migrated_db_path, work_id) == before


@pytest.mark.asyncio
async def test_create_run_rejects_archived_conversation_before_writes(client, migrated_db_path):
    """The exact archived Conversation tuple rejects create_run before writes."""
    work_id = (await client.post("/api/sessions", json={"title": "Conv Archived Run"})).json()["id"]
    conv = (await client.post(f"/api/works/{work_id}/conversations", json={"title": "Archived"})).json()
    thread = await _resolve_target_conversation_thread(client, work_id, conv["id"])
    await _archive_conversation(migrated_db_path, conv["id"])
    before = await _assistant_mutation_snapshot(migrated_db_path, work_id)

    resp = await client.post(
        f"/api/assistant/threads/{thread['id']}/runs",
        json={"prompt": "Must fail", "work_id": work_id, "conversation_id": conv["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Conversation is archived"
    assert await _assistant_mutation_snapshot(migrated_db_path, work_id) == before


@pytest.mark.asyncio
async def test_retry_rejects_archived_conversation_before_writes(client, migrated_db_path):
    """The exact archived Conversation failed turn rejects retry before writes."""
    work_id = (await client.post("/api/sessions", json={"title": "Conv Archived Retry"})).json()["id"]
    conv = (await client.post(f"/api/works/{work_id}/conversations", json={"title": "Archived"})).json()
    thread = await _resolve_target_conversation_thread(client, work_id, conv["id"])
    failed_turn_id = await _create_failed_scoped_retry_pair(
        migrated_db_path, thread_id=thread["id"], work_id=work_id, conversation_id=conv["id"]
    )
    await _archive_conversation(migrated_db_path, conv["id"])
    before = await _assistant_mutation_snapshot(migrated_db_path, work_id)

    resp = await client.post(f"/api/assistant/turns/{failed_turn_id}/retry", json={"mode": "auto"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Conversation is archived"
    assert await _assistant_mutation_snapshot(migrated_db_path, work_id) == before


@pytest.mark.asyncio
async def test_create_run_rejects_archived_work(client, migrated_db_path):
    """Archived work → create_run 409 + 0 turn mới."""
    work_id = (await client.post("/api/sessions", json={"title": "Work Archived Run"})).json()["id"]
    thread = await resolve_bound_thread(client, work_id)
    await _archive_work(migrated_db_path, work_id)

    resp = await client.post(
        f"/api/assistant/threads/{thread['id']}/runs",
        json={"prompt": "Must fail"},
    )
    assert resp.status_code == 409

    turns = (await client.get(f"/api/assistant/threads/{thread['id']}/turns")).json()
    assert len(turns) == 0
