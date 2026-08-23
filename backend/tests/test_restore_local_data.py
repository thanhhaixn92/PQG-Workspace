from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path


def _create_db(path: Path, marker: str) -> None:
    db = sqlite3.connect(path)
    try:
        db.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        db.execute("INSERT INTO marker VALUES (?)", (marker,))
        db.commit()
    finally:
        db.close()


def test_offline_restore_script_validates_manifest_previews_and_swaps_atomically(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "restore-local-data.ps1"
    target = tmp_path / "target.db"
    backup = tmp_path / "backup.db"
    _create_db(target, "old")
    _create_db(backup, "new")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = {
        "format_version": 1,
        "backup_name": backup.name,
        "created_at": 1,
        "size_bytes": backup.stat().st_size,
        "sha256": digest,
        "coverage": "database_only",
        "managed_workspace_coverage": "not_included",
    }
    Path(f"{backup}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    preview = subprocess.run(
        [
            "powershell", "-NoProfile", "-File", str(script),
            "-BackupPath", str(backup), "-TargetPath", str(target), "-WhatIf",
        ],
        check=False, capture_output=True, text=True,
    )
    assert preview.returncode == 0, preview.stderr
    db = sqlite3.connect(target)
    try:
        assert db.execute("SELECT value FROM marker").fetchone()[0] == "old"
    finally:
        db.close()

    restored = subprocess.run(
        [
            "powershell", "-NoProfile", "-File", str(script),
            "-BackupPath", str(backup), "-TargetPath", str(target), "-ConfirmRestore",
        ],
        check=False, capture_output=True, text=True,
    )
    assert restored.returncode == 0, restored.stderr
    db = sqlite3.connect(target)
    try:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT value FROM marker").fetchone()[0] == "new"
    finally:
        db.close()
    assert list(tmp_path.glob("target.db.pre-restore-*"))
    assert not Path(f"{target}.previous").exists()
    assert not Path(f"{target}.restore-stage").exists()
