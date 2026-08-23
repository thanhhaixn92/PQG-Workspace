import contextvars
from mcp.server.fastmcp import FastMCP
from app.settings import get_settings
from app.db.connection import get_db_connection

# Context var for storing session ID from request
mcp_session_id_var = contextvars.ContextVar("mcp_session_id", default=None)

mcp_server = FastMCP(
    "HermesTools", 
    instructions="Core capabilities for Hermes workspace.",
    dependencies=["app.mcp.tools"], # We will register tools here by importing them, or manually
    # These are mounted below at /mcp and /sse. FastMCP's default paths would
    # otherwise be appended a second time (/mcp/mcp and /sse/sse).
    streamable_http_path="/",
    sse_path="/",
    message_path="/messages/",
)

HERMES_MCP_TOOL_ALLOWLIST = frozenset(
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

def get_mcp_session_id() -> str:
    """Get the active session_id for the current MCP tool call."""
    session_id = mcp_session_id_var.get()
    if not session_id:
        raise ValueError("Missing session_id in tool context.")
    return session_id

def setup_mcp(fast_api_app):
    """Mount FastMCP server on the FastAPI app."""
    import app.mcp.tools # This registers the tools

    registered = {tool.name for tool in mcp_server._tool_manager.list_tools()}
    if registered != HERMES_MCP_TOOL_ALLOWLIST:
        missing = sorted(HERMES_MCP_TOOL_ALLOWLIST - registered)
        unexpected = sorted(registered - HERMES_MCP_TOOL_ALLOWLIST)
        raise RuntimeError(
            f"Hermes MCP tool allowlist mismatch; missing={missing}, unexpected={unexpected}"
        )
    
    # MCP 1.x session managers are single-run objects.  Each FastAPI app
    # instance (including isolated test apps) therefore gets its own manager;
    # the tools and policy remain shared, but a stopped manager is never
    # restarted.
    mcp_server._session_manager = None

    # Mount MCP HTTP streaming endpoints
    # FastMCP exposes factories here. Mounting the bound methods themselves
    # sends ASGI's (scope, receive, send) arguments to a zero-argument
    # factory and fails at runtime.
    fast_api_app.mount("/mcp", mcp_server.streamable_http_app())
    fast_api_app.state.mcp_session_manager = mcp_server.session_manager
    fast_api_app.mount("/sse", mcp_server.sse_app())
