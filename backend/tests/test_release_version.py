import json
import tomllib
from pathlib import Path

from app.main import app


def test_release_version_is_consistent() -> None:
    repository = Path(__file__).resolve().parents[2]
    with (repository / "backend" / "pyproject.toml").open("rb") as stream:
        backend_version = tomllib.load(stream)["project"]["version"]
    frontend_package = json.loads((repository / "frontend" / "package.json").read_text(encoding="utf-8"))
    frontend_lock = json.loads((repository / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    readme = (repository / "README.md").read_text(encoding="utf-8")

    assert backend_version == "2.2.0"
    assert app.version == backend_version
    assert frontend_package["version"] == backend_version
    assert frontend_lock["version"] == backend_version
    assert frontend_lock["packages"][""]["version"] == backend_version
    assert f'"version":"{backend_version}"' in readme


def test_product_branding_is_separate_from_hermes_runtime() -> None:
    repository = Path(__file__).resolve().parents[2]
    index_html = (repository / "frontend" / "index.html").read_text(encoding="utf-8")
    app_layout = (repository / "frontend" / "src" / "components" / "AppLayout.tsx").read_text(encoding="utf-8")
    branding = (repository / "frontend" / "src" / "branding.ts").read_text(encoding="utf-8")

    assert app.title == "PQG Workspace"
    assert "<title>PQG Workspace — Trợ lý GYO</title>" in index_html
    assert 'aria-label={PRODUCT_NAME}' in app_layout
    assert "ASSISTANT_LABEL" in branding
    assert "Hermes Local" not in index_html
    assert "Hermes Local" not in app_layout
