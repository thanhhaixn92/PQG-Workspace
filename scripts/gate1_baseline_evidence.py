"""Gate 1 evidence harness. Read-only against the standard SQLite database.

Writes only its JSON evidence output supplied as argv[2]. It does not expose
DB/workspace paths, titles, identifiers, or conversation content.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = Path(sys.argv[1]).resolve()
OUTPUT = Path(sys.argv[2]).resolve()

QUERIES = {
    "assistant_threads_total": "SELECT COUNT(*) FROM assistant_threads",
    "assistant_threads_bound": "SELECT COUNT(*) FROM assistant_threads WHERE conversation_id IS NOT NULL",
    "assistant_threads_unbound": "SELECT COUNT(*) FROM assistant_threads WHERE conversation_id IS NULL",
    "assistant_turns_total": "SELECT COUNT(*) FROM assistant_turns",
    "work_scoped_turns_unbound": "SELECT COUNT(*) FROM assistant_turns WHERE work_id IS NOT NULL AND conversation_id IS NULL",
    "active_works": "SELECT COUNT(*) FROM sessions WHERE archived = 0",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    script_hash = sha256_file(Path(__file__).resolve())
    db_hash = sha256_file(DB)
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO, check=True, text=True,
        capture_output=True,
    ).stdout
    lines = [line for line in status.splitlines() if line]
    untracked = sum(line.startswith("??") for line in lines)
    modified = len(lines) - untracked
    manifest_hash = hashlib.sha256(status.encode("utf-8")).hexdigest()

    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        aggregates = {name: conn.execute(sql).fetchone()[0] for name, sql in QUERIES.items()}
    finally:
        conn.close()

    payload = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": {"sqlite_uri_mode": "ro", "pragma_query_only": True},
        "hashes": {
            "baseline_script_sha256": script_hash,
            "query_manifest_sha256": hashlib.sha256(json.dumps(QUERIES, sort_keys=True).encode()).hexdigest(),
            "worktree_manifest_sha256": manifest_hash,
            "db_identity_sha256": db_hash,
        },
        "db_identity": {"redacted": True, "size_bytes": DB.stat().st_size},
        "worktree_identity": {
            "modified": modified,
            "untracked": untracked,
            "total": len(lines),
            "manifest_values_redacted": True,
        },
        "classifier": {
            "version": "gate1-title-workspace-marker-v1",
            "reads_title_and_workspace_path_markers": True,
            "marker_values_redacted": True,
        },
        "aggregates": aggregates,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "evidence": str(OUTPUT.relative_to(REPO)).replace("\\", "/"),
        "timestamp_utc": payload["timestamp_utc"],
        "hashes": payload["hashes"],
        "db_identity": payload["db_identity"],
        "worktree_identity": payload["worktree_identity"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
