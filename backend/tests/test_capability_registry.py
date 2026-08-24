from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.api.approvals import pending_approvals
from app.mcp.server import HERMES_MCP_TOOL_ALLOWLIST, mcp_server, setup_mcp
import app.mcp.tools  # noqa: F401 - registers the existing compatibility tool surface
from app.services.action_packages import ACTION_PACKAGE_HANDLERS, P0_INTERNAL_CAPABILITIES
from app.services.capabilities import (
    ACTION_PACKAGE_CAPABILITY_IDS,
    ADMIN_RISK_CLASSES,
    DEFAULT_CAPABILITY_REGISTRY,
    EXECUTABLE_BINDINGS,
    MCP_COMPAT_TOOL_NAMES,
    Capability,
    CapabilityNotFound,
    CapabilityRegistry,
    ExecutionMode,
    ExecutionSurface,
    ReplayClass,
    RiskClass,
    resolve_model_capability,
    validate_executable_bindings,
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
        "module.settings.update",
        "module.install",
        "module.update",
        "module.rollback",
        "module.uninstall",
        "module.data.delete",
        "provider.credentials.update",
        "provider.admin",
        "privacy.policy.update",
        "permission.settings.update",
        "memory.activate",
        "backup.restore",
        "skill.install",
        "skill.enable",
        "skill.disable",
    ],
)
def test_admin_capabilities_are_absent_from_model_lookup(capability_id):
    pending_before = dict(pending_approvals)

    with pytest.raises(CapabilityNotFound) as exc_info:
        resolve_model_capability(capability_id)

    assert exc_info.value.code == "capability_not_found"
    assert pending_approvals == pending_before


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


def test_setup_mcp_fails_if_action_package_allowlist_drifts(monkeypatch):
    import app.services.action_packages as action_packages

    monkeypatch.setattr(
        action_packages,
        "P0_INTERNAL_CAPABILITIES",
        frozenset({"work_plan_step_update", "unbound_action"}),
    )

    with pytest.raises(RuntimeError, match="handler allowlist drift"):
        setup_mcp(FastAPI())


def test_registry_metadata_is_immutable_and_not_an_executor():
    capability = resolve_model_capability("read_workspace_file")

    with pytest.raises(FrozenInstanceError):
        capability.risk_class = RiskClass.SYSTEM_ADMIN  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        EXECUTABLE_BINDINGS[0].risk_class = RiskClass.SYSTEM_ADMIN  # type: ignore[misc]
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


def _actual_runtime_handlers():
    from app.services.security_overrides import install_security_mcp_overrides

    install_security_mcp_overrides(mcp_server)
    return {
        ExecutionSurface.MCP: {
            tool.name: tool.fn for tool in mcp_server._tool_manager.list_tools()
        },
        ExecutionSurface.ACTION_PACKAGE: ACTION_PACKAGE_HANDLERS,
    }


def test_server_owned_executable_bindings_match_actual_handlers():
    validate_executable_bindings(_actual_runtime_handlers())


def test_action_package_binding_uses_the_existing_executor_routes():
    assert frozenset(ACTION_PACKAGE_HANDLERS) == P0_INTERNAL_CAPABILITIES
    assert {
        binding.route_key
        for binding in EXECUTABLE_BINDINGS
        if binding.execution_surface is ExecutionSurface.ACTION_PACKAGE
    } == P0_INTERNAL_CAPABILITIES


def test_duplicate_executable_binding_fails_closed():
    with pytest.raises(RuntimeError, match="Duplicate executable binding"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=(*EXECUTABLE_BINDINGS, EXECUTABLE_BINDINGS[0]),
        )


def test_missing_model_visible_binding_fails_closed():
    with pytest.raises(RuntimeError, match="missing=.*propose_work_update"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=EXECUTABLE_BINDINGS[1:],
        )


def test_orphan_executable_binding_fails_closed():
    orphan = replace(EXECUTABLE_BINDINGS[0], capability_id="unregistered")
    with pytest.raises(RuntimeError, match="orphan=.*unregistered"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=(orphan, *EXECUTABLE_BINDINGS[1:]),
        )


def test_compatibility_name_cannot_bypass_registry_binding():
    bypass = replace(EXECUTABLE_BINDINGS[0], route_key="compatibility_alias")
    with pytest.raises(RuntimeError, match="MCP compatibility binding mismatch"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=(bypass, *EXECUTABLE_BINDINGS[1:]),
        )


def test_action_package_mode_cannot_bind_to_mcp_surface():
    incompatible = replace(
        EXECUTABLE_BINDINGS[-1],
        execution_surface=ExecutionSurface.MCP,
    )
    with pytest.raises(RuntimeError, match="Incompatible MCP binding"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=(*EXECUTABLE_BINDINGS[:-1], incompatible),
        )


def test_server_owned_metadata_drift_fails_closed():
    drifted = replace(EXECUTABLE_BINDINGS[0], replay_class=ReplayClass.UNSAFE)
    with pytest.raises(RuntimeError, match="metadata mismatch"):
        validate_executable_bindings(
            _actual_runtime_handlers(),
            bindings=(drifted, *EXECUTABLE_BINDINGS[1:]),
        )


def test_runtime_handler_replacement_fails_closed():
    handlers = _actual_runtime_handlers()
    handlers[ExecutionSurface.MCP] = dict(handlers[ExecutionSurface.MCP])
    handlers[ExecutionSurface.MCP]["propose_work_update"] = lambda: None

    with pytest.raises(RuntimeError, match="changed_handlers=.*propose_work_update"):
        validate_executable_bindings(handlers)
