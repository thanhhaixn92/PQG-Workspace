# PQG Workspace - Security And Permission Policy

## 1. Security Model

Hermes, MCP tools, and model-generated strings are untrusted at the backend boundary. Backend services must validate every action before execution.

Trust boundaries:

- User UI is not trusted for permission enforcement.
- Hermes output is not trusted.
- MCP tool input is not trusted.
- n8n webhook payloads are not trusted.
- FastAPI service layer is the enforcement point.

## 2. Risk Levels

### read

Examples:

- list workspace files
- read workspace file
- search workspace
- list enabled skills
- read memory

Default policy: allow if inside workspace and below limits.

### write_internal

Examples:

- write workspace file
- create/update memory
- create/update skill
- rename generated output

Default policy: approval once or approval for session.

### external_or_destructive

Examples:

- delete file
- overwrite large file
- run shell command
- call n8n webhook that sends data externally
- send email
- upload/export data
- change secrets/config

Default policy: approval every time.

No `allow always` for this class.

## 3. Approval Options

Allowed options:

- `allow_once`
- `allow_for_session`
- `deny`

Optional post-MVP:

- `allow_always` only for read or low-risk write_internal tools, never for destructive/external tools.

## 4. Audit Requirements

Audit event required for:

- prompt submitted
- task run started/completed/failed
- approval requested
- approval decision
- file write/delete
- memory create/update/delete
- skill create/update/delete/enable/disable
- shell command request
- n8n webhook request
- MCP tool call with write/external/destructive effect

Audit payload should include:

- actor
- action
- target
- risk level
- decision if approval-related
- summarized payload, not raw secret
- timestamp

## 5. Workspace Sandbox

Rules:

- Store canonical `workspace_path` per session.
- Resolve requested path to absolute canonical path.
- Reject path if not inside `workspace_path`.
- Reject path traversal.
- Reject symlink escape if practical in platform support.
- Enforce max file size.
- Enforce allowed text/binary handling.

Windows-specific tests required:

- `..\secret.txt`
- `C:\Users\dtron\.ssh\id_rsa`
- mixed slash/backslash traversal
- path with encoded or normalized segments if route accepts URL input

## 6. CORS

- Development can allow exact localhost origins only.
- Never use wildcard `*` with credentials.
- Production/multi-user phase needs explicit origin config.

## 7. Secrets

Never commit:

- API keys
- n8n webhook secrets
- `N8N_ENCRYPTION_KEY`
- OAuth tokens
- session cookies

Secrets belong in:

- `.env`
- OS secret store
- private local config excluded from git

## 8. n8n Security

- n8n is not public by default.
- Webhooks need secret header or IP whitelist.
- Use production webhook URL only for active workflows.
- Pin or track n8n version; do not use known vulnerable versions.
- n8n is optional for v2.2 and must remain loopback-only when enabled.
- If n8n is configured, a persistent `/home/node/.n8n` volume and fixed `N8N_ENCRYPTION_KEY` are required. An unconfigured sidecar must report unavailable without a fake-ready state.

## 9. Rejection Criteria

Codex must reject a phase if:

- destructive/external action can execute without approval.
- file operation can escape workspace.
- secrets are hardcoded.
- audit log is missing for write/external/destructive action.
- frontend alone enforces a permission rule.
- MCP tools bypass backend validation.

