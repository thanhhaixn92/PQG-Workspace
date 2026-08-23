"""Read-scoped GYO Assistant threads and transparent local summaries.

This surface never gives a model direct mutation capability.  Changes remain
explicit proposals and are only applied through an approved action package.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
import base64
from pathlib import Path, PurePosixPath
from collections.abc import Mapping
from typing import Any

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.api.schemas import (
    ActionPackageCreateRequest,
    AssistantContextManifestResponse,
    AssistantHistoryPageResponse,
    AssistantHistoryUpdateRequest,
    AssistantThreadCreateRequest,
    AssistantThreadResponse,
    AssistantThreadUpdateRequest,
    AssistantRetryRequest,
    AssistantTurnCreateRequest,
    AssistantTurnPartResponse,
    AssistantTurnResponse,
)
from app.dependencies import get_db, get_settings, get_trusted_actor
from app.db.connection import get_db_connection
from app.services.event_bus import event_bus
from app.api.schemas import SseDoneEvent, SseErrorEvent, SseTokenEvent
from app.services.audit import log_audit_event
from app.services.assistant_context import AssistantContextPackBuilder
from app.services.work_memory_scope import WorkMemoryScope, get_work_memory_scope
from app.services.gyo_learning_worker import enqueue_learning_job
from app.settings import Settings

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_ACTION_PROPOSAL_PREFIX = "DIRAP_ACTION_PROPOSAL:"
_LEARNING_CANDIDATE_PREFIX = "DIRAP_LEARNING_CANDIDATE:"
_CONTEXT_ARTIFACT_SUFFIXES = frozenset({".txt", ".md", ".csv"})
_HISTORY_CURSOR_VERSION = 1


def _sha256_file(path: Path) -> str:
    """Hash a managed artifact without trusting its registered metadata."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
_FENCED_ACTION_PROPOSAL_RE = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<payload>[\s\S]*?)\r?\n?```\Z",
    re.IGNORECASE,
)
_CANCEL_OUTCOMES = frozenset({
    "cancelled", "not_active", "connection_unavailable", "adapter_failed", "unsupported",
})


def _normalize_cancel_outcome(value: object) -> str:
    """Normalize GYO cancellation outcomes without exposing adapter exceptions."""
    if isinstance(value, str) and value in _CANCEL_OUTCOMES:
        return value
    if value is True:
        return "cancelled"
    return "adapter_failed"


def _proposal_schema_reason(error: ValidationError) -> str:
    """Return an allow-listed reason without retaining rejected model content."""
    first_location = next(iter(error.errors()), {}).get("loc", ())
    if not first_location:
        return "schema_invalid"
    if first_location[0] == "title":
        return "title_invalid"
    if first_location[0] != "steps":
        return "schema_invalid"
    if "kind" in first_location:
        return "step_kind_invalid"
    return "steps_invalid"


def _proposal_contract_details(
    text: str,
) -> tuple[ActionPackageCreateRequest | None, str, str | None]:
    """Validate one proposal and expose only stable, non-sensitive diagnostics."""
    marker_count = text.count(_ACTION_PROPOSAL_PREFIX)
    if marker_count == 0:
        return None, "missing_marker", "marker_missing"
    if marker_count != 1:
        return None, "invalid_json", "multiple_markers"
    marker_index = text.index(_ACTION_PROPOSAL_PREFIX)
    payload_text = text[marker_index + len(_ACTION_PROPOSAL_PREFIX):].strip()
    fenced = _FENCED_ACTION_PROPOSAL_RE.fullmatch(payload_text)
    if fenced is not None:
        payload_text = fenced.group("payload").strip()
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError):
        return None, "invalid_json", "json_syntax"
    if not isinstance(payload, dict):
        return None, "invalid_schema", "payload_not_object"
    try:
        return ActionPackageCreateRequest.model_validate(payload), "valid", None
    except ValidationError as error:
        return None, "invalid_schema", _proposal_schema_reason(error)


def _proposal_contract_diagnostic(text: str) -> str:
    """Classify proposal parsing without retaining model output or JSON."""
    return _proposal_contract_details(text)[1]


def _proposal_contract_reason_code(text: str) -> str | None:
    """Return the allow-listed subreason persisted with an invalid proposal."""
    return _proposal_contract_details(text)[2]


def _extract_action_proposal(
    text: str,
    *,
    work_id: str,
    conversation_id: str | None,
) -> tuple[str, dict[str, Any] | None, str]:
    """Extract one explicitly marked and schema-valid action proposal."""
    marker_index = text.rfind(_ACTION_PROPOSAL_PREFIX)
    if marker_index < 0:
        return text, None, "missing_marker"
    visible = text[:marker_index].rstrip()
    validated, diagnostic, _reason_code = _proposal_contract_details(text)
    if diagnostic != "valid":
        safe_visible = visible or "Trợ lý GYO không thể tạo đề xuất theo định dạng an toàn. Không có thay đổi nào được thực hiện."
        return safe_visible, None, diagnostic
    assert validated is not None
    # The proposal part itself becomes the only server-owned provenance handle.
    # A model-supplied source part id must never flow back to package creation.
    proposal = validated.model_dump(exclude={"conversation_id", "source_proposal_part_id"})
    proposal.update({
        "work_id": work_id,
        "conversation_id": conversation_id,
        "impact": "Chỉ cập nhật Công việc đã chọn sau khi bạn duyệt gói bất biến.",
        "undo": "Có thể tạo một đề xuất mới để điều chỉnh lại.",
        "risk": "write",
    })
    return visible or "Trợ lý GYO đã chuẩn bị một đề xuất để bạn xem trước.", proposal, "valid"


def _extract_learning_candidate(text: str) -> tuple[str, dict[str, Any] | None, str]:
    """Parse one bounded learning trailer without retaining free-form output.

    The trailer is intentionally line-delimited and must precede the optional
    Action Package trailer.  It works with both supported streaming provider
    adapters without requiring a second model call or provider-specific tools.
    """
    matches = list(re.finditer(r"(?m)^DIRAP_LEARNING_CANDIDATE:\s*(.*)$", text))
    if not matches:
        return text, None, "missing_marker"
    if len(matches) != 1:
        return text[:matches[0].start()].rstrip(), None, "multiple_markers"
    match = matches[0]
    try:
        candidate = json.loads(match.group(1))
    except json.JSONDecodeError:
        return text[:match.start()].rstrip(), None, "invalid_json"
    if not isinstance(candidate, dict):
        return text[:match.start()].rstrip(), None, "invalid_schema"
    kind = candidate.get("kind")
    step_id = candidate.get("plan_step_id")
    if kind not in {"memory", "skill"} or not isinstance(step_id, str) or not step_id.strip():
        return text[:match.start()].rstrip(), None, "invalid_schema"
    if kind == "memory":
        allowed = {"kind", "plan_step_id", "memory_kind", "memory_key", "content", "confidence", "sensitivity"}
        valid = (
            set(candidate).issubset(allowed)
            and candidate.get("memory_kind") in {"project_context", "task_continuity", "workflow_rule", "technical_decision", "lesson"}
            and isinstance(candidate.get("memory_key"), str) and 0 < len(candidate["memory_key"].strip()) <= 160
            and isinstance(candidate.get("content"), str) and 0 < len(candidate["content"].strip()) <= 8192
            and isinstance(candidate.get("confidence", 0.5), (int, float)) and 0 <= candidate.get("confidence", 0.5) <= 1
            and candidate.get("sensitivity", "normal") == "normal"
        )
    else:
        allowed = {"kind", "plan_step_id", "basis", "name", "description", "content"}
        valid = (
            set(candidate).issubset(allowed)
            and candidate.get("basis") == "repeated_success"
            and isinstance(candidate.get("name"), str) and 0 < len(candidate["name"].strip()) <= 160
            and (candidate.get("description") is None or isinstance(candidate.get("description"), str))
            and isinstance(candidate.get("content"), str) and 0 < len(candidate["content"].strip()) <= 100_000
        )
    if not valid:
        return text[:match.start()].rstrip(), None, "invalid_schema"
    return (text[:match.start()] + text[match.end():]).strip(), candidate, "valid"


def _safe_gyo_structured_content(part_type: str, content: Mapping[str, Any]) -> dict[str, Any]:
    """Keep provider event metadata useful without persisting sensitive output."""
    allowed = {
        "source": {"id", "kind", "title", "reason", "hash", "byte_count", "included", "excluded_reason"},
        "artifact": {"artifact_id", "id", "name", "kind", "sha256", "size_bytes", "attachment"},
        "tool_result": {"tool_name", "status", "summary", "diagnostic", "reason_code"},
        "approval": {"package_id", "package_hash", "before", "after", "risk", "undo"},
    }
    if part_type == "error":
        return {"message": "Trợ lý GYO không thể hoàn tất một phần yêu cầu. Không có thay đổi nào được thực hiện."}
    return {key: value for key, value in content.items() if key in allowed.get(part_type, set())}


async def _thread(conn: aiosqlite.Connection, thread_id: str) -> aiosqlite.Row:
    async with conn.execute("SELECT * FROM assistant_threads WHERE id = ?", (thread_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    return row


async def _assert_work(conn: aiosqlite.Connection, work_id: str) -> None:
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (work_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Work not found")
    if row[0]:
        raise HTTPException(status_code=409, detail="Work is archived")


async def _assert_active_conversation(
    conn: aiosqlite.Connection, *, work_id: str, conversation_id: str
) -> None:
    """Fail closed when a new GYO turn is outside one active Work conversation."""
    async with conn.execute(
        "SELECT status FROM conversations WHERE id = ? AND session_id = ?",
        (conversation_id, work_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found in selected Work")
    if row["status"] != "active":
        raise HTTPException(status_code=409, detail="Conversation is archived")


async def _bound_thread_scope(
    conn: aiosqlite.Connection,
    thread: aiosqlite.Row,
    request: AssistantTurnCreateRequest,
) -> tuple[str | None, str | None]:
    """Use only parent-thread scope for new turns; never bind legacy history."""
    thread_work_id = thread["work_id"]
    thread_conversation_id = thread["conversation_id"]
    if bool(thread_work_id) != bool(thread_conversation_id):
        raise HTTPException(status_code=409, detail="Legacy Assistant thread without complete Work and Conversation scope is read-only")
    if thread_work_id is None:
        if request.work_id is not None or request.conversation_id is not None:
            raise HTTPException(status_code=422, detail="A global Assistant thread cannot create a Work-scoped turn")
        return None, None
    if request.work_id is not None and request.work_id != thread_work_id:
        raise HTTPException(status_code=409, detail="A Work-scoped thread cannot switch Work")
    if request.conversation_id is not None and request.conversation_id != thread_conversation_id:
        raise HTTPException(status_code=409, detail="A conversation-bound thread cannot switch conversation")
    await _assert_work(conn, thread_work_id)
    await _assert_active_conversation(conn, work_id=thread_work_id, conversation_id=thread_conversation_id)
    return thread_work_id, thread_conversation_id


async def _validated_attachments(
    conn: aiosqlite.Connection,
    work_id: str | None,
    artifact_ids: list[str],
) -> list[dict[str, Any]]:
    if not artifact_ids:
        return []
    if not work_id:
        raise HTTPException(status_code=422, detail="Attachments require a selected Work")
    async with conn.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (work_id,)) as cur:
        work = await cur.fetchone()
    if work is None:
        raise HTTPException(status_code=409, detail="Work is archived or unavailable")
    workspace = Path(work["workspace_path"]).resolve()
    result: list[dict[str, Any]] = []
    for artifact_id in artifact_ids:
        async with conn.execute(
            """SELECT artifact.id, artifact.relative_path, artifact.kind, artifact.sha256, artifact.size_bytes,
                      COALESCE(validation.status, 'pending') AS validation_status
               FROM artifacts artifact
               LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
               WHERE artifact.id = ? AND artifact.session_id = ?""",
            (artifact_id, work_id),
        ) as cur:
            artifact = await cur.fetchone()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Attachment artifact not found in selected Work")
        relative = PurePosixPath(artifact["relative_path"])
        validation_status = artifact["validation_status"]
        if validation_status != "structurally_validated":
            detail = {
                "pending": "Attachment has not passed structural validation",
                "rejected": "Attachment was rejected during structural validation",
                "failed": "Attachment structural validation failed",
            }.get(validation_status, "Attachment validation status is unavailable")
            raise HTTPException(status_code=422, detail=detail)
        if not relative.parts or relative.parts[0] not in {"inputs", "outputs"}:
            raise HTTPException(status_code=403, detail="Attachment is outside the managed workspace")
        if relative.suffix.lower() not in _CONTEXT_ARTIFACT_SUFFIXES:
            raise HTTPException(
                status_code=422,
                detail="Attachment format is structurally validated but is not supported as GYO text context",
            )
        target = (workspace / Path(*relative.parts)).resolve()
        if not target.is_relative_to(workspace) or not target.is_file():
            raise HTTPException(status_code=409, detail="Attachment is no longer available")
        try:
            actual_hash = _sha256_file(target)
        except OSError as exc:
            raise HTTPException(status_code=409, detail="Attachment is no longer available") from exc
        if not artifact["sha256"] or actual_hash != artifact["sha256"]:
            raise HTTPException(status_code=409, detail="Attachment changed since it was registered")
        result.append({
            "artifact_id": artifact["id"],
            "name": relative.name,
            "kind": artifact["kind"],
            "size_bytes": artifact["size_bytes"],
            "sha256": artifact["sha256"],
            "attachment": True,
        })
    return result


async def _insert_user_parts(
    conn: aiosqlite.Connection,
    *,
    turn_id: str,
    prompt: str,
    attachments: list[dict[str, Any]],
    now: int,
) -> None:
    await conn.execute(
        "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'text', ?, 0, ?)",
        (str(uuid.uuid4()), turn_id, json.dumps({"text": prompt}), now),
    )
    for index, attachment in enumerate(attachments, start=1):
        await conn.execute(
            "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'artifact', ?, ?, ?)",
            (str(uuid.uuid4()), turn_id, json.dumps(attachment), index, now),
        )


async def _insert_turn_context(
    conn: aiosqlite.Connection,
    *,
    user_turn_id: str | None = None,
    work_id: str | None,
    plan_step_id: str | None,
    now: int,
) -> None:
    """Freeze the effective step policy so retry cannot widen its context."""
    if not work_id or not plan_step_id:
        await conn.execute(
            """INSERT INTO assistant_turn_contexts
               (user_turn_id, work_id, plan_step_id, memory_scope_id, context_mode, auto_learning_enabled, created_at)
               VALUES (?, ?, NULL, NULL, 'suggest_only', 0, ?)""",
            (user_turn_id, work_id, now),
        )
        return
    scope = await get_work_memory_scope(conn, work_id, plan_step_id)
    await conn.execute(
        """INSERT INTO assistant_turn_contexts
           (user_turn_id, work_id, plan_step_id, memory_scope_id, context_mode, auto_learning_enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_turn_id, work_id, plan_step_id, scope.id, scope.context_mode, int(scope.auto_learning_enabled), now),
    )


async def _turn_context(conn: aiosqlite.Connection, user_turn_id: str) -> dict[str, Any]:
    async with conn.execute("SELECT * FROM assistant_turn_contexts WHERE user_turn_id = ?", (user_turn_id,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row is not None else {
        "plan_step_id": None, "memory_scope_id": None, "context_mode": "suggest_only", "auto_learning_enabled": 0,
    }


async def _copy_turn_context(conn: aiosqlite.Connection, source_turn_id: str, target_turn_id: str) -> None:
    context = await _turn_context(conn, source_turn_id)
    await conn.execute(
        """INSERT OR REPLACE INTO assistant_turn_contexts
           (user_turn_id, work_id, plan_step_id, memory_scope_id, context_mode, auto_learning_enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (target_turn_id, context.get("work_id"), context["plan_step_id"], context["memory_scope_id"],
         context["context_mode"], int(bool(context["auto_learning_enabled"])), int(time.time())),
    )


async def _parts(conn: aiosqlite.Connection, turn_id: str) -> list[AssistantTurnPartResponse]:
    async with conn.execute(
        "SELECT * FROM assistant_turn_parts WHERE turn_id = ? ORDER BY sort_order", (turn_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [
        AssistantTurnPartResponse(
            id=row["id"],
            part_type=row["part_type"],
            content=json.loads(row["content_json"]),
            sort_order=row["sort_order"],
        )
        for row in rows
    ]


async def _turn(conn: aiosqlite.Connection, row: aiosqlite.Row) -> AssistantTurnResponse:
    values = dict(row)
    values["parts"] = await _parts(conn, row["id"])
    async with conn.execute(
        """SELECT metadata.route_mode, metadata.selection_reason, metadata.fallback_chain_json,
                  provider.display_name AS provider_display_name, model.display_name AS model_display_name
           FROM assistant_run_metadata AS metadata
           LEFT JOIN ai_provider_profiles AS provider ON provider.id = metadata.provider_profile_id
           LEFT JOIN ai_model_profiles AS model ON model.id = metadata.model_profile_id
           WHERE metadata.assistant_turn_id = ?""",
        (row["id"],),
    ) as cur:
        routing_row = await cur.fetchone()
    if routing_row is not None:
        try:
            raw_attempts = json.loads(routing_row["fallback_chain_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            raw_attempts = []
        attempts = []
        if isinstance(raw_attempts, list):
            for item in raw_attempts[:3]:
                if not isinstance(item, dict):
                    continue
                outcome = item.get("outcome")
                if outcome not in {"succeeded", "rate_limited", "provider_unavailable", "connection_error", "failed", "cancelled"}:
                    outcome = "failed"
                attempts.append({
                    "provider_profile_id": item.get("provider_profile_id") if isinstance(item.get("provider_profile_id"), str) else None,
                    "model_profile_id": item.get("model_profile_id") if isinstance(item.get("model_profile_id"), str) else None,
                    "outcome": outcome,
                })
        values["routing"] = {
            "provider_display_name": routing_row["provider_display_name"],
            "model_display_name": routing_row["model_display_name"],
            "route_mode": routing_row["route_mode"],
            "selection_reason": routing_row["selection_reason"],
            "attempts": attempts,
        }
    return AssistantTurnResponse(**values)


async def _read_only_response(
    conn: aiosqlite.Connection,
    work_id: str | None,
    prompt: str,
    gyo_orchestrator: Any,
    conversation_id: str | None = None,
    event_channel: str | None = None,
    assistant_turn_id: str | None = None,
    attachment_artifact_ids: list[str] | None = None,
    model_profile_id: str | None = None,
    route_mode: str = "auto",
    plan_step_id: str | None = None,
    memory_scope_id: str | None = None,
    memory_context_mode: str = "suggest_only",
    auto_learning_enabled: bool = False,
) -> tuple[
    str, str, str, str, list[dict[str, Any]], list[tuple[str, dict[str, Any]],], dict[str, Any], dict[str, Any] | None
]:
    """Build one visible GYO response without granting mutation capability."""
    source_parts: list[dict[str, Any]] = []
    structured_parts: list[tuple[str, dict[str, Any]]] = []
    if not work_id:
        async with conn.execute("SELECT COUNT(*) FROM sessions WHERE archived = 0") as cur:
            count = (await cur.fetchone())[0]
        text = (
            f"Đây là tóm tắt local: có {count} Công việc đang lưu trên máy này. "
            "Hãy chọn một Công việc trước khi yêu cầu thay đổi dữ liệu, kế hoạch hoặc tài liệu."
        )
        source_parts.append({"kind": "overview", "title": "Tổng quan Công việc", "reason": "Dữ liệu tổng hợp chỉ đọc"})
        return "completed", "local-summary", "text", text, source_parts, [], {}, None

    scope = WorkMemoryScope(memory_scope_id, work_id, plan_step_id or "", memory_context_mode, auto_learning_enabled)
    context_pack = await AssistantContextPackBuilder(conn).build(
        work_id, conversation_id, attachment_artifact_ids=attachment_artifact_ids,
        memory_mode=scope.context_mode,
        memory_project_id=work_id if scope.id else None,
        memory_scope_id=scope.id,
    )
    selected_context = context_pack.text
    source_parts = context_pack.included
    if gyo_orchestrator is None:
        text = "Trợ lý GYO chưa sẵn sàng để trả lời cho Công việc này. Hãy kiểm tra cấu hình mô hình trong Cài đặt."
        status, model_id, part_type = "failed", "gyo-unavailable", "error"
        run_metadata: dict[str, Any] = {}
    else:
        try:
            # Imported here so an unavailable/partial runtime fails closed rather
            # than preventing the API module from loading during startup.
            from app.services.gyo_orchestrator import GyoRunRequest

            learning_instruction = (
                "Nếu phát hiện một bài học dùng lại được, bạn có thể thêm đúng một dòng "
                "DIRAP_LEARNING_CANDIDATE: theo sau là JSON thuần. Chỉ dùng kind memory hoặc skill, "
                f"plan_step_id phải là {plan_step_id}, không chứa secret, raw path hay transcript; "
                "skill chỉ dùng basis repeated_success. Đặt dòng này trước Action Proposal nếu có. "
                if scope.auto_learning_enabled and scope.id and plan_step_id else
                "Không tạo DIRAP_LEARNING_CANDIDATE. "
            )
            gyo_prompt = (
                "Bạn là Trợ lý GYO. Chỉ trả lời bằng thông tin có trong ngữ cảnh đã chọn và yêu cầu của người dùng. "
                "Bạn không được tự tạo hay thực thi thay đổi dữ liệu, kế hoạch, tài liệu hoặc cấu hình. "
                "Khi một thay đổi chỉ có thể biểu diễn bằng work_plan_step_update hoặc work_status_update, "
                "bạn chỉ được tạo action_proposal; người dùng vẫn phải tạo và duyệt gói hành động. "
                "Kết thúc phản hồi bằng đúng một dòng DIRAP_ACTION_PROPOSAL: theo sau là JSON thuần hợp lệ gồm title, description (nếu cần) và steps. "
                "Phạm vi Công việc/Phiên trao đổi do server gắn; không thêm work_id hoặc conversation_id vào JSON. "
                "Mỗi step chỉ dùng work_plan_step_update hoặc work_status_update; không dùng markdown fence, không thêm key khác và không thêm nội dung sau JSON. "
                "Ví dụ đúng: DIRAP_ACTION_PROPOSAL: {\"title\":\"Bắt đầu Work\",\"description\":\"Đề xuất cập nhật trạng thái\",\"steps\":[{\"kind\":\"work_status_update\",\"input\":{\"work_status\":\"in_progress\",\"progress_percent\":1}}]}. "
                "Nếu không thể tạo JSON hợp lệ, chỉ giải thích ngắn gọn và không thêm marker. "
                "Không yêu cầu quyền, không tiết lộ cấu hình/credential/path nội bộ.\n\n"
                f"{learning_instruction}\n"
                f"YÊU CẦU CỦA NGƯỜI DÙNG:\n{prompt}"
            )
            run_request = GyoRunRequest(
                work_id=work_id,
                prompt=gyo_prompt,
                context=selected_context,
                model_profile_id=model_profile_id,
                route_mode="manual" if route_mode == "manual" else "auto",
                event_channel=event_channel,
                assistant_turn_id=assistant_turn_id,
                attachment_count=len(attachment_artifact_ids or []),
            )
            token_chunks: list[str] = []
            terminal: Mapping[str, Any] | None = None
            saw_error = False
            async for event in gyo_orchestrator.stream(run_request):
                event_type = getattr(event, "type", None)
                data = getattr(event, "data", None)
                if not isinstance(data, Mapping):
                    data = {}
                if event_type == "token":
                    chunk = data.get("text")
                    if isinstance(chunk, str) and chunk:
                        token_chunks.append(chunk)
                        if event_channel and assistant_turn_id:
                            await event_bus.publish(
                                event_channel,
                                SseTokenEvent(text=chunk, assistant_turn_id=assistant_turn_id, thread_id=event_channel.removeprefix("assistant:")),
                            )
                elif event_type == "done":
                    terminal = data
                elif event_type == "error":
                    # The provider error may contain transport or credential
                    # details.  It is intentionally not persisted or exposed.
                    saw_error = True

            terminal = terminal or {}
            terminal_status = terminal.get("status")
            status = terminal_status if terminal_status in {"completed", "failed", "cancelled"} else "failed"
            if saw_error and status == "completed":
                status = "failed"
            terminal_model_id = terminal.get("model_id")
            model_id = terminal_model_id if isinstance(terminal_model_id, str) else (
                "gyo-unavailable" if status == "failed" else "gyo"
            )
            text = "".join(token_chunks) or terminal.get("text")
            if not isinstance(text, str) or not text.strip():
                if status == "cancelled":
                    text = "Bạn đã hủy phản hồi này. Nội dung đến muộn sẽ không được lưu hoặc hiển thị."
                elif model_id == "gyo-unavailable":
                    text = "Trợ lý GYO chưa sẵn sàng. Hãy cấu hình một model đang bật trong Cài đặt."
                else:
                    text = "Trợ lý GYO không thể hoàn tất yêu cầu này. Không có thay đổi nào được thực hiện."
                    status = "failed"
            part_type = "text" if status == "completed" else "error"
            raw_parts = terminal.get("structured_parts")
            if isinstance(raw_parts, list):
                for raw_part in raw_parts:
                    if not isinstance(raw_part, (tuple, list)) or len(raw_part) != 2:
                        continue
                    raw_type, raw_content = raw_part
                    if raw_type not in {"source", "artifact", "tool_result", "action_proposal", "approval", "error"} or not isinstance(raw_content, Mapping):
                        continue
                    if raw_type == "action_proposal":
                        try:
                            validated = ActionPackageCreateRequest.model_validate(dict(raw_content)).model_dump()
                        except Exception:
                            structured_parts.append(("tool_result", {
                                "tool_name": "action_proposal_contract",
                                "status": "failed",
                                "diagnostic": "invalid_schema",
                                "summary": "Đề xuất không được lưu vì sai contract (invalid_schema).",
                            }))
                        else:
                            validated.update({
                                "work_id": work_id,
                                "conversation_id": conversation_id,
                                "impact": "Chỉ cập nhật Công việc đã chọn sau khi bạn duyệt gói bất biến.",
                                "undo": "Có thể tạo một đề xuất mới để điều chỉnh lại.",
                                "risk": "write",
                            })
                            structured_parts.append(("action_proposal", validated))
                    else:
                        structured_parts.append((raw_type, _safe_gyo_structured_content(raw_type, raw_content)))
            run_metadata = {
                "provider_profile_id": terminal.get("provider_profile_id"),
                "model_profile_id": terminal.get("model_profile_id"),
                "route_mode": terminal.get("route_mode"),
                "selection_reason": terminal.get("selection_reason"),
                "fallback_from_model_profile_id": terminal.get("fallback_from_model_profile_id"),
                "fallback_chain": terminal.get("fallback_chain"),
            }
        except Exception:
            text = "Trợ lý GYO không thể hoàn tất yêu cầu này. Không có thay đổi nào được thực hiện."
            status, model_id, part_type = "failed", "gyo", "error"
            run_metadata = {}
    learning_candidate: dict[str, Any] | None = None
    if status == "completed":
        text, learning_candidate, learning_diagnostic = _extract_learning_candidate(text)
        if learning_diagnostic not in {"missing_marker", "valid"}:
            structured_parts.append(("tool_result", {
                "tool_name": "learning_candidate_contract", "status": "failed", "diagnostic": learning_diagnostic,
                "summary": "Đề xuất học không được tạo vì sai contract.",
            }))
        proposal_text = text
        text, proposal, proposal_diagnostic = _extract_action_proposal(text, work_id=work_id, conversation_id=conversation_id)
        if proposal is not None:
            structured_parts.append(("action_proposal", proposal))
        elif proposal_diagnostic in {"invalid_json", "invalid_schema"}:
            proposal_reason = _proposal_contract_reason_code(proposal_text)
            structured_parts.append(("tool_result", {
                "tool_name": "action_proposal_contract",
                "status": "failed",
                "diagnostic": proposal_diagnostic,
                **({"reason_code": proposal_reason} if proposal_reason is not None else {}),
                "summary": f"Đề xuất không được lưu vì sai contract ({proposal_diagnostic}).",
            }))
    if learning_candidate is not None and learning_candidate["plan_step_id"] != plan_step_id:
        structured_parts.append(("tool_result", {
            "tool_name": "learning_candidate_contract", "status": "failed", "diagnostic": "scope_mismatch",
            "summary": "Đề xuất học không thuộc bước kế hoạch đang áp dụng nên không được tạo.",
        }))
        learning_candidate = None
    if learning_candidate is not None and (scope.id is None or not scope.auto_learning_enabled):
        learning_candidate = None
    return status, model_id, part_type, text, source_parts, structured_parts, run_metadata, learning_candidate


async def _write_run_metadata(
    conn: aiosqlite.Connection,
    *,
    assistant_turn_id: str,
    metadata: Mapping[str, Any],
    now: int,
) -> None:
    """Persist model-selection provenance once, never provider diagnostics."""
    route_mode = metadata.get("route_mode")
    if route_mode not in {"auto", "manual"}:
        return
    selection_reason = metadata.get("selection_reason")
    if not isinstance(selection_reason, str) or not selection_reason.strip():
        return
    clean = lambda value: value if isinstance(value, str) and value else None
    raw_chain = metadata.get("fallback_chain")
    chain_items = raw_chain if isinstance(raw_chain, list) else []
    await conn.execute(
        """
        INSERT INTO assistant_run_metadata (
            assistant_turn_id, provider_profile_id, model_profile_id, route_mode,
            selection_reason, fallback_from_model_profile_id, fallback_chain_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(assistant_turn_id) DO NOTHING
        """,
        (
            assistant_turn_id,
            clean(metadata.get("provider_profile_id")),
            clean(metadata.get("model_profile_id")),
            route_mode,
            " ".join(selection_reason.split())[:240],
            clean(metadata.get("fallback_from_model_profile_id")),
            json.dumps([
                {
                    "provider_profile_id": clean(item.get("provider_profile_id")),
                    "model_profile_id": clean(item.get("model_profile_id")),
                    "outcome": item.get("outcome") if item.get("outcome") in {"succeeded", "rate_limited", "provider_unavailable", "connection_error", "failed", "cancelled"} else "failed",
                }
                for item in chain_items[:3]
                if isinstance(item, Mapping)
            ], separators=(",", ":")),
            now,
        ),
    )


async def _insert_assistant_response(
    conn: aiosqlite.Connection,
    *,
    thread_id: str,
    user_turn_id: str,
    work_id: str | None,
    conversation_id: str | None,
    prompt: str,
    http_request: Request,
    attachment_artifact_ids: list[str],
    model_profile_id: str | None = None,
    route_mode: str = "auto",
) -> str:
    now = int(time.time())
    assistant_id = str(uuid.uuid4())
    context = await _turn_context(conn, user_turn_id)
    status, model_id, part_type, text, source_parts, structured_parts, run_metadata, learning_candidate = await _read_only_response(
        conn, work_id, prompt, getattr(http_request.app.state, "gyo_orchestrator", None),
        conversation_id=conversation_id,
        attachment_artifact_ids=attachment_artifact_ids,
        model_profile_id=model_profile_id,
        route_mode=route_mode,
        plan_step_id=context["plan_step_id"],
        memory_scope_id=context["memory_scope_id"],
        memory_context_mode=context["context_mode"],
        auto_learning_enabled=bool(context["auto_learning_enabled"]),
    )
    await conn.execute(
        "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at, completed_at, error) VALUES (?, ?, ?, ?, 'assistant', ?, ?, ?, ?, ?)",
        (assistant_id, thread_id, work_id, conversation_id, status, model_id, now, now, text if status == "failed" else None),
    )
    await _copy_turn_context(conn, user_turn_id, assistant_id)
    await _write_run_metadata(conn, assistant_turn_id=assistant_id, metadata=run_metadata, now=now)
    if learning_candidate is not None and work_id and context["plan_step_id"] and context["memory_scope_id"]:
        enqueue_result = await enqueue_learning_job(
            conn, assistant_turn_id=assistant_id, work_id=work_id, plan_step_id=context["plan_step_id"],
            memory_scope_id=context["memory_scope_id"], candidate=learning_candidate, now=now,
        )
        structured_parts.append(("tool_result", {
            "tool_name": "gyo_learning_worker", "status": enqueue_result,
            "summary": "GYO đã đưa đề xuất học vào hàng đợi kiểm soát." if enqueue_result == "queued" else "Đề xuất học trùng lặp nên không được tạo thêm.",
        }))
    await _write_assistant_parts(
        conn, assistant_id=assistant_id, part_type=part_type, text=text,
        source_parts=source_parts, structured_parts=structured_parts, now=now,
    )
    return assistant_id


async def _write_assistant_parts(
    conn: aiosqlite.Connection,
    *,
    assistant_id: str,
    part_type: str,
    text: str,
    source_parts: list[dict[str, Any]],
    structured_parts: list[tuple[str, dict[str, Any]]],
    now: int,
) -> None:
    await conn.execute(
        "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, ?, ?, 0, ?)",
        (str(uuid.uuid4()), assistant_id, part_type, json.dumps({"text": text, "message": text}), now),
    )
    for index, source in enumerate(source_parts, start=1):
        await conn.execute(
            "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'source', ?, ?, ?)",
            (str(uuid.uuid4()), assistant_id, json.dumps(source), index, now),
        )
    for index, (extra_type, content) in enumerate(structured_parts, start=1 + len(source_parts)):
        await conn.execute(
            "INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), assistant_id, extra_type, json.dumps(content), index, now),
        )


async def _run_read_only_turn(
    *,
    assistant_id: str,
    thread_id: str,
    user_turn_id: str | None = None,
    work_id: str | None,
    conversation_id: str | None,
    prompt: str,
    gyo_orchestrator: Any,
    settings: Settings,
    attachment_artifact_ids: list[str] | None = None,
    model_profile_id: str | None = None,
    route_mode: str = "auto",
) -> None:
    """Complete an already-persisted Assistant turn outside its HTTP request.

    The Event Bus channel is deliberately thread-scoped, so an Assistant answer
    cannot leak tokens into the older Work task stream.
    """
    channel = f"assistant:{thread_id}"
    failed = False
    try:
        async with get_db_connection(settings.db_path_resolved) as conn:
            now = int(time.time())
            context = await _turn_context(conn, user_turn_id) if user_turn_id else {
                "plan_step_id": None, "memory_scope_id": None, "context_mode": "suggest_only", "auto_learning_enabled": 0,
            }
            status_value, model_id, part_type, text, source_parts, structured_parts, run_metadata, learning_candidate = await _read_only_response(
                conn, work_id, prompt, gyo_orchestrator, conversation_id=conversation_id, event_channel=channel,
                assistant_turn_id=assistant_id,
                attachment_artifact_ids=attachment_artifact_ids or [],
                model_profile_id=model_profile_id,
                route_mode=route_mode,
                plan_step_id=context["plan_step_id"],
                memory_scope_id=context["memory_scope_id"],
                memory_context_mode=context["context_mode"],
                auto_learning_enabled=bool(context["auto_learning_enabled"]),
            )
            update = await conn.execute(
                "UPDATE assistant_turns SET status = ?, model_id = ?, completed_at = ?, error = ? WHERE id = ? AND status = 'running'",
                (status_value, model_id, now, text if status_value == "failed" else None, assistant_id),
            )
            completed = update.rowcount == 1
            if completed:
                if user_turn_id:
                    await _copy_turn_context(conn, user_turn_id, assistant_id)
                await _write_run_metadata(conn, assistant_turn_id=assistant_id, metadata=run_metadata, now=now)
                if learning_candidate is not None and work_id and context["plan_step_id"] and context["memory_scope_id"]:
                    enqueue_result = await enqueue_learning_job(
                        conn, assistant_turn_id=assistant_id, work_id=work_id,
                        plan_step_id=context["plan_step_id"], memory_scope_id=context["memory_scope_id"],
                        candidate=learning_candidate, now=now,
                    )
                    structured_parts.append(("tool_result", {
                        "tool_name": "gyo_learning_worker", "status": enqueue_result,
                        "summary": "GYO đã đưa đề xuất học vào hàng đợi kiểm soát." if enqueue_result == "queued" else "Đề xuất học trùng lặp nên không được tạo thêm.",
                    }))
                await _write_assistant_parts(
                    conn,
                    assistant_id=assistant_id,
                    part_type=part_type,
                    text=text,
                    source_parts=source_parts,
                    structured_parts=structured_parts,
                    now=now,
                )
                await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            elif run_metadata:
                # A user cancellation wins over late output, but the selected
                # model provenance is still useful and contains no model text.
                async with conn.execute("SELECT status FROM assistant_turns WHERE id = ?", (assistant_id,)) as cur:
                    current = await cur.fetchone()
                if current is not None and current["status"] == "cancelled":
                    # The terminal has now identified routing, but user
                    # cancellation remains the authoritative outcome. Persist
                    # only that safe provenance; no late text or parts survive.
                    cancelled_metadata = dict(run_metadata)
                    cancelled_metadata["fallback_chain"] = [{
                        "provider_profile_id": run_metadata.get("provider_profile_id"),
                        "model_profile_id": run_metadata.get("model_profile_id"),
                        "outcome": "cancelled",
                    }]
                    await _write_run_metadata(conn, assistant_turn_id=assistant_id, metadata=cancelled_metadata, now=now)
            await conn.commit()
        if not completed:
            return
        if status_value == "failed":
            await event_bus.publish(channel, SseErrorEvent(message=text, assistant_turn_id=assistant_id, thread_id=thread_id))
        else:
            await event_bus.publish(
                channel,
                SseDoneEvent(
                    assistant_turn_id=assistant_id,
                    thread_id=thread_id,
                    routing={
                        "provider_profile_id": run_metadata.get("provider_profile_id"),
                        "model_profile_id": run_metadata.get("model_profile_id"),
                        "route_mode": run_metadata.get("route_mode"),
                        "selection_reason": run_metadata.get("selection_reason"),
                        "attempts": run_metadata.get("fallback_chain", []),
                    } if run_metadata else None,
                ),
            )
    except Exception:
        # Do not expose raw exception details. Persist a visible, user-safe part.
        failure_text = "Trợ lý GYO không thể hoàn tất yêu cầu này. Không có thay đổi nào được thực hiện."
        async with get_db_connection(settings.db_path_resolved) as conn:
            now = int(time.time())
            update = await conn.execute(
                "UPDATE assistant_turns SET status = 'failed', completed_at = ?, error = ? WHERE id = ? AND status = 'running'",
                (now, failure_text, assistant_id),
            )
            failed = update.rowcount == 1
            if failed:
                await _write_assistant_parts(
                    conn, assistant_id=assistant_id, part_type="error", text=failure_text, source_parts=[], structured_parts=[], now=now,
                )
            await conn.commit()
        if failed:
            await event_bus.publish(channel, SseErrorEvent(message=failure_text, assistant_turn_id=assistant_id, thread_id=thread_id))


def _encode_history_cursor(*, pinned_at: int | None, updated_at: int, thread_id: str) -> str:
    payload = {"v": _HISTORY_CURSOR_VERSION, "p": pinned_at or 0, "u": updated_at, "i": thread_id}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_history_cursor(cursor: str) -> dict[str, Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if (
            not isinstance(value, dict)
            or value.get("v") != _HISTORY_CURSOR_VERSION
            or not isinstance(value.get("p"), int)
            or not isinstance(value.get("u"), int)
            or not isinstance(value.get("i"), str)
            or not value["i"]
        ):
            raise ValueError
        return value
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid history cursor") from exc


async def _history_thread(conn: aiosqlite.Connection, work_id: str, thread_id: str) -> aiosqlite.Row:
    async with conn.execute(
        "SELECT * FROM assistant_threads WHERE id = ? AND work_id = ?", (thread_id, work_id)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Assistant history item not found in selected Work")
    return row


async def _assert_history_work(conn: aiosqlite.Connection, work_id: str, *, mutable: bool = False) -> None:
    async with conn.execute("SELECT archived FROM sessions WHERE id = ?", (work_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Work not found")
    if mutable and row["archived"]:
        raise HTTPException(status_code=409, detail="Work is archived")


@router.get("/works/{work_id}/history", response_model=AssistantHistoryPageResponse)
async def list_work_history(
    work_id: str,
    cursor: str | None = None,
    limit: int = 25,
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> AssistantHistoryPageResponse:
    """Work-scoped, opaque-cursor GYO history.

    Search deliberately scans only rendered text/artifact parts, never model
    tool payloads, action proposals, audit records, or internal routing data.
    """
    del actor  # trusted-actor dependency is the local fail-closed boundary.
    await _assert_history_work(conn, work_id)
    if status_filter is not None and status_filter not in {"active", "archived"}:
        raise HTTPException(status_code=422, detail="History status must be active or archived")
    limit = max(1, min(limit, 100))
    params: list[Any] = [work_id]
    where = ["thread.work_id = ?"]
    if status_filter:
        where.append("thread.status = ?")
        params.append(status_filter)
    elif not include_archived:
        where.append("thread.status = 'active'")
    if q is not None:
        needle = " ".join(q.split())
        if len(needle) > 160:
            raise HTTPException(status_code=422, detail="History search is too long")
        if needle:
            where.append(
                "(LOWER(thread.title) LIKE ? OR EXISTS ("
                "SELECT 1 FROM assistant_turns turn JOIN assistant_turn_parts part ON part.turn_id = turn.id "
                "WHERE turn.thread_id = thread.id AND part.part_type IN ('text', 'artifact') "
                "AND LOWER(part.content_json) LIKE ?))"
            )
            pattern = f"%{needle.lower()}%"
            params.extend([pattern, pattern])
    if cursor:
        decoded = _decode_history_cursor(cursor)
        where.append(
            "(COALESCE(thread.pinned_at, 0) < ? OR "
            "(COALESCE(thread.pinned_at, 0) = ? AND thread.updated_at < ?) OR "
            "(COALESCE(thread.pinned_at, 0) = ? AND thread.updated_at = ? AND thread.id < ?))"
        )
        params.extend([decoded["p"], decoded["p"], decoded["u"], decoded["p"], decoded["u"], decoded["i"]])
    query = (
        "SELECT thread.* FROM assistant_threads thread WHERE " + " AND ".join(where)
        + " ORDER BY COALESCE(thread.pinned_at, 0) DESC, thread.updated_at DESC, thread.id DESC LIMIT ?"
    )
    params.append(limit + 1)
    async with conn.execute(query, params) as cur:
        rows = await cur.fetchall()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = _encode_history_cursor(
            pinned_at=last["pinned_at"], updated_at=last["updated_at"], thread_id=last["id"]
        )
    return AssistantHistoryPageResponse(
        items=[AssistantThreadResponse(**dict(row)) for row in page],
        next_cursor=next_cursor,
    )


@router.patch("/works/{work_id}/history/{thread_id}", response_model=AssistantThreadResponse)
async def update_work_history(
    work_id: str,
    thread_id: str,
    request: AssistantHistoryUpdateRequest,
    actor: str = Depends(get_trusted_actor),
    conn: aiosqlite.Connection = Depends(get_db),
) -> AssistantThreadResponse:
    """Pin/archive/reopen one Work-scoped thread with idempotent setters."""
    await _assert_history_work(conn, work_id, mutable=True)
    if not request.model_fields_set:
        raise HTTPException(status_code=422, detail="Choose a history action")
    thread = await _history_thread(conn, work_id, thread_id)
    if request.archived is True:
        async with conn.execute(
            "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
            (thread_id,),
        ) as cur:
            if await cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="Cannot archive an Assistant thread while GYO is responding")
    updates: list[str] = []
    values: list[Any] = []
    if request.pinned is not None:
        updates.append("pinned_at = ?")
        values.append(int(time.time()) if request.pinned else None)
    if request.archived is not None:
        updates.append("status = ?")
        values.append("archived" if request.archived else "active")
    now = int(time.time())
    updates.append("updated_at = ?")
    values.extend([now, thread_id, work_id])
    await conn.execute(
        f"UPDATE assistant_threads SET {', '.join(updates)} WHERE id = ? AND work_id = ?", values
    )
    await log_audit_event(
        conn, work_id, actor, "assistant.history.updated", target=thread_id,
        payload={"pinned": request.pinned, "archived": request.archived}, commit=False,
    )
    await conn.commit()
    return AssistantThreadResponse(**dict(await _history_thread(conn, work_id, thread_id)))


@router.get("/threads", response_model=list[AssistantThreadResponse])
async def list_threads(
    include_archived: bool = False,
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[AssistantThreadResponse]:
    query = "SELECT * FROM assistant_threads"
    if not include_archived:
        query += " WHERE status = 'active'"
    query += " ORDER BY updated_at DESC"
    async with conn.execute(query) as cur:
        rows = await cur.fetchall()
    return [AssistantThreadResponse(**dict(row)) for row in rows]


@router.post("/threads", response_model=AssistantThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    request: AssistantThreadCreateRequest, conn: aiosqlite.Connection = Depends(get_db)
) -> AssistantThreadResponse:
    if request.work_id is not None or request.conversation_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Work-scoped Assistant threads must use the Work and Conversation resolver",
        )
    now = int(time.time())
    thread_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO assistant_threads (id, title, work_id, conversation_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (thread_id, request.title, request.work_id, request.conversation_id, now, now),
    )
    await conn.commit()
    return AssistantThreadResponse(
        id=thread_id,
        title=request.title,
        work_id=request.work_id,
        conversation_id=request.conversation_id,
        status="active",
        created_at=now,
        updated_at=now,
    )


@router.post(
    "/works/{work_id}/conversations/{conversation_id}/assistant-thread",
    response_model=AssistantThreadResponse,
)
async def create_thread_bound(
    work_id: str,
    conversation_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
) -> AssistantThreadResponse:
    """Atomically resolve one active GYO thread for one active Work conversation."""
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await _assert_work(conn, work_id)
        await _assert_active_conversation(conn, work_id=work_id, conversation_id=conversation_id)
        async with conn.execute(
            "SELECT * FROM assistant_threads WHERE work_id = ? AND conversation_id = ? AND status = 'active'",
            (work_id, conversation_id),
        ) as cur:
            thread = await cur.fetchone()
        outcome = "reused"
        if thread is None:
            now = int(time.time())
            thread_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO assistant_threads (id, title, work_id, conversation_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, "GYO Thread", work_id, conversation_id, now, now),
            )
            async with conn.execute("SELECT * FROM assistant_threads WHERE id = ?", (thread_id,)) as cur:
                thread = await cur.fetchone()
            outcome = "created"
        await log_audit_event(
            conn, work_id, "user", "assistant.thread.resolve", target=thread["id"],
            payload={"scope": "work_conversation", "outcome": outcome}, commit=False,
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return AssistantThreadResponse(**dict(thread))
@router.patch("/threads/{thread_id}", response_model=AssistantThreadResponse)
async def update_thread(
    thread_id: str, request: AssistantThreadUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)
) -> AssistantThreadResponse:
    current = await _thread(conn, thread_id)
    updates: list[str] = []
    values: list[Any] = []
    if request.title is not None:
        title = " ".join(request.title.split())
        if not title:
            raise HTTPException(status_code=422, detail="Thread title cannot be empty")
        updates.append("title = ?")
        values.append(title)
    if request.archived is not None:
        if request.archived:
            async with conn.execute(
                "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
                (thread_id,),
            ) as cur:
                if await cur.fetchone() is not None:
                    raise HTTPException(status_code=409, detail="Cannot archive an Assistant thread while GYO is responding")
        updates.append("status = ?")
        values.append("archived" if request.archived else "active")
    if updates:
        now = int(time.time())
        updates.append("updated_at = ?")
        values.extend([now, thread_id])
        await conn.execute(f"UPDATE assistant_threads SET {', '.join(updates)} WHERE id = ?", values)
        await conn.commit()
        current = await _thread(conn, thread_id)
    return AssistantThreadResponse(**dict(current))


@router.get("/threads/{thread_id}/turns", response_model=list[AssistantTurnResponse])
async def list_turns(thread_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> list[AssistantTurnResponse]:
    await _thread(conn, thread_id)
    async with conn.execute(
        "SELECT * FROM assistant_turns WHERE thread_id = ? ORDER BY created_at, rowid", (thread_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [await _turn(conn, row) for row in rows]


@router.post("/threads/{thread_id}/turns", response_model=list[AssistantTurnResponse])
async def create_turn(
    thread_id: str,
    request: AssistantTurnCreateRequest,
    http_request: Request,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[AssistantTurnResponse]:
    thread = await _thread(conn, thread_id)
    if thread["status"] != "active":
        raise HTTPException(status_code=409, detail="Assistant thread is archived")

    work_id, conversation_id = await _bound_thread_scope(conn, thread, request)
    async with conn.execute(
        "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
        (thread_id,),
    ) as cur:
        if await cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="GYO is already responding in this thread")
    attachments = await _validated_attachments(conn, work_id, request.attachment_artifact_ids)

    now = int(time.time())
    user_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, created_at, completed_at) VALUES (?, ?, ?, ?, 'user', 'completed', ?, ?)",
        (user_id, thread_id, work_id, conversation_id, now, now),
    )
    await _insert_user_parts(conn, turn_id=user_id, prompt=request.prompt, attachments=attachments, now=now)
    await _insert_turn_context(conn, user_turn_id=user_id, work_id=work_id, plan_step_id=request.plan_step_id, now=now)

    assistant_id = await _insert_assistant_response(
        conn,
        thread_id=thread_id,
        user_turn_id=user_id,
        work_id=work_id,
        conversation_id=conversation_id,
        prompt=request.prompt,
        http_request=http_request,
        attachment_artifact_ids=request.attachment_artifact_ids,
        model_profile_id=request.model_profile_id,
        route_mode=request.route_mode,
    )
    await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
    await conn.commit()
    async with conn.execute(
        "SELECT * FROM assistant_turns WHERE id IN (?, ?) ORDER BY created_at, rowid", (user_id, assistant_id)
    ) as cur:
        rows = await cur.fetchall()
    return [await _turn(conn, row) for row in rows]


@router.post("/threads/{thread_id}/runs", response_model=list[AssistantTurnResponse], status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    thread_id: str,
    request: AssistantTurnCreateRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[AssistantTurnResponse]:
    """Persist a read-only turn and run it after the response is returned.

    This is separate from the compatible synchronous /turns endpoint. Clients
    may subscribe to /stream before or immediately after calling this route.
    """
    thread = await _thread(conn, thread_id)
    if thread["status"] != "active":
        raise HTTPException(status_code=409, detail="Assistant thread is archived")
    work_id, conversation_id = await _bound_thread_scope(conn, thread, request)
    async with conn.execute(
        "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
        (thread_id,),
    ) as cur:
        if await cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="GYO is already responding in this thread")
    attachments = await _validated_attachments(conn, work_id, request.attachment_artifact_ids)

    now = int(time.time())
    user_id, assistant_id = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, created_at, completed_at) VALUES (?, ?, ?, ?, 'user', 'completed', ?, ?)",
        (user_id, thread_id, work_id, conversation_id, now, now),
    )
    await _insert_user_parts(conn, turn_id=user_id, prompt=request.prompt, attachments=attachments, now=now)
    await _insert_turn_context(conn, user_turn_id=user_id, work_id=work_id, plan_step_id=request.plan_step_id, now=now)
    await conn.execute(
        "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)",
        (assistant_id, thread_id, work_id, conversation_id, now),
    )
    await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
    await conn.commit()

    background_tasks.add_task(
        _run_read_only_turn,
        assistant_id=assistant_id,
        thread_id=thread_id,
        user_turn_id=user_id,
        work_id=work_id,
        conversation_id=conversation_id,
        prompt=request.prompt,
        gyo_orchestrator=getattr(http_request.app.state, "gyo_orchestrator", None),
        settings=settings,
        attachment_artifact_ids=request.attachment_artifact_ids,
        model_profile_id=request.model_profile_id,
        route_mode=request.route_mode,
    )
    async with conn.execute("SELECT * FROM assistant_turns WHERE id IN (?, ?) ORDER BY created_at, rowid", (user_id, assistant_id)) as cur:
        rows = await cur.fetchall()
    return [await _turn(conn, row) for row in rows]


@router.get("/threads/{thread_id}/stream")
async def thread_stream(thread_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> EventSourceResponse:
    """Stream visible read-only Assistant updates for one thread only."""
    await _thread(conn, thread_id)
    channel = f"assistant:{thread_id}"
    if event_bus.has_subscriber(channel):
        raise HTTPException(status_code=409, detail="Assistant thread already has an active stream")

    async def event_generator():
        async for event in event_bus.subscribe(channel):
            yield ServerSentEvent(event=event.type, data=event.model_dump_json())

    return EventSourceResponse(event_generator())


@router.post("/turns/{turn_id}/retry", response_model=AssistantTurnResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_turn(
    turn_id: str,
    http_request: Request,
    background_tasks: BackgroundTasks,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    request: AssistantRetryRequest | None = None,
) -> AssistantTurnResponse:
    """Retry a failed Assistant answer without inserting the user's prompt twice."""
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
        "SELECT 1 FROM assistant_turns WHERE thread_id = ? AND role = 'assistant' AND status = 'running' LIMIT 1",
        (failed_turn["thread_id"],),
    ) as cur:
        if await cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail="GYO is already responding in this thread")

    async with conn.execute(
        """
        SELECT user_turn.id AS user_turn_id, part.content_json
        FROM assistant_turns AS user_turn
        JOIN assistant_turn_parts AS part ON part.turn_id = user_turn.id
        WHERE user_turn.thread_id = ?
          AND user_turn.role = 'user'
          AND user_turn.rowid < ?
          AND part.part_type = 'text'
        ORDER BY user_turn.rowid DESC, part.sort_order ASC
        LIMIT 1
        """,
        (failed_turn["thread_id"], failed_turn["sequence"]),
    ) as cur:
        prompt_row = await cur.fetchone()
    if prompt_row is None:
        raise HTTPException(status_code=409, detail="Original user prompt is unavailable")
    prompt = json.loads(prompt_row["content_json"]).get("text")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=409, detail="Original user prompt is unavailable")
    async with conn.execute(
        "SELECT content_json FROM assistant_turn_parts WHERE turn_id = ? AND part_type = 'artifact' ORDER BY sort_order",
        (prompt_row["user_turn_id"],),
    ) as cur:
        attachment_rows = await cur.fetchall()
    attachment_ids = [
        content["artifact_id"]
        for row in attachment_rows
        if isinstance((content := json.loads(row["content_json"])).get("artifact_id"), str)
    ]
    await _validated_attachments(conn, failed_turn["work_id"], attachment_ids)

    retry_mode = request.mode if request is not None else "same_model"
    retry_model_id: str | None = None
    if retry_mode == "same_model":
        async with conn.execute(
            """SELECT metadata.model_profile_id
               FROM assistant_run_metadata AS metadata
               JOIN ai_model_profiles AS model ON model.id = metadata.model_profile_id
               JOIN ai_provider_profiles AS provider ON provider.id = model.provider_profile_id
               WHERE metadata.assistant_turn_id = ? AND model.enabled = 1 AND model.retired_at IS NULL
                 AND provider.enabled = 1 AND provider.retired_at IS NULL""",
            (turn_id,),
        ) as cur:
            retry_model = await cur.fetchone()
        if retry_model is None or not retry_model["model_profile_id"]:
            raise HTTPException(status_code=409, detail="Model của lượt trước không còn sẵn sàng; hãy dùng Thử lại tự động")
        retry_model_id = retry_model["model_profile_id"]

    assistant_id = str(uuid.uuid4())
    now = int(time.time())
    await conn.execute(
        "INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) "
        "VALUES (?, ?, ?, ?, 'assistant', 'running', 'gyo', ?)",
        (assistant_id, failed_turn["thread_id"], failed_turn["work_id"], failed_turn["conversation_id"], now),
    )
    await conn.execute("UPDATE assistant_threads SET updated_at = ? WHERE id = ?", (now, failed_turn["thread_id"]))
    await conn.commit()
    background_tasks.add_task(
        _run_read_only_turn,
        assistant_id=assistant_id,
        thread_id=failed_turn["thread_id"],
        user_turn_id=prompt_row["user_turn_id"],
        work_id=failed_turn["work_id"],
        conversation_id=failed_turn["conversation_id"],
        prompt=prompt,
        gyo_orchestrator=getattr(http_request.app.state, "gyo_orchestrator", None),
        settings=settings,
        attachment_artifact_ids=attachment_ids,
        # The user prompt, attachments and frozen context remain immutable.
        model_profile_id=retry_model_id,
        route_mode="manual" if retry_mode == "same_model" else "auto",
    )
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (assistant_id,)) as cur:
        created = await cur.fetchone()
    return await _turn(conn, created)


@router.post("/turns/{turn_id}/cancel", response_model=AssistantTurnResponse)
async def cancel_turn(
    turn_id: str,
    http_request: Request,
    conn: aiosqlite.Connection = Depends(get_db),
) -> AssistantTurnResponse:
    """Make a running Assistant answer terminal and discard any late response.

    Durable state remains authoritative.  GYO cancellation is best-effort;
    any late model output is still ignored by the guarded completion update.
    """
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
        "user",
        "assistant.turn.cancelled",
        target=turn_id,
        payload={"thread_id": running_turn["thread_id"]},
        commit=False,
    )
    await conn.commit()
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
        cancelled_metadata["fallback_chain"] = [{
            "provider_profile_id": routing_metadata.get("provider_profile_id"),
            "model_profile_id": routing_metadata.get("model_profile_id"),
            "outcome": "cancelled",
        }]
        await _write_run_metadata(conn, assistant_turn_id=turn_id, metadata=cancelled_metadata, now=now)
    await log_audit_event(
        conn,
        running_turn["work_id"],
        "system",
        "assistant.turn.cancel_compute",
        target=turn_id,
        payload={"outcome": cancel_outcome},
    )
    await event_bus.publish(
        f"assistant:{running_turn['thread_id']}",
        SseDoneEvent(assistant_turn_id=turn_id, thread_id=running_turn["thread_id"]),
    )
    async with conn.execute("SELECT * FROM assistant_turns WHERE id = ?", (turn_id,)) as cur:
        cancelled = await cur.fetchone()
    return await _turn(conn, cancelled)


@router.get("/context-manifest", response_model=AssistantContextManifestResponse)
async def context_manifest(
    work_id: str | None = None,
    conversation_id: str | None = None,
    plan_step_id: str | None = None,
    turn_id: str | None = None,
    package_id: str | None = None,
    conn: aiosqlite.Connection = Depends(get_db),
) -> AssistantContextManifestResponse:
    excluded: list[dict[str, Any]] = [
        {"kind": "memory_hub", "reason": "Không tự động đưa vào chat"},
        {"kind": "raw_audit", "reason": "Chỉ có trong chẩn đoán nâng cao"},
    ]
    if not work_id:
        return AssistantContextManifestResponse(
            work_id=None,
            conversation_id=None,
            included=[],
            excluded=excluded,
            byte_limit=12_000,
            byte_count=0,
            plan_step_id=None,
        )
    await _assert_work(conn, work_id)
    if conversation_id:
        await _assert_active_conversation(conn, work_id=work_id, conversation_id=conversation_id)
    used: list[dict[str, Any]] = []
    if turn_id:
        async with conn.execute(
            """SELECT id, work_id, conversation_id, role, status FROM assistant_turns
               WHERE id = ?""", (turn_id,)
        ) as cur:
            turn = await cur.fetchone()
        if (
            turn is None or turn["work_id"] != work_id
            or (conversation_id is not None and turn["conversation_id"] != conversation_id)
            or turn["role"] != "assistant" or turn["status"] != "completed"
        ):
            raise HTTPException(status_code=404, detail="Assistant turn is unavailable in selected Work")
        async with conn.execute(
            "SELECT content_json FROM assistant_turn_parts WHERE turn_id = ? AND part_type = 'source' ORDER BY sort_order",
            (turn_id,),
        ) as cur:
            source_rows = await cur.fetchall()
        for row in source_rows:
            try:
                source = json.loads(row["content_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(source, dict):
                continue
            used.append({
                "kind": source.get("kind", "source"), "id": source.get("id"),
                "title": source.get("title", "Nguồn trong câu trả lời"),
                "reason": source.get("reason", "GYO đã trích nguồn trong câu trả lời"),
            })
    targeted: list[dict[str, Any]] = []
    if package_id:
        async with conn.execute(
            "SELECT session_id, conversation_id, resolved_payload_json FROM action_packages WHERE id = ?",
            (package_id,),
        ) as cur:
            package = await cur.fetchone()
        if (
            package is None or package["session_id"] != work_id
            or (conversation_id is not None and package["conversation_id"] != conversation_id)
        ):
            raise HTTPException(status_code=404, detail="Action package is unavailable in selected Work")
        try:
            payload = json.loads(package["resolved_payload_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            raise HTTPException(status_code=409, detail="Action package payload is invalid")
        if isinstance(payload, dict):
            values = payload.get("targets", [])
            if isinstance(values, list):
                targeted.extend(item for item in values if isinstance(item, dict))
            sources = payload.get("context_snapshot", {}).get("sources", [])
            if isinstance(sources, list):
                targeted.extend(
                    {"kind": "artifact", "id": item.get("artifact_id"), "sha256": item.get("sha256"), "reason": "Đầu vào của Action Package"}
                    for item in sources if isinstance(item, dict) and item.get("artifact_id")
                )
    try:
        scope = WorkMemoryScope(None, work_id, "", "suggest_only", False)
        if plan_step_id:
            scope = await get_work_memory_scope(conn, work_id, plan_step_id)
        pack = await AssistantContextPackBuilder(conn).build(
            work_id, conversation_id, memory_mode=scope.context_mode,
            memory_project_id=work_id if scope.id else None, memory_scope_id=scope.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    accessible: list[dict[str, Any]] = [{"kind": "work", "id": work_id, "reason": "Công việc đang chọn"}]
    if conversation_id:
        accessible.append({"kind": "conversation", "id": conversation_id, "reason": "Phiên trao đổi đang chọn"})
    async with conn.execute(
        """SELECT artifact.id, artifact.relative_path, artifact.sha256
           FROM artifacts artifact JOIN artifact_validations validation ON validation.artifact_id = artifact.id
           WHERE artifact.session_id = ? AND validation.status = 'structurally_validated'
           ORDER BY artifact.created_at DESC, artifact.id LIMIT 20""",
        (work_id,),
    ) as cur:
        for artifact in await cur.fetchall():
            accessible.append({
                "kind": "artifact", "id": artifact["id"],
                "title": PurePosixPath(artifact["relative_path"]).name,
                "sha256": artifact["sha256"], "reason": "Tệp Work đã qua kiểm tra cấu trúc",
            })
    return AssistantContextManifestResponse(
        work_id=work_id,
        conversation_id=conversation_id,
        included=pack.included,
        excluded=pack.excluded,
        accessible=accessible,
        retrieved=pack.included,
        used=used,
        targeted=targeted,
        turn_id=turn_id,
        package_id=package_id,
        byte_limit=pack.byte_limit,
        byte_count=pack.byte_count,
        version=pack.version,
        generated_at=pack.generated_at,
        from_message_id=pack.from_message_id,
        through_message_id=pack.through_message_id,
        plan_step_id=plan_step_id,
        memory_context_mode=scope.context_mode,
        auto_learning_enabled=scope.auto_learning_enabled,
        memory_hub_auto_injected=scope.context_mode == "active_work_memory" and scope.id is not None,
    )
