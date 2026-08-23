# Remediation v1.2 policy matrix

This is the required policy gate for browser and integration endpoints introduced
or materially changed by the Local MVP remediation. `session` remains the API
term; the user interface calls it **Công việc**.

| Surface | Actor / scope | Risk and confirmation | Audit allowlist | Idempotency | Archived and cross-scope behavior | Error contract |
| --- | --- | --- | --- | --- | --- | --- |
| `POST/PATCH/DELETE /api/sessions` | Local user; one work item | Create/save is explicit; archive names the item and is blocked while a run is active | `session.created/renamed/goal_updated/archived`; title, goal-presence and workspace-created flag only | Create is an explicit new resource; UI has a synchronous busy guard | Archived work rejects runtime mutations; unknown is `404` | `422` validation, `409` active run/policy conflict |
| `GET /api/sessions`, `/{id}/summary`, `/{id}/messages/page` | Local user; exact work item | Read only; pagination cursor is session-scoped | Summary-open count only; messages are never copied into audit | N/A | Cursor from another work item is `404`; archived message runtime view is `409` | `404` unknown/cursor, `409` archived, `422` page limits |
| `GET preview` + `POST /api/sessions/cleanup-smoke-tests` | Local user; generated sessions matching the known title policy | Preview is mandatory; POST confirms the exact candidate-set hash; archives only | Count and IDs only, no message content | Confirmation token binds the exact current set | New/changed candidates invalidate with `409`; no hard delete | `409` stale preview, `422` missing token |
| `POST /api/sessions/{id}/prompt`, task create/start/action | Local user or bound task actor; exact session/task | Internal runtime write; approval still applies to tool effects | Lifecycle metadata, never full prompt/description | Atomic operation claim where a client key exists; task transitions are conditional | Archived is `409`; parent/action task must exist in the same session | `404`, `409`, `422`; no fail-open transition |
| `GET /api/approvals?session_id=...`, `POST /api/approvals/{id}` | Local user; approval's originating session | Pending GET returns safe metadata; one explicit decision | Safe action/target/risk/decision only | Conditional claim `WHERE status='pending'`; one winner and one side effect | UI clears/hides approval outside originating session | `404` unknown, `409` already decided, `422` invalid decision |
| File tree/content GET and conditional PUT | Local user; exact workspace | Read/write internal; editor save is explicit or debounced only within same session | Relative path, size and revision; never content | Revision/hash and per-path lock; force-save is explicit | Archived is `409`; path must remain in current workspace; reparse/hardlinks rejected | `403` sandbox, `409` revision, `413` quota, `422` content |
| Managed document import/file/folder create | Local user; `inputs/` of exact work item | Explicit file picker/form; no archive extraction | Relative managed path, size, hash prefix and artifact ID only | Atomic claim before staging; identity is actor+operation+session+client key+payload hash | Archived is `409`; Unicode/Windows reserved names, ADS, traversal and reparse points rejected | `403`, `409`, `413` request/workspace quota, `422` size/hash/name |
| Artifact list/content and report create | Local user; registered `inputs/` or `outputs/` only | Read or explicit report publish; HTML escapes user text; browser print creates PDF outside backend | Artifact ID, relative managed path, kind and size | Atomic claim; same key/hash replays; different payload is `409` | No repository scan; unregistered/out-of-root content is rejected; archived is `409` | `403`, `404`, `409`, `422`; failed finalize removes published file |
| Skills CRUD/status/version/context eligibility | Local user; global skill catalog | Delete names the skill; lifecycle is draft→review→approved; only approved may enable | Skill ID/name/status/version metadata; content is not copied into audit | DB uniqueness on canonical name; conditional lifecycle validation | NFC/trim/whitespace/casefold identity; duplicates rejected; draft never enters MCP/context | `404`, `409` duplicate/transition, `422` validation |
| `GET /api/context-preview` | Local user; exact active work item | Read-only explanation of selected/excluded legacy skills and memory | No audit and no `last_accessed_at` mutation | N/A | Exact session scope; labels/reasons/byte counts only, not content; Memory Hub explicitly reports not injected | `404` unknown, `409` archived, `422` missing scope |
| Legacy memory CRUD and session memory reads | Local user; global or exact session | Delete names the item; memory values may enter chat context | ID/key/kind/scope metadata, not full value | Resource ID; destructive UI has confirmation/busy guard | Async reads are request-version guarded; deletion is allowed only for displayed scope | `404`, `409` scope/state, `422` validation |
| DIRAP work/source/extraction | Local user; task bound to exact session | Attach/extract is explicit; extraction is read-only against source snapshot | IDs, relative provenance, hash/status; not extracted body | Atomic claims for create/attach; unique task/path semantics | Session/task/source ownership checked; archived sessions reject mutation | `403` sandbox, `404`, `409` stale/duplicate, `413/422` resource limit |
| DIRAP knowledge/review/search/usability | Local user/reviewer; exact DIRAP task | Review requires evidence/reviewer; search/usability are read-only | Record/status/evidence references only; content omitted from audit | Atomic submit/approve/reject; one lifecycle winner | Draft/rejected terminal records never appear in controlled search; every record is task/session scoped | `404`, `409` lifecycle/stale, `422` evidence/query policy |
| Memory Hub operator routes | Loopback browser operator; explicit global/project/task scope | Proposal/import preview first; activation follows lifecycle policy | ID/kind/key/lifecycle/scope only | Service transitions are transactional; active-key conflict becomes `409` | Exact loopback origin only; no browser bearer token; scope snapshot guards late responses/import | `401/403` origin/role, `404`, `409` conflict, `422` scope |
| n8n status/test/dispatch | Approved local actor; allowlisted workflow | External effect requires approval; optional status read is safe | Workflow name, operation ID and outcome only | One operation key reused across retries; no retry without downstream dedupe contract | No session widening; production webhook/secret excluded from UAT | `409` approval/duplicate, `424/502` downstream, no false success |
| Telegram webhook/callback | HMAC-verified allowlisted sender; update or chat+message identity | External input; callback decision is single-use | Update/chat/message/user IDs and decision only | Atomic operation claim and conditional callback update | Identity cannot collide across users/chats; callback token binds its task | `401` HMAC, `403` allowlist, `409` duplicate/used/expired |
| Local-data summary/backup/list/readiness | Local user; configured local DB | Backup button is explicit; readiness is read-only; live restore is absent | Backup filename, time, coverage and integrity only | Unique timestamped filename; temp publish + manifest | DB-only coverage is explicit; credentials and external workspaces excluded | `404` DB/backup, `409` hash/integrity, `500` backup failure with cleanup |

## Shared operation-claim contract

- Identity: `actor + operation + scope + client_key`.
- States: `processing -> completed | failed`.
- Same key and same payload hash replays the completed status/body/resource ID.
- Same key with a different hash is `409`; `processing` never starts a second
  side effect; a failed attempt requires a new key.
- Expired claim deletion and replacement occur in one `BEGIN IMMEDIATE`
  transaction. `INSERT OR REPLACE` is not used.

## Explicit boundaries

- No automatic Memory Hub context injection, legacy cutover, vector/AI search,
  encrypted backup, connector package 2, production credentials, deployment,
  commit or push.
- Browser-facing operator routes never receive Credential Manager bearer tokens.
- Release A creates and verifies DB-only backups. Restore is offline maintenance
  and must stop backend/Hermes/outbox/MCP before any swap.
