"""MCP adapter for Memory Hub.

The adapter has no database imports. It obtains its role token from the OS
credential manager and proxies only to the configured loopback FastAPI API.
"""
from __future__ import annotations

from typing import Annotated, Any

import httpx
import keyring
from pydantic import Field

from app.settings import get_settings


def _token(role: str) -> str:
    settings = get_settings()
    try:
        token = keyring.get_password(settings.memory_hub_keyring_service, role)
    except keyring.errors.KeyringError as exc:
        raise RuntimeError("Memory Hub credential store is unavailable") from exc
    if not token:
        raise RuntimeError(f"No Memory Hub token is configured for role '{role}'")
    return token


async def _call(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {_token(settings.memory_hub_mcp_role)}"}
    async with httpx.AsyncClient(base_url=settings.memory_hub_api_base_url, timeout=10.0) as client:
        response = await client.request(method, path, json=payload, headers=headers)
    if response.is_error:
        raise RuntimeError(f"Memory Hub API rejected request ({response.status_code})")
    return response.json()


async def search_memory(
    query: Annotated[str, Field(description="Full-text Memory Hub query.")],
    project_id: Annotated[str, Field(description="Required project scope.")],
    task_id: Annotated[str, Field(description="Required task scope.")],
) -> Any:
    """Search active, policy-visible Memory Hub records via loopback FastAPI."""
    params = {"q": query, "lifecycle": "active"}
    params["project_id"] = project_id
    params["task_id"] = task_id
    return await _call("GET", f"/api/memory-hub/records?{httpx.QueryParams(params)}")


async def get_memory_context_pack(
    project_id: Annotated[str, Field(description="Required project scope.")],
    task_id: Annotated[str, Field(description="Required task scope.")],
) -> Any:
    """Get a capped active-only context pack via loopback FastAPI."""
    return await _call("POST", "/api/memory-hub/context-pack", {"project_id": project_id, "task_id": task_id})


async def propose_memory(
    kind: Annotated[str, Field(description="Memory kind." )],
    memory_key: Annotated[str, Field(description="Stable memory key.")],
    content: Annotated[str, Field(description="Concise memory content, not a transcript.")],
    project_id: Annotated[str, Field(description="Required project scope.")],
    task_id: Annotated[str, Field(description="Required task scope.")],
    sensitivity: Annotated[str, Field(description="normal, sensitive, or restricted.")] = "normal",
) -> Any:
    """Create a proposed Memory Hub record; activation always remains policy-gated."""
    return await _call("POST", "/api/memory-hub/proposals", {"kind": kind, "memory_key": memory_key, "content": content, "project_id": project_id, "task_id": task_id, "sensitivity": sensitivity})


async def review_memory(
    record_id: Annotated[str, Field(description="Memory Hub record id.")],
    action: Annotated[str, Field(description="verify, activate, or reject.")],
    note: Annotated[str | None, Field(description="Optional concise review rationale.")] = None,
) -> Any:
    """Execute a lifecycle review through FastAPI, enforcing Hub role policy."""
    if action not in {"verify", "activate", "reject"}:
        raise ValueError("action must be verify, activate, or reject")
    return await _call("POST", f"/api/memory-hub/records/{record_id}/{action}", {"note": note})
