from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.mcp.server import HERMES_MCP_TOOL_ALLOWLIST, mcp_server, setup_mcp
from app.services.action_packages import P0_INTERNAL_CAPABILITIES
from app.services.capabilities import (
    ACTION_PACKAGE_CAPABILITY_IDS,
    ADMIN_RISK_CLASSES,
    DEFAULT_CAPABILITY_REGISTRY,
    MCP_COMPAT_TOOL_NAMES,
    Capability,
    CapabilityNotFound,
    CapabilityRegistry,
    ExecutionMode,
    ReplayClass,
    RiskClass,
    resolve_model_capability,
)


EXPECTED_MCP_COMPAT = frozenset(
    {
        "propose_work_update",
        "save_work_context_summary",
        "read_workspace_file",
        "write_workspace_file",
        "search_workspace",
        "list_skills",
        "update_memory",
        "run_safe_task",
        "call_n8n_webhook",
    }
)


def test_model_visible_catalog_excludes_admin_risk_classes():
    catalog = DEFAULT_CAPABILITY_REGISTRY.model_visible_catalog()

    assert catalog
    assert all(item.model_visible for item in catalog)
    assert not {item.risk_class for item in catalog} & ADMIN_RISK_CLASSES


@pytest.mark.parametrize(
    "capability_id",
    [
        "foundation.theme.update",
        "foundation.settings.update",
        "module.attach",
        "module.detach",
        "module.rename",
        "module.reorder",
        "module.install",
        "module.uninstall",
        "provider.credentials.update",
        "provider.admin",
        "privacy.policy.update",
        "memory.activate",
        "backup.restore",
    ],
)
def test_admin_capabilities_are_absent_from_model_lookup(capability_id):
    with pytest.raises(CapabilityNotFound) as exc_info:
        resolve_model_capability(capability_id)

    assert exc_info.value.code == "capability_not_found"


def test_unknown_capability_fails_closed():
    with pytest.raises(CapabilityNotFound, match="capability_not_found"):
        resolve_model_capability("unknown.capability")


def test_duplicate_capability_ids_fail_registry_construction():
    capability = Capability(
        capability_id="duplicate",
        risk_class=RiskClass.READ_INTERNAL,
        execution_mode=ExecutionMode.READ_INLINE,
        replay_class=ReplayClass.SAFE,
        model_visible=True,
        description="test",
    )

    with pytest.raises(ValueError, match="Duplicate capability ID"):
        CapabilityRegistry((capability, capability))


def test_admin_capability_cannot_be_model_visible():
    capability = Capability(
        capability_id="module.detach",
        risk_class=RiskClass.MODULE_ADMIN,
        execution_mode=ExecutionMode.UNAVAILABLE,
        replay_class=ReplayClass.UNSAFE,
        model_visible=True,
        description="must never be exposed",
    )

    with pytest.raises(ValueError, match="Administrative capability"):
        CapabilityRegistry((capability,))


def test_mcp_compatibility_surface_is_derived_from_registry():
    assert MCP_COMPAT_TOOL_NAMES == EXPECTED_MCP_COMPAT
    assert HERMES_MCP_TOOL_ALLOWLIST == MCP_COMPAT_TOOL_NAMES


@pytest.mark.asyncio
async def test_registered_mcp_surface_still_matches_registry():
    tools = await mcp_server.list_tools()

    assert {tool.name for tool in tools} == MCP_COMPAT_TOOL_NAMES
    assert len(tools) == 9


def test_setup_mcp_fails_if_unregistered_tool_appears(monkeypatch):
    current_tools = list(mcp_server._tool_manager.list_tools())
    monkeypatch.setattr(
        mcp_server._tool_manager,
        "list_tools",
        lambda: [*current_tools, SimpleNamespace(name="unexpected_tool")],
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        setup_mcp(FastAPI())


def test_registry_metadata_is_immutable_and_not_an_executor():
    capability = resolve_model_capability("read_workspace_file")

    with pytest.raises(FrozenInstanceError):
        capability.risk_class = RiskClass.SYSTEM_ADMIN  # type: ignore[misc]
    assert not hasattr(DEFAULT_CAPABILITY_REGISTRY, "execute")


def test_action_package_capabilities_remain_exactly_the_existing_two():
    assert ACTION_PACKAGE_CAPABILITY_IDS == frozenset(
        {"work_plan_step_update", "work_status_update"}
    )
    assert ACTION_PACKAGE_CAPABILITY_IDS == P0_INTERNAL_CAPABILITIES


def test_callers_cannot_override_server_owned_risk_or_execution_metadata():
    capability = resolve_model_capability("call_n8n_webhook")

    assert capability.risk_class is RiskClass.EXTERNAL_SIDE_EFFECT
    assert capability.execution_mode is ExecutionMode.LEGACY_APPROVAL
    assert capability.replay_class is ReplayClass.UNSAFE
