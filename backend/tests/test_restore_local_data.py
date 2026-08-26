from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest


def _create_db(path: Path, marker: str) -> None:
    db = sqlite3.connect(path)
    try:
        db.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        db.execute("INSERT INTO marker VALUES (?)", (marker,))
        db.commit()
    finally:
        db.close()


def _read_marker(path: Path) -> str:
    db = sqlite3.connect(path)
    try:
        return str(db.execute("SELECT value FROM marker").fetchone()[0])
    finally:
        db.close()


def _write_manifest(backup: Path) -> None:
    manifest = {
        "format_version": 1,
        "backup_name": backup.name,
        "created_at": 1,
        "size_bytes": backup.stat().st_size,
        "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "coverage": "database_only",
        "managed_workspace_coverage": "not_included",
    }
    Path(f"{backup}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _windows_context() -> tuple[str, Path]:
    if os.name != "nt":
        pytest.skip("P0-03 process provenance validation requires Windows")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for P0-03 provenance tests")
    repo_root = Path(__file__).resolve().parents[2]
    backend_python = repo_root / "backend" / ".venv" / "Scripts" / "python.exe"
    if not backend_python.is_file():
        pytest.skip("P0-03 Windows validation requires backend/.venv/Scripts/python.exe")
    return powershell, repo_root


def _run_ps_file(
    powershell: str,
    script: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _ps_literal(value: Path | str) -> str:
    return str(value).replace("'", "''")


def _assert_windows_powershell_git_sha_with_space_path(
    powershell: str,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    spaced_repo = tmp_path / "git repository with spaces"
    init = subprocess.run(
        ["git", "init", str(spaced_repo)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert init.returncode == 0, init.stderr or init.stdout
    (spaced_repo / "marker.txt").write_text("p0-03\n", encoding="utf-8")
    staged = subprocess.run(
        ["git", "-C", str(spaced_repo), "add", "marker.txt"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert staged.returncode == 0, staged.stderr or staged.stdout
    committed = subprocess.run(
        [
            "git",
            "-C",
            str(spaced_repo),
            "-c",
            "user.name=PQG Test",
            "-c",
            "user.email=pqg-test@example.invalid",
            "commit",
            "-m",
            "test source",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert committed.returncode == 0, committed.stderr or committed.stdout
    expected = subprocess.run(
        ["git", "-C", str(spaced_repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    helper = repo_root / "scripts" / "dev-provenance.ps1"
    command = rf"""
if ($PSVersionTable.PSVersion.Major -ne 5) {{ throw 'Windows PowerShell 5.1 is required' }}
. '{_ps_literal(helper)}'
Get-PqgCurrentSourceSha -RepositoryRoot '{_ps_literal(spaced_repo)}'
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == expected

    missing_start_time = rf"""
. '{_ps_literal(helper)}'
function Get-CimInstance {{
  [pscustomobject]@{{ ExecutablePath = 'C:\fake.exe'; ParentProcessId = 1; CommandLine = 'fake' }}
}}
function Get-Process {{
  [pscustomobject]@{{ Path = 'C:\fake.exe'; StartTime = $null }}
}}
$snapshot = Get-PqgProcessSnapshot -ProcessId 12345
if ($null -ne $snapshot) {{ throw 'A vanished process must return a null snapshot' }}
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", missing_start_time],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _assert_smoke_dev_uses_schema_v2_backend_port(
    powershell: str,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    smoke_root = tmp_path / "isolated smoke consumer"
    state_dir = smoke_root / ".dev"
    state_dir.mkdir(parents=True)
    smoke_script = smoke_root / "smoke-dev.ps1"
    shutil.copy2(repo_root / "smoke-dev.ps1", smoke_script)

    def run_smoke(backend_port: int | None = None) -> subprocess.CompletedProcess[str]:
        arguments = "" if backend_port is None else f"-BackendPort {backend_port}"
        command = rf"""
function Invoke-RestMethod {{
  param([string]$Uri, [int]$TimeoutSec)
  throw "Network disabled for isolated port-resolution test: $Uri"
}}
& '{_ps_literal(smoke_script)}' {arguments}
"""
        return subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    dynamic_port = _free_port()
    while dynamic_port == 8000:
        dynamic_port = _free_port()
    state_path = state_dir / "dev-state.json"
    state_path.write_text(
        json.dumps({"schemaVersion": 2, "backend": {"port": dynamic_port}}),
        encoding="utf-8",
    )
    from_state = run_smoke()
    assert from_state.returncode != 0
    assert f"Backend: http://127.0.0.1:{dynamic_port}" in from_state.stdout
    assert "http://127.0.0.1:8000" not in from_state.stdout

    explicit_port = _free_port()
    explicit = run_smoke(explicit_port)
    assert explicit.returncode != 0
    assert f"Backend: http://127.0.0.1:{explicit_port}" in explicit.stdout
    assert f"Backend: http://127.0.0.1:{dynamic_port}" not in explicit.stdout

    invalid_states = (
        {"schemaVersion": 1, "backend": {"port": dynamic_port}},
        {"schemaVersion": 2, "backend": {}},
        {"schemaVersion": 2, "backend": {"port": 0}},
    )
    for invalid_state in invalid_states:
        state_path.write_text(json.dumps(invalid_state), encoding="utf-8")
        invalid = run_smoke()
        assert invalid.returncode != 0
        assert "Backend: http://" not in invalid.stdout
        assert "Dev-state" in invalid.stderr


def _spawn_recorded_wrappers(
    powershell: str,
    repo_root: Path,
    state_path: Path,
    backend_db: Path,
    backend_port: int = 18123,
    frontend_port: int = 15173,
    *,
    real_backend: bool = False,
) -> dict[str, int]:
    helper = repo_root / "scripts" / "dev-provenance.ps1"
    real_backend_literal = "$true" if real_backend else "$false"
    script = rf"""
$ErrorActionPreference = 'Stop'
$root = '{_ps_literal(repo_root)}'
. '{_ps_literal(helper)}'
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$sha = Get-PqgCurrentSourceSha -RepositoryRoot $root
$backendMarker = Get-PqgIdentityMarker -Role backend -RepositoryRoot $root -SourceSha $sha
$frontendMarker = Get-PqgIdentityMarker -Role frontend -RepositoryRoot $root -SourceSha $sha
$backendCommand = Get-PqgBackendCommandIdentity -RepositoryRoot $root -SourceSha $sha -BackendDirectory $backendDir -Port {backend_port} -DbPath '{_ps_literal(backend_db)}' -Reload $false
$frontendCommand = Get-PqgFrontendCommandIdentity -RepositoryRoot $root -SourceSha $sha -FrontendDirectory $frontendDir -Port {frontend_port} -BackendPort {backend_port}
$realBackend = {real_backend_literal}
if ($realBackend) {{
  $backendPayload = "`$pqgIdentity='$backendMarker'; `$pqgCommandIdentity='$backendCommand'; `$env:DB_PATH='{_ps_literal(backend_db)}'; Set-Location -LiteralPath '$backendDir'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port {backend_port}"
}} else {{
  $backendPayload = "`$pqgIdentity='$backendMarker'; `$pqgCommandIdentity='$backendCommand'; Start-Sleep -Seconds 120"
}}
$frontendPayload = "`$pqgIdentity='$frontendMarker'; `$pqgCommandIdentity='$frontendCommand'; Start-Sleep -Seconds 120"
$bp = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $backendDir -PassThru -ArgumentList @('-NoExit', '-Command', $backendPayload)
$fp = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $frontendDir -PassThru -ArgumentList @('-NoExit', '-Command', $frontendPayload)
try {{
  $backend = New-PqgProcessRecord -ProcessId $bp.Id -WorkingDirectory $backendDir -Command $backendCommand -IdentityMarker $backendMarker -Port {backend_port} -DbPath '{_ps_literal(backend_db)}'
  $backend | Add-Member -NotePropertyName reload -NotePropertyValue $false -Force
  $frontend = New-PqgProcessRecord -ProcessId $fp.Id -WorkingDirectory $frontendDir -Command $frontendCommand -IdentityMarker $frontendMarker -Port {frontend_port}
  $state = [ordered]@{{
    schemaVersion = 2
    repositoryRoot = $root
    sourceSha = $sha
    startedAt = (Get-Date).ToUniversalTime().ToString('o')
    backend = $backend
    frontend = $frontend
  }}
  $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath '{_ps_literal(state_path)}' -Encoding UTF8
  [pscustomobject]@{{backendPid=$bp.Id; frontendPid=$fp.Id}} | ConvertTo-Json -Compress
}} catch {{
  taskkill.exe /PID $fp.Id /T /F 2>$null | Out-Null
  taskkill.exe /PID $bp.Id /T /F 2>$null | Out-Null
  throw
}}
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    return {key: int(value) for key, value in payload.items()}


def _pid_exists(powershell: str, pid: int) -> bool:
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _kill_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


def _isolated_restore_fixture(tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "target.db"
    backup = tmp_path / "backup.db"
    _create_db(target, "old")
    _create_db(backup, "new")
    _write_manifest(backup)
    return target, backup


def _env_with_db(backend_db: Path, tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DB_PATH"] = str(backend_db)
    env["DEFAULT_WORKSPACE_ROOT"] = str(tmp_path / "workspace")
    return env


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def test_offline_restore_script_validates_manifest_previews_and_swaps_atomically(tmp_path: Path) -> None:
    powershell, repo_root = _windows_context()
    _assert_windows_powershell_git_sha_with_space_path(powershell, repo_root, tmp_path)
    _assert_smoke_dev_uses_schema_v2_backend_port(powershell, repo_root, tmp_path)
    script = repo_root / "restore-local-data.ps1"
    state_path = tmp_path / "dev-state.json"
    target, backup = _isolated_restore_fixture(tmp_path)
    env = _env_with_db(repo_root / "backend" / "app.db", tmp_path)

    preview = _run_ps_file(
        powershell,
        script,
        "-BackupPath",
        str(backup),
        "-TargetPath",
        str(target),
        "-DevStatePath",
        str(state_path),
        "-WhatIf",
        env=env,
    )
    assert preview.returncode == 0, preview.stderr or preview.stdout
    assert _read_marker(target) == "old"

    restored = _run_ps_file(
        powershell,
        script,
        "-BackupPath",
        str(backup),
        "-TargetPath",
        str(target),
        "-DevStatePath",
        str(state_path),
        "-ConfirmRestore",
        env=env,
    )
    assert restored.returncode == 0, restored.stderr or restored.stdout
    assert _read_marker(target) == "new"
    assert list(tmp_path.glob("target.db.pre-restore-*"))
    assert not Path(f"{target}.previous").exists()
    assert not Path(f"{target}.restore-stage").exists()


@pytest.mark.parametrize("mutation", ["hash", "integrity", "previous_marker", "incomplete_state"])
def test_restore_failures_do_not_mutate_target(tmp_path: Path, mutation: str) -> None:
    powershell, repo_root = _windows_context()
    script = repo_root / "restore-local-data.ps1"
    state_path = tmp_path / "dev-state.json"
    target, backup = _isolated_restore_fixture(tmp_path)
    env = _env_with_db(repo_root / "backend" / "app.db", tmp_path)

    if mutation == "hash":
        manifest_path = Path(f"{backup}.manifest.json")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "integrity":
        backup.write_bytes(b"not a sqlite database")
        _write_manifest(backup)
    elif mutation == "previous_marker":
        Path(f"{target}.previous").write_bytes(b"marker")
    else:
        state_path.write_text(json.dumps({"schemaVersion": 2}), encoding="utf-8")

    before = target.read_bytes()
    result = _run_ps_file(
        powershell,
        script,
        "-BackupPath",
        str(backup),
        "-TargetPath",
        str(target),
        "-DevStatePath",
        str(state_path),
        "-ConfirmRestore",
        env=env,
    )
    assert result.returncode != 0
    assert target.read_bytes() == before
    assert _read_marker(target) == "old"
    assert not Path(f"{target}.restore-stage").exists()
    assert not list(tmp_path.glob("target.db.pre-restore-*"))


@pytest.mark.parametrize("mutation", ["start_time", "command", "source_sha"])
def test_stop_dev_refuses_stale_or_mismatched_identity_without_killing(
    tmp_path: Path,
    mutation: str,
) -> None:
    powershell, repo_root = _windows_context()
    stop_script = repo_root / "stop-dev.ps1"
    backend_db = tmp_path / "configured.db"
    _create_db(backend_db, "configured")
    state_path = tmp_path / "dev-state.json"
    pids = _spawn_recorded_wrappers(powershell, repo_root, state_path, backend_db)
    env = _env_with_db(backend_db, tmp_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        if mutation == "start_time":
            state["backend"]["processStartTime"] = "2000-01-01T00:00:00Z"
        elif mutation == "command":
            state["backend"]["command"] = "foreign command"
        else:
            state["sourceSha"] = "0" * 40
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = _run_ps_file(powershell, stop_script, "-DevStatePath", str(state_path), env=env)
        assert result.returncode != 0
        assert state_path.exists()
        assert _pid_exists(powershell, pids["backendPid"])
        assert _pid_exists(powershell, pids["frontendPid"])
    finally:
        _kill_tree(pids["frontendPid"])
        _kill_tree(pids["backendPid"])


@pytest.mark.parametrize("mutation", ["start_time", "command", "source_sha"])
def test_start_dev_refuses_mismatched_state_without_reuse_or_overwrite(
    tmp_path: Path,
    mutation: str,
) -> None:
    powershell, repo_root = _windows_context()
    if not (repo_root / "frontend" / "node_modules").is_dir():
        pytest.skip("start-dev mismatch validation requires frontend/node_modules")
    start_script = repo_root / "start-dev.ps1"
    backend_db = tmp_path / "configured.db"
    _create_db(backend_db, "configured")
    state_path = tmp_path / "dev-state.json"
    pids = _spawn_recorded_wrappers(powershell, repo_root, state_path, backend_db)
    env = _env_with_db(backend_db, tmp_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        if mutation == "start_time":
            state["backend"]["processStartTime"] = "2000-01-01T00:00:00Z"
        elif mutation == "command":
            state["backend"]["command"] = "foreign command"
        else:
            state["sourceSha"] = "0" * 40
        state_path.write_text(json.dumps(state), encoding="utf-8")
        before = state_path.read_bytes()

        result = _run_ps_file(
            powershell,
            start_script,
            "-DevStatePath",
            str(state_path),
            env=env,
        )
        assert result.returncode != 0
        assert state_path.read_bytes() == before
        assert _pid_exists(powershell, pids["backendPid"])
        assert _pid_exists(powershell, pids["frontendPid"])
    finally:
        _kill_tree(pids["frontendPid"])
        _kill_tree(pids["backendPid"])


def test_stop_dev_stops_only_exact_matching_recorded_processes(tmp_path: Path) -> None:
    powershell, repo_root = _windows_context()
    stop_script = repo_root / "stop-dev.ps1"
    backend_db = tmp_path / "configured.db"
    _create_db(backend_db, "configured")
    state_path = tmp_path / "dev-state.json"
    pids = _spawn_recorded_wrappers(powershell, repo_root, state_path, backend_db)
    env = _env_with_db(backend_db, tmp_path)
    try:
        result = _run_ps_file(powershell, stop_script, "-DevStatePath", str(state_path), env=env)
        assert result.returncode == 0, result.stderr or result.stdout
        assert not state_path.exists()
        assert not _pid_exists(powershell, pids["backendPid"])
        assert not _pid_exists(powershell, pids["frontendPid"])
    finally:
        _kill_tree(pids["frontendPid"])
        _kill_tree(pids["backendPid"])


def test_restore_blocks_dynamic_port_backend_bound_to_target_db(tmp_path: Path) -> None:
    powershell, repo_root = _windows_context()
    restore_script = repo_root / "restore-local-data.ps1"
    target, backup = _isolated_restore_fixture(tmp_path)
    state_path = tmp_path / "dev-state.json"
    backend_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == backend_port:
        frontend_port = _free_port()
    pids = _spawn_recorded_wrappers(
        powershell,
        repo_root,
        state_path,
        target,
        backend_port=backend_port,
        frontend_port=frontend_port,
        real_backend=True,
    )
    env = _env_with_db(target, tmp_path)
    try:
        assert _wait_for_port(backend_port), "isolated dynamic-port backend did not start"
        before = target.read_bytes()
        result = _run_ps_file(
            powershell,
            restore_script,
            "-BackupPath",
            str(backup),
            "-TargetPath",
            str(target),
            "-DevStatePath",
            str(state_path),
            "-ConfirmRestore",
            env=env,
        )
        assert result.returncode != 0
        assert "recorded backend PID" in (result.stderr + result.stdout)
        assert target.read_bytes() == before
    finally:
        _kill_tree(pids["frontendPid"])
        _kill_tree(pids["backendPid"])


def test_restore_does_not_use_unrelated_backend_as_false_db_proof(tmp_path: Path) -> None:
    powershell, repo_root = _windows_context()
    restore_script = repo_root / "restore-local-data.ps1"
    target, backup = _isolated_restore_fixture(tmp_path)
    unrelated_db = tmp_path / "other.db"
    _create_db(unrelated_db, "other")
    backend_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == backend_port:
        frontend_port = _free_port()
    state_path = tmp_path / "dev-state.json"
    pids = _spawn_recorded_wrappers(
        powershell,
        repo_root,
        state_path,
        unrelated_db,
        backend_port=backend_port,
        frontend_port=frontend_port,
        real_backend=True,
    )
    env = _env_with_db(unrelated_db, tmp_path)
    try:
        assert _wait_for_port(backend_port), "isolated unrelated backend did not start"
        result = _run_ps_file(
            powershell,
            restore_script,
            "-BackupPath",
            str(backup),
            "-TargetPath",
            str(target),
            "-DevStatePath",
            str(state_path),
            "-ConfirmRestore",
            env=env,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        assert _read_marker(target) == "new"
        assert _pid_exists(powershell, pids["backendPid"])
    finally:
        _kill_tree(pids["frontendPid"])
        _kill_tree(pids["backendPid"])


def test_start_check_stop_produce_and_verify_complete_isolated_dev_state(tmp_path: Path) -> None:
    powershell, repo_root = _windows_context()
    if not (repo_root / "frontend" / "node_modules").is_dir():
        pytest.skip("start-dev positive validation requires frontend/node_modules")

    start_script = repo_root / "start-dev.ps1"
    check_script = repo_root / "check-dev.ps1"
    stop_script = repo_root / "stop-dev.ps1"
    state_path = tmp_path / "dev-state.json"
    isolated_db = tmp_path / "isolated.db"
    backend_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == backend_port:
        frontend_port = _free_port()
    env = _env_with_db(isolated_db, tmp_path)
    pids: dict[str, int] = {}
    try:
        started = _run_ps_file(
            powershell,
            start_script,
            "-BackendPort",
            str(backend_port),
            "-FrontendPort",
            str(frontend_port),
            "-DevStatePath",
            str(state_path),
            "-Fresh",
            "-NoReload",
            env=env,
        )
        assert started.returncode == 0, started.stderr or started.stdout
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        assert state["schemaVersion"] == 2
        assert Path(state["repositoryRoot"]).resolve() == repo_root.resolve()
        assert len(state["sourceSha"]) == 40
        assert state["backend"]["reload"] is False
        for role in ("backend", "frontend"):
            for key in (
                "pid",
                "processStartTime",
                "workingDirectory",
                "command",
                "identityMarker",
                "executable",
                "port",
            ):
                assert state[role].get(key)
        assert Path(state["backend"]["dbPath"]).resolve() == isolated_db.resolve()
        pids = {
            "backendPid": int(state["backend"]["pid"]),
            "frontendPid": int(state["frontend"]["pid"]),
        }

        assert _wait_for_port(backend_port)
        assert _wait_for_port(frontend_port)

        checked = _run_ps_file(
            powershell,
            check_script,
            "-BackendPort",
            str(backend_port),
            "-FrontendPort",
            str(frontend_port),
            "-DevStatePath",
            str(state_path),
            env=env,
        )
        assert checked.returncode == 0, checked.stderr or checked.stdout
        assert checked.stdout.count("PROOF OK") >= 5
        assert "backend DB binding" in checked.stdout
        assert "HTTP/runtime health (khong phai identity proof)" in checked.stdout

        stopped = _run_ps_file(
            powershell,
            stop_script,
            "-DevStatePath",
            str(state_path),
            env=env,
        )
        assert stopped.returncode == 0, stopped.stderr or stopped.stdout
        assert not state_path.exists()
        assert not _pid_exists(powershell, pids["backendPid"])
        assert not _pid_exists(powershell, pids["frontendPid"])
    finally:
        for pid in pids.values():
            _kill_tree(pid)
