from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_cors_accepts_exact_loopback_origins_and_normalizes_trailing_slash() -> None:
    settings = Settings(cors_origins="http://localhost:5173/,http://127.0.0.1:8105,http://[::1]:5198")

    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:8105",
        "http://[::1]:5198",
    ]


@pytest.mark.parametrize("origin", ["*", "https://localhost:5173", "http://example.com", "http://localhost:5173/path"])
def test_cors_rejects_wildcard_remote_and_non_origin_values(origin: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings(cors_origins=[origin])


@pytest.mark.asyncio
async def test_cors_middleware_allows_only_the_configured_exact_origin(client) -> None:
    allowed = await client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"

    foreign = await client.options(
        "/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert foreign.status_code == 400
    assert "access-control-allow-origin" not in foreign.headers
