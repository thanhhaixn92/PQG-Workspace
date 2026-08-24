"""Regression coverage for E2-E's deterministic CI resolution contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_isolated_import(statement: str) -> str:
    result = subprocess.run(
        [sys.executable, "-W", "default", "-c", statement],
        cwd=ROOT / "backend",
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stderr


def test_constraints_authority_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ci" / "validate_backend_constraints.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "PASS: validated" in result.stdout


def test_mcp_lifespan_warning_remains_documented_upstream_residual() -> None:
    stderr = run_isolated_import("import app.mcp.server")
    assert "IncompleteFieldDefinitionWarning" in stderr
    assert "pydantic_settings" in stderr
    assert "Field 'lifespan'" in stderr


def test_testclient_warning_remains_documented_upstream_residual() -> None:
    stderr = run_isolated_import("from fastapi.testclient import TestClient")
    assert "StarletteDeprecationWarning" in stderr
    assert "fastapi" in stderr
    assert "httpx2" in stderr
