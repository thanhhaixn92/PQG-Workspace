"""Server-owned capability metadata and executable-binding validation.

The registry and binding table describe policy; they do not execute tools,
grant approvals, or bind actors/scopes. Existing MCP and Action Package
services remain the enforcement and execution points.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping as MappingABC
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RiskClass(StrEnum):
    READ_INTERNAL = "read_internal"
    WRITE_CANONICAL = "write_canonical"
    ARCHIVE_DELETE = "archive_delete"
    EXTERNAL_READ = "external_read"
    EXTERNAL_EGRESS = "external_egress"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    LOCAL_SIDE_EFFECT = "local_side_effect"
    SYSTEM_ADMIN = "system_admin"
    MODULE_ADMIN = "module_admin"
    FOUNDATION_ADMIN = "foundation_admin"


class ExecutionMode(StrEnum):
    READ_INLINE = "read_inline"
    READ_WORKER = "read_worker"
    ACTION_PACKAGE = "action_package"
    EXTERNAL_APPROVAL = "external_approval"
    LEGACY_APPROVAL = "legacy_approval"
    UNAVAILABLE = "unavailable"


class ReplayClass(StrEnum):
    SAFE = "safe"
    SAFE_AFTER_IDEMPOTENCY = "safe_after_idempotency"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


class ExecutionSurface(StrEnum):
    MCP = "mcp"
    ACTION_PACKAGE = "action_package"


ADMIN_RISK_CLASSES = frozenset(
    {
        RiskClass.SYSTEM_ADMIN,
        RiskClass.MODULE_ADMIN,
        RiskClass.FOUNDATION_ADMIN,
    }
)


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    risk_class: RiskClass
    execution_mode: ExecutionMode
    replay_class: ReplayClass
    model_visible: bool
    description: str
    mcp_compat_name: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutableBinding:
    """Expected server-owned route from a capability to one implementation."""

    capability_id: str
    execution_surface: ExecutionSurface
    route_key: str
    handler_key: str
    risk_class: RiskClass
    execution_mode: ExecutionMode
    replay_class: ReplayClass


class CapabilityNotFound(LookupError):
    """Fail-closed model lookup without starting an approval flow."""

    code = "capability_not_found"

    def __init__(self, capability_id: str) -> None:
        self.capability_id = capability_id
        super().__init__(f"{self.code}: {capability_id}")


class CapabilityRegistry:
    """Immutable registry of server-declared capability metadata."""

    def __init__(self, capabilities: Iterable[Capability]) -> None:
        by_id: dict[str, Capability] = {}
        by_mcp_name: dict[str, Capability] = {}

        for capability in capabilities:
            capability_id = capability.capability_id.strip()
            if not capability_id:
                raise ValueError("Capability ID must not be empty")
            if capability_id in by_id:
                raise ValueError(f"Duplicate capability ID: {capability_id}")
            if capability.model_visible and capability.risk_class in ADMIN_RISK_CLASSES:
                raise ValueError(
                    f"Administrative capability cannot be model-visible: {capability_id}"
                )

            mcp_name = capability.mcp_compat_name
            if mcp_name is not None:
                mcp_name = mcp_name.strip()
                if not mcp_name:
                    raise ValueError(f"Empty MCP compatibility name: {capability_id}")
                if not capability.model_visible:
                    raise ValueError(
                        f"MCP compatibility capability must be model-visible: {capability_id}"
                    )
                if mcp_name in by_mcp_name:
                    raise ValueError(f"Duplicate MCP compatibility name: {mcp_name}")
                by_mcp_name[mcp_name] = capability

            by_id[capability_id] = capability

        self._by_id: Mapping[str, Capability] = MappingProxyType(by_id)
        self._by_mcp_name: Mapping[str, Capability] = MappingProxyType(by_mcp_name)

    def model_visible_catalog(self) -> tuple[Capability, ...]:
        return tuple(
            capability for capability in self._by_id.values() if capability.model_visible
        )

    def resolve_model_capability(self, capability_id: str) -> Capability:
        capability = self._by_id.get(capability_id)
        if capability is None or not capability.model_visible:
            raise CapabilityNotFound(capability_id)
        return capability

    def mcp_compat_tool_names(self) -> frozenset[str]:
        return frozenset(self._by_mcp_name)

    def action_package_capability_ids(self) -> frozenset[str]:
        return frozenset(
            capability.capability_id
            for capability in self._by_id.values()
            if capability.execution_mode is ExecutionMode.ACTION_PACKAGE
        )


DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry(
    (
        Capability(
            capability_id="propose_work_update",
            risk_class=RiskClass.READ_INTERNAL,
            execution_mode=ExecutionMode.READ_INLINE,
            replay_class=ReplayClass.SAFE,
            model_visible=True,
            mcp_compat_name="propose_work_update",
            description="Validate and return a non-mutating Work Action Package proposal.",
        ),
        Capability(
            capability_id="save_work_context_summary",
            risk_class=RiskClass.WRITE_CANONICAL,
            execution_mode=ExecutionMode.LEGACY_APPROVAL,
            replay_class=ReplayClass.UNSAFE,
            model_visible=True,
            mcp_compat_name="save_work_context_summary",
            description="Save a versioned Work context summary through the existing approval flow.",
        ),
        Capability(
            capability_id="read_workspace_file",
            risk_class=RiskClass.READ_INTERNAL,
            execution_mode=ExecutionMode.READ_INLINE,
            replay_class=ReplayClass.SAFE,
            model_visible=True,
            mcp_compat_name="read_workspace_file",
            description="Read an authorized managed workspace file.",
        ),
        Capability(
            capability_id="write_workspace_file",
            risk_class=RiskClass.WRITE_CANONICAL,
            execution_mode=ExecutionMode.LEGACY_APPROVAL,
            replay_class=ReplayClass.UNSAFE,
            model_visible=True,
            mcp_compat_name="write_workspace_file",
            description="Write an authorized managed workspace file through the existing approval flow.",
        ),
        Capability(
            capability_id="search_workspace",
            risk_class=RiskClass.READ_INTERNAL,
            execution_mode=ExecutionMode.READ_INLINE,
            replay_class=ReplayClass.SAFE,
            model_visible=True,
            mcp_compat_name="search_workspace",
            description="Search text inside the authorized managed workspace.",
        ),
        Capability(
            capability_id="list_skills",
            risk_class=RiskClass.READ_INTERNAL,
            execution_mode=ExecutionMode.READ_INLINE,
            replay_class=ReplayClass.SAFE,
            model_visible=True,
            mcp_compat_name="list_skills",
            description="List enabled and approved Skills.",
        ),
        Capability(
            capability_id="update_memory",
            risk_class=RiskClass.WRITE_CANONICAL,
            execution_mode=ExecutionMode.LEGACY_APPROVAL,
            replay_class=ReplayClass.UNSAFE,
            model_visible=True,
            mcp_compat_name="update_memory",
            description="Update legacy Memory through the existing approval flow.",
        ),
        Capability(
            capability_id="run_safe_task",
            risk_class=RiskClass.LOCAL_SIDE_EFFECT,
            execution_mode=ExecutionMode.LEGACY_APPROVAL,
            replay_class=ReplayClass.UNSAFE,
            model_visible=True,
            mcp_compat_name="run_safe_task",
            description="Run an allowlisted local workspace task through the existing approval flow.",
        ),
        Capability(
            capability_id="call_n8n_webhook",
            risk_class=RiskClass.EXTERNAL_SIDE_EFFECT,
            execution_mode=ExecutionMode.LEGACY_APPROVAL,
            replay_class=ReplayClass.UNSAFE,
            model_visible=True,
            mcp_compat_name="call_n8n_webhook",
            description="Call an allowlisted n8n workflow through the existing every-time approval flow.",
        ),
        Capability(
            capability_id="work_plan_step_update",
            risk_class=RiskClass.WRITE_CANONICAL,
            execution_mode=ExecutionMode.ACTION_PACKAGE,
            replay_class=ReplayClass.SAFE_AFTER_IDEMPOTENCY,
            model_visible=True,
            description="Update an existing Work plan step only through Action Package execution.",
        ),
        Capability(
            capability_id="work_status_update",
            risk_class=RiskClass.WRITE_CANONICAL,
            execution_mode=ExecutionMode.ACTION_PACKAGE,
            replay_class=ReplayClass.SAFE_AFTER_IDEMPOTENCY,
            model_visible=True,
            description="Update Work status/progress only through Action Package execution.",
        ),
    )
)


def handler_key(handler: Callable[..., object]) -> str:
    """Return the stable Python implementation key used by binding validation."""

    return f"{handler.__module__}.{handler.__qualname__}"


EXECUTABLE_BINDINGS = (
    ExecutableBinding(
        "propose_work_update", ExecutionSurface.MCP, "propose_work_update",
        "app.mcp.tools.propose_work_update", RiskClass.READ_INTERNAL,
        ExecutionMode.READ_INLINE, ReplayClass.SAFE,
    ),
    ExecutableBinding(
        "save_work_context_summary", ExecutionSurface.MCP, "save_work_context_summary",
        "app.mcp.tools.save_work_context_summary", RiskClass.WRITE_CANONICAL,
        ExecutionMode.LEGACY_APPROVAL, ReplayClass.UNSAFE,
    ),
    ExecutableBinding(
        "read_workspace_file", ExecutionSurface.MCP, "read_workspace_file",
        "app.services.security_context_mcp.secure_read_workspace_file", RiskClass.READ_INTERNAL,
        ExecutionMode.READ_INLINE, ReplayClass.SAFE,
    ),
    ExecutableBinding(
        "write_workspace_file", ExecutionSurface.MCP, "write_workspace_file",
        "app.services.security_context_mcp.secure_write_workspace_file", RiskClass.WRITE_CANONICAL,
        ExecutionMode.LEGACY_APPROVAL, ReplayClass.UNSAFE,
    ),
    ExecutableBinding(
        "search_workspace", ExecutionSurface.MCP, "search_workspace",
        "app.services.security_context_mcp.secure_search_workspace", RiskClass.READ_INTERNAL,
        ExecutionMode.READ_INLINE, ReplayClass.SAFE,
    ),
    ExecutableBinding(
        "list_skills", ExecutionSurface.MCP, "list_skills",
        "app.mcp.tools.list_skills", RiskClass.READ_INTERNAL,
        ExecutionMode.READ_INLINE, ReplayClass.SAFE,
    ),
    ExecutableBinding(
        "update_memory", ExecutionSurface.MCP, "update_memory",
        "app.mcp.tools.update_memory", RiskClass.WRITE_CANONICAL,
        ExecutionMode.LEGACY_APPROVAL, ReplayClass.UNSAFE,
    ),
    ExecutableBinding(
        "run_safe_task", ExecutionSurface.MCP, "run_safe_task",
        "app.mcp.tools.run_safe_task", RiskClass.LOCAL_SIDE_EFFECT,
        ExecutionMode.LEGACY_APPROVAL, ReplayClass.UNSAFE,
    ),
    ExecutableBinding(
        "call_n8n_webhook", ExecutionSurface.MCP, "call_n8n_webhook",
        "app.mcp.tools.call_n8n_webhook", RiskClass.EXTERNAL_SIDE_EFFECT,
        ExecutionMode.LEGACY_APPROVAL, ReplayClass.UNSAFE,
    ),
    ExecutableBinding(
        "work_plan_step_update", ExecutionSurface.ACTION_PACKAGE, "work_plan_step_update",
        "app.services.action_packages._execute_work_plan_step_update", RiskClass.WRITE_CANONICAL,
        ExecutionMode.ACTION_PACKAGE, ReplayClass.SAFE_AFTER_IDEMPOTENCY,
    ),
    ExecutableBinding(
        "work_status_update", ExecutionSurface.ACTION_PACKAGE, "work_status_update",
        "app.services.action_packages._execute_work_status_update", RiskClass.WRITE_CANONICAL,
        ExecutionMode.ACTION_PACKAGE, ReplayClass.SAFE_AFTER_IDEMPOTENCY,
    ),
)


def validate_executable_bindings(
    runtime_handlers: MappingABC[ExecutionSurface, MappingABC[str, Callable[..., object]]],
    *,
    registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
    bindings: Iterable[ExecutableBinding] = EXECUTABLE_BINDINGS,
) -> None:
    """Fail closed when policy bindings and actual executable routes drift."""

    binding_list = tuple(bindings)
    by_capability: dict[str, ExecutableBinding] = {}
    route_keys: set[tuple[ExecutionSurface, str]] = set()
    handler_keys: set[str] = set()
    for binding in binding_list:
        if binding.capability_id in by_capability:
            raise RuntimeError(f"Duplicate executable binding: {binding.capability_id}")
        route_identity = (binding.execution_surface, binding.route_key)
        if route_identity in route_keys:
            raise RuntimeError(
                f"Duplicate executable route: {binding.execution_surface.value}:{binding.route_key}"
            )
        if binding.handler_key in handler_keys:
            raise RuntimeError(f"Duplicate executable handler: {binding.handler_key}")
        by_capability[binding.capability_id] = binding
        route_keys.add(route_identity)
        handler_keys.add(binding.handler_key)

    model_visible = {item.capability_id: item for item in registry.model_visible_catalog()}
    missing = sorted(set(model_visible) - set(by_capability))
    orphan = sorted(set(by_capability) - set(model_visible))
    if missing or orphan:
        raise RuntimeError(f"Executable capability binding mismatch; missing={missing}, orphan={orphan}")

    for capability_id, binding in by_capability.items():
        capability = model_visible[capability_id]
        if capability.risk_class in ADMIN_RISK_CLASSES:
            raise RuntimeError(f"Administrative capability has executable binding: {capability_id}")
        expected_metadata = (
            binding.risk_class,
            binding.execution_mode,
            binding.replay_class,
        )
        actual_metadata = (
            capability.risk_class,
            capability.execution_mode,
            capability.replay_class,
        )
        if expected_metadata != actual_metadata:
            raise RuntimeError(f"Executable binding metadata mismatch: {capability_id}")
        if binding.execution_surface is ExecutionSurface.ACTION_PACKAGE:
            if capability.execution_mode is not ExecutionMode.ACTION_PACKAGE:
                raise RuntimeError(f"Incompatible Action Package binding: {capability_id}")
            if capability.mcp_compat_name is not None or binding.route_key != capability_id:
                raise RuntimeError(f"Invalid Action Package route binding: {capability_id}")
        else:
            if capability.execution_mode in {ExecutionMode.ACTION_PACKAGE, ExecutionMode.UNAVAILABLE}:
                raise RuntimeError(f"Incompatible MCP binding: {capability_id}")
            if capability.mcp_compat_name != binding.route_key:
                raise RuntimeError(f"MCP compatibility binding mismatch: {capability_id}")

    expected_surfaces = set(ExecutionSurface)
    unexpected_surfaces = set(runtime_handlers) - expected_surfaces
    if unexpected_surfaces:
        raise RuntimeError(
            f"Unexpected executable surfaces: {sorted(str(item) for item in unexpected_surfaces)}"
        )
    for surface in ExecutionSurface:
        actual = runtime_handlers.get(surface, {})
        expected = {
            binding.route_key: binding.handler_key
            for binding in binding_list
            if binding.execution_surface is surface
        }
        actual_keys = {route: handler_key(call) for route, call in actual.items()}
        if actual_keys != expected:
            missing_routes = sorted(set(expected) - set(actual_keys))
            unexpected_routes = sorted(set(actual_keys) - set(expected))
            changed_handlers = sorted(
                route
                for route in set(expected) & set(actual_keys)
                if expected[route] != actual_keys[route]
            )
            raise RuntimeError(
                f"{surface.value} executable binding mismatch; missing={missing_routes}, "
                f"unexpected={unexpected_routes}, changed_handlers={changed_handlers}"
            )

MCP_COMPAT_TOOL_NAMES = DEFAULT_CAPABILITY_REGISTRY.mcp_compat_tool_names()
ACTION_PACKAGE_CAPABILITY_IDS = (
    DEFAULT_CAPABILITY_REGISTRY.action_package_capability_ids()
)


def resolve_model_capability(capability_id: str) -> Capability:
    """Resolve model-visible metadata; unknown/hidden/admin requests fail closed."""

    return DEFAULT_CAPABILITY_REGISTRY.resolve_model_capability(capability_id)
