"""Deterministic, read-only context selection for the Workspace Assistant.

The builder is the single policy boundary for Assistant context.  It only
selects registered Work data, never reads an arbitrary path, and deliberately
keeps Memory Hub outside automatic chat context unless an explicit, scoped
``active_work_memory`` selection is supplied by the caller.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import aiosqlite


CONTEXT_BYTE_LIMIT = 12_000
# GYO P0 accepts only structurally validated plain-text inputs.  Binary
# formats stay in the document library until a separately approved extractor
# or multimodal adapter can provide a safe, attributable representation.
_TEXT_SUFFIXES = {".md", ".txt", ".csv"}
MEMORY_MODES = {"off", "suggest_only", "active_work_memory"}


@dataclass(frozen=True)
class AssistantContextPack:
    text: str
    included: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    byte_limit: int
    byte_count: int
    version: str
    generated_at: int
    from_message_id: str | None = None
    through_message_id: str | None = None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fit_utf8(value: str, byte_limit: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= byte_limit:
        return value, False
    if byte_limit <= 0:
        return "", True
    clipped = encoded[:byte_limit]
    while clipped:
        try:
            return clipped.decode("utf-8").rstrip(), True
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return "", True


class AssistantContextPackBuilder:
    """Build a deterministic context pack in the product-defined priority."""

    def __init__(self, conn: aiosqlite.Connection, *, byte_limit: int = CONTEXT_BYTE_LIMIT) -> None:
        self.conn = conn
        self.byte_limit = byte_limit

    async def build(
        self,
        work_id: str,
        conversation_id: str | None = None,
        attachment_artifact_ids: list[str] | None = None,
        *,
        memory_mode: str = "suggest_only",
        memory_project_id: str | None = None,
        memory_task_id: str | None = None,
        memory_scope_id: str | None = None,
    ) -> AssistantContextPack:
        if memory_mode not in MEMORY_MODES:
            raise ValueError("Unknown Memory Hub context mode")
        async with self.conn.execute(
            "SELECT id, title, goal, work_status, progress_percent, data_scope, workspace_path "
            "FROM sessions WHERE id = ? AND archived = 0",
            (work_id,),
        ) as cur:
            work = await cur.fetchone()
        if work is None:
            raise ValueError("Work not found or archived")

        generated_at = int(time.time())
        included: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = [{"kind": "raw_audit", "reason": "Chỉ có trong chẩn đoán nâng cao"}]
        if memory_mode != "active_work_memory":
            excluded.append({
                "kind": "memory_hub",
                "reason": "Không tự động đưa vào chat" if memory_mode == "suggest_only" else "Đã tắt theo phạm vi Công việc",
                "mode": memory_mode,
            })
        sections: list[str] = []
        remaining = self.byte_limit

        def add_section(kind: str, source_id: str, title: str, reason: str, body: str, source_hash: str | None = None) -> None:
            nonlocal remaining
            rendered = f"## {title}\n{body.strip()}\n"
            fitted, truncated = _fit_utf8(rendered, remaining)
            if not fitted:
                excluded.append({"kind": kind, "id": source_id, "title": title, "reason": "Vượt giới hạn ngữ cảnh"})
                return
            sections.append(fitted)
            used = len(fitted.encode("utf-8"))
            remaining -= used
            included.append({
                "kind": kind,
                "id": source_id,
                "title": title,
                "reason": reason,
                "sha256": source_hash or _sha256_text(body),
                "bytes": used,
                "truncated": truncated,
            })

        async with self.conn.execute(
            "SELECT * FROM work_plan_phases WHERE session_id = ? ORDER BY sort_order, created_at, id",
            (work_id,),
        ) as cur:
            phases = await cur.fetchall()
        plan_lines: list[str] = []
        for phase in phases:
            plan_lines.append(f"- Giai đoạn: {phase['title']} [{phase['status']}]")
            async with self.conn.execute(
                "SELECT title, description, result, status FROM work_plan_steps "
                "WHERE phase_id = ? ORDER BY sort_order, created_at, id",
                (phase["id"],),
            ) as cur:
                for step in await cur.fetchall():
                    detail = step["result"] or step["description"] or ""
                    plan_lines.append(f"  - {step['title']} [{step['status']}]" + (f": {detail}" if detail else ""))
        work_body = (
            f"Mục tiêu: {work['goal'] or 'Chưa đặt'}\n"
            f"Trạng thái: {work['work_status']}\n"
            f"Tiến độ: {work['progress_percent']}%\n"
            f"Kế hoạch:\n" + ("\n".join(plan_lines) if plan_lines else "- Chưa có bước kế hoạch")
        )
        add_section("work", work_id, f"Công việc: {work['title']}", "Công việc đã chọn", work_body)

        # Workspace Tasks are a separate, user-facing domain from legacy plan
        # steps.  They still belong to the selected Work through session_id, so
        # surface a bounded, read-only summary here instead of asking GYO to
        # infer the current task list from a Work title or plan.
        async with self.conn.execute(
            """SELECT id, title, description, status, priority, impact, due_at,
                      estimate_minutes, ai_eligibility, blocked_reason
               FROM workspace_tasks WHERE session_id = ?
               ORDER BY CASE status
                   WHEN 'in_progress' THEN 0 WHEN 'ready' THEN 1
                   WHEN 'planned' THEN 2 WHEN 'waiting' THEN 3
                   WHEN 'blocked' THEN 4 WHEN 'done' THEN 5 ELSE 6 END,
                   priority DESC, impact DESC, due_at IS NULL, due_at, updated_at DESC, id
               LIMIT 30""",
            (work_id,),
        ) as cur:
            workspace_tasks = await cur.fetchall()
        task_lines: list[str] = []
        for task in workspace_tasks:
            metadata = [
                f"trạng thái: {task['status']}",
                f"ưu tiên: {task['priority']}",
                f"tác động: {task['impact']}",
                f"GYO: {task['ai_eligibility']}",
            ]
            if task["due_at"] is not None:
                metadata.append(f"hạn: {time.strftime('%Y-%m-%d %H:%M', time.localtime(task['due_at']))}")
            if task["estimate_minutes"] is not None:
                metadata.append(f"ước lượng: {task['estimate_minutes']} phút")
            if task["blocked_reason"]:
                metadata.append(f"vướng mắc: {task['blocked_reason']}")
            description = (task["description"] or "").strip()
            if description:
                description = description[:500].rstrip() + ("…" if len(description) > 500 else "")
            task_lines.append(
                f"- {task['title']} ({'; '.join(metadata)})"
                + (f": {description}" if description else "")
            )
        task_body = "\n".join(task_lines) if task_lines else "- Chưa có việc Workspace nào trong Công việc này"
        add_section(
            "workspace_tasks",
            work_id,
            "Danh sách việc Workspace",
            "Việc Workspace thuộc Công việc đang chọn",
            task_body,
        )

        from_message_id: str | None = None
        through_message_id: str | None = None
        if conversation_id:
            async with self.conn.execute(
                "SELECT title FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (conversation_id, work_id),
            ) as cur:
                conversation = await cur.fetchone()
            if conversation is None:
                raise ValueError("Conversation not found in selected Work")
            async with self.conn.execute(
                "SELECT id, role, content FROM chat_messages WHERE conversation_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 24",
                (conversation_id,),
            ) as cur:
                messages = list(reversed(await cur.fetchall()))
            if messages:
                from_message_id, through_message_id = messages[0]["id"], messages[-1]["id"]
                transcript = "\n".join(
                    f"{('Bạn' if message['role'] == 'user' else 'Hermes')}: {message['content']}"
                    for message in messages
                )
                add_section(
                    "conversation", conversation_id, f"Trao đổi: {conversation['title']}",
                    "24 tin nhắn gần nhất của phiên đã chọn", transcript,
                )

        workspace = Path(work["workspace_path"]).resolve()
        async with self.conn.execute(
            """SELECT artifact.id, artifact.relative_path, artifact.sha256, artifact.size_bytes,
                      COALESCE(validation.status, 'pending') AS validation_status
               FROM artifacts artifact LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
               WHERE artifact.session_id = ? ORDER BY artifact.created_at DESC, artifact.id LIMIT 20""",
            (work_id,),
        ) as cur:
            all_artifacts = await cur.fetchall()
        selected_ids = attachment_artifact_ids or []
        by_id = {artifact["id"]: artifact for artifact in all_artifacts}
        missing_selected_ids = [artifact_id for artifact_id in selected_ids if artifact_id not in by_id]
        if missing_selected_ids:
            placeholders = ", ".join("?" for _ in missing_selected_ids)
            async with self.conn.execute(
                f"""SELECT artifact.id, artifact.relative_path, artifact.sha256, artifact.size_bytes,
                           COALESCE(validation.status, 'pending') AS validation_status
                    FROM artifacts artifact LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
                    WHERE artifact.session_id = ? AND artifact.id IN ({placeholders})""",
                (work_id, *missing_selected_ids),
            ) as cur:
                by_id.update({artifact["id"]: artifact for artifact in await cur.fetchall()})
        artifacts = [by_id[artifact_id] for artifact_id in selected_ids if artifact_id in by_id]
        artifacts.extend(artifact for artifact in all_artifacts if artifact["id"] not in selected_ids)
        for artifact in artifacts:
            relative = PurePosixPath(artifact["relative_path"])
            if artifact["validation_status"] != "structurally_validated":
                excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Tệp chưa qua kiểm tra cấu trúc"})
                continue
            if not relative.parts or relative.parts[0] not in {"inputs", "outputs"}:
                excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Ngoài managed workspace"})
                continue
            if relative.suffix.lower() not in _TEXT_SUFFIXES:
                excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Định dạng nhị phân không đưa vào chat"})
                continue
            target = (workspace / Path(*relative.parts)).resolve()
            if not target.is_relative_to(workspace) or not target.is_file():
                excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Tệp không còn khả dụng"})
                continue
            try:
                if not artifact["sha256"] or _sha256_file(target) != artifact["sha256"]:
                    excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Tệp đã thay đổi kể từ khi được đăng ký"})
                    continue
                content = target.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                excluded.append({"kind": "artifact", "id": artifact["id"], "title": relative.name, "reason": "Không đọc được dưới dạng UTF-8"})
                continue
            reason = "Tệp đính kèm được người dùng chọn" if artifact["id"] in selected_ids else "Tài liệu đã đăng ký trong Work"
            add_section("artifact", artifact["id"], relative.name, reason, content, artifact["sha256"])

        # Memory Hub is intentionally opt-in per Work.  A caller must supply a
        # task-scoped project/task pair; no global preferences, unscoped items,
        # drafts, or restricted records can reach an assistant context pack.
        if memory_mode == "active_work_memory":
            effective_scope_id = memory_scope_id or memory_task_id
            if memory_project_id != work_id or not effective_scope_id:
                excluded.append({
                    "kind": "memory_hub",
                    "reason": "Cần phạm vi project/task khớp với Công việc đang chọn",
                    "mode": memory_mode,
                })
            else:
                if memory_scope_id:
                    async with self.conn.execute(
                        "SELECT id FROM work_memory_scopes WHERE id = ? AND work_id = ?",
                        (memory_scope_id, work_id),
                    ) as cur:
                        scoped_task = await cur.fetchone()
                else:
                    async with self.conn.execute(
                        "SELECT id FROM tasks WHERE id = ? AND session_id = ?",
                        (memory_task_id, work_id),
                    ) as cur:
                        scoped_task = await cur.fetchone()
                if scoped_task is None:
                    excluded.append({
                        "kind": "memory_hub",
                        "reason": "Task Memory Hub không thuộc Công việc đang chọn",
                        "mode": memory_mode,
                    })
                else:
                    async with self.conn.execute(
                        """SELECT id, memory_key, content, content_sha256, sensitivity
                           FROM memory_hub_records
                           WHERE project_id = ? AND task_id = ?
                             AND lifecycle = 'active'
                             AND kind != 'preference' AND sensitivity != 'restricted'
                           ORDER BY updated_at DESC, id ASC LIMIT 20""",
                        (memory_project_id, effective_scope_id),
                    ) as cur:
                        memories = await cur.fetchall()
                    for memory in memories:
                        add_section(
                            "memory_hub",
                            memory["id"],
                            f"Bộ nhớ đã duyệt: {memory['memory_key']}",
                            "Bộ nhớ active trong phạm vi Work/task đã chọn",
                            memory["content"],
                            memory["content_sha256"],
                        )
                    if not memories:
                        excluded.append({
                            "kind": "memory_hub",
                            "reason": "Không có bộ nhớ active phù hợp với phạm vi Work/task",
                            "mode": memory_mode,
                        })
                    async with self.conn.execute(
                        """SELECT lifecycle, sensitivity, COUNT(*) AS total
                           FROM memory_hub_records
                           WHERE project_id = ? AND task_id = ?
                             AND (lifecycle != 'active' OR kind = 'preference' OR sensitivity = 'restricted')
                           GROUP BY lifecycle, sensitivity, kind""",
                        (memory_project_id, effective_scope_id),
                    ) as cur:
                        omitted_memory = await cur.fetchall()
                    for row in omitted_memory:
                        if row["sensitivity"] == "restricted":
                            reason = "Restricted Memory Hub không được đưa vào chat"
                        elif row["lifecycle"] != "active":
                            reason = "Lifecycle Memory Hub chưa cho phép dùng trong chat"
                        else:
                            reason = "Preference không được tự động đưa vào chat"
                        excluded.append({
                            "kind": "memory_hub",
                            "lifecycle": row["lifecycle"],
                            "sensitivity": row["sensitivity"],
                            "count": row["total"],
                            "reason": reason,
                        })

        if work["data_scope"] == "approved_library":
            async with self.conn.execute(
                """SELECT record.id, record.content, record.source_sha256, record.provenance
                   FROM dirap_knowledge_records record
                   JOIN tasks task ON task.id = record.task_id
                   WHERE task.session_id = ? AND record.status = 'active'
                   ORDER BY record.updated_at DESC, record.id LIMIT 20""",
                (work_id,),
            ) as cur:
                knowledge = await cur.fetchall()
            for record in knowledge:
                add_section(
                    "knowledge", record["id"], "Tri thức đã duyệt", "Bản ghi active có nguồn",
                    record["content"], record["source_sha256"],
                )
            async with self.conn.execute(
                "SELECT id, name, description, content FROM skills "
                "WHERE enabled = 1 AND status = 'approved' ORDER BY name, id LIMIT 10"
            ) as cur:
                skills = await cur.fetchall()
            for skill in skills:
                content = "\n".join(part for part in (skill["description"], skill["content"]) if part)
                add_section("skill", skill["id"], skill["name"], "Kỹ năng đã duyệt và bật", content)
        else:
            excluded.append({"kind": "approved_library", "reason": "Work chỉ dùng dữ liệu của chính nó"})

        async with self.conn.execute(
            """SELECT record.status AS status, COUNT(*) AS total FROM dirap_knowledge_records record
               JOIN tasks task ON task.id = record.task_id
               WHERE task.session_id = ? AND record.status IN ('draft', 'rejected') GROUP BY record.status""",
            (work_id,),
        ) as cur:
            for row in await cur.fetchall():
                excluded.append({"kind": "knowledge", "status": row["status"], "count": row["total"], "reason": "Lifecycle không cho phép dùng trong chat"})

        text = "\n".join(sections).strip()
        version_material = "|".join(
            f"{item['kind']}:{item['id']}:{item['sha256']}:{item['bytes']}:{item['truncated']}" for item in included
        )
        return AssistantContextPack(
            text=text,
            included=included,
            excluded=excluded,
            byte_limit=self.byte_limit,
            byte_count=len(text.encode("utf-8")),
            version=_sha256_text(version_material)[:16],
            generated_at=generated_at,
            from_message_id=from_message_id,
            through_message_id=through_message_id,
        )
