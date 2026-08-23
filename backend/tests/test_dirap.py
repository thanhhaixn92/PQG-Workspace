"""Tests for DIRAP v3.0 Work Item endpoints.

Covers:
- Creating work items (with and without idempotency)
- Listing work items
- Getting work item detail (task package with audit trail)
- Attaching source files (with sandbox validation)
- Path safety: traversal, absolute outside, symlink escape
- Audit events for all mutations
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import aiosqlite
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_work_item(client: AsyncClient, tmp_path: Path) -> None:
    """Create a DIRAP work item from a session."""
    # 1. Create a session
    resp = await client.post("/api/sessions", json={"title": "Test", "workspace_path": str(tmp_path)})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    # 2. Create a DIRAP work item
    resp = await client.post(
        "/api/dirap/work-items",
        json={"session_id": session_id, "title": "Work 1", "goal": "Xử lý tài liệu A"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Work 1"
    assert data["goal"] == "Xử lý tài liệu A"
    assert data["session_id"] == session_id
    assert data["status"] == "queued"
    assert data["task_type"] == "dirap_work_item"
    assert data["duplicate"] is False
    assert len(data["source_files"]) == 0

    # 3. Verify audit event
    detail_resp = await client.get(f"/api/dirap/work-items/{data['task_id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["audit_events"]) > 0
    actions = [e["action"] for e in detail["audit_events"]]
    assert "dirap.work_item.created" in actions


@pytest.mark.asyncio
async def test_create_work_item_idempotency(client: AsyncClient, tmp_path: Path) -> None:
    """Idempotency-Key: same key + same payload returns original (200)."""
    resp = await client.post("/api/sessions", json={"title": "Idempotency", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    payload = {"session_id": session_id, "title": "Idempotent Work", "goal": "Test"}
    headers = {"Idempotency-Key": "key-123"}

    resp1 = await client.post("/api/dirap/work-items", json=payload, headers=headers)
    assert resp1.status_code == 201
    task_id = resp1.json()["task_id"]

    resp2 = await client.post("/api/dirap/work-items", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["task_id"] == task_id
    assert resp2.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_create_work_item_no_session(client: AsyncClient) -> None:
    """Creating a work item with a non-existent session returns 404."""
    resp = await client.post(
        "/api/dirap/work-items",
        json={"session_id": "nonexistent", "title": "No session"},
    )
    assert resp.status_code == 404
    assert "session" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_work_items(client: AsyncClient, tmp_path: Path) -> None:
    """List work items, filtered by session."""
    resp = await client.post("/api/sessions", json={"title": "S1", "workspace_path": str(tmp_path / "s1")})
    s1 = resp.json()["id"]
    resp = await client.post("/api/sessions", json={"title": "S2", "workspace_path": str(tmp_path / "s2")})
    s2 = resp.json()["id"]

    # Create 3 work items
    await client.post("/api/dirap/work-items", json={"session_id": s1, "title": "W1"})
    await client.post("/api/dirap/work-items", json={"session_id": s1, "title": "W2"})
    await client.post("/api/dirap/work-items", json={"session_id": s2, "title": "W3"})

    # List all
    resp = await client.get("/api/dirap/work-items")
    assert resp.status_code == 200
    all_items = resp.json()
    assert len(all_items) == 3

    # Filter by session
    resp = await client.get(f"/api/dirap/work-items?session_id={s1}")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(item["session_id"] == s1 for item in items)


@pytest.mark.asyncio
async def test_work_item_detail_with_audit(client: AsyncClient, tmp_path: Path) -> None:
    """Get full task package: work item + source files + audit events."""
    resp = await client.post("/api/sessions", json={"title": "Detail Test", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    # Create work item
    resp = await client.post(
        "/api/dirap/work-items",
        json={"session_id": session_id, "title": "Detail", "goal": "Chi tiết"},
    )
    task_id = resp.json()["task_id"]

    # Get detail
    resp = await client.get(f"/api/dirap/work-items/{task_id}")
    assert resp.status_code == 200
    detail = resp.json()

    assert detail["work_item"]["task_id"] == task_id
    assert detail["work_item"]["session_title"] == "Detail Test"
    assert detail["work_item"]["workspace_path"] == str(tmp_path)
    assert len(detail["work_item"]["source_files"]) == 0
    assert len(detail["audit_events"]) >= 1


@pytest.mark.asyncio
async def test_attach_source_file(client: AsyncClient, tmp_path: Path) -> None:
    """Attach a workspace-scoped source file."""
    resp = await client.post("/api/sessions", json={"title": "File Attach", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    # Create work item
    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "With Files"})
    task_id = resp.json()["task_id"]

    # Create a test source file in workspace
    (tmp_path / "source.txt").write_text("test content", encoding="utf-8")
    (tmp_path / "subdir").mkdir(exist_ok=True)
    (tmp_path / "subdir" / "nested.docx").write_text("nested content", encoding="utf-8")

    # Attach first file
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "source.txt", "note": "Tài liệu chính"},
    )
    assert resp.status_code == 201
    sf = resp.json()
    assert sf["file_path"] == "source.txt"
    assert sf["file_name"] == "source.txt"
    assert sf["note"] == "Tài liệu chính"

    # Attach nested file
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "subdir/nested.docx", "note": None},
    )
    assert resp.status_code == 201

    # Verify in detail
    resp = await client.get(f"/api/dirap/work-items/{task_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["work_item"]["source_files"]) == 2

    # Verify audit event
    actions = [e["action"] for e in detail["audit_events"]]
    assert "dirap.source_file.attached" in actions


@pytest.mark.asyncio
async def test_attach_source_file_path_traversal(client: AsyncClient, tmp_path: Path) -> None:
    """Relative path traversal must be rejected."""
    resp = await client.post("/api/sessions", json={"title": "Traversal", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "Traversal Test"})
    task_id = resp.json()["task_id"]

    # Create a file outside workspace
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret")

    # 1. Relative traversal via ..
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "../secret.txt"},
    )
    assert resp.status_code == 403

    # 2. Mixed slash/backslash traversal
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "..\\secret.txt"},
    )
    assert resp.status_code == 403

    # 3. Absolute path outside workspace
    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": outside.as_posix()},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attach_source_file_not_found(client: AsyncClient, tmp_path: Path) -> None:
    """Attaching a non-existent file returns 404."""
    resp = await client.post("/api/sessions", json={"title": "NotFound", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "NoFile"})
    task_id = resp.json()["task_id"]

    resp = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "nonexistent.txt"},
    )
    assert resp.status_code == 404


def _try_create_link(link_path: Path, target: Path, is_dir: bool = False) -> bool:
    """Try to create a symlink (or junction on Windows).

    Returns True if the link was created, False if the platform doesn't
    support link creation in the current process context.
    """
    try:
        os.symlink(target, link_path, target_is_directory=is_dir)
        return True
    except (OSError, NotImplementedError):
        pass
    # Windows fallback: try mklink junction
    if os.name == "nt":
        target_s = str(target)
        link_s = str(link_path)
        if is_dir:
            cmd = f'mklink /J "{link_s}" "{target_s}"'
        else:
            cmd = f'mklink "{link_s}" "{target_s}"'
        ret = os.system(cmd)
        if ret == 0 and link_path.exists():
            return True
        if ret == 0 and not link_path.exists():
            # mklink exited 0 but link not created - unsupported environment
            pass
    return False


@pytest.mark.asyncio
async def test_attach_source_file_idempotency(client: AsyncClient, tmp_path: Path) -> None:
    """Idempotency-Key on source-file attach: replay returns 200, diff payload 409."""
    # Setup session + work item + source file
    (tmp_path / "doc.txt").write_text("data")
    resp = await client.post("/api/sessions", json={"title": "Idem Src", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "Idem"})
    task_id = resp.json()["task_id"]

    headers = {"Idempotency-Key": "src-key-001"}

    # First call — 201
    resp1 = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "doc.txt", "note": "original"},
        headers=headers,
    )
    assert resp1.status_code == 201
    file_id = resp1.json()["id"]
    assert resp1.json()["file_path"] == "doc.txt"

    # Same key + same payload — 200 replay with same file_id
    resp2 = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "doc.txt", "note": "original"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == file_id
    assert resp2.json()["file_path"] == "doc.txt"
    assert resp2.json()["note"] == "original"

    # Same key + different payload — 409 conflict
    resp3 = await client.post(
        f"/api/dirap/work-items/{task_id}/source-files",
        json={"file_path": "doc.txt", "note": "different"},
        headers=headers,
    )
    assert resp3.status_code == 409
    assert "different payload" in resp3.json()["detail"].lower()

    # Also confirm only ONE row in DB (replay didn't create a second)
    resp_detail = await client.get(f"/api/dirap/work-items/{task_id}")
    assert resp_detail.status_code == 200
    source_files = resp_detail.json()["work_item"]["source_files"]
    assert len(source_files) == 1


@pytest.mark.asyncio
async def test_attach_source_file_concurrent_same_key_creates_once(client: AsyncClient, tmp_path: Path) -> None:
    (tmp_path / "concurrent.txt").write_text("data")
    session = await client.post("/api/sessions", json={"title": "Concurrent source", "workspace_path": str(tmp_path)})
    work = await client.post("/api/dirap/work-items", json={"session_id": session.json()["id"], "title": "Concurrent"})
    task_id = work.json()["task_id"]
    path = f"/api/dirap/work-items/{task_id}/source-files"
    payload = {"file_path": "concurrent.txt", "note": "one request only"}
    headers = {"Idempotency-Key": "concurrent-source-key"}

    first, second = await asyncio.gather(
        client.post(path, json=payload, headers=headers),
        client.post(path, json=payload, headers=headers),
    )
    assert sorted([first.status_code, second.status_code]) in ([200, 201], [201, 409])

    detail = await client.get(f"/api/dirap/work-items/{task_id}")
    assert len(detail.json()["work_item"]["source_files"]) == 1


@pytest.mark.asyncio
async def test_attach_source_file_symlink_escape(client: AsyncClient, tmp_path: Path) -> None:
    """Symlink/junction pointing outside workspace must be rejected.

    If the environment cannot create symlinks (e.g. Windows without
    Developer Mode / admin), the test is skipped with a system-specific reason.
    """
    # Setup session + work item
    resp = await client.post("/api/sessions", json={"title": "Symlink", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "SymlinkTest"})
    task_id = resp.json()["task_id"]

    # Create a file outside the workspace
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret data", encoding="utf-8")

    # Try to create a symlink inside workspace → outside_dir
    link_path = tmp_path / "link_to_outside"
    link_created = _try_create_link(link_path, outside_file, is_dir=False)

    if not link_created:
        # For junctions we need a dir target — try junction approach
        link_dir = tmp_path / "link_dir"
        link_dir_created = _try_create_link(link_dir, outside_dir, is_dir=True)
        if not link_dir_created:
            pytest.skip("Symlink/junction creation not supported in this environment — "
                        "requires Windows Developer Mode or elevated privileges")
        # Junction to dir exists; try accessing a file through it
        link_file = link_dir / "secret.txt"
        if not link_file.exists():
            pytest.skip("Junction created but target file not accessible through it")
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/source-files",
            json={"file_path": "link_dir/secret.txt"},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"].lower()
        assert "traversal" in detail or "escape" in detail
    elif not link_path.exists():
        pytest.skip("Symlink reported created but path does not exist — platform inconsistency")
    else:
        # Symlink exists; try attaching through the link
        resp = await client.post(
            f"/api/dirap/work-items/{task_id}/source-files",
            json={"file_path": "link_to_outside"},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"].lower()
        assert "traversal" in detail or "escape" in detail
