import uuid
import time
import subprocess
import asyncio
from pydantic import Field
from typing import Annotated

from app.mcp.server import mcp_server, get_mcp_session_id
from app.api.approvals import register_pending_approval, wait_for_approval
from app.dependencies import get_settings
from app.db.connection import get_db_connection
from app.services.sandbox import resolve_and_validate_path, MAX_FILE_SIZE
from app.services.audit import log_audit_event
from app.services.n8n_webhook import trigger_n8n_webhook, validate_n8n_workflow

@mcp_server.tool()
async def read_workspace_file(
    path: Annotated[str, Field(description="The path to the file relative to the workspace root.")]
) -> str:
    """Read a file from the workspace."""
    session_id = get_mcp_session_id()
    settings = get_settings()
    
    async with get_db_connection(settings.db_path_resolved) as db:
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found")
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
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found")
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
        
    # Write file
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
        
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
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found")
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
        async with db.execute("SELECT name, description, content FROM skills WHERE enabled = 1") as cur:
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
        async with db.execute("SELECT workspace_path FROM sessions WHERE id = ?", (session_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise ValueError("Session not found")
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
        
    result = await trigger_n8n_webhook(
        settings=settings,
        session_id=session_id,
        workflow_name=workflow_name,
        payload=payload,
    )
    return result.message
