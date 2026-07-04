import contextvars
from mcp.server.fastmcp import FastMCP
from app.settings import get_settings
from app.db.connection import get_db_connection

# Context var for storing session ID from request
mcp_session_id_var = contextvars.ContextVar("mcp_session_id", default=None)

mcp_server = FastMCP(
    "HermesTools", 
    instructions="Core capabilities for Hermes workspace.",
    dependencies=["app.mcp.tools"] # We will register tools here by importing them, or manually
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
    
    # Mount MCP HTTP streaming endpoints
    fast_api_app.mount("/mcp", mcp_server.streamable_http_app)
    fast_api_app.mount("/sse", mcp_server.sse_app)
