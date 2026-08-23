"""Native, provider-neutral runtime for the PQG Workspace assistant.

This module deliberately owns neither Work mutations nor persistence of visible
turns.  The Assistant API remains the policy boundary for both.  Providers may
produce text and bounded structured output, but any proposed mutation must
still travel through the existing Action Package lifecycle.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

from app.services.gyo_registry import GyoModelProfile, GyoProviderProfile, GyoProviderRegistry
from app.settings import Settings

logger = logging.getLogger(__name__)

GyoEventType = Literal["token", "text", "tool_result", "artifact", "action_proposal", "error", "done"]
GyoRunStatus = Literal["completed", "failed", "cancelled"]
GyoCancelOutcome = Literal["cancelled", "not_active", "adapter_failed"]


@dataclass(frozen=True)
class GyoRunRequest:
    work_id: str | None
    prompt: str
    context: str
    model_profile_id: str | None = None
    route_mode: Literal["auto", "manual"] = "auto"
    event_channel: str | None = None
    assistant_turn_id: str | None = None
    attachment_count: int = 0


@dataclass(frozen=True)
class GyoEvent:
    type: GyoEventType
    data: dict[str, Any]


@dataclass(frozen=True)
class GyoProviderHealth:
    status: Literal["ready", "needs_credential", "misconfigured", "unreachable", "unknown"]
    message: str


@dataclass(frozen=True)
class GyoRunResult:
    text: str
    status: GyoRunStatus
    model_id: str | None
    provider_profile_id: str | None
    model_profile_id: str | None
    route_mode: Literal["auto", "manual"]
    selection_reason: str
    fallback_from_model_profile_id: str | None = None
    fallback_chain: list[dict[str, str | None]] = field(default_factory=list)
    structured_parts: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class ModelProvider(Protocol):
    """A narrow adapter seam.  Adapters never receive a database connection."""

    async def health_check(self, profile: GyoProviderProfile, credential: str | None) -> GyoProviderHealth: ...

    async def stream(
        self,
        request: GyoRunRequest,
        profile: GyoProviderProfile,
        model: GyoModelProfile,
        credential: str,
        cancel_event: asyncio.Event,
    ) -> AsyncIterator[GyoEvent]: ...


def _normalized_base_url(profile: GyoProviderProfile) -> str:
    if profile.provider_type == "openai_responses":
        return (profile.base_url or "https://api.openai.com/v1").rstrip("/")
    if not profile.base_url:
        raise ValueError("OpenAI-compatible provider requires a base URL")
    return profile.base_url.rstrip("/")


def _safe_error_message(status_code: int | None = None) -> str:
    if status_code in {401, 403}:
        return "Provider từ chối thông tin xác thực. Hãy kiểm tra lại khóa trong Cài đặt."
    if status_code == 429:
        return "Provider đang giới hạn yêu cầu. Không có thay đổi nào được thực hiện."
    return "Provider không thể hoàn tất yêu cầu. Không có thay đổi nào được thực hiện."


def _safe_failure(status_code: int | None = None, *, connection_error: bool = False) -> dict[str, Any]:
    """Classify only routing-safe failures; never preserve provider bodies."""
    if status_code in {401, 403}:
        return {"message": _safe_error_message(status_code), "retryable": False, "outcome": "failed"}
    if status_code == 429:
        return {"message": _safe_error_message(status_code), "retryable": True, "outcome": "rate_limited"}
    if status_code is not None and status_code >= 500:
        return {"message": _safe_error_message(status_code), "retryable": True, "outcome": "provider_unavailable"}
    if connection_error:
        return {"message": _safe_error_message(), "retryable": True, "outcome": "connection_error"}
    return {"message": _safe_error_message(status_code), "retryable": False, "outcome": "failed"}


class _HttpProviderBase:
    async def health_check(self, profile: GyoProviderProfile, credential: str | None) -> GyoProviderHealth:
        if not credential:
            return GyoProviderHealth("needs_credential", "Chưa có khóa trong Windows Credential Manager.")
        try:
            _normalized_base_url(profile)
        except ValueError:
            return GyoProviderHealth("misconfigured", "Provider cần một base URL hợp lệ.")
        # Configuration health deliberately performs no outbound request.  A
        # real streamed run is the authoritative provider availability check.
        return GyoProviderHealth("ready", "Đã có cấu hình và thông tin xác thực cục bộ.")


class OpenAIResponsesProvider(_HttpProviderBase):
    """Streaming adapter for the OpenAI Responses wire protocol."""

    async def stream(self, request: GyoRunRequest, profile: GyoProviderProfile, model: GyoModelProfile, credential: str, cancel_event: asyncio.Event) -> AsyncIterator[GyoEvent]:
        base_url = _normalized_base_url(profile)
        payload = {
            "model": model.model_identifier,
            "input": f"CONTEXT:\n{request.context}\n\nUSER:\n{request.prompt}",
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {credential}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream("POST", f"{base_url}/responses", json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        yield GyoEvent("error", _safe_failure(response.status_code))
                        return
                    async for line in response.aiter_lines():
                        if cancel_event.is_set():
                            return
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            return
                        with contextlib.suppress(json.JSONDecodeError):
                            event = json.loads(raw)
                            if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str):
                                yield GyoEvent("token", {"text": event["delta"]})
        except httpx.HTTPError:
            yield GyoEvent("error", _safe_failure(connection_error=True))


class OpenAICompatibleProvider(_HttpProviderBase):
    """Streaming adapter for OpenAI-compatible chat-completions endpoints."""

    async def stream(self, request: GyoRunRequest, profile: GyoProviderProfile, model: GyoModelProfile, credential: str, cancel_event: asyncio.Event) -> AsyncIterator[GyoEvent]:
        base_url = _normalized_base_url(profile)
        payload = {
            "model": model.model_identifier,
            "messages": [
                {"role": "system", "content": "Use only the supplied context. Never claim to execute a mutation."},
                {"role": "user", "content": f"CONTEXT:\n{request.context}\n\nUSER:\n{request.prompt}"},
            ],
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {credential}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        yield GyoEvent("error", _safe_failure(response.status_code))
                        return
                    async for line in response.aiter_lines():
                        if cancel_event.is_set():
                            return
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            return
                        with contextlib.suppress(json.JSONDecodeError, IndexError, KeyError, TypeError):
                            event = json.loads(raw)
                            token = event["choices"][0].get("delta", {}).get("content")
                            if isinstance(token, str) and token:
                                yield GyoEvent("token", {"text": token})
        except httpx.HTTPError:
            yield GyoEvent("error", _safe_failure(connection_error=True))


class GyoOrchestrator:
    """Select an enabled profile and broker one read-scoped model run."""

    def __init__(self, settings: Settings, *, providers: dict[str, ModelProvider] | None = None) -> None:
        self.settings = settings
        self.registry = GyoProviderRegistry(settings)
        self.providers = providers or {
            "openai_responses": OpenAIResponsesProvider(),
            "openai_compatible": OpenAICompatibleProvider(),
        }
        self._active_cancellations: dict[str, asyncio.Event] = {}
        self._active_routing: dict[str, dict[str, Any]] = {}
        self._active_lock = asyncio.Lock()

    async def stop(self) -> None:
        async with self._active_lock:
            for cancel_event in self._active_cancellations.values():
                cancel_event.set()
            self._active_cancellations.clear()
            self._active_routing.clear()

    async def cancel(self, assistant_turn_id: str | None) -> GyoCancelOutcome:
        if not assistant_turn_id:
            return "not_active"
        async with self._active_lock:
            cancel_event = self._active_cancellations.get(assistant_turn_id)
            if cancel_event is None:
                return "not_active"
            cancel_event.set()
            return "cancelled"

    async def cancel_with_selected_routing(self, assistant_turn_id: str | None) -> tuple[GyoCancelOutcome, dict[str, Any] | None]:
        """Atomically cancel and snapshot selected routing before the stream can clean it up."""
        if not assistant_turn_id:
            return "not_active", None
        async with self._active_lock:
            cancel_event = self._active_cancellations.get(assistant_turn_id)
            if cancel_event is None:
                return "not_active", None
            metadata = self._active_routing.get(assistant_turn_id)
            cancel_event.set()
            return "cancelled", dict(metadata) if metadata is not None else None

    async def selected_routing(self, assistant_turn_id: str | None) -> dict[str, Any] | None:
        """Return selected routing only while a dispatch is active; never expose credentials."""
        if not assistant_turn_id:
            return None
        async with self._active_lock:
            metadata = self._active_routing.get(assistant_turn_id)
            return dict(metadata) if metadata is not None else None

    async def health_check(self, provider_id: str) -> GyoProviderHealth:
        profile = await self.registry.get_provider(provider_id, include_retired=True)
        if profile is None:
            return GyoProviderHealth("unknown", "Không tìm thấy provider.")
        adapter = self.providers.get(profile.provider_type)
        if adapter is None:
            return GyoProviderHealth("misconfigured", "Adapter của provider chưa khả dụng.")
        return await adapter.health_check(profile, self.registry.get_credential(profile.credential_ref))

    async def stream(self, request: GyoRunRequest) -> AsyncIterator[GyoEvent]:
        try:
            candidates = await self.registry.select_model_candidates(
                model_profile_id=request.model_profile_id,
                route_mode=request.route_mode,
                prompt=request.prompt,
                attachment_count=request.attachment_count,
            )
        except ValueError as exc:
            yield GyoEvent("error", {"message": str(exc)})
            yield self._done_event("", "failed", None, None, request, "no_eligible_model", [])
            return

        cancel_event = asyncio.Event()
        if request.assistant_turn_id:
            async with self._active_lock:
                self._active_cancellations[request.assistant_turn_id] = cancel_event
        text_parts: list[str] = []
        structured_parts: list[tuple[str, dict[str, Any]]] = []
        status: GyoRunStatus = "completed"
        chosen_profile: GyoProviderProfile | None = None
        chosen_model: GyoModelProfile | None = None
        chosen_reason = "no_eligible_model"
        fallback_chain: list[dict[str, str | None]] = []
        try:
            fallback_enabled = await self.registry.auto_fallback_enabled()
            max_attempts = 3 if fallback_enabled else 1
            for attempt_index, (profile, model, reason) in enumerate(candidates[:max_attempts]):
                chosen_profile, chosen_model, chosen_reason = profile, model, reason
                if request.assistant_turn_id:
                    async with self._active_lock:
                        self._active_routing[request.assistant_turn_id] = {
                            "provider_profile_id": profile.id,
                            "model_profile_id": model.id,
                            "route_mode": request.route_mode,
                            "selection_reason": reason,
                            "fallback_chain": [],
                        }
                credential = self.registry.get_credential(profile.credential_ref)
                adapter = self.providers.get(profile.provider_type)
                attempt_outcome = "failed"
                saw_token = False
                retryable_failure = False
                terminal_failure = False
                if adapter is None or not credential:
                    error_data = {"message": "Chưa có provider GYO sẵn sàng cho model đã chọn. Hãy kiểm tra Cài đặt.", "retryable": False, "outcome": "failed"}
                    yield GyoEvent("error", error_data)
                    fallback_chain.append({"provider_profile_id": profile.id, "model_profile_id": model.id, "outcome": "failed"})
                    status = "failed"
                    break
                async for event in adapter.stream(request, profile, model, credential, cancel_event):
                    if cancel_event.is_set():
                        status = "cancelled"
                        break
                    if event.type == "token":
                        token = event.data.get("text")
                        if isinstance(token, str):
                            saw_token = True
                            text_parts.append(token)
                    elif event.type == "error":
                        attempt_outcome = str(event.data.get("outcome") or "failed")
                        retryable_failure = bool(event.data.get("retryable"))
                        if saw_token or not retryable_failure or attempt_index + 1 >= max_attempts or attempt_index + 1 >= len(candidates):
                            status = "failed"
                            terminal_failure = True
                            yield event
                        # Otherwise suppress this intermediate provider error.
                        break
                    elif event.type in {"text", "tool_result", "artifact", "action_proposal"}:
                        structured_parts.append((event.type, event.data))
                    yield event
                if cancel_event.is_set():
                    status = "cancelled"
                    fallback_chain.append({"provider_profile_id": profile.id, "model_profile_id": model.id, "outcome": "failed"})
                    break
                if saw_token and not terminal_failure:
                    attempt_outcome = "succeeded"
                    fallback_chain.append({"provider_profile_id": profile.id, "model_profile_id": model.id, "outcome": attempt_outcome})
                    status = "completed"
                    break
                fallback_chain.append({"provider_profile_id": profile.id, "model_profile_id": model.id, "outcome": attempt_outcome})
                if terminal_failure:
                    status = "failed"
                    break
                if retryable_failure and fallback_enabled and attempt_index + 1 < max_attempts and attempt_index + 1 < len(candidates):
                    next_model = candidates[attempt_index + 1][1]
                    structured_parts.append(("tool_result", {
                        "tool_name": "model_fallback", "status": "succeeded",
                        "summary": f"{model.display_name} không phản hồi tạm thời → thử {next_model.display_name}.",
                    }))
                    continue
                status = "failed"
                break
            if cancel_event.is_set():
                status = "cancelled"
        except Exception:
            logger.exception("GYO provider adapter failed")
            status = "failed"
            yield GyoEvent("error", _safe_failure(connection_error=True))
        finally:
            if request.assistant_turn_id:
                async with self._active_lock:
                    self._active_cancellations.pop(request.assistant_turn_id, None)
                    self._active_routing.pop(request.assistant_turn_id, None)
        text = "".join(text_parts)
        if status == "completed" and not text and not structured_parts:
            status = "failed"
            yield GyoEvent("error", {"message": "Provider không trả nội dung hiển thị. Không có thay đổi nào được thực hiện."})
        yield self._done_event(text, status, chosen_profile, chosen_model, request, chosen_reason, structured_parts, fallback_chain)

    async def run(self, request: GyoRunRequest) -> GyoRunResult:
        terminal: dict[str, Any] | None = None
        async for event in self.stream(request):
            if event.type == "done":
                terminal = event.data
        if terminal is None:
            return GyoRunResult("", "failed", None, None, None, request.route_mode, "missing_terminal")
        return GyoRunResult(**terminal)

    @staticmethod
    def _done_event(
        text: str,
        status: GyoRunStatus,
        profile: GyoProviderProfile | None,
        model: GyoModelProfile | None,
        request: GyoRunRequest,
        reason: str,
        structured_parts: list[tuple[str, dict[str, Any]]],
        fallback_chain: list[dict[str, str | None]] | None = None,
    ) -> GyoEvent:
        return GyoEvent("done", {
            "text": text,
            "status": status,
            "model_id": model.model_identifier if model else None,
            "provider_profile_id": profile.id if profile else None,
            "model_profile_id": model.id if model else None,
            "route_mode": request.route_mode,
            "selection_reason": reason,
            "fallback_from_model_profile_id": (fallback_chain[0]["model_profile_id"] if fallback_chain and len(fallback_chain) > 1 else None),
            "fallback_chain": fallback_chain or [],
            "structured_parts": structured_parts,
        })
