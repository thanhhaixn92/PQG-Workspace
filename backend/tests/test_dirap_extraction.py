"""Tests for DIRAP v3.0 Extraction slice.

Covers:
- Extraction for each supported type (.txt, .md, .csv, .json, .docx)
- Hash / provenance / extractor version / file type / status
- Stale marking when the source content changes
- Audit events for extraction and stale marking
- Unsupported file types (415)
- Invalid content (400)
- Missing source file on disk (404)
- Traversal and symlink escape enforced by the sandbox at extraction time
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import aiosqlite
import pytest
from httpx import AsyncClient

from app.api import dirap
from app.services.extraction import EXTRACTOR_VERSION


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def make_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a minimal .docx using only the standard library."""
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>",
        )


def _try_create_link(link_path: Path, target: Path, is_dir: bool = False) -> bool:
    """Try to create a symlink (or junction on Windows)."""
    try:
        os.symlink(target, link_path, target_is_directory=is_dir)
        return True
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        cmd = f'mklink /J "{str(link_path)}" "{str(target)}"' if is_dir else f'mklink "{str(link_path)}" "{str(target)}"'
        return os.system(cmd) == 0 and link_path.exists()
    return False


async def _setup_session_workitem_file(
    client: AsyncClient, tmp_path: Path, file_name: str, content: bytes
) -> tuple[str, str, Path]:
    """Create session + work item + attached source file; return (session_id, task_id, file_path)."""
    resp = await client.post("/api/sessions", json={"title": "Extract", "workspace_path": str(tmp_path)})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "Extract WI"})
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


# -----------------------------------------------------------------------------
# Per-type extraction
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_txt(client: AsyncClient, tmp_path: Path) -> None:
    content = b"d\xc3\xb2ng 1\ndong 2\n\n dong 3 \n"
    _, task_id, sf_id = await _setup_session_workitem_file(client, tmp_path, "note.txt", content)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()

    ext = data["extraction"]
    assert ext["status"] == "fresh"
    assert ext["file_type"] == "txt"
    assert ext["extractor_version"] == EXTRACTOR_VERSION
    assert ext["record_count"] == 3
    assert ext["source_sha256"] == hashlib.sha256(content).hexdigest()

    records = data["records"]
    assert [r["seq"] for r in records] == [1, 2, 3]
    assert records[0]["content"] == "dòng 1"
    assert records[0]["provenance"] == "line 1"
    assert records[2]["content"] == " dong 3 "
    assert records[2]["provenance"] == "line 4"  # empty line 3 skipped
    assert data["total_records"] == 3


@pytest.mark.asyncio
async def test_extract_md(client: AsyncClient, tmp_path: Path) -> None:
    content = "# Tài liệu\n\n- mục A\n- mục B\n".encode("utf-8")
    _, task_id, sf_id = await _setup_session_workitem_file(client, tmp_path, "doc.md", content)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["file_type"] == "md"
    assert data["extraction"]["record_count"] == 3
    contents = [r["content"] for r in data["records"]]
    assert contents == ["# Tài liệu", "- mục A", "- mục B"]
    assert [r["provenance"] for r in data["records"]] == ["line 1", "line 3", "line 4"]


@pytest.mark.asyncio
async def test_extract_csv(client: AsyncClient, tmp_path: Path) -> None:
    content = b"ten,tuoi\nAn,30\nBinh,25\n"
    _, task_id, sf_id = await _setup_session_workitem_file(client, tmp_path, "data.csv", content)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["file_type"] == "csv"
    assert data["extraction"]["record_count"] == 3  # header + 2 rows

    records = data["records"]
    assert records[0]["content"] == '["ten", "tuoi"]'
    assert records[0]["provenance"] == "row 1"
    assert records[1]["content"] == '["An", "30"]'
    assert records[1]["provenance"] == "row 2"
    assert records[2]["content"] == '["Binh", "25"]'


@pytest.mark.asyncio
async def test_extract_json_array(client: AsyncClient, tmp_path: Path) -> None:
    content = b'[{"ten": "A"}, {"ten": "B"}]'
    _, task_id, sf_id = await _setup_session_workitem_file(client, tmp_path, "items.json", content)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["file_type"] == "json"
    assert data["extraction"]["record_count"] == 2
    assert data["records"][0]["content"] == '{"ten": "A"}'
    assert data["records"][0]["provenance"] == "item[0]"
    assert data["records"][1]["provenance"] == "item[1]"


@pytest.mark.asyncio
async def test_extract_json_object(client: AsyncClient, tmp_path: Path) -> None:
    content = b'{"tieu_de": "X", "so_luong": 5}'
    _, task_id, sf_id = await _setup_session_workitem_file(client, tmp_path, "meta.json", content)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["record_count"] == 2
    by_prov = {r["provenance"]: r["content"] for r in data["records"]}
    assert by_prov[".tieu_de"] == '"X"'
    assert by_prov[".so_luong"] == "5"


@pytest.mark.asyncio
async def test_extract_docx(client: AsyncClient, tmp_path: Path) -> None:
    docx_path = tmp_path / "vanban.docx"
    make_docx(docx_path, ["Đoạn 1", "", "Đoạn 2 & 3", "  "])
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "vanban.docx", docx_path.read_bytes()
    )

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["file_type"] == "docx"
    # Non-empty paragraphs: "Đoạn 1", "Đoạn 2 & 3"
    assert data["extraction"]["record_count"] == 2
    records = data["records"]
    assert records[0]["content"] == "Đoạn 1"
    assert records[0]["provenance"] == "paragraph 1"
    assert records[1]["content"] == "Đoạn 2 & 3"
    assert records[1]["provenance"] == "paragraph 2"


@pytest.mark.asyncio
async def test_extract_docx_rejects_compressed_xml_bomb_without_persisting_success(
    client: AsyncClient, tmp_path: Path
) -> None:
    """A small ZIP must not cause a multi-megabyte XML parse in the backend."""
    docx_path = tmp_path / "oversized.docx"
    document = (
        b'<?xml version="1.0"?><w:document '
        b'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + (b"x" * (4 * 1024 * 1024 + 1))
        + b"</w:body></w:document>"
    )
    with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document)
    assert docx_path.stat().st_size < 1024 * 1024
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "oversized.docx", docx_path.read_bytes()
    )

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")

    assert resp.status_code == 400
    assert "exceeds extraction limit" in resp.json()["detail"]
    listed = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert listed.status_code == 200
    assert listed.json() == []


# -----------------------------------------------------------------------------
# Hash / provenance / stale
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_stale_on_source_change(client: AsyncClient, tmp_path: Path) -> None:
    """Old extraction becomes stale when the source content changes."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "v1 content\n".encode()
    )

    resp1 = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp1.status_code == 201
    ext1_id = resp1.json()["extraction"]["id"]
    hash1 = resp1.json()["extraction"]["source_sha256"]

    # Modify source content
    (tmp_path / "doc.txt").write_text("v2 content changed\n", encoding="utf-8")

    resp2 = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp2.status_code == 201
    ext2 = resp2.json()["extraction"]
    assert ext2["status"] == "fresh"
    assert ext2["source_sha256"] != hash1

    # First extraction is now stale
    resp_list = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert resp_list.status_code == 200
    rows = resp_list.json()
    assert len(rows) == 2
    by_id = {r["id"]: r for r in rows}
    assert by_id[ext1_id]["status"] == "stale"
    assert by_id[ext2["id"]]["status"] == "fresh"

    # Detail of stale extraction still has its records, but flagged stale
    resp_detail = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/{ext1_id}"
    )
    assert resp_detail.status_code == 200
    assert resp_detail.json()["extraction"]["status"] == "stale"
    assert resp_detail.json()["total_records"] == 1


@pytest.mark.asyncio
async def test_extract_uses_one_immutable_snapshot_when_source_changes_during_parse(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stored source revision and records must describe the same bytes.

    This simulates another process replacing the workspace file immediately
    after the endpoint has captured its raw snapshot but before parsing starts.
    """
    original = b"before change\n"
    replacement = b"after change\n"
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "snapshot.txt", original
    )
    real_extract = dirap.extract_bytes

    def mutate_source_then_extract(content: bytes, file_type: str) -> list[dict]:
        (tmp_path / "snapshot.txt").write_bytes(replacement)
        return real_extract(content, file_type)

    monkeypatch.setattr(dirap, "extract_bytes", mutate_source_then_extract)
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")

    assert resp.status_code == 201
    data = resp.json()
    assert data["extraction"]["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert data["records"][0]["content"] == "before change"
    assert (tmp_path / "snapshot.txt").read_bytes() == replacement


@pytest.mark.asyncio
async def test_extract_idempotent_unchanged_source(client: AsyncClient, tmp_path: Path) -> None:
    """Re-extracting unchanged source+version reuses the existing fresh result.

    Regression: previously each call created a duplicate fresh extraction.
    Now: same extraction ID, second call HTTP 200, one extraction + one set of
    records, and no second 'completed' audit event.
    """
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "unchanged\n".encode()
    )

    resp1 = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp1.status_code == 201
    ext1 = resp1.json()["extraction"]

    resp2 = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp2.status_code == 200
    ext2 = resp2.json()["extraction"]

    # Same extraction, same records, no duplicate
    assert ext2["id"] == ext1["id"]
    assert ext2["status"] == "fresh"
    assert resp2.json()["total_records"] == 1
    assert [r["content"] for r in resp2.json()["records"]] == ["unchanged"]

    # Only one extraction row and one record row exist
    resp_list = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    rows = resp_list.json()
    assert len(rows) == 1
    assert rows[0]["id"] == ext1["id"]
    assert rows[0]["status"] == "fresh"

    # Only one 'completed' audit event for the whole session
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action FROM audit_events WHERE session_id = ?",
            (session_id,),
        ) as cur:
            actions = [r["action"] for r in await cur.fetchall()]
    assert actions.count("dirap.extraction.completed") == 1
    assert "dirap.extraction.staled" not in actions


@pytest.mark.asyncio
async def test_extract_audit_events(client: AsyncClient, tmp_path: Path) -> None:
    """Extraction + stale marking must each create audit events."""
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "audit me\n".encode()
    )

    await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")

    # Change source → triggers stale marking
    (tmp_path / "doc.txt").write_text("audit me again\n", encoding="utf-8")
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201

    # Extraction events target the extraction/source-file ids, not the task,
    # so read them from the append-only audit table directly.
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action, target, payload_json FROM audit_events "
            "WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    actions = [r["action"] for r in rows]
    assert actions.count("dirap.extraction.completed") >= 2
    assert actions.count("dirap.extraction.staled") >= 1

    # Stale event must reference the previous hash (provenance preserved)
    stale_events = [r for r in rows if r["action"] == "dirap.extraction.staled"]
    assert "previous_sha256" in stale_events[0]["payload_json"]


# -----------------------------------------------------------------------------
# Freshness refresh on read (list/detail)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_marks_stale_on_source_change(client: AsyncClient, tmp_path: Path) -> None:
    """Listing must mark a changed-source extraction stale (with audit).

    Regression: previously the stale status was only applied when a new
    extraction was requested; the list could still show old data as fresh.
    """
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "v1 content\n".encode()
    )

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    ext_id = resp.json()["extraction"]["id"]

    # Modify the source, then list without re-extracting
    (tmp_path / "doc.txt").write_text("v2 content changed\n", encoding="utf-8")
    resp_list = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert resp_list.status_code == 200

    rows = resp_list.json()
    assert len(rows) == 1
    assert rows[0]["id"] == ext_id
    assert rows[0]["status"] == "stale"

    # The stale marking produced an audit event
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE session_id = ?",
            (session_id,),
        ) as cur:
            events = [dict(r) for r in await cur.fetchall()]
    stale_events = [e for e in events if e["action"] == "dirap.extraction.staled"]
    assert len(stale_events) == 1
    assert stale_events[0]["target"] == ext_id


@pytest.mark.asyncio
async def test_detail_marks_stale_on_source_change(client: AsyncClient, tmp_path: Path) -> None:
    """Fetching extraction detail must mark a changed-source extraction stale."""
    session_id, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "v1 content\n".encode()
    )

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    ext_id = resp.json()["extraction"]["id"]

    # Modify the source, then fetch detail without re-extracting
    (tmp_path / "doc.txt").write_text("v2 content changed\n", encoding="utf-8")
    resp_detail = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/{ext_id}"
    )
    assert resp_detail.status_code == 200
    data = resp_detail.json()
    assert data["extraction"]["id"] == ext_id
    assert data["extraction"]["status"] == "stale"
    assert data["total_records"] == 1  # records preserved, just flagged stale

    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT action, target FROM audit_events WHERE session_id = ?",
            (session_id,),
        ) as cur:
            events = [dict(r) for r in await cur.fetchall()]
    stale_events = [e for e in events if e["action"] == "dirap.extraction.staled"]
    assert len(stale_events) == 1
    assert stale_events[0]["target"] == ext_id


@pytest.mark.asyncio
async def test_list_and_detail_missing_file_clear_error(client: AsyncClient, tmp_path: Path) -> None:
    """When the source file is gone, list/detail must error clearly, not keep 'fresh'."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "gone\n".encode()
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201
    ext_id = resp.json()["extraction"]["id"]

    (tmp_path / "doc.txt").unlink()

    resp_list = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert resp_list.status_code == 404
    assert "not found" in resp_list.json()["detail"].lower()

    resp_detail = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/{ext_id}"
    )
    assert resp_detail.status_code == 404
    assert "not found" in resp_detail.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_sandbox_rejection_clear_error(client: AsyncClient, tmp_path: Path) -> None:
    """Sandbox rejection during the freshness check must error, not silently keep 'fresh'."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "ok.txt", b"safe\n"
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 201

    # Tamper the stored path to escape the workspace
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        await db.execute(
            "UPDATE dirap_source_files SET file_path = '../secret.txt' WHERE id = ?",
            (sf_id,),
        )
        await db.commit()

    resp_list = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert resp_list.status_code == 403
    assert "traversal" in resp_list.json()["detail"].lower()


# -----------------------------------------------------------------------------
# Error paths
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_unsupported_type(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.pdf", b"%PDF-1.4 fake"
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 415
    assert "unsupported" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_invalid_utf8(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "bad.txt", b"\xff\xfe\x00binary"
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 400
    assert "utf-8" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_invalid_json(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "bad.json", b"{not valid json"
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 400
    assert "json" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_missing_file_on_disk(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "ghost.txt", b"gone\n"
    )
    (tmp_path / "ghost.txt").unlink()
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_source_file_not_found(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "X", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    resp = await client.post("/api/dirap/work-items", json={"session_id": session_id, "title": "X"})
    task_id = resp.json()["task_id"]
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/nonexistent/extract")
    assert resp.status_code == 404


# -----------------------------------------------------------------------------
# Sandbox enforcement at extraction time
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_traversal_after_db_tamper(client: AsyncClient, tmp_path: Path) -> None:
    """Even if the stored file_path is tampered to escape, the sandbox rejects it."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "ok.txt", b"safe\n"
    )
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    # Tamper the stored path to point outside the workspace
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        await db.execute(
            "UPDATE dirap_source_files SET file_path = '../secret.txt' WHERE id = ?",
            (sf_id,),
        )
        await db.commit()

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 403
    assert "traversal" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_symlink_escape(client: AsyncClient, tmp_path: Path) -> None:
    """A symlink swapped in for the attached file must be rejected.

    Skips with a system-specific reason when link creation is unavailable.
    """
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", b"original\n"
    )

    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("secret", encoding="utf-8")

    # Replace the real file with a symlink pointing outside
    real = tmp_path / "doc.txt"
    real.unlink()
    if not _try_create_link(real, outside, is_dir=False):
        pytest.skip("Symlink creation not supported in this environment — "
                    "requires Windows Developer Mode or elevated privileges")

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "traversal" in detail or "escape" in detail


@pytest.mark.asyncio
async def test_extract_rejects_hard_link_to_file_outside_workspace(
    client: AsyncClient, tmp_path: Path
) -> None:
    """Hard links bypass resolve/reparse checks and therefore fail closed."""
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "linked.txt", b"original\n"
    )
    outside = tmp_path.parent / "outside_hardlink_source.txt"
    outside.write_text("sensitive outside content", encoding="utf-8")
    inside = tmp_path / "linked.txt"
    inside.unlink()
    os.link(outside, inside)

    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")

    assert resp.status_code == 403
    assert "hard-linked" in resp.json()["detail"].lower()
    async with aiosqlite.connect(str(tmp_path / "test_app.db")) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM dirap_extractions WHERE source_file_id = ?", (sf_id,)
        ) as cur:
            assert (await cur.fetchone())[0] == 0


# -----------------------------------------------------------------------------
# List + detail endpoints
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraction_list_and_detail(client: AsyncClient, tmp_path: Path) -> None:
    _, task_id, sf_id = await _setup_session_workitem_file(
        client, tmp_path, "doc.txt", "a\nb\nc\n".encode()
    )
    resp = await client.post(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extract")
    extraction_id = resp.json()["extraction"]["id"]

    # List
    resp = await client.get(f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == extraction_id
    assert rows[0]["record_count"] == 3

    # Detail with preview limit
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/{extraction_id}?limit=2"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_records"] == 3
    assert len(data["records"]) == 2
    assert data["records"][0]["seq"] == 1
    assert data["records"][1]["seq"] == 2

    # Unknown extraction id
    resp = await client.get(
        f"/api/dirap/work-items/{task_id}/source-files/{sf_id}/extractions/does-not-exist"
    )
    assert resp.status_code == 404
