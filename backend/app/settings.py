"""Application settings loaded from environment / .env file.

Uses pydantic-settings so all values can be overridden by env vars.
No secrets are hardcoded here; defaults are safe development values only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object for the Hermes Local Stack backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------
    db_path: str = "./app.db"
    default_workspace_root: str = "../workspace_outputs"

    @property
    def db_path_resolved(self) -> Path:
        """Return an absolute Path for the SQLite file."""
        return Path(self.db_path).resolve()

    @property
    def default_workspace_root_resolved(self) -> Path:
        """Return an absolute Path for automatically-created session workspaces."""
        return Path(self.default_workspace_root).resolve()

    # -----------------------------------------------------------------
    # CORS - configurable list; never use wildcard with credentials.
    # Default targets the local Vite dev server only.
    # -----------------------------------------------------------------
    cors_origins: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> List[str]:
        """Accept either a list or a comma-separated string from env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    # -----------------------------------------------------------------
    # Hermes Agent
    # -----------------------------------------------------------------
    hermes_executable_path: str = "hermes"
    hermes_args: Annotated[list[str], NoDecode] = ["acp"]
    hermes_dev_mock: bool = False
    hermes_startup_timeout_seconds: int = 15
    hermes_request_timeout_seconds: int = 60
    hermes_restart_backoff_seconds: int = 5

    @field_validator("hermes_args", mode="before")
    @classmethod
    def _parse_hermes_args(cls, v: object) -> list[str]:
        """Accept either a list or a comma-separated string from env."""
        if isinstance(v, str):
            return [arg.strip() for arg in v.split(",") if arg.strip()]
        return v  # type: ignore[return-value]

    # -----------------------------------------------------------------
    # n8n Sidecar Integration
    # -----------------------------------------------------------------
    n8n_webhook_base_url: str = "http://localhost:5678/webhook/"
    n8n_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("N8N_WEBHOOK_SECRET", "HERMES_N8N_WEBHOOK_SECRET"),
    )
    n8n_timeout_seconds: int = 30
    n8n_max_retries: int = 2
    
    # Dictionary mapping safe workflow names to their webhook paths
    n8n_allowed_workflows: dict[str, str] = {
        "echo": "hermes-echo"
    }

    @field_validator("n8n_allowed_workflows", mode="before")
    @classmethod
    def _parse_allowed_workflows(cls, v: object) -> dict[str, str]:
        """Parse dictionary from JSON string if set via env var."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v  # type: ignore[return-value]

    # -----------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------
    log_level: str = "INFO"


# Singleton instance used via dependency injection (see dependencies.py).
# Tests must NOT import this directly; they should override via DI.
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings instance (created once at startup)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
