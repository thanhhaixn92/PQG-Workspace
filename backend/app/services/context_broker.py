"""F7 Resource Catalog + Context Broker.

The broker deliberately separates resource discovery from authorization and
ranking:

    discover metadata -> SECURITY FILTER -> deterministic ranking -> hydrate -> pack

Only resources that survive the security filter may reach ranking or content
hydration. Internal locators (workspace paths, relative paths, DB details) are
never serialized to the model-visible/public catalog.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import aiosqlite


CONTEXT_BYTE_LIMIT = 12_000
TEXT_SUFFIXES = frozenset({".md", ".txt", ".csv"})
MEMORY_MODES = frozenset({"off", "suggest_only", "active_work_memory"})
Sensitivity = Literal["public", "internal", "sensitive", "restricted"]
Trust = Literal[
    "canonical_user_data",
    "verified_knowledge",
    "derived_text",
    "external_unverified",
    "agent_generated_draft",
]

SENSITIVITY_CLASSES = frozenset({"public", "internal", "sensitive", "restricted"})
TRUST_CLASSES = frozenset({
    "canonical_user_data",
    "verified_knowledge",
    "derived_text",
    "external_unverified",
    "agent_generated_draft",
})


@dataclass(frozen=True)
class AssistantContextPack:
    text: str
    included: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    accessible: list[dict[str, Any]]
    byte_limit: int
    byte_count: int
    version: str
    generated_at: int
    from_message_id: str | None = None
    through_message_id: str | None = None


@dataclass(frozen=True)
class CatalogResource:
    """Metadata-only resource descriptor.

    ``locator`` is backend-only and may contain path or DB lookup metadata. It
    must never be copied into ``public_metadata`` or provider context.
    """

    kind: str
    resource_id: str
    title: str
    sensitivity: Sensitivity
    trust: Trust
    rank_group: int
    rank_order: int = 0
    selected: bool = False
    source_hash: str | None = None
    locator: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class BrokerScope:
    work_id: str
    conversation_id: str | None
    memory_mode: str
    memory_project_id: str | None
    memory_task_id: str | None
    memory_scope_id: str | None
    data_scope: str
    workspace_path: str


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


def _memory_sensitivity(value: str) -> Sensitivity:
    if value == "restricted":
        return "restricted"
    if value == "sensitive":
        return "sensitive"
    return "internal"


def _public_reason(resource: CatalogResource) -> str:
    if resource.kind == "work":
        return "Công việc đang chọn"
    if resource.kind == "workspace_tasks":
        return "Việc Workspace thuộc Công việc đang chọn"
    if resource.kind == "conversation":
        return "Phiên trao đổi đang chọn"
    if resource.kind == "artifact":
        return "Tệp đính kèm được người dùng chọn" if resource.selected else "Tài liệu Work đủ điều kiện dùng làm ngữ cảnh"
    if resource.kind == "memory_hub":
        return "Bộ nhớ active trong phạm vi Work/task đã chọn"
    if resource.kind == "knowledge":
        return "Tri thức active đã được duyệt và có nguồn"
    if resource.kind == "skill":
        return "Kỹ năng đã duyệt và bật"
    return "Nguồn đã qua Context Broker"


class ContextBroker:
    """F7 policy boundary for model-visible local context."""

    def __init__(self, conn: aiosqlite.Connection, *, byte_limit: int = CONTEXT_BYTE_LIMIT) -> None:
        self.conn = conn
        self.byte_limit = byte_limit

    async def _scope(
        self,
        work_id: str,
        conversation_id: str | None,
        *,
        memory_mode: str,
        memory_project_id: str | None,
        memory_task_id: str | None,
        memory_scope_id: str | None,
    ) -> tuple[aiosqlite.Row, BrokerScope]:
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

        if conversation_id:
            async with self.conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (conversation_id, work_id),
            ) as cur:
                if await cur.fetchone() is None:
                    raise ValueError("Conversation not found in selected Work")

        return work, BrokerScope(
            work_id=work_id,
            conversation_id=conversation_id,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
            data_scope=work["data_scope"],
            workspace_path=work["workspace_path"],
        )

    async def discover(
        self,
        work_id: str,
        conversation_id: str | None = None,
        attachment_artifact_ids: list[str] | None = None,
        *,
        memory_mode: str = "suggest_only",
        memory_project_id: str | None = None,
        memory_task_id: str | None = None,
        memory_scope_id: str | None = None,
    ) -> tuple[aiosqlite.Row, BrokerScope, list[CatalogResource]]:
        """Discover metadata only. No resource body is loaded in this stage."""

        work, scope = await self._scope(
            work_id,
            conversation_id,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
        )
        resources: list[CatalogResource] = [
            CatalogResource(
                kind="work",
                resource_id=work_id,
                title=f"Công việc: {work['title']}",
                sensitivity="internal",
                trust="canonical_user_data",
                rank_group=10,
            ),
            CatalogResource(
                kind="workspace_tasks",
                resource_id=work_id,
                title="Danh sách việc Workspace",
                sensitivity="internal",
                trust="canonical_user_data",
                rank_group=20,
            ),
        ]
        if conversation_id:
            async with self.conn.execute(
                "SELECT title FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (conversation_id, work_id),
            ) as cur:
                conversation = await cur.fetchone()
            if conversation is not None:
                resources.append(CatalogResource(
                    kind="conversation",
                    resource_id=conversation_id,
                    title=f"Trao đổi: {conversation['title']}",
                    sensitivity="sensitive",
                    trust="canonical_user_data",
                    rank_group=30,
                ))

        selected_ids = list(dict.fromkeys(attachment_artifact_ids or []))
        async with self.conn.execute(
            """SELECT artifact.id, artifact.relative_path, artifact.sha256, artifact.size_bytes,
                      artifact.created_at, COALESCE(validation.status, 'pending') AS validation_status
               FROM artifacts artifact
               LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
               WHERE artifact.session_id = ?
               ORDER BY artifact.created_at DESC, artifact.id
               LIMIT 100""",
            (work_id,),
        ) as cur:
            artifacts = await cur.fetchall()
        by_id = {row["id"]: row for row in artifacts}
        missing_selected = [resource_id for resource_id in selected_ids if resource_id not in by_id]
        if missing_selected:
            placeholders = ", ".join("?" for _ in missing_selected)
            async with self.conn.execute(
                f"""SELECT artifact.id, artifact.relative_path, artifact.sha256, artifact.size_bytes,
                           artifact.created_at, COALESCE(validation.status, 'pending') AS validation_status
                    FROM artifacts artifact
                    LEFT JOIN artifact_validations validation ON validation.artifact_id = artifact.id
                    WHERE artifact.session_id = ? AND artifact.id IN ({placeholders})""",
                (work_id, *missing_selected),
            ) as cur:
                by_id.update({row["id"]: row for row in await cur.fetchall()})

        ordered_artifacts: list[aiosqlite.Row] = []
        ordered_artifacts.extend(by_id[resource_id] for resource_id in selected_ids if resource_id in by_id)
        ordered_artifacts.extend(row for row in artifacts if row["id"] not in selected_ids)
        for index, artifact in enumerate(ordered_artifacts):
            relative = PurePosixPath(artifact["relative_path"])
            selected = artifact["id"] in selected_ids
            resources.append(CatalogResource(
                kind="artifact",
                resource_id=artifact["id"],
                title=relative.name or "Tài liệu",
                sensitivity="sensitive",
                trust="canonical_user_data",
                rank_group=0 if selected else 50,
                rank_order=selected_ids.index(artifact["id"]) if selected else index,
                selected=selected,
                source_hash=artifact["sha256"],
                locator={
                    "relative_path": artifact["relative_path"],
                    "validation_status": artifact["validation_status"],
                    "size_bytes": artifact["size_bytes"],
                },
            ))

        effective_scope_id = memory_scope_id or memory_task_id
        if effective_scope_id:
            async with self.conn.execute(
                """SELECT id, memory_key, content_sha256, sensitivity, lifecycle, kind, updated_at
                   FROM memory_hub_records
                   WHERE project_id = ? AND task_id = ?
                   ORDER BY updated_at DESC, id ASC
                   LIMIT 100""",
                (work_id, effective_scope_id),
            ) as cur:
                memory_rows = await cur.fetchall()
            for index, memory in enumerate(memory_rows):
                resources.append(CatalogResource(
                    kind="memory_hub",
                    resource_id=memory["id"],
                    title=f"Bộ nhớ: {memory['memory_key']}",
                    sensitivity=_memory_sensitivity(memory["sensitivity"]),
                    trust="verified_knowledge" if memory["lifecycle"] == "active" else "agent_generated_draft",
                    rank_group=40,
                    rank_order=index,
                    source_hash=memory["content_sha256"],
                    locator={
                        "lifecycle": memory["lifecycle"],
                        "memory_kind": memory["kind"],
                        "scope_id": effective_scope_id,
                    },
                ))

        if scope.data_scope == "approved_library":
            async with self.conn.execute(
                """SELECT record.id, record.source_sha256, record.status, record.updated_at
                   FROM dirap_knowledge_records record
                   JOIN tasks task ON task.id = record.task_id
                   WHERE task.session_id = ?
                   ORDER BY record.updated_at DESC, record.id
                   LIMIT 100""",
                (work_id,),
            ) as cur:
                knowledge_rows = await cur.fetchall()
            for index, record in enumerate(knowledge_rows):
                resources.append(CatalogResource(
                    kind="knowledge",
                    resource_id=record["id"],
                    title="Tri thức đã duyệt" if record["status"] == "active" else "Tri thức chờ duyệt",
                    sensitivity="internal",
                    trust="verified_knowledge" if record["status"] == "active" else "agent_generated_draft",
                    rank_group=60,
                    rank_order=index,
                    source_hash=record["source_sha256"],
                    locator={"status": record["status"]},
                ))

            async with self.conn.execute(
                "SELECT id, name, enabled, status FROM skills ORDER BY name, id LIMIT 100"
            ) as cur:
                skill_rows = await cur.fetchall()
            for index, skill in enumerate(skill_rows):
                resources.append(CatalogResource(
                    kind="skill",
                    resource_id=skill["id"],
                    title=skill["name"],
                    sensitivity="internal",
                    trust="verified_knowledge" if skill["status"] == "approved" else "agent_generated_draft",
                    rank_group=70,
                    rank_order=index,
                    locator={"enabled": bool(skill["enabled"]), "status": skill["status"]},
                ))

        return work, scope, resources

    async def security_filter(
        self,
        scope: BrokerScope,
        resources: list[CatalogResource],
    ) -> tuple[list[CatalogResource], list[dict[str, Any]]]:
        """Authorize metadata before ranking.

        Denied resources are summarized by kind/reason only. Their IDs, titles
        and locators never enter model-visible/public catalog output.
        """

        allowed: list[CatalogResource] = []
        denied_counts: dict[tuple[str, str], int] = {}
        effective_scope_id = scope.memory_scope_id or scope.memory_task_id
        memory_scope_valid = False
        if scope.memory_mode == "active_work_memory" and scope.memory_project_id == scope.work_id and effective_scope_id:
            if scope.memory_scope_id:
                async with self.conn.execute(
                    "SELECT id FROM work_memory_scopes WHERE id = ? AND work_id = ?",
                    (scope.memory_scope_id, scope.work_id),
                ) as cur:
                    memory_scope_valid = await cur.fetchone() is not None
            else:
                async with self.conn.execute(
                    "SELECT id FROM tasks WHERE id = ? AND session_id = ?",
                    (scope.memory_task_id, scope.work_id),
                ) as cur:
                    memory_scope_valid = await cur.fetchone() is not None

        workspace = Path(scope.workspace_path).resolve()
        for resource in resources:
            reason: str | None = None
            if resource.sensitivity == "restricted":
                reason = "restricted"
            elif resource.kind in {"work", "workspace_tasks"}:
                pass
            elif resource.kind == "conversation":
                if resource.resource_id != scope.conversation_id:
                    reason = "scope_mismatch"
            elif resource.kind == "artifact":
                relative = PurePosixPath(str(resource.locator.get("relative_path", "")))
                if resource.locator.get("validation_status") != "structurally_validated":
                    reason = "structural_validation"
                elif not relative.parts or relative.parts[0] not in {"inputs", "outputs"}:
                    reason = "managed_root"
                elif relative.suffix.lower() not in TEXT_SUFFIXES:
                    reason = "unsupported_format"
                else:
                    target = (workspace / Path(*relative.parts)).resolve()
                    if not target.is_relative_to(workspace):
                        reason = "managed_root"
                    elif not target.is_file():
                        reason = "unavailable"
            elif resource.kind == "memory_hub":
                if scope.memory_mode != "active_work_memory":
                    reason = "memory_mode"
                elif not memory_scope_valid:
                    reason = "scope_mismatch"
                elif resource.locator.get("scope_id") != effective_scope_id:
                    reason = "scope_mismatch"
                elif resource.locator.get("lifecycle") != "active":
                    reason = "lifecycle"
                elif resource.locator.get("memory_kind") == "preference":
                    reason = "preference"
            elif resource.kind == "knowledge":
                if scope.data_scope != "approved_library":
                    reason = "data_scope"
                elif resource.locator.get("status") != "active":
                    reason = "lifecycle"
            elif resource.kind == "skill":
                if scope.data_scope != "approved_library":
                    reason = "data_scope"
                elif resource.locator.get("status") != "approved" or not resource.locator.get("enabled"):
                    reason = "lifecycle"
            else:
                reason = "unsupported_kind"

            if reason is None:
                allowed.append(resource)
            else:
                denied_counts[(resource.kind, reason)] = denied_counts.get((resource.kind, reason), 0) + 1

        excluded = [
            {"kind": kind, "count": count, "reason": self._denial_text(reason)}
            for (kind, reason), count in sorted(denied_counts.items())
        ]
        return allowed, excluded

    @staticmethod
    def _denial_text(reason: str) -> str:
        return {
            "restricted": "Nguồn restricted không được đưa vào catalog hoặc ngữ cảnh GYO",
            "scope_mismatch": "Nguồn không thuộc phạm vi Work/task đã được cấp",
            "structural_validation": "Nguồn chưa qua kiểm tra cấu trúc",
            "managed_root": "Nguồn không thuộc managed workspace",
            "unsupported_format": "Định dạng chưa được phép làm ngữ cảnh văn bản",
            "memory_mode": "Memory Hub chưa được bật cho phạm vi này",
            "lifecycle": "Lifecycle chưa cho phép dùng trong chat",
            "preference": "Preference không được tự động đưa vào chat",
            "data_scope": "Data scope của Work không cho phép nguồn thư viện dùng lại",
            "unsupported_kind": "Loại nguồn không được Context Broker hỗ trợ",
            "unavailable": "Nguồn không còn khả dụng trong managed workspace",
        }.get(reason, "Nguồn không đủ điều kiện dùng trong ngữ cảnh")

    def rank(self, resources: list[CatalogResource]) -> list[CatalogResource]:
        """Rank only the already-authorized descriptor set.

        Per-kind caps preserve the pre-F7 bounded context contract after
        authorization. Denied resources never consume those caps.
        """

        ordered = sorted(
            resources,
            key=lambda resource: (
                resource.rank_group,
                resource.rank_order,
                resource.title.casefold(),
                resource.resource_id,
            ),
        )
        caps = {"artifact": 20, "memory_hub": 20, "knowledge": 20, "skill": 10}
        counts: dict[str, int] = {}
        ranked: list[CatalogResource] = []
        for resource in ordered:
            if resource.kind == "artifact" and resource.selected:
                ranked.append(resource)
                continue
            cap = caps.get(resource.kind)
            if cap is not None:
                count = counts.get(resource.kind, 0)
                if count >= cap:
                    continue
                counts[resource.kind] = count + 1
            ranked.append(resource)
        return ranked

    def public_catalog(self, ranked: list[CatalogResource]) -> list[dict[str, Any]]:
        """Serialize authorized metadata only."""

        result: list[dict[str, Any]] = []
        for resource in ranked:
            item: dict[str, Any] = {
                "kind": resource.kind,
                "id": resource.resource_id,
                "title": resource.title,
                "reason": _public_reason(resource),
                "sensitivity": resource.sensitivity,
                "trust": resource.trust,
            }
            if resource.selected:
                item["selected"] = True
            if resource.source_hash:
                item["sha256"] = resource.source_hash
            result.append(item)
        return result

    async def authorized_catalog(
        self,
        work_id: str,
        conversation_id: str | None = None,
        attachment_artifact_ids: list[str] | None = None,
        *,
        memory_mode: str = "suggest_only",
        memory_project_id: str | None = None,
        memory_task_id: str | None = None,
        memory_scope_id: str | None = None,
    ) -> tuple[aiosqlite.Row, BrokerScope, list[CatalogResource], list[dict[str, Any]], list[dict[str, Any]]]:
        work, scope, discovered = await self.discover(
            work_id,
            conversation_id,
            attachment_artifact_ids,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
        )
        authorized, denied = await self.security_filter(scope, discovered)
        ranked = self.rank(authorized)
        return work, scope, ranked, self.public_catalog(ranked), denied

    async def _hydrate(
        self,
        work: aiosqlite.Row,
        scope: BrokerScope,
        resource: CatalogResource,
    ) -> tuple[str, str | None, dict[str, str | None]] | None:
        """Load one authorized resource, with fail-closed revalidation."""

        if resource.kind == "work":
            async with self.conn.execute(
                "SELECT * FROM work_plan_phases WHERE session_id = ? ORDER BY sort_order, created_at, id",
                (scope.work_id,),
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
                        plan_lines.append(
                            f"  - {step['title']} [{step['status']}]"
                            + (f": {detail}" if detail else "")
                        )
            body = (
                f"Mục tiêu: {work['goal'] or 'Chưa đặt'}\n"
                f"Trạng thái: {work['work_status']}\n"
                f"Tiến độ: {work['progress_percent']}%\n"
                f"Kế hoạch:\n" + ("\n".join(plan_lines) if plan_lines else "- Chưa có bước kế hoạch")
            )
            return body, _sha256_text(body), {}

        if resource.kind == "workspace_tasks":
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
                (scope.work_id,),
            ) as cur:
                tasks = await cur.fetchall()
            lines: list[str] = []
            for task in tasks:
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
                lines.append(
                    f"- {task['title']} ({'; '.join(metadata)})"
                    + (f": {description}" if description else "")
                )
            body = "\n".join(lines) if lines else "- Chưa có việc Workspace nào trong Công việc này"
            return body, _sha256_text(body), {}

        if resource.kind == "conversation":
            async with self.conn.execute(
                "SELECT title FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (resource.resource_id, scope.work_id),
            ) as cur:
                if await cur.fetchone() is None:
                    return None
            async with self.conn.execute(
                "SELECT id, role, content FROM chat_messages WHERE conversation_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 24",
                (resource.resource_id,),
            ) as cur:
                messages = list(reversed(await cur.fetchall()))
            if not messages:
                return None
            body = "\n".join(
                f"{('Bạn' if message['role'] == 'user' else 'GYO')}: {message['content']}"
                for message in messages
            )
            return body, _sha256_text(body), {
                "from_message_id": messages[0]["id"],
                "through_message_id": messages[-1]["id"],
            }

        if resource.kind == "artifact":
            relative = PurePosixPath(str(resource.locator.get("relative_path", "")))
            workspace = Path(scope.workspace_path).resolve()
            if (
                resource.locator.get("validation_status") != "structurally_validated"
                or not relative.parts
                or relative.parts[0] not in {"inputs", "outputs"}
                or relative.suffix.lower() not in TEXT_SUFFIXES
            ):
                return None
            target = (workspace / Path(*relative.parts)).resolve()
            if not target.is_relative_to(workspace) or not target.is_file():
                return None
            try:
                actual_hash = _sha256_file(target)
                if not resource.source_hash or actual_hash != resource.source_hash:
                    return None
                body = target.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                return None
            return body, actual_hash, {}

        if resource.kind == "memory_hub":
            effective_scope_id = scope.memory_scope_id or scope.memory_task_id
            async with self.conn.execute(
                """SELECT content, content_sha256, sensitivity, lifecycle, kind
                   FROM memory_hub_records
                   WHERE id = ? AND project_id = ? AND task_id = ?""",
                (resource.resource_id, scope.work_id, effective_scope_id),
            ) as cur:
                memory = await cur.fetchone()
            if (
                memory is None
                or memory["lifecycle"] != "active"
                or memory["kind"] == "preference"
                or memory["sensitivity"] == "restricted"
            ):
                return None
            return memory["content"], memory["content_sha256"], {}

        if resource.kind == "knowledge":
            async with self.conn.execute(
                """SELECT record.content, record.source_sha256
                   FROM dirap_knowledge_records record
                   JOIN tasks task ON task.id = record.task_id
                   WHERE record.id = ? AND task.session_id = ? AND record.status = 'active'""",
                (resource.resource_id, scope.work_id),
            ) as cur:
                record = await cur.fetchone()
            if record is None:
                return None
            return record["content"], record["source_sha256"], {}

        if resource.kind == "skill":
            async with self.conn.execute(
                "SELECT description, content FROM skills WHERE id = ? AND enabled = 1 AND status = 'approved'",
                (resource.resource_id,),
            ) as cur:
                skill = await cur.fetchone()
            if skill is None:
                return None
            body = "\n".join(part for part in (skill["description"], skill["content"]) if part)
            return body, _sha256_text(body), {}

        return None

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
        work, scope, ranked, accessible, denied = await self.authorized_catalog(
            work_id,
            conversation_id,
            attachment_artifact_ids,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
        )

        excluded: list[dict[str, Any]] = [
            {"kind": "raw_audit", "reason": "Raw audit không phải Resource Catalog source"},
            {"kind": "credentials", "reason": "Credential, env và API key không phải Resource Catalog source"},
            {"kind": "raw_database", "reason": "Raw app.db không phải Resource Catalog source"},
            {"kind": "chain_of_thought", "reason": "Internal reasoning không phải Resource Catalog source"},
            *denied,
        ]
        if memory_mode != "active_work_memory":
            excluded.append({
                "kind": "memory_hub",
                "reason": "Không tự động đưa vào chat" if memory_mode == "suggest_only" else "Đã tắt theo phạm vi Công việc",
                "mode": memory_mode,
            })
        if scope.data_scope != "approved_library":
            excluded.append({"kind": "approved_library", "reason": "Work chỉ dùng dữ liệu của chính nó"})

        sections: list[str] = []
        included: list[dict[str, Any]] = []
        remaining = self.byte_limit
        from_message_id: str | None = None
        through_message_id: str | None = None

        for resource in ranked:
            hydrated = await self._hydrate(work, scope, resource)
            if hydrated is None:
                excluded.append({
                    "kind": resource.kind,
                    "count": 1,
                    "reason": "Nguồn thay đổi hoặc không còn đủ điều kiện sau bước catalog",
                })
                continue
            body, source_hash, metadata = hydrated
            rendered = f"## {resource.title}\n{body.strip()}\n"
            fitted, truncated = _fit_utf8(rendered, remaining)
            if not fitted:
                excluded.append({
                    "kind": resource.kind,
                    "count": 1,
                    "reason": "Vượt giới hạn ngữ cảnh",
                })
                continue
            sections.append(fitted)
            used = len(fitted.encode("utf-8"))
            remaining -= used
            included.append({
                "kind": resource.kind,
                "id": resource.resource_id,
                "title": resource.title,
                "reason": _public_reason(resource),
                "sensitivity": resource.sensitivity,
                "trust": resource.trust,
                "sha256": source_hash or _sha256_text(body),
                "bytes": used,
                "truncated": truncated,
                **({"selected": True} if resource.selected else {}),
            })
            if resource.kind == "conversation":
                from_message_id = metadata.get("from_message_id")
                through_message_id = metadata.get("through_message_id")

        text = "\n".join(sections).strip()
        version_material = "|".join(
            f"{item['kind']}:{item['id']}:{item['sha256']}:{item['bytes']}:{item['truncated']}:{item['sensitivity']}:{item['trust']}"
            for item in included
        )
        return AssistantContextPack(
            text=text,
            included=included,
            excluded=excluded,
            accessible=accessible,
            byte_limit=self.byte_limit,
            byte_count=len(text.encode("utf-8")),
            version=_sha256_text(version_material)[:16],
            generated_at=int(time.time()),
            from_message_id=from_message_id,
            through_message_id=through_message_id,
        )
