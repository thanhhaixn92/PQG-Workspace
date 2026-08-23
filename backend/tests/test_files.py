import os
import pytest
from pathlib import Path
from starlette.testclient import TestClient
import aiosqlite

@pytest.mark.asyncio
async def test_file_tree(client: TestClient, tmp_path: Path) -> None:
    # 1. Create a real session
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    # Add some files
    (tmp_path / "file1.txt").write_text("hello")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "file2.txt").write_text("world")
    
    # Hidden dir
    hidden = tmp_path / "node_modules"
    hidden.mkdir()
    (hidden / "secret.txt").write_text("no")

    resp = await client.get(f"/api/sessions/{session_id}/files/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert "tree" in data
    
    # Check tree
    tree = data["tree"]
    assert any(n["name"] == "file1.txt" for n in tree)
    subdir_node = next(n for n in tree if n["name"] == "subdir")
    assert any(n["name"] == "file2.txt" for n in subdir_node["children"])
    
    # Check hidden excluded
    assert not any(n["name"] == "node_modules" for n in tree)


@pytest.mark.asyncio
async def test_grouped_file_tree_separates_managed_work_documents(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Grouped documents", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]

    for folder in ("inputs", "working"):
        (tmp_path / folder).mkdir()
    (tmp_path / "inputs" / "brief.md").write_text("brief", encoding="utf-8")
    (tmp_path / "working" / "notes.md").write_text("notes", encoding="utf-8")
    (tmp_path / "legacy.txt").write_text("legacy", encoding="utf-8")

    response = await client.get(f"/api/sessions/{session_id}/files/tree?grouped=true")
    assert response.status_code == 200
    tree = response.json()["tree"]
    groups = {(node["name"], node["path"]): node for node in tree}

    assert ("Tài liệu đầu vào", "inputs") in groups
    assert ("Tài liệu làm việc", "working") in groups
    assert ("Đầu ra", "outputs") in groups
    assert all(node["path"] in {"inputs", "working", "outputs"} for node in tree)
    assert not any(child["name"] == "legacy.txt" for node in tree for child in node.get("children", []))
    assert any(child["name"] == "notes.md" for child in groups[("Tài liệu làm việc", "working")]["children"])
    assert groups[("Đầu ra", "outputs")]["children"] == []

@pytest.mark.asyncio
async def test_path_traversal_windows(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    # Outside file
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret")
    
    # 1. Relative traversal
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path=../secret.txt")
    assert resp.status_code == 403
    
    # 2. Mixed slash traversal
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path=..\\secret.txt")
    assert resp.status_code == 403
    
    # 3. Absolute escape
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path={outside.as_posix()}")
    assert resp.status_code == 403
    
    # 4. URL encoded traversal
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path=..%2fsecret.txt")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_legacy_relative_workspace_path_is_canonicalized_before_file_access(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legacy relative workspace value cannot widen the file sandbox."""
    workspace = tmp_path / "relative-workspace"
    workspace.mkdir()
    (workspace / "inside.txt").write_text("inside", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    created = await client.post(
        "/api/sessions",
        json={"title": "Legacy relative workspace", "workspace_path": "relative-workspace"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    inside = await client.get(f"/api/sessions/{session_id}/files/content?path=inside.txt")
    assert inside.status_code == 200
    escaped = await client.get(f"/api/sessions/{session_id}/files/content?path=../secret.txt")
    assert escaped.status_code == 403

@pytest.mark.asyncio
async def test_file_size_limit(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    large_file = tmp_path / "large.txt"
    # Create 1.1 MB file (filled with spaces)
    with open(large_file, "wb") as f:
        f.seek((1 * 1024 * 1024) + 100)
        f.write(b"\0")
        
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path=large.txt")
    assert resp.status_code == 413

@pytest.mark.asyncio
async def test_binary_rejection(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    bin_file = tmp_path / "test.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    
    resp = await client.get(f"/api/sessions/{session_id}/files/content?path=test.bin")
    assert resp.status_code == 400
    assert "binary" in resp.json()["detail"].lower()

@pytest.mark.asyncio
async def test_file_write_audit(client: TestClient, tmp_path: Path, temp_db_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    resp = await client.put(f"/api/sessions/{session_id}/files/content?path=newfile.txt", json={"content": "hello world"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"
    assert resp.json()["size"] == len("hello world")
    
    assert (tmp_path / "newfile.txt").read_text() == "hello world"
    
    from app.dependencies import get_settings
    
    async with aiosqlite.connect(temp_db_path) as db:
        async with db.execute(
            "SELECT action, target, payload_json FROM audit_events WHERE session_id = ? AND action = 'file.write' LIMIT 1",
            (session_id,)
        ) as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == "file.write"
            assert row[1] == "newfile.txt"


@pytest.mark.asyncio
async def test_file_content_returns_metadata_and_write_conflict(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    target = tmp_path / "tracked.txt"
    target.write_text("first", encoding="utf-8")

    read_resp = await client.get(f"/api/sessions/{session_id}/files/content?path=tracked.txt")
    assert read_resp.status_code == 200
    data = read_resp.json()
    assert data["content"] == "first"
    assert data["size"] == len("first")
    assert isinstance(data["mtime"], float)

    target.write_text("external change", encoding="utf-8")

    conflict_resp = await client.put(
        f"/api/sessions/{session_id}/files/content?path=tracked.txt",
        json={"content": "user edit", "expected_mtime": data["mtime"]},
    )
    assert conflict_resp.status_code == 409

    force_resp = await client.put(
        f"/api/sessions/{session_id}/files/content?path=tracked.txt",
        json={"content": "user edit", "expected_mtime": data["mtime"], "force": True},
    )
    assert force_resp.status_code == 200
    assert target.read_text(encoding="utf-8") == "user edit"


@pytest.mark.asyncio
async def test_file_hash_detects_external_change_with_same_mtime(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Hash Conflict", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    target = tmp_path / "tracked.txt"
    target.write_text("first", encoding="utf-8")

    read_resp = await client.get(f"/api/sessions/{session_id}/files/content?path=tracked.txt")
    original = read_resp.json()
    target.write_text("other", encoding="utf-8")
    os.utime(target, (original["mtime"], original["mtime"]))

    conflict = await client.put(
        f"/api/sessions/{session_id}/files/content?path=tracked.txt",
        json={"content": "editor", "expected_mtime": original["mtime"], "expected_hash": original["hash"]},
    )

    assert conflict.status_code == 409
    assert target.read_text(encoding="utf-8") == "other"

@pytest.mark.asyncio
async def test_file_write_oversized(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    # Generate content > 1MB
    large_content = "A" * (1 * 1024 * 1024 + 100)
    
    resp = await client.put(f"/api/sessions/{session_id}/files/content?path=oversized.txt", json={"content": large_content})
    assert resp.status_code == 413

@pytest.mark.asyncio
async def test_file_tree_symlink_escape(client: TestClient, tmp_path: Path) -> None:
    resp = await client.post("/api/sessions", json={"title": "Test Session", "workspace_path": str(tmp_path)})
    session_id = resp.json()["id"]
    
    # Outside file
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "secret.txt").write_text("secret")
    
    # Try to create a symlink to outside_dir inside the workspace
    symlink_path = tmp_path / "link_to_outside"
    try:
        os.symlink(outside_dir, symlink_path, target_is_directory=True)
    except OSError:
        # Symlinks may not be supported on this Windows environment without admin privs
        # If it fails, we skip testing the actual escape logic but the test will just pass.
        pass
    else:
        resp = await client.get(f"/api/sessions/{session_id}/files/tree")
        assert resp.status_code == 200
        tree = resp.json()["tree"]
        
        # Link shouldn't be included if it escapes, or at least it shouldn't show children.
        # Currently the logic skips it if it escapes.
        assert not any(n["name"] == "link_to_outside" for n in tree)
