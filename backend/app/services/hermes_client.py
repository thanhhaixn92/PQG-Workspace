from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from pathlib import Path
from typing import Any

from acp import Agent, Client, spawn_agent_process
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AllowedOutcome,
    AvailableCommandsUpdate,
    ConfigOptionUpdate,
    CreateTerminalResponse,
    CurrentModeUpdate,
    DeniedOutcome,
    EnvVariable,
    KillTerminalResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    SessionInfoUpdate,
    TerminalOutputResponse,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UsageUpdate,
    UserMessageChunk,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from app.api.approvals import register_pending_approval, wait_for_approval
from app.api.schemas import (
    SseApprovalRequiredEvent,
    SseErrorEvent,
    SseTerminalEvent,
    SseTokenEvent,
    SseToolCallEvent,
)
from app.db.connection import get_db_connection
from app.services.audit import log_audit_event
from app.services.event_bus import event_bus
from app.services.sandbox import MAX_FILE_SIZE, get_workspace_path, resolve_and_validate_path
from app.settings import Settings

logger = logging.getLogger(__name__)


class HermesClientManager(Client):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._spawn_task: asyncio.Task[None] | None = None
        self._process_context: Any | None = None
        self._agent_conn: Any | None = None
        self._subprocess: asyncio.subprocess.Process | None = None
        self._acp_to_internal: dict[str, str] = {}
        self._internal_to_acp: dict[str, str] = {}
        self._response_buffers: dict[str, list[str]] = {}
        self._stopping = False

    async def _watch_process(self) -> None:
        if not self._subprocess:
            return

        await self._subprocess.wait()
        if not self._stopping:
            logger.warning("Hermes process exited.")
        self._agent_conn = None
        self._subprocess = None
        self._process_context = None

    async def ensure_spawned(self) -> None:
        async with self._lock:
            if self._agent_conn is not None:
                return

            logger.info("Spawning Hermes ACP process...")
            self._process_context = spawn_agent_process(
                self,
                self.settings.hermes_executable_path,
                *self.settings.hermes_args,
            )
            try:
                conn, proc = await asyncio.wait_for(
                    self._process_context.__aenter__(),
                    timeout=self.settings.hermes_startup_timeout_seconds,
                )
            except Exception:
                self._process_context = None
                raise

            self._agent_conn = conn
            self._subprocess = proc
            self._spawn_task = asyncio.create_task(self._watch_process())
            logger.info("Hermes ACP process ready.")

    async def stop(self) -> None:
        self._stopping = True

        if self._subprocess and self._subprocess.returncode is None:
            self._subprocess.terminate()
            try:
                await asyncio.wait_for(self._subprocess.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                if self._subprocess.returncode is None:
                    self._subprocess.kill()
                    await self._subprocess.wait()

        if self._spawn_task:
            self._spawn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._spawn_task

        if self._process_context:
            with contextlib.suppress(Exception):
                await self._process_context.__aexit__(None, None, None)

        self._agent_conn = None
        self._subprocess = None
        self._spawn_task = None
        self._process_context = None

    async def send_prompt(self, session_id: str, prompt: str) -> str:
        try:
            if self.settings.hermes_dev_mock:
                return await self._send_mock_prompt(session_id, prompt)

            await self.ensure_spawned()
            if not self._agent_conn:
                raise RuntimeError("Agent connection not established.")

            if session_id not in self._internal_to_acp:
                workspace = await self._get_workspace_for_internal_session(session_id)
                response = await self._agent_conn.new_session(
                    cwd=str(workspace),
                    mcp_servers=[],
                )
                self._internal_to_acp[session_id] = response.session_id
                self._acp_to_internal[response.session_id] = session_id

            acp_session_id = self._internal_to_acp[session_id]
            self._response_buffers[session_id] = []
            await self._agent_conn.prompt(
                session_id=acp_session_id,
                prompt=[TextContentBlock(type="text", text=prompt)],
            )
            await asyncio.sleep(0.05)
            return "".join(self._response_buffers.pop(session_id, [])).strip()

        except Exception as exc:
            self._response_buffers.pop(session_id, None)
            error_message = str(exc) or f"{type(exc).__name__}: {exc!r}"
            logger.error("Failed to send prompt: %s", error_message)
            await event_bus.publish(session_id, SseErrorEvent(message=error_message))
            raise RuntimeError(error_message) from exc

    async def _send_mock_prompt(self, session_id: str, prompt: str) -> str:
        """Stream a deterministic local response for first-chat smoke testing."""
        await event_bus.publish(
            session_id,
            SseToolCallEvent(
                tool_name="mock_hermes_dev_agent",
                arguments={"prompt_length": len(prompt)},
            ),
        )
        chunks = [
            "Xin chào, đây là phản hồi mẫu từ Hermes dev mock.\n\n",
            "Luồng chat, SSE và trạng thái hoàn tất đang hoạt động bình thường.\n\n",
            "Bạn có thể cấu hình Hermes thật bằng HERMES_EXECUTABLE_PATH trong backend/.env.",
        ]
        for chunk in chunks:
            await asyncio.sleep(0.05)
            await event_bus.publish(session_id, SseTokenEvent(text=chunk))
        return "".join(chunks).strip()

    def on_connect(self, conn: Agent) -> None:
        logger.info("ACP connection established with agent.")

    def _internal_session_id(self, acp_session_id: str) -> str:
        internal_session_id = self._acp_to_internal.get(acp_session_id)
        if not internal_session_id:
            raise RuntimeError(f"Unknown ACP session: {acp_session_id}")
        return internal_session_id

    async def _get_workspace_for_internal_session(self, internal_session_id: str) -> Path:
        async with get_db_connection(self.settings.db_path_resolved) as db:
            return await get_workspace_path(internal_session_id, db)

    async def session_update(
        self,
        session_id: str,
        update: (
            UserMessageChunk
            | AgentMessageChunk
            | AgentThoughtChunk
            | ToolCallStart
            | ToolCallProgress
            | AgentPlanUpdate
            | AvailableCommandsUpdate
            | CurrentModeUpdate
            | ConfigOptionUpdate
            | SessionInfoUpdate
            | UsageUpdate
        ),
        **kwargs: Any,
    ) -> None:
        internal_session_id = self._acp_to_internal.get(session_id)
        if not internal_session_id:
            logger.warning("Received event for unknown ACP session: %s", session_id)
            return

        if isinstance(update, AgentMessageChunk):
            text = ""
            if isinstance(update.content, TextContentBlock):
                text = update.content.text
            if text:
                self._response_buffers.setdefault(internal_session_id, []).append(text)
            await event_bus.publish(internal_session_id, SseTokenEvent(text=text))
        elif isinstance(update, ToolCallStart):
            await event_bus.publish(
                internal_session_id,
                SseToolCallEvent(tool_name=update.title, arguments={}),
            )

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        internal_session_id = self._internal_session_id(session_id)
        await event_bus.publish(
            internal_session_id,
            SseTerminalEvent(output=f"Terminal command blocked by policy: {command}"),
        )
        raise RuntimeError("Terminal execution is blocked in the ACP bridge. Use approved MCP run_safe_task instead.")

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs: Any) -> TerminalOutputResponse:
        return TerminalOutputResponse(output="", truncated=False)

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> KillTerminalResponse | None:
        return KillTerminalResponse()

    async def release_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> ReleaseTerminalResponse | None:
        return ReleaseTerminalResponse()

    async def wait_for_terminal_exit(self, session_id: str, terminal_id: str, **kwargs: Any) -> WaitForTerminalExitResponse:
        return WaitForTerminalExitResponse(exit_code=1)

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        internal_session_id = self._internal_session_id(session_id)
        workspace = await self._get_workspace_for_internal_session(internal_session_id)
        target = resolve_and_validate_path(workspace, path, check_binary=True)
        if not target.exists():
            raise RuntimeError(f"File not found: {path}")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"File is not valid UTF-8: {path}") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to read file: {path}") from exc

        if line is not None:
            lines = content.splitlines(keepends=True)
            start = max(line - 1, 0)
            selected = lines[start:]
            if limit is not None:
                selected = selected[:limit]
            content = "".join(selected)
        elif limit is not None:
            content = content[:limit]

        rel_path = target.relative_to(workspace).as_posix()
        async with get_db_connection(self.settings.db_path_resolved) as db:
            await log_audit_event(
                db,
                internal_session_id,
                "hermes",
                "file.read",
                target=rel_path,
                payload={"bytes": len(content.encode("utf-8"))},
            )
        return ReadTextFileResponse(content=content)

    async def write_text_file(
        self,
        content: str,
        path: str,
        session_id: str,
        **kwargs: Any,
    ) -> WriteTextFileResponse | None:
        internal_session_id = self._internal_session_id(session_id)
        workspace = await self._get_workspace_for_internal_session(internal_session_id)
        target = resolve_and_validate_path(workspace, path, check_binary=False)

        if len(content.encode("utf-8")) > MAX_FILE_SIZE:
            raise RuntimeError("File content exceeds 1 MB limit")

        rel_path = target.relative_to(workspace).as_posix()
        approval_id = f"appr-{uuid.uuid4().hex[:8]}"
        description = f"Hermes muốn ghi/sửa tệp: {rel_path}"
        await register_pending_approval(
            approval_id=approval_id,
            session_id=internal_session_id,
            action="write_workspace_file",
            target=rel_path,
            risk_level="write_internal",
            description=description,
            settings=self.settings,
        )
        await event_bus.publish(
            internal_session_id,
            SseApprovalRequiredEvent(
                approval_id=approval_id,
                action="write_workspace_file",
                target=rel_path,
                risk_level="write_internal",
                description=description,
            ),
        )
        decision = await wait_for_approval(approval_id, timeout_seconds=self.settings.hermes_request_timeout_seconds)
        if decision == "deny":
            raise RuntimeError("User denied file write")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to write file: {path}") from exc

        async with get_db_connection(self.settings.db_path_resolved) as db:
            await log_audit_event(
                db,
                internal_session_id,
                "hermes",
                "file.write",
                target=rel_path,
                payload={"size": len(content.encode("utf-8"))},
            )
        return WriteTextFileResponse()

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        if not options:
            raise RuntimeError("Hermes requested permission without options.")

        internal_session_id = self._internal_session_id(session_id)
        target = getattr(tool_call, "title", None) or getattr(tool_call, "id", None) or "Hermes tool call"
        target_text = str(target)
        description = f"Hermes yêu cầu quyền thực hiện: {target_text}"
        risk_level = "external_or_destructive" if any(
            marker in target_text.lower()
            for marker in (
                "script execution",
                "terminal",
                "shell",
                "python -c",
                "powershell",
                "cmd.exe",
                "execution via",
            )
        ) else "write_internal"
        approval_id = f"appr-{uuid.uuid4().hex[:8]}"
        await register_pending_approval(
            approval_id=approval_id,
            session_id=internal_session_id,
            action="hermes.permission",
            target=target_text,
            risk_level=risk_level,
            description=description,
            settings=self.settings,
        )
        await event_bus.publish(
            internal_session_id,
            SseApprovalRequiredEvent(
                approval_id=approval_id,
                action="hermes.permission",
                target=target_text,
                risk_level=risk_level,
                description=description,
            ),
        )
        decision = await wait_for_approval(approval_id, timeout_seconds=self.settings.hermes_request_timeout_seconds)
        if decision == "deny":
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=options[0].option_id)
        )

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass
