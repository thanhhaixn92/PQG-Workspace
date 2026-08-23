# PQG Workspace - Execution Principles

## 1. Engineering Principles

- Read existing code before changing it.
- Keep changes scoped to current phase.
- Prefer simple service boundaries over broad abstractions.
- FastAPI owns policy and validation.
- Frontend never bypasses backend to access file system, Hermes, n8n, or MCP tools.
- Do not introduce cloud dependencies for MVP.
- Do not add vector DB, graph DB, or auth system before MVP acceptance.

## 2. Implementation Rules

- Every route validates input with Pydantic models.
- Every file operation uses resolved absolute path and workspace jail.
- Every write/external/destructive operation creates audit event.
- Every long-running task has task_run record.
- Every SSE event has explicit event type and JSON payload.
- Every tool has clear schema, descriptions, and validation.
- Every secret comes from env/settings, never source code.

## 3. Backend Rules

- Use FastAPI lifespan to create/teardown Hermes client.
- Do not use scattered module-level global Hermes client imports.
- Dependency injection should return app-managed services.
- Hermes stderr goes to structured logs, not user-visible raw stream by default.
- Timeouts and retry/backoff required for Hermes process calls.
- API errors should be typed and user-readable.

## 4. Frontend Rules

- Zustand store handles canonical state.
- SSE reducer handles events by `event:` type, not by guessing payload shape.
- Approval UI must clearly show action, target, risk level, and options.
- No `allow always` option for `external_or_destructive`.
- File editor has dirty state and autosave debounce.
- UI must recover from stream errors without page reload.

## 5. MCP/FastMCP Rules

- Hermes MCP exposes exactly the nine allowlisted tools named in PRD v2.2 and `app/mcp/server.py`. Adding or removing a tool requires a PRD/security review and a matching regression update.
- Do not expose all CRUD endpoints as tools.
- MCP tools call backend/service policy layer, not raw filesystem.
- Tool parameters must use clear descriptions and validation constraints.
- LLM-generated input is untrusted input.

## 6. n8n Rules

- n8n is a sidecar, not the central orchestrator.
- Backend calls n8n; frontend does not call n8n directly.
- Webhook URL/secret come from env.
- n8n is an optional loopback-only sidecar. If it is configured, its data volume must persist; an unconfigured n8n instance must degrade gracefully and does not block v2.2 acceptance.
- `N8N_ENCRYPTION_KEY` must be fixed for a given installation.
- External workflow execution is `external_or_destructive` unless proven read-only.

## 7. Testing Rules

- Add tests with each feature.
- Do not mark phase complete with only manual testing if automated test is practical.
- Security behavior needs negative tests.
- Path traversal tests must include Windows path patterns.
- SSE format tests must validate event type and JSON payload.

## 8. Review Rules

Codex review focuses on:

- Correctness.
- Security.
- Data ownership.
- Test coverage.
- Scope control.
- Regression risk.

Codex should reject work that:

- Bypasses policy boundary.
- Writes secrets to source.
- Allows destructive/external actions without approval.
- Uses fragile parsing for ACP/SSE.
- Accesses files outside workspace.
- Expands scope without plan update.

