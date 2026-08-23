"""Safe Marketplace read/install state.

The app accepts only records that a server-side catalog verifier has already
stored.  There is deliberately no raw Git or arbitrary URL install endpoint.
On this local MVP, plugins remain disabled until OS-level isolation is
explicitly available; this prevents an attractive UI from becoming a false
security promise.
"""
from __future__ import annotations

import json
import time

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import InstalledPluginResponse, MarketplacePackageResponse
from app.dependencies import get_db
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


def _package(row: aiosqlite.Row) -> MarketplacePackageResponse:
    return MarketplacePackageResponse(package_id=row["package_id"], version=row["version"], catalog_name=row["catalog_name"], publisher=row["publisher"], manifest=json.loads(row["manifest_json"]), package_hash=row["package_hash"], signature_valid=bool(row["signature_valid"]))


def _installed(row: aiosqlite.Row) -> InstalledPluginResponse:
    return InstalledPluginResponse(package_id=row["package_id"], version=row["version"], catalog_name=row["catalog_name"], manifest=json.loads(row["manifest_json"]), install_state=row["install_state"], previous_version=row["previous_version"], installed_at=row["installed_at"], updated_at=row["updated_at"])


@router.get("/catalog", response_model=list[MarketplacePackageResponse])
async def list_catalog(conn: aiosqlite.Connection = Depends(get_db)) -> list[MarketplacePackageResponse]:
    async with conn.execute("SELECT * FROM marketplace_packages WHERE signature_valid = 1 ORDER BY package_id, version DESC") as cur:
        rows = await cur.fetchall()
    return [_package(row) for row in rows]


@router.get("/installed", response_model=list[InstalledPluginResponse])
async def list_installed(conn: aiosqlite.Connection = Depends(get_db)) -> list[InstalledPluginResponse]:
    async with conn.execute("SELECT * FROM installed_plugins WHERE install_state != 'removed' ORDER BY updated_at DESC") as cur:
        rows = await cur.fetchall()
    return [_installed(row) for row in rows]


@router.post("/{package_id}/{version}/install", response_model=InstalledPluginResponse)
async def install_verified_package(package_id: str, version: str, conn: aiosqlite.Connection = Depends(get_db)) -> InstalledPluginResponse:
    async with conn.execute("SELECT * FROM marketplace_packages WHERE package_id = ? AND version = ? AND signature_valid = 1", (package_id, version)) as cur:
        package = await cur.fetchone()
    if package is None: raise HTTPException(status_code=404, detail="Verified Marketplace package not found")
    now = int(time.time())
    async with conn.execute("SELECT version FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        previous = await cur.fetchone()
    await conn.execute(
        """INSERT INTO installed_plugins (package_id, version, catalog_name, manifest_json, install_state, previous_version, installed_at, updated_at)
           VALUES (?, ?, ?, ?, 'cannot_run_safely', ?, ?, ?)
           ON CONFLICT(package_id) DO UPDATE SET version = excluded.version, catalog_name = excluded.catalog_name,
             manifest_json = excluded.manifest_json, install_state = 'cannot_run_safely', previous_version = installed_plugins.version, updated_at = excluded.updated_at""",
        (package_id, version, package["catalog_name"], package["manifest_json"], previous[0] if previous and previous[0] != version else None, now, now),
    )
    await log_audit_event(conn, None, "user", "marketplace.plugin_installed_disabled", package_id, {"version": version, "isolation": "unavailable"}, commit=False)
    await conn.commit()
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        return _installed(await cur.fetchone())


@router.post("/{package_id}/rollback", response_model=InstalledPluginResponse)
async def rollback_plugin(package_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> InstalledPluginResponse:
    """Return to a retained, verified catalog version without starting code."""
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ? AND install_state != 'removed'", (package_id,)) as cur:
        installed = await cur.fetchone()
    if installed is None:
        raise HTTPException(status_code=404, detail="Installed plugin not found")
    if not installed["previous_version"]:
        raise HTTPException(status_code=409, detail="No retained Marketplace version is available for rollback")
    async with conn.execute("SELECT * FROM marketplace_packages WHERE package_id = ? AND version = ? AND signature_valid = 1", (package_id, installed["previous_version"])) as cur:
        package = await cur.fetchone()
    if package is None:
        raise HTTPException(status_code=409, detail="The retained version is no longer verified in the catalog")
    now = int(time.time())
    await conn.execute(
        "UPDATE installed_plugins SET version = ?, catalog_name = ?, manifest_json = ?, install_state = 'cannot_run_safely', previous_version = ?, updated_at = ? WHERE package_id = ?",
        (package["version"], package["catalog_name"], package["manifest_json"], installed["version"], now, package_id),
    )
    await log_audit_event(conn, None, "user", "marketplace.plugin_rolled_back_disabled", package_id, {"version": package["version"], "isolation": "unavailable"}, commit=False)
    await conn.commit()
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        return _installed(await cur.fetchone())


@router.post("/{package_id}/enable", response_model=InstalledPluginResponse)
async def enable_plugin(package_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> InstalledPluginResponse:
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        plugin = await cur.fetchone()
    if plugin is None: raise HTTPException(status_code=404, detail="Installed plugin not found")
    # There is no approved AppContainer/restricted-token launcher in this MVP.
    raise HTTPException(status_code=409, detail="Plugin cannot run safely on this machine until isolated runtime support is configured")


@router.post("/{package_id}/uninstall", response_model=InstalledPluginResponse)
async def uninstall_plugin(package_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> InstalledPluginResponse:
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        plugin = await cur.fetchone()
    if plugin is None: raise HTTPException(status_code=404, detail="Installed plugin not found")
    now = int(time.time())
    await conn.execute("UPDATE installed_plugins SET install_state = 'removed', updated_at = ? WHERE package_id = ?", (now, package_id))
    await log_audit_event(conn, None, "user", "marketplace.plugin_removed", package_id, {}, commit=False)
    await conn.commit()
    async with conn.execute("SELECT * FROM installed_plugins WHERE package_id = ?", (package_id,)) as cur:
        return _installed(await cur.fetchone())
