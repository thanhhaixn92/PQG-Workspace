"""Tests for DIRAP v3.0 Knowledge Records slice.

Covers:
- Creating a draft knowledge record from exactly one fresh extraction record
  with durable source provenance (task, extraction, record, hash, version)
- Rejecting stale extractions (409) and foreign/unknown IDs (404)
- Idempotency: same key + same payload replays; same key + different payload conflicts
- Audit event on successful creation
- List/detail scoped to the work item
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import aiosqlite
import pytest
from httpx import AsyncClient

from app.services.extraction import EXTRACTOR_VERSION


async def _setup_session_workitem_file(
    client: AsyncClient, tmp_path: Path, file_name: str, content: bytes
) -> tuple[str, str, str]:
    """Create session + work item + attached source file; return (session_id, task_id, source_file_id)."""
    resp = await client.post("/api/sessions", json={"title": "KR", "workspace_path": str(tmp_path)})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "KR WI"})
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    file_path = tmp_path / file_name
    file_path.write_bytes(content)

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": file_name},
    )
    assert resp.status_code == 201
    source_file_id = resp.json()["id"]
    return session_id, task_id, source_file_id


async def _extract_and_first_record(
    client: AsyncClient, task_id: str, source_file_id: str
) -> tuple[str, str]:
    """Extract; return (extraction_id, first extraction_record_id)."""
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{source_file_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    extraction_id = data["extraction"]["id"]
    assert data["records"], "expected at least one record"
    return extraction_id, data["records"][0]["id"]


async def _created_audit_events(tmp_path: Path, record_id: str) -> list[dict]:
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT session_id, actor, action, target, payload_json FROM audit_events "
            "WHERE action = 'dirap.knowledge_record.created' AND target = ?",
            (record_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# -----------------------------------------------------------------------------
# Happy path + provenance
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_knowledge_record_happy_path(client: AsyncClient, tmp_path: Path) -> None:
    """A fresh extraction record becomes a draft with full source provenance."""
    content = b"d\xc3\xb2ng 1\ndong 2\n"
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "note.txt", content
    )
    extraction_id, record_id = await _extract_and_first_record(client, task_id, sf_id)

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={
            "extraction_id": extraction_id,
            "extraction_record_id": record_id,
            "note": "candidate fact",
        },
    )
    assert resp.status_code == 201
    kr = resp.json()

    assert kr["task_id"] == task_id
    assert kr["extraction_id"] == extraction_id
    assert kr["extraction_record_id"] == record_id
    assert kr["source_file_id"] == sf_id
    assert kr["source_sha256"] == hashlib.sha256(content).hexdigest()
    assert kr["extractor_version"] == EXTRACTOR_VERSION
    assert kr["provenance"] == "line 1"
    assert kr["content"] == "dòng 1"
    assert kr["status"] == "draft"  # never auto-verified/approved
    assert kr["note"] == "candidate fact"
    assert kr["created_at"] == kr["updated_at"]

    # Creation produced an audit event
    events = await _created_audit_events(tmp_path, kr["id"])
    assert len(events) == 1
    assert events[0]["session_id"] == session_id
    payload = json.loads(events[0]["payload_json"])
    assert payload["task_id"] == task_id
    assert payload["status"] == "draft"
    assert payload["source_sha256"] == kr["source_sha256"]


@pytest.mark.asyncio
async def test_create_knowledge_record_status_always_draft(client: AsyncClient, tmp_path: Path) -> None:
    """Even with a note, the record is a draft — no verified/in-use claims."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "fact\n".encode()
    )
    extraction_id, record_id = await _extract_and_first_record(client, task_id, sf_id)
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_id},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


# -----------------------------------------------------------------------------
# Stale / foreign-ID rejection
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_from_stale_extraction_rejected(client: AsyncClient, tmp_path: Path) -> None:
    """A stale extraction must be rejected clearly (409), never silently used."""
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "v1 content\n".encode()
    )
    extraction_id, record_id = await _extract_and_first_record(client, task_id, sf_id)

    # Change the source so the extraction is no longer current
    (tmp_path / "doc.txt").write_text("v2 content changed\n", encoding="utf-8")

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_id},
    )
    assert resp.status_code == 409
    assert "stale" in resp.json()["detail"].lower()

    # No knowledge record was created
    list_resp = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records")
    assert list_resp.json() == []
    assert session_id  # session still valid (keeps tuple unpacking honest)


@pytest.mark.asyncio
async def test_create_foreign_extraction_rejected(client: AsyncClient, tmp_path: Path) -> None:
    """An extraction from another work item must be rejected (404)."""
    _, task_a, sf_a = await _setup_session_workitem_file(
        client, tmp_path, "a.txt", "a\n".encode()
    )
    extraction_a, record_a = await _extract_and_first_record(client, task_a, sf_a)

    # Second work item in the same session
    detail_a = await client.get(f"/api/dirap/work-items/{task_a}")
    session_id = detail_a.json()["work_item"]["session_id"]
    resp = await client.post(
        "/api/dirap/work-items", json={"session_id": session_id, "title": "WI B"}
    )
    assert resp.status_code == 201
    task_b = resp.json()["task_id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_b}/knowledge-records",
        json={"extraction_id": extraction_a, "extraction_record_id": record_a},
    )
    assert resp.status_code == 404
    assert "belong" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_unknown_extraction_404(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, _ = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "x\n".encode()
    )
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": "dext-nonexistent", "extraction_record_id": "drec-x"},
    )
    assert resp.status_code == 404
    assert "extraction" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_record_not_in_extraction_404(client: AsyncClient, tmp_path: Path) -> None:
    """A record ID that does not belong to the given extraction is rejected."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "x\n".encode()
    )
    extraction_id, _ = await _extract_and_first_record(client, task_id, sf_id)
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={
            "extraction_id": extraction_id,
            "extraction_record_id": "drec-does-not-exist",
        },
    )
    assert resp.status_code == 404
    assert "record" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# Idempotency
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_idempotent_replay(client: AsyncClient, tmp_path: Path) -> None:
    """Same Idempotency-Key + same payload: one record, second call replays with 200."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "fact\n".encode()
    )
    extraction_id, record_id = await _extract_and_first_record(client, task_id, sf_id)

    payload = {
        "extraction_id": extraction_id,
        "extraction_record_id": record_id,
        "note": "same",
    }
    headers = {"Idempotency-Key": "kr-key-1"}
    resp1 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records", json=payload, headers=headers
    )
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]

    resp2 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records", json=payload, headers=headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == first_id

    # Exactly one knowledge record and one created-audit exist
    list_resp = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records")
    assert len(list_resp.json()) == 1
    assert len(await _created_audit_events(tmp_path, first_id)) == 1


@pytest.mark.asyncio
async def test_create_idempotent_concurrent_request_creates_once(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, source_file_id = await _setup_session_workitem_file(client, tmp_path, "concurrent.txt", b"fact\n")
    extraction_id, extraction_record_id = await _extract_and_first_record(client, task_id, source_file_id)
    path = f"/api/dirap/work-items/{task_id}/knowledge-records"
    payload = {"extraction_id": extraction_id, "extraction_record_id": extraction_record_id}
    headers = {"Idempotency-Key": "knowledge-concurrent-key"}
    first, second = await asyncio.gather(
        client.post(path, json=payload, headers=headers), client.post(path, json=payload, headers=headers),
    )
    assert sorted([first.status_code, second.status_code]) in ([200, 201], [201, 409])
    listed = await client.get(path)
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_create_idempotency_conflict(client: AsyncClient, tmp_path: Path) -> None:
    """Same Idempotency-Key + different payload: 409 conflict, nothing created."""
    content = b"fact 1\nfact 2\n"
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", content
    )
    extraction_id, record_1 = await _extract_and_first_record(client, task_id, sf_id)

    # Second record id inside the same extraction
    detail = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/{extraction_id}"
    )
    record_2 = detail.json()["records"][1]["id"]

    headers = {"Idempotency-Key": "kr-key-conflict"}
    resp1 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_1},
        headers=headers,
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/dirap/work-items/{task_id}/knowledge-records",
        json={"extraction_id": extraction_id, "extraction_record_id": record_2},
        headers=headers,
    )
    assert resp2.status_code == 409
    assert "different payload" in resp2.json()["detail"].lower()

    # Only the first record exists
    list_resp = await client.get(f"/api/dirap/work-items/{task_id}/knowledge-records")
    assert len(list_resp.json()) == 1


# -----------------------------------------------------------------------------
# List / detail scoping
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_and_detail_scoped_to_work_item(client: AsyncClient, tmp_path: Path) -> None:
    """Knowledge records are only visible under their own work item."""
    content = b"shared fact\n"
    _, task_a, sf_a = await _setup_session_workitem_file(
        client, tmp_path, "a.txt", content
    )
    extraction_a, record_a = await _extract_and_first_record(client, task_a, sf_a)
    resp = await client.post(
        f"/api/dirap/work-items/{task_a}/knowledge-records",
        json={"extraction_id": extraction_a, "extraction_record_id": record_a},
    )
    assert resp.status_code == 201
    kr_id = resp.json()["id"]

    # Second work item in a second session
    resp = await client.post(
        "/api/sessions", json={"title": "KR2", "workspace_path": str(tmp_path)}
    )
    session_b = resp.json()["id"]
    resp = await client.post(
        "/api/dirap/work-items", json={"session_id": session_b, "title": "WI B"}
    )
    task_b = resp.json()["task_id"]

    # List under task B is empty
    list_b = await client.get(f"/api/dirap/work-items/{task_b}/knowledge-records")
    assert list_b.json() == []

    # Detail under task B is 404
    detail_b = await client.get(f"/api/dirap/work-items/{task_b}/knowledge-records/{kr_id}")
    assert detail_b.status_code == 404

    # List/detail under task A work
    list_a = await client.get(f"/api/dirap/work-items/{task_a}/knowledge-records")
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["id"] == kr_id

    detail_a = await client.get(f"/api/dirap/work-items/{task_a}/knowledge-records/{kr_id}")
    assert detail_a.status_code == 200
    assert detail_a.json()["content"] == "shared fact"
    assert detail_a.json()["status"] == "draft"

    # Unknown record id under a valid work item → 404
    miss = await client.get(f"/api/dirap/work-items/{task_a}/knowledge-records/dkr-nonexistent")
    assert miss.status_code == 404
