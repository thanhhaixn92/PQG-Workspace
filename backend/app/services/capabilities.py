"""Server-owned capability metadata for GYO and compatibility adapters.

F6 centralizes capability *description and exposure policy* only. It does not
execute tools, grant approvals, bind actors/scopes, or change Action Package
semantics. Those enforcement points remain in their existing backend services.
"""
from __future__ import annotations

from collections.abc import Iterable
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

MCP_COMPAT_TOOL_NAMES = DEFAULT_CAPABILITY_REGISTRY.mcp_compat_tool_names()
ACTION_PACKAGE_CAPABILITY_IDS = (
    DEFAULT_CAPABILITY_REGISTRY.action_package_capability_ids()
)


def resolve_model_capability(capability_id: str) -> Capability:
    """Resolve model-visible metadata; unknown/hidden/admin requests fail closed."""

    return DEFAULT_CAPABILITY_REGISTRY.resolve_model_capability(capability_id)
