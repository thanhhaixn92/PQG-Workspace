"""User-facing overview data without exposing machine diagnostics."""
from __future__ import annotations

from pathlib import Path, PurePosixPath

import aiosqlite
from fastapi import APIRouter, Depends

from app.api.schemas import OverviewResponse, SessionResponse
from app.dependencies import get_db, get_settings
from app.settings import Settings

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OverviewResponse:
    """Return a small, read-only dashboard for the local end user."""
    async with conn.execute(
        """SELECT id, acp_session_id, title, workspace_path, created_at, updated_at, archived, goal, last_opened_at
           FROM sessions WHERE archived = 0
           ORDER BY COALESCE(last_opened_at, updated_at) DESC, id DESC LIMIT 5"""
    ) as cursor:
        recent_rows = await cursor.fetchall()

    async def count(query: str) -> int:
        async with conn.execute(query) as cursor:
            row = await cursor.fetchone()
        return int(row[0])

    active_work_count = await count(
        """SELECT COUNT(*) FROM task_runs task
           JOIN sessions session ON session.id = task.session_id
           WHERE session.archived = 0 AND task.status IN ('queued', 'running', 'waiting_approval')"""
    )
    pending_approval_count = await count(
        """SELECT COUNT(*) FROM (
             SELECT approval.id
             FROM approval_requests approval
             LEFT JOIN sessions session ON session.id = approval.session_id
             WHERE approval.status = 'pending' AND (session.id IS NULL OR session.archived = 0)
             UNION ALL
             SELECT package.id
             FROM action_packages package
             JOIN sessions session ON session.id = package.session_id
             WHERE package.status = 'awaiting_approval' AND session.archived = 0
           )"""
    )
    output_count = await count(
        """SELECT COUNT(*) FROM artifacts artifact
           JOIN sessions session ON session.id = artifact.session_id
           WHERE session.archived = 0"""
    )
    blocked_step_count = await count(
        """SELECT COUNT(*) FROM work_plan_steps step
           JOIN sessions session ON session.id = step.session_id
           WHERE session.archived = 0 AND step.status = 'blocked'"""
    )
    waiting_confirmation_count = await count(
        "SELECT COUNT(*) FROM sessions WHERE archived = 0 AND work_status = 'waiting_confirmation'"
    )

    attention_items: list[dict[str, object]] = []
    async with conn.execute(
        """SELECT step.session_id, session.title AS work_title, step.title, step.updated_at
           FROM work_plan_steps step JOIN sessions session ON session.id = step.session_id
           WHERE session.archived = 0 AND step.status = 'blocked'
           ORDER BY step.updated_at DESC LIMIT 3"""
    ) as cursor:
        for row in await cursor.fetchall():
            attention_items.append({
                "kind": "blocked_step", "work_id": row["session_id"], "work_title": row["work_title"],
                "title": row["title"], "reason": "Bước kế hoạch đang bị chặn", "severity": "warning", "updated_at": row["updated_at"],
            })
    async with conn.execute(
        """SELECT package.session_id, session.title AS work_title, package.title, package.updated_at
           FROM action_packages package JOIN sessions session ON session.id = package.session_id
           WHERE session.archived = 0 AND package.status = 'awaiting_approval'
           ORDER BY package.updated_at DESC LIMIT 3"""
    ) as cursor:
        for row in await cursor.fetchall():
            attention_items.append({
                "kind": "approval", "work_id": row["session_id"], "work_title": row["work_title"],
                "title": row["title"], "reason": "Đề xuất đang chờ bạn duyệt", "severity": "attention", "updated_at": row["updated_at"],
            })
    async with conn.execute(
        """SELECT id, title, updated_at FROM sessions
           WHERE archived = 0 AND work_status = 'waiting_confirmation'
           ORDER BY updated_at DESC LIMIT 3"""
    ) as cursor:
        for row in await cursor.fetchall():
            attention_items.append({
                "kind": "completion", "work_id": row["id"], "work_title": row["title"],
                "title": row["title"], "reason": "Hermes đề xuất xác nhận hoàn tất", "severity": "attention", "updated_at": row["updated_at"],
            })
    attention_items.sort(key=lambda item: int(item["updated_at"]), reverse=True)

    async with conn.execute(
        """SELECT artifact.session_id, artifact.relative_path, artifact.kind, artifact.size_bytes, artifact.created_at,
                  session.title AS work_title
           FROM artifacts artifact JOIN sessions session ON session.id = artifact.session_id
           WHERE session.archived = 0
           ORDER BY artifact.created_at DESC LIMIT 5"""
    ) as cursor:
        recent_artifacts = [
            {
                "work_id": row["session_id"], "work_title": row["work_title"],
                "title": PurePosixPath(row["relative_path"]).name, "kind": row["kind"],
                "size_bytes": row["size_bytes"], "created_at": row["created_at"],
            }
            for row in await cursor.fetchall()
        ]

    backup_dir = Path(settings.db_path_resolved).parent / "backups"
    backup_times = [int(path.stat().st_mtime) for path in backup_dir.glob("*.db")] if backup_dir.exists() else []
    return OverviewResponse(
        recent_work=[SessionResponse(**dict(row)) for row in recent_rows],
        active_work_count=active_work_count,
        pending_approval_count=pending_approval_count,
        output_count=output_count,
        latest_backup_at=max(backup_times) if backup_times else None,
        blocked_step_count=blocked_step_count,
        waiting_confirmation_count=waiting_confirmation_count,
        attention_items=attention_items[:5],
        recent_artifacts=recent_artifacts,
        latest_work_updates=[SessionResponse(**dict(row)) for row in recent_rows],
    )
