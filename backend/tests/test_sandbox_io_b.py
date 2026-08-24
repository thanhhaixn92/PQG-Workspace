from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import sandbox_io
from app.services.context_broker import BrokerScope, CatalogResource
from app.services.sandbox_io import (
    normalize_relative_path,
    read_snapshot,
    search_text,
    write_bytes,
)
from app.services.security_context_mcp import SecureContextBroker


def _status(exc: pytest.ExceptionInfo[HTTPException]) -> int:
    return exc.value.status_code


def _make_dir_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(f"Windows junction creation unavailable: {result.stderr or result.stdout}")
    else:
        link.symlink_to(target, target_is_directory=True)


def test_b_rejects_cross_platform_escape_aliases() -> None:
    rejected = [
        "../secret.txt",
        "..\\secret.txt",
        "/etc/passwd",
        r"C:\Users\owner\secret.txt",
        r"\\server\share\secret.txt",
        "safe.txt:secret",
        "CON.txt",
        "folder/NUL",
    ]
    for value in rejected:
        with pytest.raises(HTTPException) as exc:
            normalize_relative_path(value)
        assert exc.value.status_code == 403, value
    assert normalize_relative_path("folder\\safe.txt") == ("folder", "safe.txt")


def test_b_rejects_hard_link_leaf(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("outside", encoding="utf-8")
    hard = workspace / "hard.txt"
    os.link(secret, hard)

    with pytest.raises(HTTPException) as exc:
        read_snapshot(workspace, "hard.txt")
    assert _status(exc) == 403

    with pytest.raises(HTTPException) as exc:
        write_bytes(workspace, "hard.txt", b"changed")
    assert _status(exc) == 403
    assert secret.read_text(encoding="utf-8") == "outside"


def test_b_rejects_symlink_or_junction_parent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    link = workspace / "linked"
    _make_dir_link(link, outside)
    with pytest.raises(HTTPException) as exc:
        read_snapshot(workspace, "linked/secret.txt")
    assert _status(exc) == 403


def test_b_parent_swap_after_open_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    parent = workspace / "parent"
    held = workspace / "held-parent"
    outside = tmp_path / "outside"
    workspace.mkdir()
    parent.mkdir()
    outside.mkdir()
    (parent / "value.txt").write_text("old", encoding="utf-8")
    outside_target = outside / "value.txt"
    outside_target.write_text("outside", encoding="utf-8")
    swapped = False

    def hook(stage: str, relative: str) -> None:
        nonlocal swapped
        if stage != "before_replace" or swapped:
            return
        swapped = True
        parent.rename(held)
        _make_dir_link(parent, outside)

    sandbox_io._TEST_HOOK = hook
    try:
        with pytest.raises(HTTPException) as exc:
            write_bytes(workspace, "parent/value.txt", b"new")
        assert _status(exc) == 403
    finally:
        sandbox_io._TEST_HOOK = None
    assert outside_target.read_text(encoding="utf-8") == "outside"
    assert (held / "value.txt").read_text(encoding="utf-8") == "old"


def test_b_creation_under_swapped_parent_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    parent = workspace / "parent"
    held = workspace / "held-parent"
    outside = tmp_path / "outside"
    workspace.mkdir()
    parent.mkdir()
    outside.mkdir()
    swapped = False

    def hook(stage: str, relative: str) -> None:
        nonlocal swapped
        if stage != "before_replace" or swapped:
            return
        swapped = True
        parent.rename(held)
        _make_dir_link(parent, outside)

    sandbox_io._TEST_HOOK = hook
    try:
        with pytest.raises(HTTPException) as exc:
            write_bytes(workspace, "parent/new.txt", b"new", create_only=True)
        assert _status(exc) == 403
    finally:
        sandbox_io._TEST_HOOK = None
    assert not (outside / "new.txt").exists()
    assert not (held / "new.txt").exists()


def test_b_atomic_target_hardlink_swap_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    target = workspace / "value.txt"
    target.write_text("old", encoding="utf-8")
    secret = outside / "secret.txt"
    secret.write_text("outside", encoding="utf-8")
    swapped = False

    def hook(stage: str, relative: str) -> None:
        nonlocal swapped
        if stage != "before_replace" or swapped:
            return
        swapped = True
        target.unlink()
        os.link(secret, target)

    sandbox_io._TEST_HOOK = hook
    try:
        with pytest.raises(HTTPException) as exc:
            write_bytes(workspace, "value.txt", b"new")
        assert _status(exc) == 403
    finally:
        sandbox_io._TEST_HOOK = None
    assert secret.read_text(encoding="utf-8") == "outside"


def test_b_read_hash_race_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "race.txt"
    target.write_bytes(b"before")
    mutated = False

    def hook(stage: str, relative: str) -> None:
        nonlocal mutated
        if stage == "after_read" and not mutated:
            mutated = True
            target.write_bytes(b"after-different-size")

    sandbox_io._TEST_HOOK = hook
    try:
        with pytest.raises(HTTPException) as exc:
            read_snapshot(workspace, "race.txt")
        assert _status(exc) == 409
    finally:
        sandbox_io._TEST_HOOK = None


def test_b_search_iteration_swap_never_reads_hardlink_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    search_root = workspace / "search"
    outside = tmp_path / "outside"
    search_root.mkdir(parents=True)
    outside.mkdir()
    victim = search_root / "victim.txt"
    victim.write_text("local text", encoding="utf-8")
    secret = outside / "secret.txt"
    secret.write_text("OUTSIDE_NEVER_LEAK", encoding="utf-8")
    swapped = False

    def hook(stage: str, relative: str) -> None:
        nonlocal swapped
        if stage == "before_open_child" and relative == "victim.txt" and not swapped:
            swapped = True
            victim.unlink()
            os.link(secret, victim)

    sandbox_io._TEST_HOOK = hook
    try:
        results, _truncated = search_text(workspace, "search", "OUTSIDE_NEVER_LEAK")
    finally:
        sandbox_io._TEST_HOOK = None
    assert results == []


@pytest.mark.asyncio
async def test_b_f7_post_authorization_artifact_swap_is_excluded(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    inputs = workspace / "inputs"
    inputs.mkdir(parents=True)
    target = inputs / "context.txt"
    original = b"AUTHORIZED_CONTEXT"
    target.write_bytes(original)
    resource = CatalogResource(
        kind="artifact",
        resource_id="artifact-b-race",
        title="context.txt",
        sensitivity="internal",
        trust="canonical_user_data",
        rank_group=20,
        source_hash=hashlib.sha256(original).hexdigest(),
        locator={"relative_path": "inputs/context.txt", "validation_status": "structurally_validated"},
    )
    scope = BrokerScope(
        work_id="work-b",
        conversation_id=None,
        memory_mode="suggest_only",
        memory_project_id=None,
        memory_task_id=None,
        memory_scope_id=None,
        data_scope="work_only",
        workspace_path=str(workspace),
    )
    mutated = False

    def hook(stage: str, relative: str) -> None:
        nonlocal mutated
        if stage == "after_read" and not mutated:
            mutated = True
            target.write_bytes(b"ATTACKER_REPLACED_CONTEXT")

    sandbox_io._TEST_HOOK = hook
    try:
        hydrated = await SecureContextBroker(None)._hydrate({}, scope, resource)
    finally:
        sandbox_io._TEST_HOOK = None
    assert hydrated is None


@pytest.mark.asyncio
async def test_b_mcp_approval_wait_parent_replacement_fails_closed(
    client,
    migrated_db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.mcp.server import mcp_session_id_var
    from app.services import security_context_mcp

    work = (await client.post("/api/sessions", json={"title": "B approval race"})).json()
    workspace = Path(work["workspace_path"])
    parent = workspace / "approved"
    held = workspace / "approved-held"
    outside = workspace.parent / f"outside-{work['id']}"
    parent.mkdir(parents=True, exist_ok=True)
    outside.mkdir(parents=True, exist_ok=True)
    outside_target = outside / "result.txt"
    outside_target.write_text("outside", encoding="utf-8")

    async def noop(*args, **kwargs):
        return None

    async def allow_after_swap(_approval_id: str):
        parent.rename(held)
        _make_dir_link(parent, outside)
        return "allow_once"

    monkeypatch.setattr(
        security_context_mcp,
        "get_settings",
        lambda: SimpleNamespace(db_path_resolved=migrated_db_path),
    )
    monkeypatch.setattr(security_context_mcp, "register_pending_approval", noop)
    monkeypatch.setattr(security_context_mcp.event_bus, "publish", noop)
    monkeypatch.setattr(security_context_mcp, "wait_for_approval", allow_after_swap)

    token = mcp_session_id_var.set(work["id"])
    try:
        with pytest.raises(HTTPException) as exc:
            await security_context_mcp.secure_write_workspace_file("approved/result.txt", "new")
        assert exc.value.status_code == 403
    finally:
        mcp_session_id_var.reset(token)
    assert outside_target.read_text(encoding="utf-8") == "outside"
    assert not (held / "result.txt").exists()
