"""Persistent Foundation Module instance state and user-admin mutations."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import aiosqlite

from app.services.audit import log_audit_event


@dataclass(slots=True)
class ModuleAdminError(Exception):
    status_code: int
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _parse_module_config(row: aiosqlite.Row) -> dict[str, Any]:
    try:
        config = json.loads(row["config_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ModuleAdminError(
            500,
            "MODULE_CONFIG_INVALID",
            "Stored Module config is invalid; repair local Module state before continuing",
        ) from exc
    if not isinstance(config, dict):
        raise ModuleAdminError(
            500,
            "MODULE_CONFIG_INVALID",
            "Stored Module config is invalid; repair local Module state before continuing",
        )
    return config


def _module(row: aiosqlite.Row) -> dict[str, Any]:
    config = _parse_module_config(row)
    return {
        "id": row["id"],
        "module_id": row["module_id"],
        "source_kind": row["source_kind"],
        "package_id": row["package_id"],
        "display_name": row["display_name"],
        "attached": bool(row["attached"]),
        "sort_order": int(row["sort_order"]),
        "config": config,
        "config_version": int(row["config_version"]),
        "health_state": row["health_state"],
        "revision": int(row["revision"]),
        "created_at": int(row["created_at"]),
        "updated_at": int(row["updated_at"]),
    }


async def list_module_instances(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    async with conn.execute(
        "SELECT * FROM module_instances ORDER BY attached DESC, sort_order, module_id"
    ) as cur:
        return [_module(row) async for row in cur]


async def _module_row(conn: aiosqlite.Connection, module_id: str) -> aiosqlite.Row:
    async with conn.execute("SELECT * FROM module_instances WHERE module_id = ?", (module_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise ModuleAdminError(404, "MODULE_NOT_FOUND", "Module instance not found")
    return row


def _require_revision(row: aiosqlite.Row, expected_revision: int) -> None:
    current = int(row["revision"])
    if current != expected_revision:
        raise ModuleAdminError(
            409,
            "MODULE_REVISION_CONFLICT",
            f"Module changed since it was loaded (expected {expected_revision}, current {current})",
        )


def _require_update_rowcount(cursor: aiosqlite.Cursor) -> None:
    if cursor.rowcount != 1:
        raise ModuleAdminError(
            409,
            "MODULE_REVISION_CONFLICT",
            "Module changed while the update was being applied; reload before saving",
        )


async def set_module_attached(
    conn: aiosqlite.Connection,
    *,
    module_id: str,
    attached: bool,
    expected_revision: int,
    actor: str,
) -> dict[str, Any]:
    await conn.execute("BEGIN IMMEDIATE")
    try:
        row = await _module_row(conn, module_id)
        _require_revision(row, expected_revision)
        current = _module(row)
        if bool(row["attached"]) == attached:
            await conn.commit()
            return current

        next_order = int(row["sort_order"])
        if attached:
            async with conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM module_instances WHERE attached = 1"
            ) as cur:
                next_order = int((await cur.fetchone())[0])
        now = int(time.time())
        cursor = await conn.execute(
            """UPDATE module_instances
               SET attached = ?, sort_order = ?, revision = revision + 1, updated_at = ?
               WHERE module_id = ? AND revision = ?""",
            (int(attached), next_order, now, module_id, expected_revision),
        )
        _require_update_rowcount(cursor)
        await log_audit_event(
            conn,
            None,
            actor,
            "foundation.module_attached" if attached else "foundation.module_detached",
            module_id,
            {"attached": attached, "data_deleted": False},
            commit=False,
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return _module(await _module_row(conn, module_id))


async def rename_module(
    conn: aiosqlite.Connection,
    *,
    module_id: str,
    display_name: str,
    expected_revision: int,
    actor: str,
) -> dict[str, Any]:
    normalized = " ".join(display_name.split())
    if not normalized or len(normalized) > 80:
        raise ModuleAdminError(422, "MODULE_DISPLAY_NAME_INVALID", "Display name must be 1-80 characters")

    await conn.execute("BEGIN IMMEDIATE")
    try:
        row = await _module_row(conn, module_id)
        _require_revision(row, expected_revision)
        current = _module(row)
        if row["display_name"] == normalized:
            await conn.commit()
            return current
        now = int(time.time())
        cursor = await conn.execute(
            """UPDATE module_instances
               SET display_name = ?, revision = revision + 1, updated_at = ?
               WHERE module_id = ? AND revision = ?""",
            (normalized, now, module_id, expected_revision),
        )
        _require_update_rowcount(cursor)
        await log_audit_event(
            conn,
            None,
            actor,
            "foundation.module_renamed",
            module_id,
            {"from": row["display_name"], "to": normalized},
            commit=False,
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return _module(await _module_row(conn, module_id))


async def reorder_attached_modules(
    conn: aiosqlite.Connection,
    *,
    module_ids: list[str],
    expected_revisions: dict[str, int],
    actor: str,
) -> list[dict[str, Any]]:
    if len(module_ids) != len(set(module_ids)):
        raise ModuleAdminError(422, "MODULE_ORDER_INVALID", "Module order contains duplicates")

    await conn.execute("BEGIN IMMEDIATE")
    try:
        # Reorder returns the full projection. Validate every persisted config
        # before any write so corrupt state cannot cause a post-commit 500.
        await list_module_instances(conn)
        async with conn.execute(
            "SELECT * FROM module_instances WHERE attached = 1 ORDER BY sort_order, module_id"
        ) as cur:
            rows = [row async for row in cur]
        current_by_id = {row["module_id"]: row for row in rows}
        if set(module_ids) != set(current_by_id):
            raise ModuleAdminError(
                409,
                "MODULE_ORDER_STALE",
                "Attached Module set changed; reload before reordering",
            )
        if set(expected_revisions) != set(current_by_id):
            raise ModuleAdminError(409, "MODULE_ORDER_STALE", "Module revisions are incomplete")
        for module_id, row in current_by_id.items():
            _require_revision(row, int(expected_revisions[module_id]))

        changed = False
        now = int(time.time())
        for index, module_id in enumerate(module_ids, start=1):
            row = current_by_id[module_id]
            new_order = index * 10
            if int(row["sort_order"]) == new_order:
                continue
            changed = True
            cursor = await conn.execute(
                """UPDATE module_instances
                   SET sort_order = ?, revision = revision + 1, updated_at = ?
                   WHERE module_id = ? AND revision = ?""",
                (new_order, now, module_id, int(row["revision"])),
            )
            _require_update_rowcount(cursor)
        if changed:
            await log_audit_event(
                conn,
                None,
                actor,
                "foundation.modules_reordered",
                "module-navigation",
                {"module_ids": module_ids},
                commit=False,
            )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return await list_module_instances(conn)
