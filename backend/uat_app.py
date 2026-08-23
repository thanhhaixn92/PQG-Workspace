"""Isolated UAT backend for Gate 2 Package A Browser UAT.

- Uses a private SQLite DB and workspace root under the UAT profile directory.
- Overrides CORS to allow only the isolated frontend origin.
- Replaces the real GYO provider with a deterministic in-process fake so that
  NO external/provider request is performed.
- Does NOT modify any repository source file; the override is applied at runtime
  via dependency_overrides only, on an isolated app instance.

This file lives OUTSIDE the repository (under %TEMP%/uat-codex-*).
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

# Ensure the backend package is importable without touching the repo venv.
REPO = os.path.abspath(r"C:\Users\dtron\Documents\DIRAP-Personal-v3")
BACKEND = os.path.join(REPO, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.main import APP_VERSION, create_app  # noqa: E402
from app.settings import Settings  # noqa: E402


class UatFakeOrchestrator:
    """In-process fake GYO orchestrator used only by the isolated UAT harness.

    It is intentionally tiny and deterministic; it never reaches out to a model
    provider. It streams a single token batch then marks the turn completed.
    """

    def __init__(self) -> None:
        self.requests: list = []
        self.cancel_outcome = "cancelled"

    async def stream(self, request):
        self.requests.append(request)
        yield SimpleNamespace(
            type="token",
            data={"text": "UAT isolated mock response."},
        )
        yield SimpleNamespace(
            type="done",
            data={
                "text": "UAT isolated mock response.",
                "status": "completed",
                "model_id": "fake-uat-model",
                "provider_profile_id": None,
                "model_profile_id": None,
                "route_mode": request.route_mode,
                "selection_reason": "uat-fake",
                "structured_parts": [],
            },
        )

    async def cancel(self, assistant_turn_id: str) -> str:
        return self.cancel_outcome


def build_uat_app():
    profile = os.environ.get("UAT_PROFILE", "")
    settings = Settings(
        db_path=f"{profile}/app.db",
        default_workspace_root=f"{profile}/workspaces",
        cors_origins=["http://127.0.0.1:5184"],
    )
    app = create_app(settings_override=settings)
    # Replace the real orchestrator with the in-process fake.
    app.state.gyo_orchestrator = UatFakeOrchestrator()
    return app


app = build_uat_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8011)
