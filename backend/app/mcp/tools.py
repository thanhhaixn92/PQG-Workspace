import uuid
import time
import subprocess
import asyncio
import os
import tempfile
from pathlib import Path
from pydantic import Field
from typing import Annotated, Any, Literal

from app.mcp.server import mcp_server, get_mcp_session_id
from app.api.approvals import register_pending_approval, wait_for_approval
from app.dependencies import get_settings
from app.db.connection import get_db_connection
from app.services.sandbox import resolve_and_validate_path, MAX_FILE_SIZE
from app.services.audit import log_audit_event
from app.services.n8n_webhook import trigger_n8n_webhook, validate_n8n_workflow
from app.api.schemas import ActionPackageCreateRequest, SseApprovalRequiredEvent
from app.services.event_bus import event_bus


async def _require_active_session(session_id: str, settings, *, after_approval: bool = False) -> None:
    """Fail closed when a stale MCP tool call targets an archived session."""
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute(
            "SELECT 1 FROM sessions WHERE id = ? AND archived = 0", (session_id,)
        ) as cur:
            active = await cur.fetchone()
    if active is None:
        if after_approval:
            raise PermissionError("Session is unavailable or archived after approval")
        raise ValueError("Session not found or archived")


async def _validate_proposal_input(
    session_id: str, kind: str, proposal_input: dict[str, Any], settings
) -> None:
    if kind == "work_plan_step_update":
        if set(proposal_input) != {"step_id", "changes"} or not isinstance(proposal_input.get("changes"), dict):
            raise ValueError("Invalid plan-step proposal input")
        step_id = proposal_input.get("step_id")
        changes = proposal_input["changes"]
        allowed = {"title", "description", "result", "status"}
        if not isinstance(step_id, str) or not step_id or not changes or not set(changes).issubset(allowed):
            raise ValueError("Invalid plan-step proposal input")
        if "status" in changes and changes["status"] not in {"not_started", "in_progress", "blocked", "completed"}:
            raise ValueError("Unsupported plan-step status")
        async with get_db_connection(settings.db_path_resolved) as db:
            async with db.execute(
                "SELECT 1 FROM work_plan_steps WHERE id = ? AND session_id = ?",
                (step_id, session_id),
            ) as cur:
                if await cur.fetchone() is None:
                    raise ValueError("Plan step is not part of selected Work")
        return
    if set(proposal_input) != {"work_status", "progress_percent"}:
        raise ValueError("Invalid Work-status proposal input")
    if proposal_input.get("work_status") not in {"not_started", "in_progress", "paused"}:
        raise ValueError("Unsupported Work status")
    progress = proposal_input.get("progress_percent")
    if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100:
        raise ValueError("Progress must be an integer from 0 to 100")


async def _validate_summary_scope(
    session_id: str,
    conversation_id: str | None,
    from_message_id: str | None,
    through_message_id: str | None,
    settings,
    *,
    after_approval: bool = False,
) -> None:
    await _require_active_session(session_id, settings, after_approval=after_approval)
    error_type = PermissionError if after_approval else ValueError
    async with get_db_connection(settings.db_path_resolved) as db:
        if conversation_id is not None:
            async with db.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (conversation_id, session_id),
            ) as cur:
                if await cur.fetchone() is None:
                    raise error_type("Conversation is unavailable or outside the selected Work")
        positions: list[tuple[int, str]] = []
        for message_id in (from_message_id, through_message_id):
            if message_id is None:
                continue
            async with db.execute(
                "SELECT created_at, id FROM chat_messages WHERE id = ? AND session_id = ? AND (? IS NULL OR conversation_id = ?)",
                (message_id, session_id, conversation_id, conversation_id),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                raise error_type("Summary source message is unavailable or outside the selected Work conversation")
            positions.append((row[0], row[1]))
        if len(positions) == 2 and positions[0] > positions[1]:
            raise error_type("Summary message range is reversed")


@mcp_server.tool()
async def propose_work_update(
    title: Annotated[str, Field(min_length=1, max_length=160, description="User-visible title for the proposed Action Package.")],
    kind: Annotated[Literal["work_plan_step_update", "work_status_update"], Field(description="Allowlisted Work mutation kind.")],
    proposal_input: Annotated[dict[str, Any], Field(description="Input matching the selected Action Package step schema.")],
    description: Annotated[str | None, Field(max_length=2000, description="Optional explanation shown before the user creates the package.")] = None,
    conversation_id: Annotated[str | None, Field(description="Optional active conversation in the selected Work.")] = None,
) -> str:
    """Return a validated Action Package proposal without writing any application state."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    await _require_active_session(session_id, settings)
    if kind not in {"work_plan_step_update", "work_status_update"}:
        raise ValueError("Unsupported Work proposal kind")
    if conversation_id is not None:
        async with get_db_connection(settings.db_path_resolved) as db:
            async with db.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND session_id = ? AND status = 'active'",
                (conversation_id, session_id),
            ) as cur:
                if await cur.fetchone() is None:
                    raise ValueError("Conversation does not belong to this Work or is archived")
    await _validate_proposal_input(session_id, kind, proposal_input, settings)
    request = ActionPackageCreateRequest(
        title=title,
        description=description,
        conversation_id=conversation_id,
        steps=[{"kind": kind, "input": proposal_input}],
    )
    return "DIRAP_ACTION_PROPOSAL:" + request.model_dump_json(exclude_none=True)


@mcp_server.tool()
async def save_work_context_summary(
    content: Annotated[str, Field(min_length=1, max_length=8000, description="A concise user-visible summary of decisions, unfinished work and relevant sources.")],
    conversation_id: Annotated[str | None, Field(description="Optional conversation this summary covers.", default=None)] = None,
    from_message_id: Annotated[str | None, Field(description="Optional first source message id.", default=None)] = None,
    through_message_id: Annotated[str | None, Field(description="Optional last source message id.", default=None)] = None,
) -> str:
    """Save a versioned, user-visible Work summary without injecting it into chat."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    summary = content.strip()
    if not summary:
        raise ValueError("Summary content is required")
    await _validate_summary_scope(
        session_id, conversation_id, from_message_id, through_message_id, settings
    )

    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = "Hermes requests permission to save a persistent Work context summary."
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="save_work_context_summary",
        target="work_context_summaries",
        risk_level="write_internal",
        description=description,
        payload={
            "conversation_id": conversation_id,
            "has_message_range": bool(from_message_id or through_message_id),
        },
        settings=settings,
    )
    await event_bus.publish(
        session_id,
        SseApprovalRequiredEvent(
            approval_id=approval_id,
            action="save_work_context_summary",
            target="work_context_summaries",
            risk_level="write_internal",
            description=description,
        ),
    )
    decision = await wait_for_approval(approval_id)
    if decision not in {"allow_once", "allow_for_session"}:
        raise PermissionError("Approval denied for saving Work context summary")

    await _validate_summary_scope(
        session_id,
        conversation_id,
        from_message_id,
        through_message_id,
        settings,
        after_approval=True,
    )
    now = int(time.time())
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM work_context_summaries WHERE session_id = ?", (session_id,)
        ) as cur:
            version = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO work_context_summaries (id, session_id, conversation_id, content, from_message_id, through_message_id, version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), session_id, conversation_id, summary, from_message_id, through_message_id, version, now),
        )
        await log_audit_event(
            db, session_id, "hermes", "work.context_summary_saved",
            payload={"version": version, "conversation_id": conversation_id, "has_message_range": bool(from_message_id or through_message_id), "approval_id": approval_id},
        )
        await db.commit()
    return f"Saved context summary version {version}. It remains user-visible only and is not automatically injected into chat."

@mcp_server.tool()
async def read_workspace_file(
    path: Annotated[str, Field(description="The path to the file relative to the workspace root.")]
) -> str:
    """Read a file from the workspace."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found or archived")
            workspace_path = row[0]
            
    abs_path = resolve_and_validate_path(workspace_path, path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()

@mcp_server.tool()
async def write_workspace_file(
    path: Annotated[str, Field(description="The path to the file relative to the workspace root.")],
    content: Annotated[str, Field(description="The content to write to the file. Cannot exceed 1 MB.")]
) -> str:
    """Write content to a file in the workspace. Requires user approval."""
    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        raise ValueError(f"Content size exceeds {MAX_FILE_SIZE} bytes.")
        
    session_id = get_mcp_session_id()
    settings = get_settings()
    
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found or archived")
            workspace_path = row[0]
            
    abs_path = resolve_and_validate_path(workspace_path, path)
    
    # Request approval
    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = f"Tool wants to write to {path}"
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="write_workspace_file",
        target=path,
        risk_level="write_internal",
        description=description,
        settings=settings
    )
    
    # Emit event to frontend via event bus
    from app.services.event_bus import event_bus
    from app.api.schemas import SseApprovalRequiredEvent
    event = SseApprovalRequiredEvent(
        approval_id=approval_id,
        action="write_workspace_file",
        target=path,
        risk_level="write_internal",
        description=description
    )
    await event_bus.publish(session_id, event)
    
    decision = await wait_for_approval(approval_id)
    if decision == "deny":
        raise PermissionError(f"Approval denied for writing to {path}")
        
    # Re-fetch and re-resolve after approval: an attacker must not be able to swap a
    # junction/symlink while the decision dialog is open.
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise PermissionError("Session is unavailable or archived")
            workspace_path = row[0]
    abs_path = resolve_and_validate_path(workspace_path, path)
    # Do not open the destination for writing: replacing a destination entry
    # atomically means a leaf symlink swapped after validation is replaced,
    # rather than followed.  The temporary file is inside the resolved
    # workspace, so os.replace stays on the same filesystem.
    workspace = Path(workspace_path).resolve()
    temp_fd, temp_name = tempfile.mkstemp(prefix=".dirap-mcp-", dir=workspace)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        # Validate the complete parent chain once more immediately before the
        # replacement. Existing reparse points are rejected by the sandbox.
        abs_path = resolve_and_validate_path(workspace, path)
        os.replace(temp_name, abs_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
        
    # Audit log
    async with get_db_connection(settings.db_path_resolved) as db:
        await log_audit_event(db, session_id, "system", "file.write", path, {"size": len(content)})
        await db.commit()
        
    return f"Successfully wrote to {path}"

@mcp_server.tool()
async def search_workspace(
    query: Annotated[str, Field(description="The search query.")],
    path: Annotated[str, Field(description="Directory to search in, relative to workspace root. Use '.' for root.", default=".")]
) -> str:
    """Search for a string in the workspace."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found or archived")
            workspace_path = row[0]
            
    abs_path = resolve_and_validate_path(workspace_path, path)
    
    if not abs_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
        
    results = []
    # Simple search for MVP
    for file_path in abs_path.rglob("*"):
        if file_path.is_file():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f):
                        if query in line:
                            rel_path = file_path.relative_to(abs_path)
                            results.append(f"{rel_path}:{i+1}: {line.strip()}")
                            if len(results) >= 100:
                                break
            except Exception:
                continue
        if len(results) >= 100:
            results.append("... search truncated.")
            break
            
    if not results:
        return "No matches found."
    return "\n".join(results)

@mcp_server.tool()
async def list_skills() -> str:
    """List all enabled skills and their descriptions."""
    settings = get_settings()
    skills = []
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT name, description, content FROM skills WHERE enabled = 1 AND status = 'approved'") as cur:
            async for row in cur:
                skills.append(f"Skill: {row[0]}\nDescription: {row[1] or 'N/A'}\nContent:\n{row[2]}\n---")
                
    if not skills:
        return "No skills enabled."
    return "\n".join(skills)

@mcp_server.tool()
async def update_memory(
    key: Annotated[str, Field(description="The key of the memory entry.")],
    value: Annotated[str, Field(description="The value of the memory entry.")],
    kind: Annotated[str, Field(description="The kind of memory (e.g. project_fact, preference, workflow_rule, style_rule).")],
    importance_score: Annotated[float, Field(description="Score from 0.0 to 10.0 indicating importance.", default=5.0)]
) -> str:
    """Update or create a global memory entry. Requires user approval."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    await _require_active_session(session_id, settings)
    
    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = f"Tool wants to save memory: [{kind}] {key} = {value}"
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="mcp.update_memory",
        target="memory_entries",
        risk_level="write_internal",
        description=description,
        settings=settings
    )
    
    from app.services.event_bus import event_bus
    from app.api.schemas import SseApprovalRequiredEvent
    event = SseApprovalRequiredEvent(
        approval_id=approval_id,
        action="mcp.update_memory",
        target="memory_entries",
        risk_level="write_internal",
        description=description
    )
    await event_bus.publish(session_id, event)
    
    decision = await wait_for_approval(approval_id)
    if decision == "deny":
        raise PermissionError("Approval denied for updating memory")
    await _require_active_session(session_id, settings, after_approval=True)
        
    mem_id = f"mem-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    
    async with get_db_connection(settings.db_path_resolved) as db:
        # For simplicity, we just insert. We could check if key exists and update.
        async with db.execute("SELECT id FROM memory_entries WHERE key = ? AND (session_id IS NULL OR session_id = ?)", (key, session_id)) as cur:
            row = await cur.fetchone()
            if row:
                existing_id = row[0]
                await db.execute(
                    "UPDATE memory_entries SET value = ?, kind = ?, importance_score = ? WHERE id = ?",
                    (value, kind, importance_score, existing_id)
                )
                await log_audit_event(db, session_id, "system", "memory.updated", existing_id, {"key": key})
            else:
                await db.execute(
                    "INSERT INTO memory_entries (id, session_id, key, value, kind, importance_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (mem_id, None, key, value, kind, importance_score, now)
                )
                await log_audit_event(db, session_id, "system", "memory.created", mem_id, {"key": key})
        await db.commit()
        
    return f"Successfully updated memory for {key}"

@mcp_server.tool()
async def run_safe_task(
    task_name: Annotated[str, Field(description="The exact task name to run (e.g. 'pytest', 'test', 'typecheck', 'build').")]
) -> str:
    """Run a safe, allowlisted task in the workspace. Requires user approval every time."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    await _require_active_session(session_id, settings)
    
    # 1. Allowlist enforcement
    ALLOWED_TASKS = {
        "pytest": ["pytest"],
        "test": ["npm", "run", "test"],
        "typecheck": ["npm", "run", "type-check"],
        "build": ["npm", "run", "build"],
        "lint": ["npm", "run", "lint"],
    }
    
    if task_name not in ALLOWED_TASKS:
        raise ValueError(f"Task '{task_name}' is not in the allowlist. Allowed: {list(ALLOWED_TASKS.keys())}")
        
    cmd_args = ALLOWED_TASKS[task_name]
    target_str = " ".join(cmd_args)
        
    # 2. Workspace path
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found or archived")
            workspace_path = row[0]
            
    # 3. Request approval
    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = f"Tool wants to execute task: {task_name} ({target_str})"
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="run_safe_task",
        target=target_str,
        risk_level="external_or_destructive",
        description=description,
        settings=settings
    )
    
    from app.services.event_bus import event_bus
    from app.api.schemas import SseApprovalRequiredEvent
    event = SseApprovalRequiredEvent(
        approval_id=approval_id,
        action="run_safe_task",
        target=target_str,
        risk_level="external_or_destructive",
        description=description
    )
    await event_bus.publish(session_id, event)
    
    decision = await wait_for_approval(approval_id)
    # 4. (Note: allow_for_session is rejected early in approvals API now, so we just expect allow_once)
    if decision != "allow_once":
        raise PermissionError(f"Approval denied for task '{task_name}'.")
        
    # Re-fetch/re-resolve only after approval, preventing a changed workspace
    # path from becoming the process cwd.
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ? AND archived = 0", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise PermissionError("Session is unavailable after approval")
            workspace = Path(row[0]).resolve()
            if not workspace.is_dir():
                raise PermissionError("Workspace is unavailable after approval")
            workspace_path = str(workspace)

    # 5. Execute command safely
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=str(workspace_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={} # Env scrubbed
        )
        
        # 6. Timeout and size caps
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("Command timed out after 30 seconds.")
            
        out_str = stdout.decode(errors='ignore')
        err_str = stderr.decode(errors='ignore')
        
        # Cap output size (e.g. 10KB max)
        MAX_OUTPUT = 10000
        if len(out_str) > MAX_OUTPUT:
            out_str = out_str[:MAX_OUTPUT] + "\n... [stdout truncated]"
        if len(err_str) > MAX_OUTPUT:
            err_str = err_str[:MAX_OUTPUT] + "\n... [stderr truncated]"
            
        result = f"Exit code: {proc.returncode}\nSTDOUT:\n{out_str}\nSTDERR:\n{err_str}"
        
        async with get_db_connection(settings.db_path_resolved) as db:
            await log_audit_event(db, session_id, "system", "shell.run", target_str, {"exit_code": proc.returncode})
            await db.commit()
            
        return result
        
    except Exception as e:
        async with get_db_connection(settings.db_path_resolved) as db:
            await log_audit_event(db, session_id, "system", "shell.error", target_str, {"error": str(e)})
            await db.commit()
        raise e

@mcp_server.tool()
async def call_n8n_webhook(
    workflow_name: Annotated[str, Field(description="The safe name of the workflow to call.")],
    payload: Annotated[dict, Field(description="The JSON payload to send to the workflow.")]
) -> str:
    """Trigger an n8n webhook workflow. Requires user approval every time."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    await _require_active_session(session_id, settings)
    
    validate_n8n_workflow(settings, workflow_name)
    
    # Request approval
    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    description = f"Tool wants to trigger n8n workflow: {workflow_name}"
    await register_pending_approval(
        approval_id=approval_id,
        session_id=session_id,
        action="call_n8n_webhook",
        target=workflow_name,
        risk_level="external_or_destructive",
        description=description,
        settings=settings
    )
    
    from app.services.event_bus import event_bus
    from app.api.schemas import SseApprovalRequiredEvent
    event = SseApprovalRequiredEvent(
        approval_id=approval_id,
        action="call_n8n_webhook",
        target=workflow_name,
        risk_level="external_or_destructive",
        description=description
    )
    await event_bus.publish(session_id, event)
    
    decision = await wait_for_approval(approval_id)
    if decision != "allow_once":
        raise PermissionError(f"Approval denied for workflow '{workflow_name}'.")
    await _require_active_session(session_id, settings, after_approval=True)
        
    result = await trigger_n8n_webhook(
        settings=settings,
        session_id=session_id,
        workflow_name=workflow_name,
        payload=payload,
    )
    return result.message
