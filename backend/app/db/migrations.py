"""Active PQG Workspace migration registry.

Historical migrations 0001-0036 are frozen byte-for-byte in
``migrations_0001_0036.py``.  This registry re-exports the historical module
for compatibility and appends protected Foundation migrations in small,
reviewable modules.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.db import migrations_0001_0036 as _legacy
from app.db.module_migrations import apply_0037_foundation_module_instances

# Preserve the public/private import surface used by existing tests and code.
# Dunder names are intentionally excluded; every historical migration helper,
# constant and type remains available from app.db.migrations.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

MIGRATIONS: list[tuple[str, MigrationStep]] = [
    *_legacy.MIGRATIONS,
    ("0037_foundation_module_instances", apply_0037_foundation_module_instances),
]


async def run_migrations(db_path: Path) -> None:
    """Apply the complete ordered migration registry to *db_path*.

    The implementation intentionally mirrors the validated historical runner:
    already-applied versions are skipped, each migration is committed only
    after its version record is stored, and any failure rolls back before it is
    surfaced to startup/tests.
    """
    conn = await open_db(db_path)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT    PRIMARY KEY,
                applied_at INTEGER NOT NULL
            );
            """
        )
        await conn.commit()

        async with conn.execute("SELECT version FROM schema_migrations;") as cursor:
            applied = {row[0] async for row in cursor}

        for version, step in MIGRATIONS:
            if version in applied:
                logger.debug("Migration %s already applied, skipping.", version)
                continue
            logger.info("Applying migration: %s", version)
            try:
                if isinstance(step, str):
                    await conn.executescript(step)
                else:
                    await step(conn)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (version, int(time.time())),
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
            logger.info("Migration %s applied.", version)
    finally:
        await conn.close()
