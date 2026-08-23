"""Signature verification for Marketplace catalogs.

Catalog ingestion is deliberately server-side only.  Browser clients can list
verified records but cannot submit a URL, a raw Git reference, or a signature.
"""
from __future__ import annotations

import base64
import json
import re
import time
from hashlib import sha256
from typing import Any

import aiosqlite
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from app.settings import Settings

_HASH = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_MANIFEST_KEYS = {"name", "publisher", "entrypoint", "permissions", "network_domains", "dependencies", "changelog"}


def canonical_catalog_payload(catalog_name: str, packages: list[dict[str, Any]]) -> bytes:
    """Stable bytes signed by the catalog publisher; no transport fields."""
    return json.dumps({"catalog_name": catalog_name, "packages": packages}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _decode(value: str, label: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid {label} encoding") from exc


def verify_catalog_signature(settings: Settings, catalog_name: str, packages: list[dict[str, Any]], signature_b64: str) -> None:
    pinned_key = settings.marketplace_catalog_public_keys.get(catalog_name)
    if not pinned_key:
        raise ValueError("Catalog signer is not pinned")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(pinned_key, "catalog public key")).verify(_decode(signature_b64, "catalog signature"), canonical_catalog_payload(catalog_name, packages))
    except InvalidSignature as exc:
        raise ValueError("Catalog signature is invalid") from exc


def _validated_manifest(item: dict[str, Any]) -> tuple[str, str, str, str, dict[str, Any]]:
    package_id = str(item.get("package_id", ""))
    version = str(item.get("version", ""))
    package_hash = str(item.get("package_hash", "")).lower()
    manifest = item.get("manifest")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,119}", package_id) or not version or not _HASH.fullmatch(package_hash):
        raise ValueError("Catalog package identity is invalid")
    if not isinstance(manifest, dict) or not _REQUIRED_MANIFEST_KEYS.issubset(manifest):
        raise ValueError("Catalog manifest is incomplete")
    if any(not isinstance(manifest[key], list) for key in ("permissions", "network_domains", "dependencies")):
        raise ValueError("Catalog manifest permissions must be lists")
    # Catalogs describe an immutable package. Downloads/extraction/runtime are
    # a separate controlled pipeline and never happen in this ingestion path.
    return package_id, version, str(manifest["publisher"]), package_hash, manifest


async def ingest_verified_catalog(conn: aiosqlite.Connection, settings: Settings, catalog_name: str, packages: list[dict[str, Any]], signature_b64: str) -> int:
    """Verify every catalog atomically, then make its manifests discoverable."""
    verify_catalog_signature(settings, catalog_name, packages, signature_b64)
    validated = [_validated_manifest(item) for item in packages]
    now = int(time.time())
    await conn.execute("BEGIN IMMEDIATE")
    try:
        for package_id, version, publisher, package_hash, manifest in validated:
            await conn.execute(
                """INSERT INTO marketplace_packages (package_id, version, catalog_name, publisher, manifest_json, package_hash, signature_valid, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                   ON CONFLICT(package_id, version, catalog_name) DO UPDATE SET publisher = excluded.publisher,
                     manifest_json = excluded.manifest_json, package_hash = excluded.package_hash, signature_valid = 1""",
                (package_id, version, catalog_name, publisher, json.dumps(manifest, sort_keys=True), package_hash, now),
            )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    return len(validated)
