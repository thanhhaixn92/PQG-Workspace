"""Run one bounded real-GYO E2 acceptance flow without touching app.db.

The runner copies only one currently configured free provider/model *metadata*
into a newly migrated SQLite database.  Its opaque keyring reference continues
to resolve through the existing Windows Credential Manager; neither a secret
nor any provider configuration is read into evidence or modified.  A single
natural request may produce an inert proposal.  Only a contract-valid proposal
is allowed to progress through Action Package, explicit approval, and exactly
one manually invoked executor claim in the disposable database.
"""
from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations
from app.main import create_app
from app.services.action_packages import execute_one_approved_package
from app.services.gyo_registry import GyoProviderRegistry
from app.settings import Settings


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "backend/app/api/assistant.py",
    "backend/app/api/action_packages.py",
    "backend/app/api/model_config.py",
    "backend/app/services/action_packages.py",
    "backend/app/services/gyo_orchestrator.py",
    "frontend/src/components/ActionPackagesPanel.tsx",
)
SCENARIO_ID = "synthetic_status_change_v3"
PROMPT = (
    "Work kiểm thử này hiện chưa bắt đầu và tiến độ là 0%. "
    "Xin bắt đầu công việc và cập nhật tiến độ lên 1%."
)
EXPECTED_STEP = {
    "kind": "work_status_update",
    "input": {"work_status": "in_progress", "progress_percent": 1},
}
_SAFE_PROPOSAL_DIAGNOSTICS = frozenset({"missing_marker", "invalid_json", "invalid_schema"})
_SAFE_PROPOSAL_REASON_CODES = frozenset({
    "marker_missing", "json_syntax", "multiple_markers", "payload_not_object", "schema_invalid",
    "title_invalid", "steps_invalid", "step_kind_invalid", "structured_payload_invalid",
})
CATALOG_FREE_MODELS = {
    "hy3-free": {"display_name": "HY3 Free", "tier": "balanced"},
    "laguna-s-2.1-free": {"display_name": "Laguna S 2.1 Free", "tier": "balanced"},
    "mimo-v2.5-free": {"display_name": "MiMo V2.5 Free", "tier": "balanced"},
    "muse-spark-1.2-contributor-free": {"display_name": "Muse Spark 1.2 Contributor Free", "tier": "balanced"},
}


class CountingAdapter:
    """Observes adapter dispatches without changing request or response data."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.stream_calls = 0

    async def health_check(self, *args: Any, **kwargs: Any) -> Any:
        return await self.delegate.health_check(*args, **kwargs)

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        self.stream_calls += 1
        async for event in self.delegate.stream(*args, **kwargs):
            yield event


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    return {path: _sha256(REPO_ROOT / path) for path in SOURCE_FILES}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def _snapshot(db_path: Path, work_id: str) -> dict[str, Any]:
    """Return only aggregate fixture state; never provider text or credentials."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        work = conn.execute(
            "SELECT work_status, progress_percent FROM sessions WHERE id = ?", (work_id,)
        ).fetchone()
        counts: dict[str, int] = {}
        for table, column in (
            ("conversations", "session_id"),
            ("assistant_threads", "work_id"),
            ("assistant_turns", "work_id"),
            ("action_packages", "session_id"),
            ("audit_events", "session_id"),
            ("artifacts", "session_id"),
        ):
            counts[table] = int(
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (work_id,)).fetchone()[0]
            )
        counts["action_steps"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM action_steps s JOIN action_packages p ON p.id = s.package_id WHERE p.session_id = ?",
                (work_id,),
            ).fetchone()[0]
        )
        counts["action_attempts"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM action_attempts a JOIN action_packages p ON p.id = a.package_id WHERE p.session_id = ?",
                (work_id,),
            ).fetchone()[0]
        )
        counts["generic_approvals"] = 0
        if _table_exists(conn, "approval_requests"):
            counts["generic_approvals"] = int(conn.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0])
        return {
            "work_status": work["work_status"] if work else None,
            "progress_percent": work["progress_percent"] if work else None,
            "counts": counts,
        }
    finally:
        conn.close()


async def _selected_profile(settings: Settings, model_profile_id: str | None) -> dict[str, Any] | None:
    """Read one default free profile, without exposing its opaque credential ref."""
    async with get_db_connection(settings.db_path_resolved) as conn:
        condition = "AND m.id = ?" if model_profile_id else "AND m.is_default = 1"
        parameters = (model_profile_id,) if model_profile_id else ()
        async with conn.execute(
            """SELECT p.id AS provider_id, p.display_name AS provider_name, p.provider_type,
                      p.base_url, p.credential_ref, p.enabled AS provider_enabled,
                      p.retired_at AS provider_retired_at, p.created_at AS provider_created_at,
                      p.updated_at AS provider_updated_at, m.*
               FROM ai_model_profiles AS m
               JOIN ai_provider_profiles AS p ON p.id = m.provider_profile_id
               WHERE m.enabled = 1 AND m.retired_at IS NULL
                 AND p.enabled = 1 AND p.retired_at IS NULL
                 AND m.cost_class = 'free' """ + condition + " ORDER BY m.id",
            parameters,
        ) as cursor:
            rows = await cursor.fetchall()
    if len(rows) != 1:
        return None
    row = dict(rows[0])
    configured = bool(GyoProviderRegistry(settings).get_credential(str(row["credential_ref"])))
    if not configured:
        return None
    return row


async def _catalog_profile(
    settings: Settings, model_identifier: str, provider_profile_id: str,
) -> dict[str, Any] | None:
    """Seed only a catalog-confirmed free model into the disposable database."""
    metadata = CATALOG_FREE_MODELS.get(model_identifier)
    if metadata is None:
        return None
    async with get_db_connection(settings.db_path_resolved) as conn:
        async with conn.execute(
            """SELECT id AS provider_id, display_name AS provider_name, provider_type,
                      base_url, credential_ref, created_at AS provider_created_at,
                      updated_at AS provider_updated_at
               FROM ai_provider_profiles
               WHERE id = ? AND enabled = 1 AND retired_at IS NULL
                 AND provider_type IN ('openai_compatible', 'openai_responses')""",
            (provider_profile_id,),
        ) as cursor:
            providers = await cursor.fetchall()
    if len(providers) != 1:
        return None
    provider = dict(providers[0])
    if not GyoProviderRegistry(settings).get_credential(str(provider["credential_ref"])):
        return None
    now = int(time.time())
    return {
        **provider,
        "id": f"e2-catalog-{model_identifier}",
        "provider_profile_id": provider["provider_id"],
        "display_name": metadata["display_name"],
        "model_identifier": model_identifier,
        "tier": metadata["tier"],
        "capabilities_json": '["chat"]',
        "priority": 1,
        "created_at": now,
        "updated_at": now,
    }


async def _seed_profile(temp_settings: Settings, profile: dict[str, Any]) -> None:
    async with get_db_connection(temp_settings.db_path_resolved) as conn:
        await conn.execute(
            """INSERT INTO ai_provider_profiles
               (id, display_name, provider_type, base_url, credential_ref, enabled, retired_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, NULL, ?, ?)""",
            (
                profile["provider_id"], profile["provider_name"], profile["provider_type"],
                profile["base_url"], profile["credential_ref"], profile["provider_created_at"],
                profile["provider_updated_at"],
            ),
        )
        await conn.execute(
            """INSERT INTO ai_model_profiles
               (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json,
                priority, enabled, is_default, cost_class, retired_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'free', NULL, ?, ?)""",
            (
                profile["id"], profile["provider_profile_id"], profile["display_name"],
                profile["model_identifier"], profile["tier"], profile["capabilities_json"],
                profile["priority"], profile["created_at"], profile["updated_at"],
            ),
        )
        await conn.execute("UPDATE gyo_routing_policy SET auto_fallback_enabled = 0 WHERE id = 1")
        await conn.commit()


def _proposal_is_expected(turn: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    proposals = [part for part in turn.get("parts", []) if part.get("part_type") == "action_proposal"]
    if turn.get("status") != "completed":
        return None, "assistant_not_completed"
    if len(proposals) != 1:
        return None, "proposal_count_not_one"
    proposal = proposals[0].get("content")
    if not isinstance(proposal, dict) or proposal.get("steps") != [EXPECTED_STEP]:
        return None, "proposal_contract_not_expected"
    return {"part_id": proposals[0].get("id"), "content": proposal}, "valid"


def _persisted_proposal_contract_diagnostics(turn: dict[str, Any]) -> list[dict[str, str]]:
    """Read only allow-listed contract metadata; never copy provider text."""
    diagnostics: list[dict[str, str]] = []
    for part in turn.get("parts", []):
        if part.get("part_type") != "tool_result":
            continue
        content = part.get("content")
        if not isinstance(content, dict) or content.get("tool_name") != "action_proposal_contract":
            continue
        diagnostic = content.get("diagnostic")
        reason_code = content.get("reason_code")
        if diagnostic not in _SAFE_PROPOSAL_DIAGNOSTICS:
            continue
        item = {"diagnostic": diagnostic}
        if reason_code in _SAFE_PROPOSAL_REASON_CODES:
            item["reason_code"] = reason_code
        diagnostics.append(item)
    return diagnostics


def _e2_contract_diagnostics(turn: dict[str, Any]) -> list[dict[str, str]]:
    """Preserve persisted failure evidence or classify a missing marker for E2 only."""
    persisted = _persisted_proposal_contract_diagnostics(turn)
    if persisted:
        return persisted
    proposals = [part for part in turn.get("parts", []) if part.get("part_type") == "action_proposal"]
    if turn.get("status") == "completed" and not proposals:
        return [{"diagnostic": "missing_marker", "reason_code": "marker_missing", "source": "e2_runner_inference"}]
    return []


async def _run(
    receipt: dict[str, Any], temp_root: Path, model_profile_id: str | None,
    catalog_model: str | None, provider_profile_id: str | None,
) -> int:
    # The repository root is not the backend process working directory.  Bind
    # this read-only source lookup explicitly to the configured local app DB;
    # relative Settings defaults would otherwise create/read a different file.
    source_settings = Settings(db_path=str(REPO_ROOT / "backend" / "app.db"))
    profile = (
        await _catalog_profile(source_settings, catalog_model, provider_profile_id or "")
        if catalog_model else await _selected_profile(source_settings, model_profile_id)
    )
    if profile is None:
        receipt.update({"status": "NOT_RUN", "stop_reason": "no_unique_default_free_credential_ready_model"})
        return 4
    receipt["provider"] = {
        "profile_id": profile["provider_id"], "model_profile_id": profile["id"],
        "model_identifier": profile["model_identifier"], "cost_class": "free",
        "selection": "catalog_ephemeral" if catalog_model else ("manual_candidate" if model_profile_id else "default"),
    }

    db_path = temp_root / "e2.sqlite"
    workspace_root = temp_root / "workspaces"
    await run_migrations(db_path)
    temp_settings = Settings(
        db_path=str(db_path), default_workspace_root=str(workspace_root),
        cors_origins=["http://localhost:5173"], gyo_keyring_service=source_settings.gyo_keyring_service,
        outbox_dispatcher_enabled=False, model_fallback_enabled=False, log_level="WARNING",
    )
    await _seed_profile(temp_settings, profile)
    app = create_app(settings_override=temp_settings)
    orchestrator = app.state.gyo_orchestrator
    counter = CountingAdapter(orchestrator.providers[profile["provider_type"]])
    orchestrator.providers[profile["provider_type"]] = counter

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 12345)),
        base_url="http://testserver",
        timeout=75.0,
    ) as client:
        session_response = await client.post("/api/sessions", json={
            "title": "E2 bounded real-provider fixture",
            "goal": "Validate one inert GYO proposal against synthetic Work state.",
            "data_scope": "work_only",
        })
        if session_response.status_code != 201:
            receipt.update({"status": "FAIL", "stop_reason": "fixture_work_create_failed", "http": session_response.status_code})
            return 2
        work_id = session_response.json()["id"]
        conversation_id = f"conversation-{work_id}"
        thread_response = await client.post(
            f"/api/assistant/works/{work_id}/conversations/{conversation_id}/assistant-thread"
        )
        if thread_response.status_code != 200:
            receipt.update({"status": "FAIL", "stop_reason": "fixture_thread_create_failed", "http": thread_response.status_code})
            return 2
        thread_id = thread_response.json()["id"]
        receipt["fixture"] = {"work_created": True, "conversation_created": True, "thread_created": True}
        before_proposal = _snapshot(db_path, work_id)
        response = await client.post(f"/api/assistant/threads/{thread_id}/turns", json={
            "prompt": PROMPT,
            "work_id": work_id,
            "conversation_id": conversation_id,
            "model_profile_id": profile["id"],
            "route_mode": "manual",
        })
        receipt["proposal_http_status"] = response.status_code
        receipt["provider_adapter_stream_calls"] = counter.stream_calls
        if response.status_code != 200:
            receipt.update({"status": "NOT_RUN", "stop_reason": "real_provider_turn_not_completed"})
            return 4
        turns = response.json()
        assistant_turns = [turn for turn in turns if turn.get("role") == "assistant"]
        assistant_turn = assistant_turns[0] if len(assistant_turns) == 1 else {}
        proposal, diagnostic = _proposal_is_expected(assistant_turn)
        contract_diagnostics = _e2_contract_diagnostics(assistant_turn)
        after_proposal = _snapshot(db_path, work_id)
        proposal_inert = (
            after_proposal["work_status"] == before_proposal["work_status"]
            and after_proposal["progress_percent"] == before_proposal["progress_percent"]
            and after_proposal["counts"]["action_packages"] == before_proposal["counts"]["action_packages"] == 0
            and after_proposal["counts"]["action_steps"] == before_proposal["counts"]["action_steps"] == 0
            and after_proposal["counts"]["action_attempts"] == before_proposal["counts"]["action_attempts"] == 0
        )
        receipt["proposal"] = {
            "assistant_turn_count": len(assistant_turns), "diagnostic": diagnostic,
            "contract_diagnostics": contract_diagnostics,
            "inert": proposal_inert,
            "persisted_part_types": (
                [part.get("part_type") for part in assistant_turns[0].get("parts", [])]
                if len(assistant_turns) == 1 else []
            ),
        }
        if counter.stream_calls != 1 or proposal is None or not proposal_inert:
            receipt.update({"status": "NOT_RUN", "stop_reason": "proposal_not_contract_valid_or_provider_attempt_not_one"})
            return 4

        request = {
            "title": proposal["content"]["title"],
            "description": proposal["content"].get("description"),
            "conversation_id": conversation_id,
            "source_proposal_part_id": proposal["part_id"],
            "steps": proposal["content"]["steps"],
        }
        idempotency_key = f"e2-{uuid.uuid4()}"
        created = await client.post(
            f"/api/works/{work_id}/action-packages", json=request,
            headers={"Idempotency-Key": idempotency_key},
        )
        replayed = await client.post(
            f"/api/works/{work_id}/action-packages", json=request,
            headers={"Idempotency-Key": idempotency_key},
        )
        if created.status_code != 201 or replayed.status_code != 200 or created.json().get("id") != replayed.json().get("id"):
            receipt.update({"status": "FAIL", "stop_reason": "action_package_idempotency_failed"})
            return 2
        package_id = created.json()["id"]
        pre_approval = _snapshot(db_path, work_id)
        if (
            pre_approval["work_status"] != "not_started"
            or pre_approval["progress_percent"] != 0
            or pre_approval["counts"]["action_packages"] != 1
            or pre_approval["counts"]["action_steps"] != 1
            or pre_approval["counts"]["action_attempts"] != 0
            or pre_approval["counts"]["generic_approvals"] != 0
        ):
            receipt.update({"status": "FAIL", "stop_reason": "proposal_or_package_mutated_work_before_approval"})
            return 2
        approved = await client.post(f"/api/action-packages/{package_id}/approve")
        if approved.status_code != 200 or approved.json().get("approved_hash") != created.json().get("package_hash"):
            receipt.update({"status": "FAIL", "stop_reason": "explicit_approval_hash_binding_failed"})
            return 2
        first_execution = await execute_one_approved_package(temp_settings, "e2-bounded-worker")
        second_execution = await execute_one_approved_package(temp_settings, "e2-bounded-worker")
        final = _snapshot(db_path, work_id)

    conn = sqlite3.connect(db_path)
    try:
        package = conn.execute(
            "SELECT status, attempt_count FROM action_packages WHERE id = ?", (package_id,)
        ).fetchone()
        attempts = conn.execute(
            "SELECT COUNT(*) FROM action_attempts WHERE package_id = ? AND status = 'succeeded'", (package_id,)
        ).fetchone()[0]
        audit_actions = [row[0] for row in conn.execute(
            "SELECT action FROM audit_events WHERE target = ? ORDER BY rowid", (package_id,)
        ).fetchall()]
    finally:
        conn.close()
    expected_audit = [
        "action_package.proposed", "action_package.approved", "action_package.executing", "action_package.succeeded",
    ]
    receipt["lifecycle"] = {
        "idempotency_statuses": [created.status_code, replayed.status_code],
        "approval_status": approved.status_code,
        "executor": {"first_claim": first_execution, "second_claim": second_execution},
        "package_status": package[0] if package else None,
        "attempt_count": package[1] if package else None,
        "succeeded_attempts": attempts,
        "audit_actions": audit_actions,
        "final_work": final,
    }
    passed = (
        package is not None and package[0] == "succeeded" and package[1] == 1 and attempts == 1
        and first_execution is True and second_execution is False
        and final["work_status"] == "in_progress" and final["progress_percent"] == 1
        and audit_actions == expected_audit
    )
    receipt.update({"status": "PASS" if passed else "FAIL", "stop_reason": None if passed else "postcondition_failed"})
    return 0 if passed else 2


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded isolated E2 real-provider acceptance flow.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model-profile-id", help="Existing enabled free model profile to select manually.")
    selection.add_argument("--catalog-model", choices=sorted(CATALOG_FREE_MODELS), help="Catalog-confirmed free model seeded only in the temporary DB.")
    parser.add_argument(
        "--provider-profile-id",
        help="Existing enabled OpenAI-compatible or OpenAI Responses provider used only with --catalog-model.",
    )
    args = parser.parse_args()
    if args.catalog_model and not args.provider_profile_id:
        parser.error("--catalog-model requires --provider-profile-id")
    if args.model_profile_id and args.provider_profile_id:
        parser.error("--provider-profile-id is only valid with --catalog-model")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = REPO_ROOT / "output" / "e2-real-provider" / f"package-e2-bounded-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {
        "package": "E2 bounded real provider",
        "started_at": int(time.time()),
        "provider_request_budget": 1,
        "fallback_budget": 0,
        "scenario": SCENARIO_ID,
        "source_hashes": _source_hashes(),
        "runner_sha256": _sha256(Path(__file__)),
    }
    temp_root = Path(tempfile.mkdtemp(prefix="dirap-e2-bounded-"))
    exit_code = 2
    try:
        exit_code = await _run(
            receipt, temp_root, args.model_profile_id, args.catalog_model, args.provider_profile_id,
        )
    except Exception as exc:  # Keep evidence safe: no transport detail, path, or provider body.
        receipt.update({"status": "FAIL", "stop_reason": "runner_exception", "exception_type": type(exc).__name__})
        exit_code = 2
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        receipt["cleanup"] = {"temporary_root_removed": not temp_root.exists()}
        receipt["finished_at"] = int(time.time())
        receipt["exit_code"] = exit_code
        (output_dir / "run-metadata.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"status": receipt["status"], "exit_code": exit_code, "evidence": str(output_dir)}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
