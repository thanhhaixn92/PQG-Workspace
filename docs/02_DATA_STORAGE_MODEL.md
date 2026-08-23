# PQG Workspace - Data And Storage Model

## 1. Nguyen Tac Luu Tru

- App SQLite `app.db` la owner cua Work, conversation va Assistant turns hien thi cho nguoi dung cung business metadata.
- GYO chay qua `GyoOrchestrator` sau FastAPI; browser chi giao tiep REST/SSE va khong doc/sua state provider/runtime noi bo.
- Hermes/ACP state, neu con ton tai tu cai dat cu, la compatibility/historical data; GYO khong doc, sua, dong bo hoac dung lam fallback.
- Moi data co kha nang thay doi hanh vi dai han cua agent phai co audit.
- Moi secret nam ngoai source code, trong `.env` hoac store rieng.

## 2. Storage Boundaries

| Storage | Owner | Noi dung | Ghi chu |
|---|---|---|---|
| Legacy Hermes state.db (neu co) | Legacy external runtime | ACP sessions, reasoning, internal runtime/recall cu | Khong thuoc runtime GYO; khong doc, sua hoac dong bo tu app |
| app.db | PQG Workspace | Work, plan, conversations, Assistant turns/parts, task runs, approvals/action packages, knowledge, memory, skills, audit | SQLite WAL |
| workspace files | User/project | source docs, output files, editor content | Chi truy cap trong workspace path |
| n8n data volume | n8n | workflows, credentials, settings neu sidecar duoc cau hinh | Tuy chon, loopback-only |
| `.env` | Operator | secrets, webhook URLs, keys | Khong commit |

## 3. Core Entities

### sessions

Entity tuong thich dai dien cho Work. `acp_session_id` duoc giu de tuong thich schema cu, khong la owner cua GYO reasoning/runtime.

Fields bat buoc:

- `id`
- `acp_session_id`
- `title`
- `workspace_path`
- `created_at`
- `updated_at`
- `archived`

### task_runs

Dung de debug, replay, audit prompt execution.

Fields bat buoc:

- `id`
- `session_id`
- `status`
- `started_at`
- `finished_at`
- `error`
- `retry_count`

Status hop le:

- `queued`
- `running`
- `waiting_approval`
- `completed`
- `failed`
- `cancelled`

### memory_entries

Dung cho app-visible long-term memory.

Fields bat buoc:

- `id`
- `session_id`
- `key`
- `value`
- `kind`
- `importance_score`
- `last_accessed_at`
- `created_at`

Kind hop le:

- `preference`
- `project_fact`
- `workflow_rule`
- `style_rule`
- `temporary_note`

### skills

Dung cho reusable instruction content.

Fields bat buoc:

- `id`
- `name`
- `description`
- `content`
- `enabled`
- `updated_at`

### tool_permissions

Dung de dinh nghia policy cho tools.

Fields bat buoc:

- `id`
- `tool_name`
- `risk_level`
- `default_policy`
- `created_at`

Risk levels:

- `read`
- `write_internal`
- `external_or_destructive`

Default policies:

- `allow`
- `approval_once`
- `approval_session`
- `approval_always`
- `deny`

### audit_events

Dung de ghi lai hanh dong co tac dong.

Fields bat buoc:

- `id`
- `session_id`
- `actor`
- `action`
- `target`
- `payload_json`
- `created_at`

Actor hop le:

- `user`
- `codex`
- `hermes`
- `system`
- `antigravity`

### files_index

Dung de cache metadata file, khong phai source of truth cua file content.

Fields bat buoc:

- `id`
- `session_id`
- `path`
- `mime_type`
- `size_bytes`
- `created_at`

## 4. Data Ownership Rules

- User-visible Work conversations, Assistant turns va parts: app owns.
- GYO provider/runtime state: chi backend/provider boundary quan ly; browser khong doc hoac sua truc tiep.
- Session title/workspace/archive: app owns.
- Skills: app owns.
- Memory entries: app owns.
- File content: workspace owns.
- File metadata cache: app owns.
- Workflow credentials: n8n owns neu optional sidecar duoc cau hinh.
- Approval decisions: app owns.
- Audit events: app owns and should be append-only.

## 4.1 Ba lop tri thuc dai han

- Legacy `memory_entries`: kho tuong thich cu, khong dong nghia voi Memory Hub.
- Governed Memory Hub: proposal/review/activation rieng, khong auto-inject vao Assistant context.
- Knowledge Records: lifecycle tri thuc theo Work va nguon; Review chi projection, khong tao lifecycle thu hai.

## 5. Retention

- `audit_events`: giu mac dinh vinh vien trong MVP.
- `task_runs`: giu mac dinh vinh vien trong MVP; co the archive post-MVP.
- `memory_entries`: co the cleanup theo `importance_score` va `last_accessed_at`.
- `files_index`: co the rebuild tu workspace.
- n8n logs: theo config n8n, khong can sync vao app.db.

## 6. Migration Rules

- Moi thay doi schema phai co migration ro.
- Migration phai idempotent hoac co version tracking.
- Khong drop column/table khi chua co backup va user approval.
- Seed data chi gom permission defaults, khong gom secret.

## 7. Backup Rules

Can backup:

- `app.db`
- n8n data volume
- workspace important files
- `.env` separately, encrypted or private

Khong can backup trong app:

- cache file index neu co the rebuild.
- temporary logs.

