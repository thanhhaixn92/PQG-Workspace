"""F5 Foundation Module persistence and user-only administration tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.connection import open_db
from app.db.migrations import run_migrations
from app.main import create_app
from app.settings import Settings

ADMIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "Sec-Fetch-Site": "same-origin",
}


async def _module(client: AsyncClient, module_id: str) -> dict:
    response = await client.get("/api/modules")
    assert response.status_code == 200, response.text
    return next(item for item in response.json() if item["module_id"] == module_id)


@pytest.mark.asyncio
async def test_0037_creates_and_seeds_module_instances(migrated_db_path):
    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT version FROM schema_migrations WHERE version = '0037_foundation_module_instances'"
        ) as cur:
            assert await cur.fetchone() is not None
        async with conn.execute(
            "SELECT module_id, attached, sort_order, revision FROM module_instances ORDER BY sort_order, module_id"
        ) as cur:
            rows = [tuple(row) async for row in cur]
    finally:
        await conn.close()

    assert rows == [
        ("work", 1, 10, 1),
        ("documents", 0, 20, 1),
        ("knowledge", 1, 30, 1),
        ("review", 1, 40, 1),
        ("reports", 1, 50, 1),
        ("memory", 0, 60, 1),
        ("memory-hub", 0, 70, 1),
        ("local-data", 0, 80, 1),
        ("research", 0, 90, 1),
    ]


@pytest.mark.asyncio
async def test_migration_registry_remains_idempotent_with_0037(temp_db_path):
    await run_migrations(temp_db_path)
    await run_migrations(temp_db_path)
    conn = await open_db(temp_db_path)
    try:
        async with conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = '0037_foundation_module_instances'"
        ) as cur:
            assert (await cur.fetchone())[0] == 1
        async with conn.execute("SELECT COUNT(*) FROM module_instances") as cur:
            assert (await cur.fetchone())[0] == 9
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_read_projection_does_not_require_admin_origin(client):
    response = await client.get("/api/modules")
    assert response.status_code == 200
    payload = response.json()
    assert {item["module_id"] for item in payload} == {
        "work", "documents", "knowledge", "review", "reports",
        "memory", "memory-hub", "local-data", "research",
    }
    assert all("config" in item for item in payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_config", ["{invalid", "[]", "null"])
async def test_read_projection_fails_visible_on_invalid_config_json(
    client,
    migrated_db_path,
    stored_config,
):
    conn = await open_db(migrated_db_path)
    try:
        await conn.execute(
            "UPDATE module_instances SET config_json = ? WHERE module_id = 'work'",
            (stored_config,),
        )
        await conn.commit()
    finally:
        await conn.close()

    response = await client.get("/api/modules")
    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "MODULE_CONFIG_INVALID",
        "message": "Stored Module config is invalid; repair local Module state before continuing",
    }


@pytest.mark.asyncio
async def test_admin_mutation_rejects_corrupt_config_before_write(client, migrated_db_path):
    work = await _module(client, "work")
    conn = await open_db(migrated_db_path)
    try:
        await conn.execute(
            "UPDATE module_instances SET config_json = ? WHERE module_id = 'work'",
            ("{invalid",),
        )
        await conn.commit()
    finally:
        await conn.close()

    response = await client.post(
        "/api/admin/modules/work/detach",
        json={"expected_revision": work["revision"]},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "MODULE_CONFIG_INVALID"

    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT attached, revision, config_json FROM module_instances WHERE module_id = 'work'"
        ) as cur:
            row = await cur.fetchone()
        assert tuple(row) == (1, work["revision"], "{invalid")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_admin_mutation_requires_interactive_browser_origin(client):
    work = await _module(client, "work")
    response = await client.post(
        "/api/admin/modules/work/detach",
        json={"expected_revision": work["revision"]},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "USER_ADMIN_INTERACTIVE_REQUIRED"


@pytest.mark.asyncio
async def test_admin_mutation_rejects_cross_site_origin(client):
    work = await _module(client, "work")
    response = await client.post(
        "/api/admin/modules/work/detach",
        json={"expected_revision": work["revision"]},
        headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "USER_ADMIN_INTERACTIVE_REQUIRED"


@pytest.mark.asyncio
async def test_forged_actor_header_cannot_create_admin_identity(temp_db_path):
    await run_migrations(temp_db_path)
    settings = Settings(
        db_path=str(temp_db_path),
        cors_origins=["http://localhost:5173"],
        hermes_dev_mock=False,
        log_level="WARNING",
        outbox_dispatcher_enabled=False,
        local_actor_subject=None,
    )
    application = create_app(settings_override=settings)
    async with AsyncClient(
        transport=ASGITransport(app=application, client=("127.0.0.1", 12345)),
        base_url="http://testserver",
    ) as no_actor_client:
        response = await no_actor_client.post(
            "/api/admin/modules/work/detach",
            json={"expected_revision": 1},
            headers={**ADMIN_HEADERS, "X-Actor": "user"},
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "IDENTITY_ENFORCEMENT_INSUFFICIENT"


@pytest.mark.asyncio
async def test_attach_and_detach_are_revisioned_and_preserve_module_row(client, migrated_db_path):
    documents = await _module(client, "documents")
    assert documents["attached"] is False

    attach = await client.post(
        "/api/admin/modules/documents/attach",
        json={"expected_revision": documents["revision"]},
        headers=ADMIN_HEADERS,
    )
    assert attach.status_code == 200, attach.text
    attached = attach.json()
    assert attached["attached"] is True
    assert attached["revision"] == documents["revision"] + 1

    detach = await client.post(
        "/api/admin/modules/documents/detach",
        json={"expected_revision": attached["revision"]},
        headers=ADMIN_HEADERS,
    )
    assert detach.status_code == 200, detach.text
    detached = detach.json()
    assert detached["attached"] is False
    assert detached["revision"] == attached["revision"] + 1

    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            "SELECT module_id, config_json, config_version FROM module_instances WHERE module_id = 'documents'"
        ) as cur:
            row = await cur.fetchone()
        assert tuple(row) == ("documents", "{}", 1)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rename_changes_display_only_and_rejects_stale_revision(client):
    knowledge = await _module(client, "knowledge")
    response = await client.patch(
        "/api/admin/modules/knowledge",
        json={"display_name": "  Kho tri thức  ", "expected_revision": knowledge["revision"]},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200, response.text
    renamed = response.json()
    assert renamed["module_id"] == "knowledge"
    assert renamed["id"] == knowledge["id"]
    assert renamed["display_name"] == "Kho tri thức"
    assert renamed["revision"] == knowledge["revision"] + 1

    stale = await client.patch(
        "/api/admin/modules/knowledge",
        json={"display_name": "Tên cũ", "expected_revision": knowledge["revision"]},
        headers=ADMIN_HEADERS,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "MODULE_REVISION_CONFLICT"


@pytest.mark.asyncio
async def test_reorder_requires_complete_current_attached_set(client):
    projection = (await client.get("/api/modules")).json()
    attached = [item for item in projection if item["attached"]]
    by_id = {item["module_id"]: item for item in attached}
    new_order = ["reports", "work", "knowledge", "review"]
    response = await client.post(
        "/api/admin/modules/reorder",
        json={
            "module_ids": new_order,
            "expected_revisions": {module_id: by_id[module_id]["revision"] for module_id in new_order},
        },
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200, response.text
    result = [item for item in response.json() if item["attached"]]
    assert [item["module_id"] for item in result] == new_order
    assert [item["sort_order"] for item in result] == [10, 20, 30, 40]

    stale = await client.post(
        "/api/admin/modules/reorder",
        json={
            "module_ids": ["work", "knowledge"],
            "expected_revisions": {"work": 1, "knowledge": 1},
        },
        headers=ADMIN_HEADERS,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "MODULE_ORDER_STALE"


@pytest.mark.asyncio
async def test_module_admin_audit_uses_server_actor_not_browser_header(client, migrated_db_path):
    documents = await _module(client, "documents")
    response = await client.post(
        "/api/admin/modules/documents/attach",
        json={"expected_revision": documents["revision"]},
        headers={**ADMIN_HEADERS, "X-Actor": "forged-agent"},
    )
    assert response.status_code == 200

    conn = await open_db(migrated_db_path)
    try:
        async with conn.execute(
            """SELECT actor, action, target FROM audit_events
               WHERE action = 'foundation.module_attached' ORDER BY created_at DESC LIMIT 1"""
        ) as cur:
            row = await cur.fetchone()
        assert tuple(row) == ("user", "foundation.module_attached", "documents")
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_f5_exposes_no_module_delete_endpoint(client):
    response = await client.delete(
        "/api/admin/modules/work",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code in {404, 405}
