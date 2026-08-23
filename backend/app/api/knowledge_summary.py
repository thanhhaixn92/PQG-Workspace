"""Read-only Knowledge overview assembled from existing lifecycle stores."""
from __future__ import annotations

from collections import Counter

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import KnowledgeSummaryResponse
from app.dependencies import get_db
from app.services.assistant_context import AssistantContextPackBuilder

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


async def _scalar(conn: aiosqlite.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    async with conn.execute(sql, params) as cursor:
        row = await cursor.fetchone()
    return int(row[0] or 0)


async def _group_counts(
    conn: aiosqlite.Connection,
    sql: str,
    params: tuple[object, ...] = (),
) -> Counter[str]:
    counts: Counter[str] = Counter()
    async with conn.execute(sql, params) as cursor:
        for row in await cursor.fetchall():
            counts[str(row[0])] += int(row[1])
    return counts


@router.get("/summary", response_model=KnowledgeSummaryResponse)
async def get_knowledge_summary(
    work_id: str | None = Query(default=None),
    conn: aiosqlite.Connection = Depends(get_db),
) -> KnowledgeSummaryResponse:
    """Summarize existing stores without changing their lifecycle or contents.

    Global skills remain visible for a selected Work because approved, enabled
    skills are app-wide capabilities. Work-owned sources stay strictly scoped.
    Memory Hub is counted for operator awareness but never auto-injected.
    """
    work = None
    if work_id:
        async with conn.execute(
            "SELECT id, archived FROM sessions WHERE id = ?", (work_id,)
        ) as cursor:
            work = await cursor.fetchone()
        if work is None:
            raise HTTPException(status_code=404, detail="Work not found")

    source_counts: dict[str, int] = {
        "skills": await _scalar(conn, "SELECT COUNT(*) FROM skills"),
    }
    lifecycle_counts = await _group_counts(
        conn, "SELECT status, COUNT(*) FROM skills GROUP BY status"
    )

    if work_id:
        source_counts["memory"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM memory_entries WHERE session_id IS NULL OR session_id = ?",
            (work_id,),
        )
        source_counts["knowledge"] = await _scalar(
            conn,
            """SELECT COUNT(*) FROM dirap_knowledge_records record
               JOIN tasks task ON task.id = record.task_id
               WHERE task.session_id = ?""",
            (work_id,),
        )
        lifecycle_counts.update(await _group_counts(
            conn,
            """SELECT record.status, COUNT(*) FROM dirap_knowledge_records record
               JOIN tasks task ON task.id = record.task_id
               WHERE task.session_id = ? GROUP BY record.status""",
            (work_id,),
        ))
        source_counts["memory_hub"] = await _scalar(
            conn,
            """SELECT COUNT(*) FROM memory_hub_records record
               WHERE record.project_id = ?
                  OR record.task_id IN (SELECT id FROM tasks WHERE session_id = ?)""",
            (work_id, work_id),
        )
        lifecycle_counts.update(await _group_counts(
            conn,
            """SELECT record.lifecycle, COUNT(*) FROM memory_hub_records record
               WHERE record.project_id = ?
                  OR record.task_id IN (SELECT id FROM tasks WHERE session_id = ?)
               GROUP BY record.lifecycle""",
            (work_id, work_id),
        ))
        source_counts["artifacts"] = await _scalar(
            conn, "SELECT COUNT(*) FROM artifacts WHERE session_id = ?", (work_id,)
        )
        source_counts["action_packages"] = await _scalar(
            conn, "SELECT COUNT(*) FROM action_packages WHERE session_id = ?", (work_id,)
        )
        lifecycle_counts.update(await _group_counts(
            conn,
            "SELECT status, COUNT(*) FROM action_packages WHERE session_id = ? GROUP BY status",
            (work_id,),
        ))
    else:
        source_counts["memory"] = await _scalar(
            conn, "SELECT COUNT(*) FROM memory_entries WHERE session_id IS NULL"
        )
        source_counts["knowledge"] = await _scalar(
            conn, "SELECT COUNT(*) FROM dirap_knowledge_records"
        )
        lifecycle_counts.update(await _group_counts(
            conn, "SELECT status, COUNT(*) FROM dirap_knowledge_records GROUP BY status"
        ))
        source_counts["memory_hub"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM memory_hub_records WHERE project_id IS NULL AND task_id IS NULL",
        )
        lifecycle_counts.update(await _group_counts(
            conn,
            """SELECT lifecycle, COUNT(*) FROM memory_hub_records
               WHERE project_id IS NULL AND task_id IS NULL GROUP BY lifecycle""",
        ))
        source_counts["artifacts"] = 0
        source_counts["action_packages"] = 0

    pending_review = (
        lifecycle_counts["review_pending"]
        + lifecycle_counts["proposed"]
        + lifecycle_counts["verified"]
        + lifecycle_counts["awaiting_approval"]
    )

    timestamps: list[int] = []
    timestamp_queries: list[tuple[str, tuple[object, ...]]] = [
        ("SELECT MAX(updated_at) FROM skills", ()),
        ("SELECT MAX(created_at) FROM memory_entries WHERE session_id IS NULL", ()),
    ]
    if work_id:
        timestamp_queries.extend([
            ("SELECT MAX(created_at) FROM memory_entries WHERE session_id = ?", (work_id,)),
            ("""SELECT MAX(record.updated_at) FROM dirap_knowledge_records record
                JOIN tasks task ON task.id = record.task_id WHERE task.session_id = ?""", (work_id,)),
            ("""SELECT MAX(record.updated_at) FROM memory_hub_records record
                WHERE record.project_id = ? OR record.task_id IN
                (SELECT id FROM tasks WHERE session_id = ?)""", (work_id, work_id)),
            ("SELECT MAX(created_at) FROM artifacts WHERE session_id = ?", (work_id,)),
            ("SELECT MAX(updated_at) FROM action_packages WHERE session_id = ?", (work_id,)),
        ])
    else:
        timestamp_queries.extend([
            ("SELECT MAX(updated_at) FROM dirap_knowledge_records", ()),
            ("""SELECT MAX(updated_at) FROM memory_hub_records
                WHERE project_id IS NULL AND task_id IS NULL""", ()),
        ])
    for sql, params in timestamp_queries:
        value = await _scalar(conn, sql, params)
        if value:
            timestamps.append(value)

    context_included = 0
    context_excluded = 0
    if work_id and not bool(work["archived"]):
        try:
            pack = await AssistantContextPackBuilder(conn).build(work_id)
        except (OSError, ValueError):
            # Summary remains useful when the managed workspace is temporarily
            # unavailable; the dedicated context view reports that failure.
            pass
        else:
            context_included = len(pack.included)
            context_excluded = len(pack.excluded)

    return KnowledgeSummaryResponse(
        work_id=work_id,
        counts_by_source=source_counts,
        counts_by_lifecycle=dict(sorted(lifecycle_counts.items())),
        context_included_count=context_included,
        context_excluded_count=context_excluded,
        pending_review_count=pending_review,
        last_updated_at=max(timestamps, default=None),
    )
