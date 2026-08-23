"""Pydantic schemas for REST requests, responses, and SSE payloads."""
from __future__ import annotations

from typing import Any, Literal, Union, List, Dict, Optional
from enum import Enum

from pydantic import BaseModel, Field, SecretStr, field_validator


def _required_text(value: str, field_name: str, *, max_length: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} exceeds {max_length} characters")
    return normalized


# -----------------------------------------------------------------------------
# REST Requests & Responses
# -----------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: str = Field(..., description="Title of the session", max_length=160)
    goal: str | None = Field(None, description="Optional plain-language work goal", max_length=2_000)
    data_scope: Literal["work_only", "approved_library"] = Field(
        "work_only",
        description="Whether Hermes may use only this Work or also approved reusable knowledge.",
    )
    workspace_path: str | None = Field(
        None,
        description="Absolute path to the workspace directory. If omitted, a local workspace is created automatically.",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Title", max_length=160)

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(None, description="New session title")
    goal: str | None = Field(None, max_length=2_000)
    data_scope: Literal["work_only", "approved_library"] | None = None
    archived: bool | None = Field(None, description="Whether the session is archived")


class SessionResponse(BaseModel):
    id: str
    acp_session_id: str | None = None
    title: str
    workspace_path: str
    created_at: int
    updated_at: int
    archived: int
    goal: str | None = None
    data_scope: Literal["work_only", "approved_library"] = "work_only"
    last_opened_at: int | None = None
    work_status: Literal["not_started", "in_progress", "paused", "waiting_confirmation", "completed"] = "not_started"
    progress_percent: int = 0
    completion_proposed_at: int | None = None
    completed_at: int | None = None
    progress_source: Literal["stored", "plan_steps"] = "stored"
    next_step: dict[str, Any] | None = None
    blocked_step_count: int = 0
    pending_approval_count: int = 0


class SessionSummaryResponse(BaseModel):
    session: SessionResponse
    message_count: int
    pending_approval_count: int
    artifact_count: int
    latest_task_status: str | None = None


class OverviewResponse(BaseModel):
    """Plain-language dashboard data; it deliberately excludes local paths and diagnostics."""
    recent_work: list[SessionResponse]
    active_work_count: int
    pending_approval_count: int
    output_count: int
    latest_backup_at: int | None = None
    blocked_step_count: int = 0
    waiting_confirmation_count: int = 0
    attention_items: list[dict[str, Any]] = []
    recent_artifacts: list[dict[str, Any]] = []
    latest_work_updates: list[SessionResponse] = []


WorkspaceTaskStatus = Literal["planned", "ready", "in_progress", "blocked", "waiting", "done", "cancelled"]
WorkspaceAiEligibility = Literal["delegatable", "assistable", "human_only"]


class WorkspaceTaskCreateRequest(BaseModel):
    session_id: str
    title: str = Field(..., max_length=240)
    description: str | None = Field(None, max_length=20_000)
    priority: int = Field(0, ge=0, le=5)
    impact: int = Field(0, ge=0, le=5)
    due_at: int | None = None
    estimate_minutes: int | None = Field(None, ge=1, le=100_000)
    ai_eligibility: WorkspaceAiEligibility = "assistable"
    ai_reason: str | None = Field(None, max_length=1_000)

    @field_validator("title")
    @classmethod
    def validate_workspace_task_title(cls, value: str) -> str:
        return _required_text(value, "Task title", max_length=240)


class WorkspaceTaskUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=240)
    description: str | None = Field(None, max_length=20_000)
    status: WorkspaceTaskStatus | None = None
    priority: int | None = Field(None, ge=0, le=5)
    impact: int | None = Field(None, ge=0, le=5)
    due_at: int | None = None
    estimate_minutes: int | None = Field(None, ge=1, le=100_000)
    blocked_reason: str | None = Field(None, max_length=2_000)
    ai_eligibility: WorkspaceAiEligibility | None = None
    ai_reason: str | None = Field(None, max_length=1_000)
    version: int = Field(..., ge=1)


class WorkspaceTaskResponse(BaseModel):
    id: str
    session_id: str
    title: str
    description: str | None = None
    status: WorkspaceTaskStatus
    priority: int
    impact: int
    due_at: int | None = None
    estimate_minutes: int | None = None
    blocked_reason: str | None = None
    ai_eligibility: WorkspaceAiEligibility
    ai_reason: str | None = None
    version: int
    created_at: int
    updated_at: int
    work_title: str | None = None


class WorkspaceAiJobResponse(BaseModel):
    id: str
    task_id: str
    task_title: str
    session_id: str
    work_title: str
    status: Literal["queued", "running", "waiting_user", "completed", "failed", "cancelled"]
    stage_text: str | None = None
    output_summary: str | None = None
    conversation_id: str | None = None
    assistant_thread_id: str | None = None
    created_at: int
    updated_at: int


class WorkspaceDashboardResponse(BaseModel):
    generated_at: int
    recommendation: WorkspaceTaskResponse | None = None
    recommendation_reason: str | None = None
    alternatives: list[WorkspaceTaskResponse] = []
    timeline: list[WorkspaceTaskResponse] = []
    attention_items: list[dict[str, Any]] = []


class ArtifactResponse(BaseModel):
    id: str
    session_id: str | None = None
    relative_path: str
    kind: str
    sha256: str
    size_bytes: int
    created_at: int
    validation_status: Literal["pending", "structurally_validated", "rejected", "failed"] = "pending"
    media_type: str | None = None


class ReportCreateRequest(BaseModel):
    title: str = Field(..., max_length=160)
    content: str = Field(..., max_length=200_000)
    output_format: Literal["markdown", "html"] = "markdown"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Report title", max_length=160)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Report content cannot be empty")
        return value


class ReportCreateResponse(ArtifactResponse):
    duplicate: bool = False


class DocumentImportResponse(ArtifactResponse):
    duplicate: bool = False


class ManagedTextFileCreateRequest(BaseModel):
    relative_path: str = Field(..., max_length=500)
    content: str = Field("", max_length=1_000_000)


class ManagedFolderCreateRequest(BaseModel):
    relative_path: str = Field(..., max_length=500)


class ManagedFolderResponse(BaseModel):
    relative_path: str
    duplicate: bool = False


class PromptRequest(BaseModel):
    prompt: str = Field(..., description="The user's prompt text", max_length=20_000)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _required_text(value, "Prompt", max_length=20_000)


class TaskRunResponse(BaseModel):
    id: str
    session_id: str
    status: Literal["queued", "running", "waiting_approval", "completed", "failed", "cancelled"]
    started_at: int
    finished_at: int | None = None
    error: str | None = None
    retry_count: int
    conversation_id: str | None = None


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    task_id: str | None = None
    role: Literal["user", "assistant"]
    content: str
    created_at: int
    conversation_id: str | None = None


class ConversationCreateRequest(BaseModel):
    title: str = Field(..., max_length=160)
    purpose: str | None = Field(None, max_length=2_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Conversation title", max_length=160)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=160)
    purpose: str | None = Field(None, max_length=2_000)
    archived: bool | None = None


class ConversationResponse(BaseModel):
    id: str
    session_id: str
    title: str
    purpose: str | None = None
    status: Literal["active", "archived"]
    created_at: int
    updated_at: int
    last_opened_at: int | None = None
    message_count: int = 0
    latest_task_status: str | None = None


class WorkUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=160)
    goal: str | None = Field(None, max_length=2_000)
    data_scope: Literal["work_only", "approved_library"] | None = None
    work_status: Literal["not_started", "in_progress", "paused"] | None = None
    progress_percent: int | None = Field(None, ge=0, le=100)


class WorkCompletionResponse(BaseModel):
    work: SessionResponse


class WorkPlanPhaseCreateRequest(BaseModel):
    title: str = Field(..., max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Phase title", max_length=200)


class WorkPlanPhaseUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    status: Literal["not_started", "in_progress", "blocked", "completed"] | None = None
    sort_order: int | None = Field(None, ge=0)


class WorkPlanStepCreateRequest(BaseModel):
    phase_id: str
    title: str = Field(..., max_length=240)
    description: str | None = Field(None, max_length=4_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Step title", max_length=240)


class WorkPlanStepUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=240)
    description: str | None = Field(None, max_length=4_000)
    result: str | None = Field(None, max_length=20_000)
    status: Literal["not_started", "in_progress", "blocked", "completed"] | None = None
    sort_order: int | None = Field(None, ge=0)


class WorkPlanStepResponse(BaseModel):
    id: str
    phase_id: str
    session_id: str
    title: str
    description: str | None = None
    result: str | None = None
    sort_order: int
    status: Literal["not_started", "in_progress", "blocked", "completed"]
    source: Literal["user", "hermes"]
    created_at: int
    updated_at: int


class WorkMemoryContextUpdateRequest(BaseModel):
    context_mode: Literal["off", "suggest_only", "active_work_memory"] = "suggest_only"
    auto_learning_enabled: bool = False


class WorkMemoryContextResponse(BaseModel):
    work_id: str
    plan_step_id: str
    scope_id: str | None = None
    context_mode: Literal["off", "suggest_only", "active_work_memory"]
    auto_learning_enabled: bool
    active_memory_count: int = 0
    excluded: list[dict[str, Any]] = Field(default_factory=list)


class WorkPlanPhaseResponse(BaseModel):
    id: str
    session_id: str
    title: str
    sort_order: int
    status: Literal["not_started", "in_progress", "blocked", "completed"]
    source: Literal["user", "hermes"]
    created_at: int
    updated_at: int
    steps: list[WorkPlanStepResponse] = []


class WorkContextSummaryResponse(BaseModel):
    id: str
    session_id: str
    conversation_id: str | None = None
    content: str
    from_message_id: str | None = None
    through_message_id: str | None = None
    version: int
    created_at: int


class WorkDashboardResponse(BaseModel):
    work: SessionResponse
    next_step: WorkPlanStepResponse | None = None
    conversations: list[ConversationResponse]
    phases: list[WorkPlanPhaseResponse]
    pending_approval_count: int
    artifacts: list[ArtifactResponse]
    context_summary: WorkContextSummaryResponse | None = None
    capabilities_used: list[dict[str, Any]]
    progress_source: Literal["stored", "plan_steps"] = "stored"


class ChatMessagePageResponse(BaseModel):
    messages: list[ChatMessageResponse]
    has_more: bool


# -----------------------------------------------------------------------------
# Hermes Assistant and durable action packages
# -----------------------------------------------------------------------------

class AssistantThreadCreateRequest(BaseModel):
    title: str = Field(..., max_length=160)
    work_id: str | None = None
    conversation_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Thread title", max_length=160)


class AssistantThreadUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=160)
    archived: bool | None = None


class AssistantThreadResponse(BaseModel):
    id: str
    title: str
    work_id: str | None = None
    conversation_id: str | None = None
    status: Literal["active", "archived"]
    created_at: int
    updated_at: int
    pinned_at: int | None = None


class AssistantHistoryUpdateRequest(BaseModel):
    """Idempotent Work-scoped history setters."""

    pinned: bool | None = None
    archived: bool | None = None


class AssistantHistoryPageResponse(BaseModel):
    items: list[AssistantThreadResponse] = Field(default_factory=list)
    next_cursor: str | None = None
    cursor_version: int = 1


class AssistantTurnPartResponse(BaseModel):
    id: str
    part_type: Literal["text", "source", "tool_result", "artifact", "action_proposal", "approval", "error"]
    content: dict[str, Any]
    sort_order: int


class AssistantTurnResponse(BaseModel):
    id: str
    thread_id: str
    work_id: str | None = None
    conversation_id: str | None = None
    role: Literal["user", "assistant"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    model_id: str | None = None
    error: str | None = None
    created_at: int
    completed_at: int | None = None
    parts: list[AssistantTurnPartResponse] = []
    routing: "AssistantRoutingResponse | None" = None


class AssistantRoutingAttemptResponse(BaseModel):
    provider_profile_id: str | None = None
    model_profile_id: str | None = None
    provider_display_name: str | None = None
    model_display_name: str | None = None
    outcome: Literal["succeeded", "rate_limited", "provider_unavailable", "connection_error", "failed", "cancelled"]


class AssistantRoutingResponse(BaseModel):
    provider_display_name: str | None = None
    model_display_name: str | None = None
    route_mode: Literal["auto", "manual"]
    selection_reason: str
    attempts: list[AssistantRoutingAttemptResponse] = Field(default_factory=list)


class AssistantTurnCreateRequest(BaseModel):
    prompt: str = Field(..., max_length=20_000)
    work_id: str | None = None
    conversation_id: str | None = None
    plan_step_id: str | None = None
    attachment_artifact_ids: list[str] = Field(default_factory=list)
    # A model may be pinned for one turn.  The backend still verifies that the
    # selected profile is enabled and can serve the requested capability.
    model_profile_id: str | None = None
    route_mode: Literal["auto", "manual"] = "auto"

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _required_text(value, "Prompt", max_length=20_000)

    @field_validator("attachment_artifact_ids", mode="before")
    @classmethod
    def validate_attachment_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Attachments must be a list of artifact IDs")
        result: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Every attachment must have a valid artifact ID")
            normalized = item.strip()
            if normalized not in result:
                result.append(normalized)
        if len(result) > 10:
            raise ValueError("At most 10 attachments are allowed")
        return result


class AssistantRetryRequest(BaseModel):
    mode: Literal["same_model", "auto"] = "same_model"


class AssistantContextManifestResponse(BaseModel):
    work_id: str | None = None
    conversation_id: str | None = None
    included: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    # ``included`` remains for compatible clients. New clients consume these
    # precise provenance groups and never infer use from accessibility.
    accessible: list[dict[str, Any]] = Field(default_factory=list)
    retrieved: list[dict[str, Any]] = Field(default_factory=list)
    used: list[dict[str, Any]] = Field(default_factory=list)
    targeted: list[dict[str, Any]] = Field(default_factory=list)
    turn_id: str | None = None
    package_id: str | None = None
    byte_limit: int
    byte_count: int = 0
    version: str | None = None
    generated_at: int | None = None
    from_message_id: str | None = None
    through_message_id: str | None = None
    plan_step_id: str | None = None
    memory_context_mode: Literal["off", "suggest_only", "active_work_memory"] = "suggest_only"
    auto_learning_enabled: bool = False
    memory_hub_auto_injected: bool = False


class KnowledgeSummaryResponse(BaseModel):
    work_id: str | None = None
    counts_by_source: dict[str, int]
    counts_by_lifecycle: dict[str, int]
    context_included_count: int = 0
    context_excluded_count: int = 0
    pending_review_count: int = 0
    last_updated_at: int | None = None


class ActionStepCreateRequest(BaseModel):
    kind: Literal["work_plan_step_update", "work_status_update"]
    input: dict[str, Any] = Field(default_factory=dict)


class ActionPackageCreateRequest(BaseModel):
    title: str = Field(..., max_length=160)
    description: str | None = Field(None, max_length=2_000)
    conversation_id: str | None = None
    source_proposal_part_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list, max_length=10)
    steps: list[ActionStepCreateRequest] = Field(..., min_length=1, max_length=20)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _required_text(value, "Action package title", max_length=160)


class ActionStepResponse(BaseModel):
    id: str
    sort_order: int
    kind: str
    risk_level: str
    input: dict[str, Any]
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None
    capability: str | None = None
    expected_version: dict[str, Any] | None = None
    postcondition: dict[str, Any] | None = None


class ActionPackageResponse(BaseModel):
    id: str
    session_id: str
    conversation_id: str | None = None
    title: str
    description: str | None = None
    package_hash: str
    status: str
    approved_hash: str | None = None
    approved_at: int | None = None
    attempt_count: int
    created_at: int
    updated_at: int
    steps: list[ActionStepResponse]
    revision: int = 1
    approved_revision: int | None = None
    created_by: str = "user"
    dto_version: int = 1
    capabilities: list[str] = Field(default_factory=list)
    schema_version: int = 1
    payload_hash: str = ""
    approved_payload_hash: str | None = None
    expires_at: int | None = None
    approval_ttl_seconds: int = 900
    snapshot: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    resolved_payload: dict[str, Any] = Field(default_factory=dict)


class ActionPackageApproveRequest(BaseModel):
    expected_revision: int
    expected_payload_hash: str


class ActionPackageDecisionRequest(ActionPackageApproveRequest):
    """A deny/cancel decision bound to the package version the user reviewed."""


class ActionPackagePreflightRequest(BaseModel):
    """Proposed package used only to compute a server-side resolve/diff report."""

    title: str = Field(..., max_length=160)
    description: str | None = Field(None, max_length=2_000)
    conversation_id: str | None = None
    source_proposal_part_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list, max_length=10)
    steps: list[ActionStepCreateRequest] = Field(..., min_length=1, max_length=20)


class ActionPackagePreflightResponse(BaseModel):
    title: str
    package_hash: str
    targets: list[dict[str, Any]]
    preconditions: list[dict[str, Any]]
    diffs: list[dict[str, Any]]
    snapshot: dict[str, Any]
    capabilities: list[str]
    valid: bool
    errors: list[str] = Field(default_factory=list)
    package_id: str | None = None
    revision: int | None = None
    payload_hash: str | None = None
    expires_at: int | None = None


class ActionPackageReviseRequest(BaseModel):
    """Creator-only re-proposal that bumps the immutable payload revision."""

    title: str | None = Field(None, max_length=160)
    description: str | None = Field(None, max_length=2_000)
    steps: list[ActionStepCreateRequest] | None = Field(None, min_length=1, max_length=20)


class MarketplacePackageResponse(BaseModel):
    package_id: str
    version: str
    catalog_name: str
    publisher: str
    manifest: dict[str, Any]
    package_hash: str
    signature_valid: bool


class InstalledPluginResponse(BaseModel):
    package_id: str
    version: str
    catalog_name: str
    manifest: dict[str, Any]
    install_state: Literal["installed_disabled", "cannot_run_safely", "enabled", "failed", "removed"]
    previous_version: str | None = None
    installed_at: int
    updated_at: int


class GyoProviderCreateRequest(BaseModel):
    display_name: str = Field(..., max_length=100)
    provider_type: Literal["openai_responses", "openai_compatible"]
    base_url: str | None = Field(None, max_length=500)
    api_key: SecretStr | None = Field(default=None, exclude=True)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _required_text(value, "Provider display name", max_length=100)

    @field_validator("api_key")
    @classmethod
    def validate_optional_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("API key cannot be empty")
        return value


class GyoProviderUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    enabled: bool | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return _required_text(value, "Provider display name", max_length=100) if value is not None else None


class GyoProviderCredentialRequest(BaseModel):
    api_key: SecretStr = Field(..., min_length=1, exclude=True)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("API key cannot be empty")
        return value


class GyoProviderResponse(BaseModel):
    id: str
    display_name: str
    provider_type: Literal["openai_responses", "openai_compatible"]
    base_url: str | None = None
    enabled: bool
    retired_at: int | None = None
    credential_configured: bool
    health_status: Literal["ready", "needs_credential", "misconfigured", "unreachable", "unknown"] = "unknown"
    health_message: str | None = None
    created_at: int
    updated_at: int


class GyoModelCreateRequest(BaseModel):
    provider_profile_id: str
    display_name: str = Field(..., max_length=100)
    model_identifier: str = Field(..., max_length=200)
    tier: Literal["fast", "balanced", "deep", "vision"] = "balanced"
    capabilities: list[Literal["chat", "vision", "tools"]] = Field(default_factory=lambda: ["chat"])
    priority: int = Field(100, ge=0, le=10_000)
    make_default: bool = False

    @field_validator("display_name", "model_identifier")
    @classmethod
    def validate_model_text(cls, value: str) -> str:
        return _required_text(value, "Model field", max_length=200)

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        if "chat" not in result:
            result.insert(0, "chat")
        return result


class GyoModelUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    tier: Literal["fast", "balanced", "deep", "vision"] | None = None
    capabilities: list[Literal["chat", "vision", "tools"]] | None = None
    priority: int | None = Field(None, ge=0, le=10_000)
    enabled: bool | None = None
    make_default: bool | None = None

    @field_validator("display_name")
    @classmethod
    def validate_model_display_name(cls, value: str | None) -> str | None:
        return _required_text(value, "Model display name", max_length=100) if value is not None else None

    @field_validator("capabilities")
    @classmethod
    def normalize_optional_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        if "chat" not in result:
            result.insert(0, "chat")
        return result


class GyoModelResponse(BaseModel):
    id: str
    provider_profile_id: str
    display_name: str
    model_identifier: str
    tier: Literal["fast", "balanced", "deep", "vision"]
    capabilities: list[Literal["chat", "vision", "tools"]]
    priority: int
    enabled: bool
    is_default: bool
    cost_class: Literal["free", "unknown", "may_charge"] = "unknown"
    retired_at: int | None = None
    created_at: int
    updated_at: int


class GyoProviderHealthResponse(BaseModel):
    provider_id: str
    status: Literal["ready", "needs_credential", "misconfigured", "unreachable", "unknown"]
    message: str


class GyoDiscoveredModelResponse(BaseModel):
    """A browser-safe, non-persistent model discovered from a provider catalog."""
    model_identifier: str
    display_name: str
    tier: Literal["fast", "balanced", "deep", "vision"] = "balanced"
    capabilities: list[Literal["chat", "vision", "tools"]] = Field(default_factory=lambda: ["chat"])
    is_free: bool = True
    availability: Literal["available"] = "available"


class GyoProviderCatalogResponse(BaseModel):
    provider_id: str
    source: Literal["opencode_zen"]
    models: list[GyoDiscoveredModelResponse] = Field(default_factory=list)
    skipped_count: int = 0


class GyoZenFreeImportRequest(BaseModel):
    model_identifiers: list[str] = Field(..., min_length=1, max_length=7)

    @field_validator("model_identifiers")
    @classmethod
    def validate_model_identifiers(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            normalized = _required_text(item, "Model ID", max_length=200)
            if normalized not in result:
                result.append(normalized)
        return result


class GyoZenFreeImportResponse(BaseModel):
    provider_id: str
    models: list[GyoModelResponse] = Field(default_factory=list)
    unavailable_model_ids: list[str] = Field(default_factory=list)


class GyoRoutingPolicyUpdateRequest(BaseModel):
    auto_fallback_enabled: bool


class GyoRoutingPolicyResponse(BaseModel):
    auto_fallback_enabled: bool = False
    max_fallback_attempts: Literal[2] = 2
    fallback_scope: Literal["all_enabled_models"] = "all_enabled_models"
    enabled_model_counts: dict[Literal["free", "unknown", "may_charge"], int] = Field(
        default_factory=lambda: {"free": 0, "unknown": 0, "may_charge": 0},
    )


class ModelConfigResponse(BaseModel):
    """Browser-safe provider/model settings.

    ``provider`` and ``model`` remain for older Settings clients.  They are
    derived only from the active default model and never reveal credentials.
    """
    provider: str | None = None
    model: str | None = None
    auth_ready: bool = False
    mutable_from_browser: bool = True
    guidance: str
    providers: list[GyoProviderResponse] = Field(default_factory=list)
    models: list[GyoModelResponse] = Field(default_factory=list)
    default_model_profile_id: str | None = None
    routing_policy: GyoRoutingPolicyResponse = Field(default_factory=GyoRoutingPolicyResponse)


class AuditEventResponse(BaseModel):
    id: str
    session_id: str | None = None
    actor: str
    action: str
    target: str | None = None
    payload_json: str | None = None
    created_at: int


class ArchiveSessionResponse(BaseModel):
    status: Literal["archived"]


class CleanupSmokeTestsResponse(BaseModel):
    archived_count: int


class CleanupSmokeTestItem(BaseModel):
    id: str
    title: str


class CleanupSmokeTestsPreviewResponse(BaseModel):
    items: list[CleanupSmokeTestItem]
    confirmation_token: str


class CleanupSmokeTestsConfirmRequest(BaseModel):
    confirmation_token: str = Field(..., min_length=64, max_length=64)


class ApprovalRequest(BaseModel):
    decision: Literal["allow_once", "allow_for_session", "deny"]


class ApprovalDecisionResponse(BaseModel):
    status: Literal["recorded"]
    approval_id: str
    session_id: str | None = None
    decision: Literal["allow_once", "allow_for_session", "deny"]
    audit_action: str


class PublicTaskCreateRequest(BaseModel):
    session_id: str | None = None
    title: str | None = Field(None, max_length=240)
    description: str | None = Field(None, max_length=20_000)
    task_type: str = Field("prompt", max_length=80)
    parent_task_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value, "Task title", max_length=240)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Task description cannot be empty")
        return value

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        return _required_text(value, "Task type", max_length=80)


class PublicTaskResponse(BaseModel):
    id: str
    session_id: str | None = None
    parent_task_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: Literal["queued", "running", "waiting_approval", "succeeded", "failed", "cancelled"]
    task_type: str
    created_at: int
    updated_at: int
    duplicate: bool = False


class PublicTaskEventResponse(BaseModel):
    id: str
    task_id: str
    run_id: str | None = None
    type: str
    status: str
    data_json: str | None = None
    created_at: int


class PublicTaskActionCreateRequest(BaseModel):
    tool_name: str = Field(..., max_length=160)
    description: str = Field(..., max_length=5_000)
    risk_level: Literal["read", "write_internal", "external_or_destructive"] = "write_internal"

    @field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, value: str) -> str:
        return _required_text(value, "Tool name", max_length=160)

    @field_validator("description")
    @classmethod
    def validate_action_description(cls, value: str) -> str:
        return _required_text(value, "Action description", max_length=5_000)


class PublicTaskActionDecisionRequest(BaseModel):
    approved: bool
    output_json: str | None = Field(None, max_length=100_000)


class PublicTaskActionResponse(BaseModel):
    id: str
    task_id: str
    tool_name: str
    risk_level: str
    status: str
    description: str | None = None
    input_json: str | None = None
    output_json: str | None = None
    created_at: int
    resolved_at: int | None = None


# -----------------------------------------------------------------------------
# SSE Event Payloads
# -----------------------------------------------------------------------------

class SseTokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str
    assistant_turn_id: str | None = None
    thread_id: str | None = None


class SseToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_name: str
    arguments: dict[str, Any]


class SseTerminalEvent(BaseModel):
    type: Literal["terminal"] = "terminal"
    output: str


class SseFileDiffEvent(BaseModel):
    type: Literal["file_diff"] = "file_diff"
    path: str
    diff: str


class SseApprovalRequiredEvent(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    approval_id: str
    action: str
    target: str
    risk_level: Literal["read", "write_internal", "external_or_destructive"]
    description: str


class SsePlanUpdateEvent(BaseModel):
    type: Literal["plan_update"] = "plan_update"
    plan: str


class SseErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    assistant_turn_id: str | None = None
    thread_id: str | None = None


class SseDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    assistant_turn_id: str | None = None
    thread_id: str | None = None
    routing: dict[str, Any] | None = None


# Union of all possible SSE payloads sent over the event bus
SseEventPayload = Union[
    SseTokenEvent,
    SseToolCallEvent,
    SseTerminalEvent,
    SseFileDiffEvent,
    SseApprovalRequiredEvent,
    SsePlanUpdateEvent,
    SseErrorEvent,
    SseDoneEvent,
]

# -----------------------------------------------------------------------------
# Phase 4: Skills & Memory
# -----------------------------------------------------------------------------

class SkillCreate(BaseModel):
    name: str = Field(..., description="Unique name for the skill", max_length=160)
    description: Optional[str] = None
    content: str = Field(..., description="Skill instructions/content", max_length=100_000)
    enabled: bool = False
    status: Literal["draft"] = "draft"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _required_text(value, "Skill name", max_length=160)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Skill content cannot be empty")
        return value

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    enabled: Optional[bool] = None
    # Status lifecycle is intentionally exposed only by SkillStatusChange.
    status: None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value, "Skill name", max_length=160)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Skill content cannot be empty")
        return value

class Skill(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    content: str
    enabled: bool
    status: Literal["draft", "review_pending", "approved"]
    version: int
    updated_at: int

class SkillVersion(BaseModel):
    id: str
    skill_id: str
    version_number: int
    name: str
    description: Optional[str] = None
    content: str
    status: Literal["draft", "review_pending", "approved"]
    updated_at: int

class SkillStatusChange(BaseModel):
    status: Literal["draft", "review_pending", "approved"]


# -----------------------------------------------------------------------------
# Governed learning candidates
# -----------------------------------------------------------------------------

class CompletedRunEvidence(BaseModel):
    """Explicit, durable evidence used to create a governed learning draft.

    The IDs are provenance only.  Callers must not put raw transcript text,
    provider output, credentials, or filesystem paths in this object.
    """

    work_id: str = Field(..., min_length=1, max_length=240)
    task_id: str = Field(..., min_length=1, max_length=240)
    assistant_turn_ids: list[str] = Field(..., min_length=1, max_length=10)
    artifact_ids: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("work_id", "task_id")
    @classmethod
    def validate_scope_id(cls, value: str) -> str:
        return _required_text(value, "Evidence scope ID", max_length=240)

    @field_validator("assistant_turn_ids", "artifact_ids", mode="before")
    @classmethod
    def validate_evidence_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Evidence IDs must be a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Every evidence ID must be a non-empty string")
            item = item.strip()
            if item not in normalized:
                normalized.append(item)
        return normalized


class MemoryLearningCandidateCreate(BaseModel):
    evidence: CompletedRunEvidence
    kind: Literal["project_context", "task_continuity", "workflow_rule", "technical_decision", "lesson"]
    memory_key: str = Field(..., min_length=1, max_length=160)
    content: str = Field(..., min_length=1, max_length=8_192)
    confidence: float = Field(default=0.5, ge=0, le=1)
    sensitivity: Literal["normal", "sensitive"] = "normal"

    @field_validator("memory_key")
    @classmethod
    def validate_memory_key(cls, value: str) -> str:
        return _required_text(value, "Memory key", max_length=160)

    @field_validator("content")
    @classmethod
    def validate_memory_candidate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Memory candidate content cannot be empty")
        return value


class SkillLearningCandidateCreate(BaseModel):
    evidence: CompletedRunEvidence
    basis: Literal["user_requested", "repeated_success"]
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    content: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("name")
    @classmethod
    def validate_candidate_name(cls, value: str) -> str:
        return _required_text(value, "Skill name", max_length=160)

    @field_validator("content")
    @classmethod
    def validate_candidate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Skill candidate content cannot be empty")
        return value


class MemoryKind(str, Enum):
    preference = "preference"
    project_fact = "project_fact"
    workflow_rule = "workflow_rule"
    style_rule = "style_rule"
    temporary_note = "temporary_note"

class MemoryEntryCreate(BaseModel):
    session_id: Optional[str] = Field(None, description="If provided, scopes memory to session. Otherwise global.")
    key: str = Field(..., max_length=160)
    value: str = Field(..., max_length=20_000)
    kind: MemoryKind
    importance_score: float = Field(0.0, ge=0.0, le=100.0)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        return _required_text(value, "Memory key", max_length=160)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Memory value cannot be empty")
        return value

class MemoryEntryUpdate(BaseModel):
    key: Optional[str] = Field(None, max_length=160)
    value: Optional[str] = Field(None, max_length=20_000)
    kind: Optional[MemoryKind] = None
    importance_score: Optional[float] = Field(None, ge=0.0, le=100.0)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value, "Memory key", max_length=160)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Memory value cannot be empty")
        return value

class MemoryEntry(BaseModel):
    id: str
    session_id: Optional[str] = None
    key: str
    value: str
    kind: MemoryKind
    importance_score: float
    last_accessed_at: Optional[int] = None
    created_at: int


# -----------------------------------------------------------------------------
# CP7: Telegram Channel (Webhook & Callback)
# -----------------------------------------------------------------------------

class TelegramWebhookRequest(BaseModel):
    update_id: int
    message_id: str | None = None
    from_id: int | str | None = None
    text: str | None = None
    await_callback: bool = False


class TelegramCallbackRequest(BaseModel):
    token: str


class TelegramWebhookResponse(BaseModel):
    status: str
    task_id: str
    duplicate: bool = False
    callback_token: str | None = None


class TelegramCallbackResponse(BaseModel):
    status: str
    action: str
    task_id: str


# -----------------------------------------------------------------------------
# DIRAP v3.0 Work Items
# -----------------------------------------------------------------------------

class DirapWorkItemCreateRequest(BaseModel):
    session_id: str = Field(..., description="ID của session hiện có")
    title: str = Field(..., description="Tiêu đề work item")
    goal: str | None = Field(None, description="Mục tiêu của work item")


class DirapSourceFileAttachRequest(BaseModel):
    file_path: str = Field(..., description="Đường dẫn tệp tương đối so với workspace")
    note: str | None = Field(None, description="Ghi chú về tệp nguồn")


class DirapSourceFileResponse(BaseModel):
    id: str
    task_id: str
    file_path: str
    file_name: str
    note: str | None = None
    attached_at: int


class DirapWorkItemResponse(BaseModel):
    task_id: str
    session_id: str
    title: str | None = None
    goal: str | None = None
    status: str
    task_type: str
    session_title: str | None = None
    workspace_path: str | None = None
    source_files: list[DirapSourceFileResponse] = []
    created_at: int
    updated_at: int
    duplicate: bool = False


class DirapWorkItemDetailResponse(BaseModel):
    """Full task package với liên kết task/session, mục tiêu, trạng thái, tệp nguồn và audit trail."""
    work_item: DirapWorkItemResponse
    audit_events: list[AuditEventResponse] = []


# -----------------------------------------------------------------------------
# DIRAP v3.0 Extraction
# -----------------------------------------------------------------------------

class DirapExtractionSummaryResponse(BaseModel):
    id: str
    source_file_id: str
    source_sha256: str
    extracted_at: int
    extractor_version: str
    file_type: str
    status: Literal["fresh", "stale"]
    record_count: int


class DirapExtractionRecordResponse(BaseModel):
    id: str | None = None
    seq: int
    content: str
    provenance: str | None = None


class DirapExtractionDetailResponse(BaseModel):
    extraction: DirapExtractionSummaryResponse
    records: list[DirapExtractionRecordResponse] = []
    total_records: int = 0


# -----------------------------------------------------------------------------
# DIRAP v3.0 Knowledge Records
# -----------------------------------------------------------------------------

# Giá trị vòng đời: draft -> review_pending -> active|rejected.
# Bốn chiều xác minh lưu độc lập; mặc định: unverified/unverified/pending/none.
DirapKnowledgeLifecycle = Literal["draft", "review_pending", "active", "rejected"]
DirapVerificationState = Literal["unverified", "verified"]
DirapOwnerAcceptanceState = Literal["pending", "accepted", "rejected"]
# Vocabulary quyền hạn nguồn — tập đóng, do Codex chốt hợp đồng dữ liệu:
# none (mặc định) | regulatory | organizational | expert | derived.
DirapKnowledgeAuthorityStatus = Literal["none", "regulatory", "organizational", "expert", "derived"]


class DirapKnowledgeRecordCreateRequest(BaseModel):
    extraction_id: str = Field(..., description="ID của extraction chứa bản ghi nguồn")
    extraction_record_id: str = Field(..., description="ID của đúng một extraction record trong extraction đó")
    note: str | None = Field(None, description="Ghi chú người dùng cho bản ghi tri thức")


class DirapKnowledgeRecordResponse(BaseModel):
    id: str
    task_id: str
    session_id: str | None = None
    extraction_id: str
    extraction_record_id: str
    source_file_id: str
    source_sha256: str
    extractor_version: str
    provenance: str | None = None
    content: str
    status: DirapKnowledgeLifecycle = "draft"
    note: str | None = None
    # Bốn chiều xác minh độc lập — do server tính từ bằng chứng, client không ghi trực tiếp
    source_verification_state: DirapVerificationState = "unverified"
    calculation_verification_state: DirapVerificationState = "unverified"
    owner_acceptance_state: DirapOwnerAcceptanceState = "pending"
    authority_status: DirapKnowledgeAuthorityStatus = "none"
    created_at: int
    updated_at: int


class DirapKnowledgeSubmitRequest(BaseModel):
    """Gửi dự thảo đi rà soát (draft → review_pending)."""
    note: str | None = Field(None, description="Lưu ý kèm khi gửi rà soát")


class DirapKnowledgeApproveRequest(BaseModel):
    """Duyệt rà soát (review_pending → active) với đủ bằng chứng tham chiếu."""
    reviewer: str = Field(..., min_length=1, description="Reference của người rà soát")
    source_evidence_reference: str = Field(..., min_length=1, description="Reference bằng chứng nguồn")
    authority_status: DirapKnowledgeAuthorityStatus = Field(..., description="Quyền hạn nguồn (regulatory|organizational|expert|derived); phải khác 'none'")
    authority_reference: str = Field(..., min_length=1, description="Reference thẩm quyền")
    calculation_evidence_reference: str | None = Field(
        None, description="Reference bằng chứng tính toán (tùy chọn; có mới đặt calculation là verified)"
    )
    note: str | None = Field(None, description="Ghi chú người duyệt")


class DirapKnowledgeRejectRequest(BaseModel):
    """Từ chối rà soát (review_pending → rejected). Giữ nguyên nguồn và lịch sử."""
    reviewer: str = Field(..., min_length=1, description="Reference thêm người rà soát")
    reason: str = Field(..., min_length=1, description="Lý do từ chối (bắt buộc)")


class DirapKnowledgeEvidenceResponse(BaseModel):
    id: str
    knowledge_record_id: str
    evidence_type: str
    reference: str
    note: str | None = None
    created_at: int


class DirapKnowledgeRecordDetailResponse(DirapKnowledgeRecordResponse):
    """Bản ghi tri thức kèm danh sách bằng chứng rà soát."""
    evidence: list[DirapKnowledgeEvidenceResponse] = []


# -----------------------------------------------------------------------------
# DIRAP v3.0 Usability (chỉ đọc — policy v1)
# -----------------------------------------------------------------------------

# Sáu mục đích sử dụng chuẩn, duy nhất (USABILITY_POLICY_DECISION.md).
DirapUsabilityQueryType = Literal[
    "official_search",
    "exploratory_search",
    "analysis_input",
    "legal_review",
    "context_packaging",
    "memory_query",
]
DirapUsabilityState = Literal["usable", "partial_usable", "unusable"]


class DirapUsabilityExclusionResponse(BaseModel):
    """Một điều kiện chưa đạt của chính sách."""

    dimension: str
    required_state: str
    actual_state: str
    reason: str


class DirapUsabilityResponse(BaseModel):
    """Kết quả tính khả dụng theo chính sách v1 — chỉ đọc, không bao giờ lưu.

    - ``overall_usability_state`` là kết quả tính lúc đọc cho đúng ``query_type``;
      không có API ghi giá trị này và không có cột trong cơ sở dữ liệu.
    - ``usable_for_query_types`` chỉ gồm các mục đích đạt ``usable``
      (không gồm ``partial_usable``), tính cho chính bản ghi này.
    """

    record_id: str
    lifecycle_state: DirapKnowledgeLifecycle
    query_type: DirapUsabilityQueryType
    # Bốn chiều dữ kiện gốc (không thay đổi, chỉ đọc lại)
    source_verification_state: DirapVerificationState
    calculation_verification_state: DirapVerificationState
    owner_acceptance_state: DirapOwnerAcceptanceState
    authority_status: DirapKnowledgeAuthorityStatus
    overall_usability_state: DirapUsabilityState
    policy_version: Literal["v1"] = "v1"
    exclusions: list[DirapUsabilityExclusionResponse] = []
    usable_for_query_types: list[DirapUsabilityQueryType] = []


class DirapKnowledgeSearchResult(BaseModel):
    """Một kết quả tìm kiếm được chính sách v1 cho phép trả về."""

    record_id: str
    content_excerpt: str
    provenance: str | None = None
    lifecycle_state: DirapKnowledgeLifecycle
    # Bốn chiều dữ kiện gốc (chỉ đọc lại, không đổi)
    source_verification_state: DirapVerificationState
    calculation_verification_state: DirapVerificationState
    owner_acceptance_state: DirapOwnerAcceptanceState
    authority_status: DirapKnowledgeAuthorityStatus
    matched_field: Literal["content", "provenance", "both"]
    usability_state: DirapUsabilityState


class DirapKnowledgeSearchResponse(BaseModel):
    """Kết quả tìm kiếm tri thức có kiểm soát (chỉ đọc, không lưu).

    - ``total`` là tổng số bản ghi sau khi so khớp + lọc chính sách,
      trước khi phân trang.
    - Không bao giờ trả nội dung của bản ghi ``unusable``.
    """

    query_type: DirapUsabilityQueryType
    total: int
    limit: int
    offset: int
    results: list[DirapKnowledgeSearchResult] = []
