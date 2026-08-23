"""Compatibility facade for the F7 Resource Catalog + Context Broker.

Existing callers keep using ``AssistantContextPackBuilder`` while all context
selection now flows through the broker's explicit security-first pipeline.
"""
from __future__ import annotations

import aiosqlite

from app.services.context_broker import (
    CONTEXT_BYTE_LIMIT,
    MEMORY_MODES,
    TEXT_SUFFIXES,
    AssistantContextPack,
    ContextBroker,
    _fit_utf8,
    _sha256_file,
    _sha256_text,
)

# Compatibility alias for focused tests/legacy imports. Policy ownership lives
# in context_broker.py.
_TEXT_SUFFIXES = set(TEXT_SUFFIXES)


class AssistantContextPackBuilder:
    """Preserve the existing builder API while routing through ContextBroker."""

    def __init__(self, conn: aiosqlite.Connection, *, byte_limit: int = CONTEXT_BYTE_LIMIT) -> None:
        self.broker = ContextBroker(conn, byte_limit=byte_limit)

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
        pack = await self.broker.build(
            work_id,
            conversation_id,
            attachment_artifact_ids=attachment_artifact_ids,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
        )
        # Preserve the pre-F7 manifest contract for an explicitly enabled
        # Memory mode without an explicit matching scope. This is safe
        # compatibility metadata only: discovery/filter/ranking/hydration have
        # already remained inside ContextBroker and no denied resource ID or
        # content is reintroduced here.
        effective_scope_id = memory_scope_id or memory_task_id
        if (
            memory_mode == "active_work_memory"
            and (memory_project_id != work_id or not effective_scope_id)
            and not any(
                item.get("kind") == "memory_hub"
                and "Cần phạm vi" in str(item.get("reason", ""))
                for item in pack.excluded
            )
        ):
            return AssistantContextPack(
                text=pack.text,
                included=pack.included,
                excluded=[
                    *pack.excluded,
                    {
                        "kind": "memory_hub",
                        "reason": "Cần phạm vi project/task khớp với Công việc đang chọn",
                        "mode": memory_mode,
                    },
                ],
                accessible=pack.accessible,
                byte_limit=pack.byte_limit,
                byte_count=pack.byte_count,
                version=pack.version,
                generated_at=pack.generated_at,
                from_message_id=pack.from_message_id,
                through_message_id=pack.through_message_id,
            )
        return pack
