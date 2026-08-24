# PQG Workspace - Security And Permission Policy

## 1. Security Model

GYO/provider output, MCP tools, and model-generated strings are untrusted at the backend boundary. Backend services must validate every action before execution.

Trust boundaries:

- User UI is not trusted for permission enforcement.
- GYO/provider output is not trusted.
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

## 9. Interactive local-user admin boundary

The v2.2 administrative claim is **interactive local-user admin**, not
cryptographic proof of human presence. The constitutional Module mutation
routes (`attach`, `detach`, display-name `rename`, and `reorder`) enforce:

- a loopback request;
- an approved, canonical local browser `Origin`;
- same-origin/same-site Fetch Metadata when the browser supplies it; and
- a non-empty actor identity bound by server configuration, never `X-Actor` or
  another client/model field.

These checks provide a local-browser/CSRF boundary. They do not distinguish a
sufficiently privileged hostile local process that can reproduce HTTP headers
from the interactive user. They must not be described as WebAuthn, Windows
Hello, hardware-backed identity, biometrics, or proof of human presence.

The current admin-risk inventory is:

| Operation class | Public UI/API | Model-visible | Authorization / actor source | Approval | Docs claim / actual control | Mismatch | Package C action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Module attach | Yes, local Settings and `/api/admin/modules/{id}/attach` | No | Loopback + approved Origin + Fetch Metadata; actor from server config | Explicit UI action; no model approval path | Interactive local-user; revisioned mutation and audit | Wording/tests previously incomplete | Code-contract wording + positive/negative tests + docs |
| Module detach | Yes, local Settings and `/api/admin/modules/{id}/detach` | No | Same as attach; actor from server config | Explicit UI action; no model approval path | Interactive local-user; preserves data; revisioned audit | Wording/tests previously incomplete | Code-contract wording + positive/negative tests + docs |
| Module display-name rename | Yes, local Settings and `PATCH /api/admin/modules/{id}` | No | Same as attach; actor from server config | Explicit UI action; no model approval path | Interactive local-user; identity/route/data unchanged | Wording/tests previously incomplete | Shared boundary tests + docs |
| Module reorder | Yes, local Settings and `/api/admin/modules/reorder` | No | Same as attach; actor from server config | Explicit UI action; no model approval path | Interactive local-user; complete-set revision binding and audit | Wording/tests previously incomplete | Shared boundary tests + docs |
| Module install/settings/update/rollback/uninstall/data deletion | No constitutional Module route in v2.2 | No | Absent/fail closed | Not applicable | Not implemented in this surface | No | Expanded negative capability inventory only |
| Provider/model administration and credentials | Local Settings/API only | No | Existing local API validation; audit actor is a server-owned local-user constant; credentials stay in Credential Manager | Explicit local UI action; no GYO approval path | Local operator surface, not a GYO capability; current headers do not prove a human | No model-exposure mismatch; local-process limitation applies | Characterize and document only; provider/credential changes remain out of scope |
| Marketplace install/rollback/uninstall | Local Settings/API only; installed code remains disabled when isolation is unavailable | No | Verified server catalog; audit actor is a server-owned local-user constant | Explicit local UI action; no GYO approval path | Disabled execution state and audit | No model-exposure mismatch | Characterize and document only |
| Privacy/permission administration | No dedicated v2.2 admin route/capability | No | Absent/fail closed | Not applicable | Not implemented as a model action | No | Expanded negative capability inventory only |
| Local backup/readiness; restore execution | Backup/readiness UI exists; live restore execution is absent | No | Existing local-data integrity/readiness contract; server-owned local-user audit where applicable | Explicit local UI action where implemented | Restore remains unavailable | No model-exposure mismatch | Characterize; restore capability negative test |
| Skill create/review/enable/disable | Local review UI/API only | Admin actions: No | Existing Skill lifecycle; audit actor is server-owned by the applicable route/service contract | Explicit local UI action; no model admin approval path | GYO learning creates disabled candidates only | No model-exposure mismatch | Expanded admin-Skill negative capability inventory |

Admin-risk or unknown capability IDs must be absent from the model-visible
CapabilityRegistry. Model lookup fails closed with `capability_not_found`
before any approval request is created. This exposure rule is separate from
Package D executable-binding consistency validation.

## 10. Rejection Criteria

Codex must reject a phase if:

- destructive/external action can execute without approval.
- file operation can escape workspace.
- secrets are hardcoded.
- audit log is missing for write/external/destructive action.
- frontend alone enforces a permission rule.
- MCP tools bypass backend validation.

