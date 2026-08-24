"""Install Package B secure filesystem implementations behind existing contracts."""
from __future__ import annotations

from app.api import artifacts as artifacts_api
from app.api import assistant as assistant_api
from app.api import dirap as dirap_api
from app.api import files as files_api
from app.services import assistant_context as assistant_context_api
from app.services.security_artifact_create import (
    secure_create_managed_folder,
    secure_create_managed_text_file,
    secure_create_report,
)
from app.services.security_artifact_import import secure_get_artifact_content, secure_import_document
from app.services.security_context_mcp import (
    SecureContextBroker,
    secure_read_workspace_file,
    secure_search_workspace,
    secure_validated_attachments,
    secure_write_workspace_file,
)
from app.services.security_dirap import (
    secure_attach_source_file,
    secure_extract_source_file,
    secure_refresh_source_freshness,
)
from app.services.security_files import secure_get_file_content, secure_get_file_tree, secure_put_file_content


def _replace_router_route(router, original, method: str, call) -> None:
    """Patch one APIRouter route before FastAPI clones it; repeat calls are safe."""
    matches = [
        route
        for route in router.routes
        if getattr(route, "endpoint", None) in {original, call}
        and method.upper() in (getattr(route, "methods", None) or set())
    ]
    if len(matches) != 1:
        name = getattr(original, "__name__", repr(original))
        raise RuntimeError(
            f"Package B expected exactly one router endpoint {name} [{method}]; found {len(matches)}"
        )
    route = matches[0]
    if not hasattr(route, "dependant"):
        raise RuntimeError(f"Package B route has no FastAPI dependant: {method} {route.path}")
    route.endpoint = call
    route.dependant.call = call


def install_security_api_overrides() -> None:
    """Install filesystem-sensitive REST/F7 replacements before app.include_router."""
    route_replacements = [
        (files_api.router, files_api.get_file_tree, "GET", secure_get_file_tree),
        (files_api.router, files_api.get_file_content, "GET", secure_get_file_content),
        (files_api.router, files_api.put_file_content, "PUT", secure_put_file_content),
        (artifacts_api.router, artifacts_api.get_artifact_content, "GET", secure_get_artifact_content),
        (artifacts_api.router, artifacts_api.import_document, "POST", secure_import_document),
        (artifacts_api.router, artifacts_api.create_managed_text_file, "POST", secure_create_managed_text_file),
        (artifacts_api.router, artifacts_api.create_managed_folder, "POST", secure_create_managed_folder),
        (artifacts_api.router, artifacts_api.create_report, "POST", secure_create_report),
        (dirap_api.router, dirap_api.attach_source_file, "POST", secure_attach_source_file),
        (dirap_api.router, dirap_api.extract_source_file, "POST", secure_extract_source_file),
    ]
    for router, original, method, call in route_replacements:
        _replace_router_route(router, original, method, call)

    dirap_api._refresh_source_freshness = secure_refresh_source_freshness
    assistant_api._validated_attachments = secure_validated_attachments
    assistant_context_api.ContextBroker = SecureContextBroker


def install_security_mcp_overrides(mcp_server) -> None:
    """Replace the three filesystem MCP tools after their normal registration."""
    replacements = {
        "read_workspace_file": secure_read_workspace_file,
        "write_workspace_file": secure_write_workspace_file,
        "search_workspace": secure_search_workspace,
    }
    current = {tool.name for tool in mcp_server._tool_manager.list_tools()}
    for name, call in replacements.items():
        if name not in current:
            raise RuntimeError(f"Package B expected MCP tool {name!r} before hardening")
        mcp_server.remove_tool(name)
        mcp_server.add_tool(call, name=name)
