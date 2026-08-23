from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_markdown_report_is_managed_registered_and_idempotent(client, migrated_db_path):
    session = await client.post("/api/sessions", json={"title": "Report work"})
    assert session.status_code == 201
    session_data = session.json()
    headers = {"Idempotency-Key": "report-create-1"}
    payload = {"title": "Weekly update", "content": "Completed the first milestone."}

    first = await client.post(f"/api/sessions/{session_data['id']}/reports", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    artifact = first.json()
    assert artifact["kind"] == "report_markdown"
    assert artifact["relative_path"].startswith("outputs/reports/")
    assert not artifact["duplicate"]
    file_path = Path(session_data["workspace_path"]) / artifact["relative_path"]
    assert file_path.read_text(encoding="utf-8") == "# Weekly update\n\nCompleted the first milestone.\n"

    replay = await client.post(f"/api/sessions/{session_data['id']}/reports", json=payload, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == artifact["id"]
    assert replay.json()["duplicate"]

    listed = await client.get(f"/api/sessions/{session_data['id']}/artifacts")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [artifact["id"]]


@pytest.mark.asyncio
async def test_report_requires_key_and_archived_work_is_rejected(client):
    session = await client.post("/api/sessions", json={"title": "Archived report"})
    session_id = session.json()["id"]
    missing_key = await client.post(f"/api/sessions/{session_id}/reports", json={"title": "One", "content": "Text"})
    assert missing_key.status_code == 422
    assert (await client.delete(f"/api/sessions/{session_id}")).status_code == 200
    archived = await client.post(
        f"/api/sessions/{session_id}/reports", json={"title": "One", "content": "Text"},
        headers={"Idempotency-Key": "archived-report"},
    )
    assert archived.status_code == 409


@pytest.mark.asyncio
async def test_report_publish_is_cleaned_up_when_registry_finalization_fails(client, monkeypatch):
    session = await client.post("/api/sessions", json={"title": "Failing report"})
    session_data = session.json()

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr("app.api.artifacts.log_audit_event", fail_audit)
    response = await client.post(
        f"/api/sessions/{session_data['id']}/reports",
        json={"title": "Must not remain", "content": "This publish must roll back."},
        headers={"Idempotency-Key": "report-cleanup-1"},
    )
    assert response.status_code == 500
    assert not (Path(session_data["workspace_path"]) / "outputs" / "reports" / "must-not-remain.md").exists()
    assert (await client.get(f"/api/sessions/{session_data['id']}/artifacts")).json() == []


@pytest.mark.asyncio
async def test_html_report_is_escaped_registered_and_openable(client):
    session = (await client.post("/api/sessions", json={"title": "HTML report"})).json()
    created = await client.post(
        f"/api/sessions/{session['id']}/reports",
        json={"title": "Review", "content": "<script>alert(1)</script>", "output_format": "html"},
        headers={"Idempotency-Key": "html-report-1"},
    )
    assert created.status_code == 201, created.text
    artifact = created.json()
    assert artifact["kind"] == "report_html"
    assert artifact["relative_path"].endswith(".html")
    opened = await client.get(f"/api/sessions/{session['id']}/artifacts/{artifact['id']}/content")
    assert opened.status_code == 200
    assert "&lt;script&gt;" in opened.text
    assert "<script>alert(1)</script>" not in opened.text


@pytest.mark.asyncio
async def test_document_import_streams_verifies_hash_registers_and_replays(client):
    session = (await client.post("/api/sessions", json={"title": "Import"})).json()
    content = b"managed input\n"
    digest = hashlib.sha256(content).hexdigest()
    headers = {
        "Idempotency-Key": "import-1",
        "X-File-Name": "nguon.txt",
        "X-Content-SHA256": digest,
        "Content-Length": str(len(content)),
        "Content-Type": "application/octet-stream",
    }
    first = await client.post(f"/api/sessions/{session['id']}/documents/import", content=content, headers=headers)
    assert first.status_code == 201, first.text
    artifact = first.json()
    assert artifact["relative_path"] == "inputs/nguon.txt"
    assert artifact["sha256"] == digest
    assert (Path(session["workspace_path"]) / "inputs" / "nguon.txt").read_bytes() == content

    replay = await client.post(f"/api/sessions/{session['id']}/documents/import", content=content, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["id"] == artifact["id"]
    assert replay.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_document_import_rejects_bad_hash_reserved_name_and_traversal(client):
    session = (await client.post("/api/sessions", json={"title": "Unsafe import"})).json()
    content = b"content"
    base = {
        "Idempotency-Key": "bad-hash",
        "X-File-Name": "safe.txt",
        "X-Content-SHA256": "0" * 64,
        "Content-Length": str(len(content)),
    }
    bad_hash = await client.post(f"/api/sessions/{session['id']}/documents/import", content=content, headers=base)
    assert bad_hash.status_code == 422
    assert not (Path(session["workspace_path"]) / "inputs" / "safe.txt").exists()

    for index, name in enumerate(("../escape.txt", "CON.txt", "bad:name.txt")):
        headers = dict(base, **{
            "Idempotency-Key": f"unsafe-name-{index}",
            "X-File-Name": name,
            "X-Content-SHA256": hashlib.sha256(content).hexdigest(),
        })
        rejected = await client.post(f"/api/sessions/{session['id']}/documents/import", content=content, headers=headers)
        assert rejected.status_code in {403, 422}


@pytest.mark.asyncio
async def test_document_import_requires_safe_type_and_signature(client):
    session = (await client.post("/api/sessions", json={"title": "Structural validation"})).json()

    async def upload(name: str, content: bytes, key: str):
        return await client.post(
            f"/api/sessions/{session['id']}/documents/import",
            content=content,
            headers={
                "Idempotency-Key": key, "X-File-Name": name,
                "X-Content-SHA256": hashlib.sha256(content).hexdigest(),
                "Content-Length": str(len(content)),
            },
        )

    assert (await upload("unsafe.html", b"<script>alert(1)</script>", "struct-html")).status_code == 422
    assert (await upload("macro.docm", b"PK\x03\x04", "struct-macro")).status_code == 422
    assert (await upload("fake.pdf", b"not a pdf", "struct-pdf")).status_code == 422
    safe = await upload("note.txt", b"safe context", "struct-txt")
    assert safe.status_code == 201, safe.text
    assert safe.json()["validation_status"] == "structurally_validated"


@pytest.mark.asyncio
async def test_document_import_rejects_pdf_exceeding_structural_resource_limits(client):
    session = (await client.post("/api/sessions", json={"title": "Bounded PDF"})).json()
    # A valid header alone is not enough: excessive indirect objects must be
    # rejected before the file can become GYO context.
    content = b"%PDF-1.7\n" + b"1 0 obj\nendobj\n" * 10_001
    response = await client.post(
        f"/api/sessions/{session['id']}/documents/import",
        content=content,
        headers={
            "Idempotency-Key": "pdf-resource-limit",
            "X-File-Name": "many-objects.pdf",
            "X-Content-SHA256": hashlib.sha256(content).hexdigest(),
            "Content-Length": str(len(content)),
        },
    )
    assert response.status_code == 422
    assert "resource limits" in response.text


@pytest.mark.asyncio
async def test_managed_text_file_and_folder_creation_are_atomic_and_idempotent(client):
    session = (await client.post("/api/sessions", json={"title": "Create documents"})).json()
    folder_headers = {"Idempotency-Key": "folder-1"}
    folder = await client.post(
        f"/api/sessions/{session['id']}/documents/folders",
        json={"relative_path": "Tai lieu"}, headers=folder_headers,
    )
    assert folder.status_code == 201, folder.text
    assert folder.json()["relative_path"] == "inputs/Tai lieu"
    folder_replay = await client.post(
        f"/api/sessions/{session['id']}/documents/folders",
        json={"relative_path": "Tai lieu"}, headers=folder_headers,
    )
    assert folder_replay.status_code == 200
    assert folder_replay.json()["duplicate"] is True

    file_headers = {"Idempotency-Key": "file-1"}
    created = await client.post(
        f"/api/sessions/{session['id']}/documents/files",
        json={"relative_path": "ghi-chu.txt", "content": "Nội dung"}, headers=file_headers,
    )
    assert created.status_code == 201, created.text
    artifact = created.json()
    assert artifact["kind"] == "created_text_file"
    assert artifact["validation_status"] == "structurally_validated"
    assert (Path(session["workspace_path"]) / artifact["relative_path"]).read_text(encoding="utf-8") == "Nội dung"
    replay = await client.post(
        f"/api/sessions/{session['id']}/documents/files",
        json={"relative_path": "ghi-chu.txt", "content": "Nội dung"}, headers=file_headers,
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == artifact["id"]
