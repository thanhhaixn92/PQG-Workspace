"""Foundation module-instance migrations.

This file starts at migration 0037. Historical migrations 0001-0036 remain
frozen in ``migrations_0001_0036.py`` so protected Foundation changes stay
small and reviewable without rewriting the validated migration ledger.
"""
from __future__ import annotations

import time

import aiosqlite


_BUILTIN_MODULE_SEEDS: tuple[tuple[str, str, str, int, int], ...] = (
    ("builtin:work", "work", "Công việc", 1, 10),
    ("builtin:documents", "documents", "Tài liệu", 0, 20),
    ("builtin:knowledge", "knowledge", "Thư viện", 1, 30),
    ("builtin:review", "review", "Hộp duyệt", 1, 40),
    ("builtin:reports", "reports", "Báo cáo", 1, 50),
    ("builtin:memory", "memory", "Bộ nhớ", 0, 60),
    ("builtin:memory-hub", "memory-hub", "Memory Hub", 0, 70),
    ("builtin:local-data", "local-data", "Dữ liệu", 0, 80),
    ("builtin:research", "research", "Nghiên cứu", 0, 90),
)


async def apply_0037_foundation_module_instances(conn: aiosqlite.Connection) -> None:
    """Persist user-controlled Module attachment/presentation state.

    The migration is additive and deliberately contains no delete/cutover.
    Existing navigation behaviour is preserved by seeding only the four
    modules that were already primary navigation items as attached.
    """
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS module_instances (
            id TEXT PRIMARY KEY,
            module_id TEXT NOT NULL UNIQUE,
            source_kind TEXT NOT NULL CHECK (source_kind IN ('builtin', 'marketplace')),
            package_id TEXT,
            display_name TEXT NOT NULL,
            attached INTEGER NOT NULL DEFAULT 0 CHECK (attached IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            config_json TEXT NOT NULL DEFAULT '{}',
            config_version INTEGER NOT NULL DEFAULT 1,
            health_state TEXT NOT NULL DEFAULT 'unknown'
                CHECK (health_state IN ('ready', 'degraded', 'unavailable', 'unknown')),
            revision INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )"""
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_module_instances_attached_order "
        "ON module_instances(attached, sort_order, module_id)"
    )

    now = int(time.time())
    await conn.executemany(
        """INSERT OR IGNORE INTO module_instances
           (id, module_id, source_kind, package_id, display_name, attached,
            sort_order, config_json, config_version, health_state, revision,
            created_at, updated_at)
           VALUES (?, ?, 'builtin', NULL, ?, ?, ?, '{}', 1, 'ready', 1, ?, ?)""",
        [(*seed, now, now) for seed in _BUILTIN_MODULE_SEEDS],
    )
