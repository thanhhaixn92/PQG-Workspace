"""Tests for local data summary and backup endpoints."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "app.db"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = create_app(
        settings_override=Settings(
            db_path=str(db_path),
            hermes_dev_mock=True,
            log_level="WARNING",
        )
    )
    app.state.test_workspace = str(workspace)
    with TestClient(app) as test_client:
        yield test_client


def test_local_data_summary_counts_rows(client: TestClient) -> None:
    session = client.post(
        "/api/sessions",
        json={"title": "Local Data", "workspace_path": client.app.state.test_workspace},
    ).json()
    client.patch(f"/api/sessions/{session['id']}", json={"title": "Local Data Renamed"})

    response = client.get("/api/local-data/summary")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["db_path"].endswith(".db")
    assert data["db_size_bytes"] > 0
    assert data["sessions_count"] >= 1
    assert data["active_sessions_count"] >= 1
    assert data["audit_events_count"] >= 2
    assert "messages_count" in data
    assert "task_runs_count" in data


def test_local_data_backup_creates_new_file_without_overwrite(client: TestClient) -> None:
    session = client.post(
        "/api/sessions",
        json={"title": "Backup Me", "workspace_path": client.app.state.test_workspace},
    ).json()

    first = client.post("/api/local-data/backup")
    second = client.post("/api/local-data/backup")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_path = Path(first.json()["backup_path"])
    second_path = Path(second.json()["backup_path"])
    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path
    assert first_path.name.startswith("app-")
    assert second_path.name.startswith("app-")

    with sqlite3.connect(first_path) as db:
        row = db.execute("SELECT title FROM sessions WHERE id = ?", (session["id"],)).fetchone()
    assert row == ("Backup Me",)
