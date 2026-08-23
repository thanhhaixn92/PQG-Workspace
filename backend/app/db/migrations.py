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
from app.db.assistant_run_migrations import apply_0038_durable_assistant_runs
from app.db.module_migrations import apply_0037_foundation_module_instances

# Explicit bindings keep static analysis honest while the compatibility export
# below preserves historical private/public imports used by tests and code.
MigrationStep = _legacy.MigrationStep
open_db = _legacy.open_db
logger = _legacy.logger

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

# Preserve the historical monkeypatch seam used by migration rollback tests.
# Migration 0022 resolves ``_migration_audit`` from the module where its
# function was defined. After the F5 ledger split that module is ``_legacy``,
# while existing callers/tests still patch ``app.db.migrations._migration_audit``.
# Bridge only this migration at execution time so the frozen 0001-0036 source
# remains byte-for-byte unchanged.
_migration_audit = _legacy._migration_audit


async def _apply_migration_0022_security_integrity(conn) -> None:
    original_audit = _legacy._migration_audit
    _legacy._migration_audit = _migration_audit
    try:
        await _legacy._apply_migration_0022_security_integrity(conn)
    finally:
        _legacy._migration_audit = original_audit


MIGRATIONS: list[tuple[str, MigrationStep]] = [
    (
        version,
        _apply_migration_0022_security_integrity
        if version == "0022_security_integrity"
        else step,
    )
    for version, step in _legacy.MIGRATIONS
]
MIGRATIONS.extend(
    [
        ("0037_foundation_module_instances", apply_0037_foundation_module_instances),
        ("0038_durable_assistant_runs", apply_0038_durable_assistant_runs),
    ]
)


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
