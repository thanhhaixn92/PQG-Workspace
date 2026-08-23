"""Durable execution overlay for GYO Assistant runs.

The existing Assistant module remains the content/scope contract owner. This
router replaces only run/retry/cancel lifecycle endpoints so execution is
persisted and lease-backed instead of owned by FastAPI BackgroundTasks.
"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.assistant import (
    _assert_active_conversation,
    _assert_work,
    _bound_thread_scope,
    _copy_turn_context,
    _insert_turn_context,
    _insert_user_parts,
    _normalize_cancel_outcome,
    _read_only_response,
    _thread,
    _turn,
    _turn_context,
    _validated_attachments,
    _write_assistant_parts,
    _write_run_metadata,
)
from app.api.schemas import (
    AssistantRetryRequest,
    AssistantTurnCreateRequest,
    AssistantTurnResponse,
    SseDoneEvent,
    SseErrorEvent,
)
from app.dependencies import get_db, get_settings, get_trusted_actor
from app.services.assistant_runs import (
    AssistantRunClaim,
    enqueue_assistant_run,
    execute_one_assistant_run,
    get_assistant_run,
    is_cancel_requested,
    request_assistant_run_cancel,
    run_public_dict,
)
from app.services.audit import log_audit_event
from app.services.event_bus import event_bus
from app.services.gyo_learning_worker import enqueue_learning_job
from app.settings import Settings


router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class _CancelAwareGyo:
    """Stop forwarding provider events once durable cancellation is requested."""

    def __init__(self, delegate: Any, settings: Settings, run_id: str) -> None:
        self._delegate = delegate
        self._settings = settings
        self._run_id = run_id

    async def stream(self, request):
        if await is_cancel_requested(self._settings.db_path_resolved, self._run_id):
            yield SimpleNamespace(type="done", data={"status": "cancelled", "model_id": "gyo"})
            return
        async for event in self._delegate.stream(request):
            if await is_cancel_requested(self._settings.db_path_resolved, self._run_id):
                yield SimpleNamespace(type="done", data={"status": "cancelled", "model_id": "gyo"})
                return
            yield event


async def _stored_prompt_and_attachments(
    conn: aiosqlite.Connection,
    user_turn_id: str | None,
) -> tuple[str, list[str]]:
    if not user_turn_id:
        raise RuntimeError("durable_run_input_missing")
    async with conn.execute(
        "SELECT content_json FROM assistant_turn_parts WHERE turn_id = ? AND part_type = 'text' ORDER BY sort_order LIMIT 1",
        (user_turn_id,),
    ) as cur:
        prompt_row = await cur.fetchone()
    if prompt_row is None:
        raise RuntimeError("durable_run_prompt_missing")
    try:
        prompt = json.loads(prompt_row["content_json"]).get("text")
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("durable_run_prompt_invalid") from exc
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError("durable_run_prompt_invalid")

    async with conn.execute(
        "SELECT content_json FROM assistant_turn_parts WHERE turn_id = ? AND part_type = 'artifact' ORDER BY sort_order",
        (user_turn_id,),
    ) as cur:
        rows = await cur.fetchall()
    artifact_ids: list[str] = []
    for row in rows:
        try:
            value = json.loads(row["content_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        artifact_id = value.get("artifact_id") if isinstance(value, dict) else None
        if isinstance(artifact_id, str) and artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)
    return prompt, artifact_ids


async def execute_assistant_run_claim(
    claim: AssistantRunClaim,
    *,
    gyo_orchestrator: Any,
    settings: Settings,
) -> None:
    """Execute one claimed run while durable run state remains authoritative."""
    channel = f"assistant:{claim.thread_id}"
    try:
        async with __import__("app.db.connection", fromlist=["get_db_connection"]).get_db_connection(
            settings.db_path_resolved
        ) as conn:
            prompt, attachment_ids = await _stored_prompt_and_attachments(conn, claim.user_turn_id)
            await _validated_attachments(conn, claim.work_id, attachment_ids)
            context = await _turn_context(conn, claim.user_turn_id) if claim.user_turn_id else {
                "plan_step_id": None,
                "memory_scope_id": None,
                "context_mode": "suggest_only",
                "auto_learning_enabled": 0,
            }
            wrapped_gyo = (
                _CancelAwareGyo(gyo_orchestrator, settings, claim.id)
                if gyo_orchestrator is not None
                else None
            )
            (
                status_value,
                model_id,
                part_type,
                text,
                source_parts,
                structured_parts,
                run_metadata,
                learning_candidate,
            ) = await _read_only_response(
                conn,
                claim.work_id,
                prompt,
                wrapped_gyo,
                conversation_id=claim.conversation_id,
                event_channel=channel,
                assistant_turn_id=claim.assistant_turn_id,
                attachment_artifact_ids=attachment_ids,
                model_profile_id=claim.requested_model_profile_id,
                route_mode=claim.route_mode,
                plan_step_id=context["plan_step_id"],
                memory_scope_id=context["memory_scope_id"],
                memory_context_mode=context["context_mode"],
                auto_learning_enabled=bool(context["auto_learning_enabled"]),
            )

            async with conn.execute("SELECT status FROM assistant_runs WHERE id = ?", (claim.id,)) as cur:
                current_run = await cur.fetchone()
            if current_run is None:
                return
            if current_run["status"] == "cancel_requested":
                if run_metadata:
                    cancelled_metadata = dict(run_metadata)
                    cancelled_metadata["fallback_chain"] = [
                        {
                            "provider_profile_id": run_metadata.get("provider_profile_id"),
                            "model_profile_id": run_metadata.get("model_profile_id"),
                            "outcome": "cancelled",
                        }
                    ]
                    await _write_run_metadata(
                        conn,
                        assistant_turn_id=claim.assistant_turn_id,
                        metadata=cancelled_metadata,
                        now=int(time.time()),
                    )
                    await conn.commit()
                return

            now = int(time.time())
            updated = await conn.execute(
                """UPDATE assistant_turns
                   SET status = ?, model_id = ?, completed_at = ?, error = ?
                   WHERE id = ? AND status = 'running'
                     AND EXISTS (
                         SELECT 1 FROM assistant_runs
                         WHERE id = ? AND status = 'running'
                     )""",
                (
                    status_value,
                    model_id,
                    now,
                    text if status_value == "failed" else None,
                    claim.assistant_turn_id,
                    claim.id,
                ),
            )
            completed = updated.rowcount == 1
            if not completed:
                await conn.rollback()
                return
            if claim.user_turn_id:
                await _copy_turn_context(conn, claim.user_turn_id, claim.assistant_turn_id)
            await _write_run_metadata(
                conn,
                assistant_turn_id=claim.assistant_turn_id,
                metadata=run_metadata,
                now=now,
            )
            if (
                learning_candidate is not None
                and claim.work_id
                and context["plan_step_id"]
                and context["memory_scope_id"]
            ):
                enqueue_result = await enqueue_learning_job(
                    conn,
                    assistant_turn_id=claim.assistant_turn_id,
                    work_id=claim.work_id,
                    plan_step_id=context["plan_step_id"],
                    memory_scope_id=context["memory_scope_id"],
                    candidate=learning_candidate,
                    now=now,
                )
                structured_parts.append(
                    (
                        "tool_result",
                        {
                            "tool_name": "gyo_learning_worker",
                            "status": enqueue_result,
                            "summary": (
                                "GYO đã đưa đề xuất học vào hàng đợi kiểm soát."
                                if enqueue_result == "queued"
                                else "Đề xuất học trùng lặp nên không được tạo thêm."
                            ),
                        },
                    )
                )
            await _write_assistant_parts(
                conn,
                assistant_id=claim.assistant_turn_id,
                part_type=part_type,
                text=text,
                source_parts=source_parts,
                structured_parts=structured_parts,
                now=now,
            )
            await conn.execute(
                "UPDATE assistant_threads SET updated_at = ? WHERE id = ?",
                (now, claim.thread_id),
            )
            await conn.commit()
        if status_value == "failed":
            await event_bus.publish(
                channel,
                SseErrorEvent(
                    message=text,
                    assistant_turn_id=claim.assistant_turn_id,
                    thread_id=claim.thread_id,
                ),
            )
        else:
            await event_bus.publish(
                channel,
                SseDoneEvent(
                    assistant_turn_id=claim.assistant_turn_id,
                    thread_id=claim.thread_id,
                    routing=(
                        {
                            "provider_profile_id": run_metadata.get("provider_profile_id"),
                            "model_profile_id": run_metadata.get("model_profile_id"),
                            "route_mode": run_metadata.get("route_mode"),
                            "selection_reason": run_metadata.get("selection_reason"),
                            "attempts": run_metadata.get("fallback_chain", []),
                        }
                        if run_metadata
                        else None
                    ),
                ),
            )
    except Exception:
        failure_text = "Trợ lý GYO không thể hoàn tất yêu cầu này. Không có thay đổi nào được thực hiện."
        await event_bus.publish(
            channel,
            SseErrorEvent(
                message=failure_text,
                assistant_turn_id=claim.assistant_turn_id,
                thread_id=claim.thread_id,
            ),
        )
        raise


async def _execute_inline_if_no_worker(
    http_request: Request,
    settings: Settings,
    run_id: str,
) -> None:
    """Compatibility for isolated ASGI apps that do not execute lifespan.

    The run is still persisted and claimed through the durable lease service
    before execution. Normal uvicorn runtime always uses the lifespan worker.
    """
    if getattr(http_request.app.state, "assistant_run_worker_active", False):
        return

    async def executor(claim: AssistantRunClaim) -> None:
        await execute_assistant_run_claim(
            claim,
            gyo_orchestrator=getattr(http_request.app.state, "gyo_orchestrator", None),
            settings=settings,
        )

    await execute_one_assistant_run(
        settings,
        f"inline-{uuid.uuid4()}",
        executor,
        run_id=run_id,
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    del actor
    row = await get_assistant_run(conn, run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assistant run not found")
    return run_public_dict(row)


@router.post(
    "/threads/{thread_id}/runs",
    response_model=list[AssistantTurnResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(
    thread_id: str,
    request: AssistantTurnCreateRequest,
    http_request: Request,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[AssistantTurnResponse]:
    thread = await _thread(conn, thread_id)
    if thread["status"] != "active":
        raise HTTPException(status_code=409, detail="Assistant thread is archived")
    work_id, conversation_id = await _bound_thread_scope(conn, thread, request)
    attachments = await _validated_attachments(conn, work_id, request.attachment_artifact_ids)
    now = int(time.time())
    user_id, assistant_id = str(uuid.uuid4()), str(uuid.uuid4())

    await conn.execute("BEGIN IMMEDIATE")
    try:
        thread = await _thread(conn, thread_id)
        if thread["status"] != "active":
            raise HTTPException(status_code=409, detail="Assistant thread is archived")
        await _bound_thread_scope(conn, thread, request)
        async with conn.execute(
            "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
            (thread_id,),
        ) as cur:
            if await cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="GYO is already responding in this thread")
        await conn.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, created_at, completed_at)
               VALUES (?, ?, ?, ?, 'user', 'completed', ?, ?)""",
            (user_id, thread_id, work_id, conversation_id, now, now),
        )
        await _insert_user_parts(conn, turn_id=user_id, prompt=request.prompt, attachments=attachments, now=now)
        await _insert_turn_context(
            conn,
            user_turn_id=user_id,
            work_id=work_id,
            plan_step_id=request.plan_step_id,
            now=now,
        )
        await conn.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
               VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
            (assistant_id, thread_id, work_id, conversation_id, now),
        )
        await enqueue_assistant_run(
            conn,
            assistant_turn_id=assistant_id,
            user_turn_id=user_id,
            thread_id=thread_id,
            work_id=work_id,
            conversation_id=conversation_id,
            requested_model_profile_id=request.model_profile_id,
            route_mode=request.route_mode,
            now=now,
        )
        await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
        await log_audit_event(
            conn,
            work_id,
            actor,
            "assistant.run.queued",
            target=assistant_id,
            payload={"thread_id": thread_id, "conversation_id": conversation_id},
            commit=False,
        )
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        raise HTTPException(status_code=409, detail="GYO is already responding in this thread") from exc
    except Exception:
        await conn.rollback()
        raise

    await _execute_inline_if_no_worker(http_request, settings, assistant_id)
    async with conn.execute(
        "SELECT * FROM assistant_turns WHERE id IN (?, ?) ORDER BY created_at, rowid",
        (user_id, assistant_id),
    ) as cur:
        rows = await cur.fetchall()
    return [await _turn(conn, row) for row in rows]


@router.post(
    "/turns/{turn_id}/retry",
    response_model=AssistantTurnResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_turn(
    turn_id: str,
    http_request: Request,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    request: AssistantRetryRequest | None = None,
) -> AssistantTurnResponse:
    async with conn.execute("SELECT *, rowid AS sequence FROM assistant_turns WHERE id = ?", (turn_id,)) as cur:
        failed_turn = await cur.fetchone()
    if failed_turn is None:
        raise HTTPException(status_code=404, detail="Assistant turn not found")
    if failed_turn["role"] != "assistant" or failed_turn["status"] != "failed":
        raise HTTPException(status_code=409, detail="Only a failed Assistant response can be retried")
    thread = await _thread(conn, failed_turn["thread_id"])
    if thread["status"] != "active":
        raise HTTPException(status_code=409, detail="Assistant thread is archived")
    if failed_turn["work_id"]:
        await _assert_work(conn, failed_turn["work_id"])
    if failed_turn["work_id"] and failed_turn["conversation_id"]:
        await _assert_active_conversation(
            conn,
            work_id=failed_turn["work_id"],
            conversation_id=failed_turn["conversation_id"],
        )

    async with conn.execute(
        """SELECT user_turn.id AS user_turn_id, part.content_json
           FROM assistant_turns AS user_turn
           JOIN assistant_turn_parts AS part ON part.turn_id = user_turn.id
           WHERE user_turn.thread_id = ?
             AND user_turn.role = 'user'
             AND user_turn.rowid < ?
             AND part.part_type = 'text'
           ORDER BY user_turn.rowid DESC, part.sort_order ASC
           LIMIT 1""",
        (failed_turn["thread_id"], failed_turn["sequence"]),
    ) as cur:
        prompt_row = await cur.fetchone()
    if prompt_row is None:
        raise HTTPException(status_code=409, detail="Original user prompt is unavailable")
    try:
        prompt = json.loads(prompt_row["content_json"]).get("text")
    except (TypeError, json.JSONDecodeError):
        prompt = None
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=409, detail="Original user prompt is unavailable")

    async with conn.execute(
        "SELECT content_json FROM assistant_turn_parts WHERE turn_id = ? AND part_type = 'artifact' ORDER BY sort_order",
        (prompt_row["user_turn_id"],),
    ) as cur:
        attachment_rows = await cur.fetchall()
    attachment_ids: list[str] = []
    for row in attachment_rows:
        try:
            content = json.loads(row["content_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        artifact_id = content.get("artifact_id") if isinstance(content, dict) else None
        if isinstance(artifact_id, str) and artifact_id not in attachment_ids:
            attachment_ids.append(artifact_id)
    await _validated_attachments(conn, failed_turn["work_id"], attachment_ids)

    retry_mode = request.mode if request is not None else "same_model"
    retry_model_id: str | None = None
    if retry_mode == "same_model":
        async with conn.execute(
            """SELECT metadata.model_profile_id
               FROM assistant_run_metadata AS metadata
               JOIN ai_model_profiles AS model ON model.id = metadata.model_profile_id
               JOIN ai_provider_profiles AS provider ON provider.id = model.provider_profile_id
               WHERE metadata.assistant_turn_id = ?
                 AND model.enabled = 1 AND model.retired_at IS NULL
                 AND provider.enabled = 1 AND provider.retired_at IS NULL""",
            (turn_id,),
        ) as cur:
            retry_model = await cur.fetchone()
        if retry_model is None or not retry_model["model_profile_id"]:
            raise HTTPException(
                status_code=409,
                detail="Model của lượt trước không còn sẵn sàng; hãy dùng Thử lại tự động",
            )
        retry_model_id = retry_model["model_profile_id"]

    assistant_id = str(uuid.uuid4())
    now = int(time.time())
    await conn.execute("BEGIN IMMEDIATE")
    try:
        async with conn.execute(
            "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
            (failed_turn["thread_id"],),
        ) as cur:
            if await cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="GYO is already responding in this thread")
        await conn.execute(
            """INSERT INTO assistant_turns
               (id, thread_id, work_id, conversation_id, role, status, model_id, created_at)
               VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)""",
            (
                assistant_id,
                failed_turn["thread_id"],
                failed_turn["work_id"],
                failed_turn["conversation_id"],
                now,
            ),
        )
        await enqueue_assistant_run(
            conn,
            assistant_turn_id=assistant_id,
            user_turn_id=prompt_row["user_turn_id"],
            thread_id=failed_turn["thread_id"],
            work_id=failed_turn["work_id"],
            conversation_id=failed_turn["conversation_id"],
            requested_model_profile_id=retry_model_id,
            route_mode="manual" if retry_mode == "same_model" else "auto",
            now=now,
        )
        await conn.execute(
            "UPDATE assistant_threads SET updated_at = ? WHERE id = ?",
            (now, failed_turn["thread_id"]),
        )
        await log_audit_event(
            conn,
            failed_turn["work_id"],
            actor,
            "assistant.run.retry_queued",
            target=assistant_id,
            payload={"retry_of_turn_id": turn_id, "mode": retry_mode},
            commit=False,
        )
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        raise HTTPException(status_code=409, detail="GYO is already responding in this thread") from exc
    except Exception:
        await conn.rollback()
        raise

    await _execute_inline_if_no_worker(http_request, settings, assistant_id)
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (assistant_id,)) as cur:
        created = await cur.fetchone()
    return await _turn(conn, created)


async def _legacy_cancel(
    turn_id: str,
    http_request: Request,
    actor: str,
    conn: aiosqlite.Connection,
) -> dict[str, Any]:
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (turn_id,)) as cur:
        running_turn = await cur.fetchone()
    if running_turn is None:
        raise HTTPException(status_code=404, detail="Assistant turn not found")
    if running_turn["role"] != "assistant" or running_turn["status"] != "running":
        raise HTTPException(status_code=409, detail="Only a running Assistant response can be cancelled")
    now = int(time.time())
    message = "Bạn đã hủy phản hồi này. Nội dung đến muộn sẽ không được lưu hoặc hiển thị."
    updated = await conn.execute(
        "UPDATE assistant_turns SET status = 'cancelled', completed_at = ?, error = ? WHERE id = ? AND status = 'running'",
        (now, message, turn_id),
    )
    if updated.rowcount != 1:
        raise HTTPException(status_code=409, detail="Assistant response is no longer running")
    await _write_assistant_parts(
        conn,
        assistant_id=turn_id,
        part_type="error",
        text=message,
        source_parts=[],
        structured_parts=[],
        now=now,
    )
    await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, running_turn["thread_id"]))
    await log_audit_event(
        conn,
        running_turn["work_id"],
        actor,
        "assistant.turn.cancelled",
        target=turn_id,
        payload={"thread_id": running_turn["thread_id"], "legacy": True},
        commit=False,
    )
    await conn.commit()
    await event_bus.publish(
        f"assistant:{running_turn['thread_id']}",
        SseDoneEvent(assistant_turn_id=turn_id, thread_id=running_turn["thread_id"]),
    )
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (turn_id,)) as cur:
        cancelled = await cur.fetchone()
    return (await _turn(conn, cancelled)).model_dump()


@router.post("/turns/{turn_id}/cancel")
async def cancel_turn(
    turn_id: str,
    http_request: Request,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    run = await get_assistant_run(conn, assistant_turn_id=turn_id)
    if run is None:
        return await _legacy_cancel(turn_id, http_request, actor, conn)
    if run["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Assistant run is already terminal")

    now = int(time.time())
    await conn.execute("BEGIN IMMEDIATE")
    try:
        requested = await request_assistant_run_cancel(conn, assistant_turn_id=turn_id, now=now)
        if requested is None:
            raise HTTPException(status_code=404, detail="Assistant run not found")
        await log_audit_event(
            conn,
            requested["work_id"],
            actor,
            "assistant.run.cancel_requested",
            target=requested["id"],
            payload={"thread_id": requested["thread_id"]},
            commit=False,
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise

    gyo_orchestrator = getattr(http_request.app.state, "gyo_orchestrator", None)
    cancel_method = getattr(gyo_orchestrator, "cancel", None)
    cancel_with_routing = getattr(gyo_orchestrator, "cancel_with_selected_routing", None)
    cancel_outcome = "connection_unavailable"
    routing_metadata: Mapping[str, Any] | None = None
    if cancel_with_routing is not None:
        try:
            cancel_outcome, selected = await cancel_with_routing(turn_id)
            cancel_outcome = _normalize_cancel_outcome(cancel_outcome)
            routing_metadata = selected if isinstance(selected, Mapping) else None
        except Exception:
            cancel_outcome = "adapter_failed"
    elif cancel_method is not None:
        try:
            cancel_outcome = _normalize_cancel_outcome(await cancel_method(turn_id))
        except Exception:
            cancel_outcome = "adapter_failed"

    selected_routing = getattr(gyo_orchestrator, "selected_routing", None)
    if cancel_outcome == "cancelled" and routing_metadata is None and selected_routing is not None:
        try:
            routing_metadata = await selected_routing(turn_id)
        except Exception:
            routing_metadata = None
    if cancel_outcome == "cancelled" and isinstance(routing_metadata, Mapping):
        cancelled_metadata = dict(routing_metadata)
        cancelled_metadata["fallback_chain"] = [
            {
                "provider_profile_id": routing_metadata.get("provider_profile_id"),
                "model_profile_id": routing_metadata.get("model_profile_id"),
                "outcome": "cancelled",
            }
        ]
        await _write_run_metadata(
            conn,
            assistant_turn_id=turn_id,
            metadata=cancelled_metadata,
            now=now,
        )
    await log_audit_event(
        conn,
        requested["work_id"],
        "system",
        "assistant.run.cancel_compute",
        target=requested["id"],
        payload={"outcome": cancel_outcome, "remote_compute_stop_proven": False},
    )
    await event_bus.publish(
        f"assistant:{requested['thread_id']}",
        SseDoneEvent(assistant_turn_id=turn_id, thread_id=requested["thread_id"]),
    )
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (turn_id,)) as cur:
        turn_row = await cur.fetchone()
    async with conn.execute("SELECT * FROM assistant_runs WHERE id = ?", (requested["id"],)) as cur:
        run_row = await cur.fetchone()
    payload = (await _turn(conn, turn_row)).model_dump()
    payload["run_id"] = requested["id"]
    payload["run_status"] = run_row["status"] if run_row is not None else "cancel_requested"
    payload["remote_compute_stop_proven"] = False
    return payload
