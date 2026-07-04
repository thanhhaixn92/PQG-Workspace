"""Pydantic schemas for REST requests, responses, and SSE payloads."""
from __future__ import annotations

from typing import Any, Literal, Union, List, Dict, Optional
from enum import Enum

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# REST Requests & Responses
# -----------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: str = Field(..., description="Title of the session")
    workspace_path: str | None = Field(
        None,
        description="Absolute path to the workspace directory. If omitted, a local workspace is created automatically.",
    )


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(None, description="New session title")
    archived: bool | None = Field(None, description="Whether the session is archived")


class SessionResponse(BaseModel):
    id: str
    acp_session_id: str | None = None
    title: str
    workspace_path: str
    created_at: int
    updated_at: int
    archived: int


class PromptRequest(BaseModel):
    prompt: str = Field(..., description="The user's prompt text")


class TaskRunResponse(BaseModel):
    id: str
    session_id: str
    status: Literal["queued", "running", "waiting_approval", "completed", "failed", "cancelled"]
    started_at: int
    finished_at: int | None = None
    error: str | None = None
    retry_count: int


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    task_id: str | None = None
    role: Literal["user", "assistant"]
    content: str
    created_at: int


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


class ApprovalRequest(BaseModel):
    decision: Literal["allow_once", "allow_for_session", "deny"]


class ApprovalDecisionResponse(BaseModel):
    status: Literal["recorded"]
    approval_id: str
    session_id: str | None = None
    decision: Literal["allow_once", "allow_for_session", "deny"]
    audit_action: str


# -----------------------------------------------------------------------------
# SSE Event Payloads
# -----------------------------------------------------------------------------

class SseTokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


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


class SseDoneEvent(BaseModel):
    type: Literal["done"] = "done"


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
    name: str = Field(..., description="Unique name for the skill")
    description: Optional[str] = None
    content: str = Field(..., description="Skill instructions/content")
    enabled: bool = True

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    enabled: Optional[bool] = None

class Skill(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    content: str
    enabled: bool
    updated_at: int

class MemoryKind(str, Enum):
    preference = "preference"
    project_fact = "project_fact"
    workflow_rule = "workflow_rule"
    style_rule = "style_rule"
    temporary_note = "temporary_note"

class MemoryEntryCreate(BaseModel):
    session_id: Optional[str] = Field(None, description="If provided, scopes memory to session. Otherwise global.")
    key: str
    value: str
    kind: MemoryKind
    importance_score: float = 0.0

class MemoryEntryUpdate(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    kind: Optional[MemoryKind] = None
    importance_score: Optional[float] = None

class MemoryEntry(BaseModel):
    id: str
    session_id: Optional[str] = None
    key: str
    value: str
    kind: MemoryKind
    importance_score: float
    last_accessed_at: Optional[int] = None
    created_at: int
