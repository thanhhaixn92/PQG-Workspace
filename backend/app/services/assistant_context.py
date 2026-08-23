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
        return await self.broker.build(
            work_id,
            conversation_id,
            attachment_artifact_ids=attachment_artifact_ids,
            memory_mode=memory_mode,
            memory_project_id=memory_project_id,
            memory_task_id=memory_task_id,
            memory_scope_id=memory_scope_id,
        )
