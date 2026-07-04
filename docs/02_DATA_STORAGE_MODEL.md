# Hermes Local Stack - Data And Storage Model

## 1. Nguyen Tac Luu Tru

- Hermes state.db la owner cua conversation/runtime state chi tiet.
- App SQLite `app.db` la owner cua business metadata.
- Khong duplicate full chat history vao app.db trong MVP.
- Moi data co kha nang thay doi hanh vi dai han cua agent phai co audit.
- Moi secret nam ngoai source code, trong `.env` hoac store rieng.

## 2. Storage Boundaries

| Storage | Owner | Noi dung | Ghi chu |
|---|---|---|---|
| Hermes state.db | Hermes | conversation history, ACP sessions, internal recall | Khong sua truc tiep tu app |
| app.db | Hermes Local Stack | sessions metadata, task runs, memory, skills, audit, permissions, files index | SQLite WAL |
| workspace files | User/project | source docs, output files, editor content | Chi truy cap trong workspace path |
| n8n data volume | n8n | workflows, credentials, settings | Can persistent volume va encryption key |
| `.env` | Operator | secrets, webhook URLs, keys | Khong commit |

## 3. Core Entities

### sessions

Dung de map app session voi ACP session.

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

- Conversation content: Hermes owns.
- Session title/workspace/archive: app owns.
- Skills: app owns.
- Memory entries: app owns.
- File content: workspace owns.
- File metadata cache: app owns.
- Workflow credentials: n8n owns.
- Approval decisions: app owns.
- Audit events: app owns and should be append-only.

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

