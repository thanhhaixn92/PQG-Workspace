"""Bounded native-GYO acceptance using only disposable local state.

The runner copies one manually selected, enabled free model's *metadata* into a
fresh migrated SQLite database.  Its opaque Credential Manager reference is
resolved only by the current GYO registry.  Receipts deliberately exclude
credential material, prompts, provider output, and temporary filesystem paths.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import logging
import runpy
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.assistant_runs import execute_assistant_run_claim
from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.main import create_app
from app.services.assistant_runs import execute_one_assistant_run
from app.settings import Settings


E2_HELPERS = runpy.run_path(str(REPO_ROOT / "scripts" / "run-package-e2-bounded-real-provider.py"))
CountingAdapter = E2_HELPERS["CountingAdapter"]
selected_profile = E2_HELPERS["_selected_profile"]
seed_profile = E2_HELPERS["_seed_profile"]

SOURCE_FILES = (
    ".github/workflows/smoke.yml",
    "backend/app/api/assistant.py",
    "backend/app/api/assistant_runs.py",
    "backend/app/services/assistant_runs.py",
    "backend/app/services/gyo_orchestrator.py",
    "scripts/run-e4-native-gyo-acceptance.py",
)


class GateAdapter:
    """Delay one current-GYO dispatch until cancellation is durably requested."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.stream_calls = 0

    async def health_check(self, *args: Any, **kwargs: Any) -> Any:
        return await self.delegate.health_check(*args, **kwargs)

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        self.stream_calls += 1
        self.started.set()
        await self.release.wait()
        async for event in self.delegate.stream(*args, **kwargs):
            yield event


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    return {path: _sha256(REPO_ROOT / path) for path in SOURCE_FILES}


async def _fixture(client: httpx.AsyncClient, title: str) -> tuple[str, str, str]:
    work = await client.post("/api/sessions", json={"title": title, "data_scope": "work_only"})
    if work.status_code != 201:
        raise RuntimeError("fixture_work_create_failed")
    work_id = work.json()["id"]
    conversation = await client.post(
        f"/api/works/{work_id}/conversations", json={"title": "E4 synthetic conversation"}
    )
    if conversation.status_code != 201:
        raise RuntimeError("fixture_conversation_create_failed")
    conversation_id = conversation.json()["id"]
    thread = await client.post(
        f"/api/assistant/works/{work_id}/conversations/{conversation_id}/assistant-thread"
    )
    if thread.status_code != 200:
        raise RuntimeError("fixture_thread_create_failed")
    return work_id, conversation_id, thread.json()["id"]


async def _create_run(
    client: httpx.AsyncClient, *, work_id: str, conversation_id: str, thread_id: str, model_profile_id: str, prompt: str,
) -> str:
    response = await client.post(
        f"/api/assistant/threads/{thread_id}/runs",
        json={
            "prompt": prompt,
            "work_id": work_id,
            "conversation_id": conversation_id,
            "model_profile_id": model_profile_id,
            "route_mode": "manual",
        },
    )
    if response.status_code != 202:
        raise RuntimeError("durable_run_create_failed")
    turns = response.json()
    assistants = [turn for turn in turns if turn.get("role") == "assistant"]
    if len(assistants) != 1:
        raise RuntimeError("durable_run_shape_invalid")
    return str(assistants[0]["id"])


async def _execute(settings: Settings, app: Any, run_id: str) -> bool:
    async def executor(claim: Any) -> None:
        await execute_assistant_run_claim(claim, gyo_orchestrator=app.state.gyo_orchestrator, settings=settings)

    return await execute_one_assistant_run(settings, "e4-native-gyo", executor, run_id=run_id)


def _turn_summary(turn: dict[str, Any]) -> dict[str, Any]:
    parts = turn.get("parts", []) if isinstance(turn.get("parts"), list) else []
    return {
        "status": turn.get("status"),
        "part_types": [part.get("part_type") for part in parts if isinstance(part, dict)],
        "has_source": any(isinstance(part, dict) and part.get("part_type") == "source" for part in parts),
        "has_action_proposal": any(isinstance(part, dict) and part.get("part_type") == "action_proposal" for part in parts),
    }


async def _turn(client: httpx.AsyncClient, thread_id: str, turn_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/assistant/threads/{thread_id}/turns")
    if response.status_code != 200:
        raise RuntimeError("turn_read_failed")
    for turn in response.json():
        if turn.get("id") == turn_id:
            return turn
    raise RuntimeError("assistant_turn_missing")


async def _run(receipt: dict[str, Any], temp_root: Path, model_profile_id: str) -> int:
    source_settings = Settings(db_path=str(REPO_ROOT / "backend" / "app.db"))
    profile = await selected_profile(source_settings, model_profile_id)
    if profile is None:
        receipt.update({"status": "NOT_RUN", "stop_reason": "manual_free_model_not_credential_ready"})
        return 4
    receipt["provider"] = {
        "profile_id": profile["provider_id"],
        "model_profile_id": profile["id"],
        "model_identifier": profile["model_identifier"],
        "cost_class": "free",
        "selection": "manual",
    }
    db_path = temp_root / "e4.sqlite"
    # Migration helpers print progress and HTTPX logs request URLs. Neither is
    # suitable for the redacted receipt/console channel.
    with contextlib.redirect_stdout(io.StringIO()):
        await run_migrations(db_path)
    settings = Settings(
        db_path=str(db_path),
        default_workspace_root=str(temp_root / "workspaces"),
        cors_origins=["http://localhost:5173"],
        gyo_keyring_service=source_settings.gyo_keyring_service,
        outbox_dispatcher_enabled=False,
        model_fallback_enabled=False,
        local_actor_subject="e4-synthetic",
        log_level="WARNING",
    )
    await seed_profile(settings, profile)
    app = create_app(settings_override=settings)
    app.state.assistant_run_worker_active = True
    orchestrator = app.state.gyo_orchestrator
    counter = CountingAdapter(orchestrator.providers[profile["provider_type"]])
    orchestrator.providers[profile["provider_type"]] = counter

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)), base_url="http://testserver", timeout=90.0,
    ) as client:
        # R1: one real native-GYO durable run with persisted source/context evidence.
        work_id, conversation_id, thread_id = await _fixture(client, "E4 R1 synthetic Work")
        r1_id = await _create_run(
            client, work_id=work_id, conversation_id=conversation_id, thread_id=thread_id,
            model_profile_id=profile["id"], prompt="Tóm tắt ngắn gọn Công việc hiện tại, chỉ sử dụng ngữ cảnh được cấp.",
        )
        before_r1 = counter.stream_calls
        await _execute(settings, app, r1_id)
        r1_run = await client.get(f"/api/assistant/runs/{r1_id}")
        r1_turn = await _turn(client, thread_id, r1_id)
        r1 = _turn_summary(r1_turn)
        r1["run_status"] = r1_run.json().get("status") if r1_run.status_code == 200 else None
        r1["provider_dispatches"] = counter.stream_calls - before_r1
        r1["manual_route"] = True
        receipt["r1"] = r1

        # R2: the gate makes cancellation deterministic while preserving one current-provider dispatch after release.
        work_id, conversation_id, thread_id = await _fixture(client, "E4 R2 synthetic Work")
        gate = GateAdapter(counter.delegate)
        orchestrator.providers[profile["provider_type"]] = gate
        r2_id = await _create_run(
            client, work_id=work_id, conversation_id=conversation_id, thread_id=thread_id,
            model_profile_id=profile["id"], prompt="Trả lời ngắn gọn cho Work tổng hợp này.",
        )
        worker = asyncio.create_task(_execute(settings, app, r2_id))
        try:
            await asyncio.wait_for(gate.started.wait(), timeout=15)
            cancelled = await client.post(f"/api/assistant/turns/{r2_id}/cancel")
            gate.release.set()
            await asyncio.wait_for(worker, timeout=90)
            r2_run = await client.get(f"/api/assistant/runs/{r2_id}")
            r2_turn = await _turn(client, thread_id, r2_id)
            r2 = _turn_summary(r2_turn)
            r2.update({
                "cancel_http_status": cancelled.status_code,
                "run_status": r2_run.json().get("status") if r2_run.status_code == 200 else None,
                "provider_dispatches": gate.stream_calls,
                "remote_compute_stop": "NOT_PROVEN",
            })
            receipt["r2"] = r2
        except (asyncio.TimeoutError, httpx.HTTPError):
            gate.release.set()
            if not worker.done():
                await asyncio.wait_for(worker, timeout=90)
            receipt["r2"] = {"status": "NOT_RUN", "reason": "cancel_timing_not_exercised", "remote_compute_stop": "NOT_PROVEN"}
        finally:
            orchestrator.providers[profile["provider_type"]] = counter

        # R3: a single natural proposal-intent request; never hunt or execute a proposal.
        work_id, conversation_id, thread_id = await _fixture(client, "E4 R3 synthetic Work")
        r3_id = await _create_run(
            client, work_id=work_id, conversation_id=conversation_id, thread_id=thread_id,
            model_profile_id=profile["id"], prompt="Nếu phù hợp, hãy đề xuất một Action Proposal; không thực hiện thay đổi nào.",
        )
        before_r3 = counter.stream_calls
        await _execute(settings, app, r3_id)
        r3_turn = await _turn(client, thread_id, r3_id)
        r3 = _turn_summary(r3_turn)
        r3["provider_dispatches"] = counter.stream_calls - before_r3
        r3["proposal_execution"] = "NOT_ATTEMPTED"
        receipt["r3"] = r3

    r1_pass = r1["run_status"] == "completed" and r1["provider_dispatches"] == 1 and r1["has_source"]
    r2_pass = receipt["r2"].get("run_status") == "cancelled" and receipt["r2"].get("provider_dispatches") == 1
    r3_status = "PASS" if receipt["r3"]["has_action_proposal"] else "NOT_RUN"
    receipt["r1"]["status"] = "PASS" if r1_pass else "FAIL"
    receipt["r2"]["status"] = "PASS" if r2_pass else receipt["r2"].get("status", "NOT_RUN")
    receipt["r3"]["status"] = r3_status
    receipt.update({"status": "PASS" if r1_pass and receipt["r2"]["status"] in {"PASS", "NOT_RUN"} else "FAIL", "stop_reason": None})
    return 0 if receipt["status"] == "PASS" else 2


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded E4 native current-GYO acceptance.")
    parser.add_argument("--model-profile-id", required=True, help="Existing enabled free model profile selected manually.")
    args = parser.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    output_dir = REPO_ROOT / "output" / "e4-native-gyo" / f"package-e4-{time.strftime('%Y%m%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {"package": "E4 native current-GYO", "started_at": int(time.time()), "provider_request_budget": 3, "fallback_budget": 0, "source_hashes": _source_hashes(), "runner_sha256": _sha256(Path(__file__))}
    temp_root = Path(tempfile.mkdtemp(prefix="pqg-e4-native-"))
    exit_code = 2
    try:
        exit_code = await _run(receipt, temp_root, args.model_profile_id)
    except Exception as exc:
        receipt.update({"status": "FAIL", "stop_reason": "runner_exception", "exception_type": type(exc).__name__})
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        receipt["cleanup"] = {"temporary_root_removed": not temp_root.exists()}
        receipt["finished_at"] = int(time.time())
        receipt["exit_code"] = exit_code
        (output_dir / "run-metadata.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "exit_code": exit_code, "evidence_dir": output_dir.name}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
