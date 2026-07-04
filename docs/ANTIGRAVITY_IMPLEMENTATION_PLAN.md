# Hermes Local Stack - Antigravity Implementation Plan

## Phase 12-18 + UX Status Update - 2026-07-03

Implemented by Codex after Antigravity quota was exhausted:

- Phase 12: Added task detail API and grouped Activity Panel audit events by task id.
- Phase 13: Added safe runtime smoke API and Runtime Panel quick check UI.
- Phase 14: Added local data summary/backup API and "Du lieu cuc bo" UI panel.
- Phase 15: Added file content metadata, write conflict detection, file tree refresh after save, and editor conflict actions.
- Phase 16: Added Memory/Skills search, Vietnamese memory kind labels, and quick skill toggle.
- Phase 17: Added safe n8n status/allowlist API, Runtime Panel allowlist display, and approved echo workflow test.
- Phase 18: Lazy-loaded Mermaid renderer and kept Excalidraw out of scope.
- UX pass: Added smarter chat file cards, task summary headers in Activity, Vietnamese prompt guidance for Hermes responses, and a daily acceptance checklist.

Verification:

- Backend: `.venv\Scripts\pytest.exe tests -v` -> 79 passed.
- Frontend: `npm run type-check` -> passed.
- Frontend: `npm run test -- --run` -> 91 passed.
- Frontend: `npm run build` -> passed, with expected Mermaid chunk-size warnings.
- Source text check for common mojibake patterns in `frontend/src/components`, `frontend/src/api`, and `frontend/src/store` -> no results.

## 1. Muc Tieu

Xay dung ban local-first cua Hermes office assistant theo kien truc:

- Hermes Agent chay qua ACP lam loi reasoning/execution.
- FastAPI lam backend boundary: policy, audit, streaming, dependency lifecycle.
- React/Zustand lam frontend dieu khien chat, file, memory, skills, approval.
- SQLite chi luu business metadata, khong duplicate toan bo hoi thoai Hermes.
- n8n la automation sidecar, chi dung cho workflow dinh ky hoac external automation.
- Codex dong vai tro checker: review code, chay test, kiem tra acceptance criteria, va phe duyet ky thuat neu dat checklist.

Nguyen tac quan trong: Codex co the duyet ket qua ky thuat thay nguoi dung cho cac thay doi nam trong plan nay. Codex khong duoc tu phe duyet cac hanh dong rui ro cao nhu xoa du lieu that, gui email/bao cao ra ngoai, public webhook/API len internet, cap quyen `allow always` cho destructive command, hoac thay doi ngoai workspace neu chua co yeu cau ro.

## 2. Pham Vi Ban Dau

### In Scope

- Backend FastAPI co lifecycle quan ly Hermes ACP process.
- Typed SSE bridge tu ACP updates sang frontend.
- SQLite schema cho sessions, task_runs, memory_entries, skills, tool_permissions, audit_events, files_index.
- Frontend chat UI, session list, approval prompt, file editor co autosave, memory/skills CRUD.
- Workspace sandbox cho file operations.
- FastMCP/MCP tool layer gioi han 4-6 tool cot loi.
- n8n local integration qua webhook co hardening toi thieu.
- Test va audit checklist cho tung phase.

### Out of Scope

- Multi-user auth production.
- Cloud deployment.
- Vector database rieng.
- Graph database.
- Agent tu tao tool moi cap Level 3 autonomy.
- Public internet exposure cho n8n/FastAPI.
- Dong bo hai chieu toan bo conversation history tu Hermes state.db sang app.db.

## 3. Kien Truc Bat Buoc

```text
React/Zustand UI
  |
  | REST + typed SSE
  v
FastAPI Backend
  |
  | ACP client / stdio process boundary
  v
Hermes Agent ACP Server
  |
  | tools, terminal, file ops, approvals
  v
Workspace sandbox

SQLite app.db:
  sessions
  task_runs
  memory_entries
  skills
  tool_permissions
  audit_events
  files_index

n8n sidecar:
  webhook-triggered workflows only
```

FastAPI la policy boundary. Frontend khong noi truc tiep voi Hermes process, n8n, MCP server, hoac file system.

## 4. Stack De Xuat

- Backend: Python 3.11+, FastAPI, Pydantic Settings, aiosqlite hoac SQLAlchemy async.
- ACP: official `agent-client-protocol` client/protocol integration; khong tu viet parser JSON-RPC thu cong neu SDK dap ung duoc.
- Frontend: Vite + React + TypeScript + Zustand.
- Editor: Monaco.
- Diagram: Mermaid la intermediate format; Excalidraw integration la phase sau.
- DB: SQLite WAL mode.
- Automation: n8n Docker Compose voi persistent volume va fixed `N8N_ENCRYPTION_KEY`.
- MCP: FastMCP 3.x, expose tool co chon loc.

## 5. Database Schema Yeu Cau

Antigravity can tao migration dau tien voi cac bang sau:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  acp_session_id TEXT UNIQUE,
  title TEXT,
  workspace_path TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  archived INTEGER DEFAULT 0
);

CREATE TABLE task_runs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  status TEXT NOT NULL,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  error TEXT,
  retry_count INTEGER DEFAULT 0
);

CREATE TABLE memory_entries (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(id),
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  kind TEXT NOT NULL,
  importance_score REAL DEFAULT 0,
  last_accessed_at INTEGER,
  created_at INTEGER NOT NULL
);

CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  content TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  updated_at INTEGER NOT NULL
);

CREATE TABLE tool_permissions (
  id TEXT PRIMARY KEY,
  tool_name TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  default_policy TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  payload_json TEXT,
  created_at INTEGER NOT NULL
);

CREATE TABLE files_index (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES sessions(id),
  path TEXT NOT NULL,
  mime_type TEXT,
  size_bytes INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX idx_sessions_updated ON sessions(updated_at);
CREATE INDEX idx_task_runs_session ON task_runs(session_id);
CREATE INDEX idx_memory_session ON memory_entries(session_id);
CREATE INDEX idx_audit_session ON audit_events(session_id);
```

## 6. Permission Model

Antigravity phai implement 3 muc risk:

| Risk level | Vi du | Default |
|---|---|---|
| read | list file, read file, search workspace, load skill | allow if inside workspace |
| write_internal | create/edit file inside workspace, update memory, update skill | approval once/session |
| external_or_destructive | delete file, overwrite large file, shell command, call n8n webhook, send email/export external | manual approval every time |

Khong co `allow always` cho `external_or_destructive`.

Moi action co rui ro `write_internal` tro len phai ghi `audit_events`.

## 7. Phase 0 - Project Bootstrap

### Antigravity Tasks

1. Tao repo structure:
   - `backend/app`
   - `backend/tests`
   - `frontend/src`
   - `infra/n8n`
   - `docs`
2. Tao backend FastAPI minimal:
   - health route `GET /health`
   - settings loader
   - lifespan function
   - DB init/migration
3. Tao frontend minimal:
   - Vite React TypeScript
   - root layout
   - API client shell
4. Tao scripts:
   - backend test command
   - frontend lint/typecheck command
   - dev start docs

### Acceptance Criteria

- `GET /health` tra ve OK.
- SQLite `app.db` duoc tao voi dung schema.
- WAL va foreign keys duoc bat.
- Frontend start duoc va goi health endpoint.
- README co lenh setup/dev/test.

### Codex Checker

- Chay backend tests.
- Chay frontend typecheck/lint neu co.
- Mo schema DB va doi chieu voi plan.
- Khong duyet neu migration thieu `audit_events` hoac `tool_permissions`.

## 8. Phase 1 - Hermes ACP Backend Bridge

### Antigravity Tasks

1. Tao `HermesClient` class:
   - spawn Hermes ACP process trong FastAPI lifespan.
   - stdout reserved cho ACP messages.
   - stderr routed vao structured logs.
   - reconnect co lock, timeout, retry/backoff.
2. Tao routes:
   - `POST /api/sessions`
   - `GET /api/sessions`
   - `POST /api/sessions/{session_id}/prompt`
   - `GET /api/sessions/{session_id}/events`
3. Map app session voi ACP session.
4. Luu task run khi prompt duoc gui.
5. Ghi audit events cho prompt, tool call, approval request, error.

### SSE Events Required

Backend phai re-emit ACP updates thanh typed SSE:

```text
event: token
event: tool_call
event: terminal
event: file_diff
event: approval_required
event: plan_update
event: error
event: done
```

Moi event `data:` la JSON hop le.

### Acceptance Criteria

- Gui prompt tu API tao duoc task run.
- Frontend hoac curl doc duoc SSE stream.
- Hermes process crash thi request sau co reconnect hoac error ro rang.
- Khong co route nao import global singleton truc tiep; dung dependency/lifespan.

### Codex Checker

- Review lifecycle va cleanup process.
- Test SSE format bang curl/script.
- Simulate Hermes unavailable neu co mock.
- Khong duyet neu backend parse SSE/JSON-RPC bang string splitting mong manh ma khong co framing ro.

## 9. Phase 2 - Frontend Chat, Sessions, Approval

### Antigravity Tasks

1. Tao UI 3 cot:
   - session list
   - chat/stream panel
   - inspector/activity panel
2. Zustand store cho:
   - sessions
   - active session
   - streamed messages
   - pending approvals
   - task run status
3. Approval modal:
   - allow once
   - allow for session
   - deny
   - khong hien allow always cho destructive/external actions
4. Activity timeline hien:
   - tool call
   - terminal command
   - file diff
   - errors

### Acceptance Criteria

- User tao session, gui prompt, thay token stream.
- Approval request block execution cho den khi co response.
- Deny approval duoc hien la cancelled/denied, khong treo UI.
- UI khong can reload page khi stream ket thuc.

### Codex Checker

- Kiem tra reducer xu ly tung SSE event type.
- Kiem tra UI khong hardcode fake events.
- Chay typecheck.
- Khong duyet neu approval co nut `allow always` cho destructive/external action.

## 10. Phase 3 - Workspace Files + Monaco

### Antigravity Tasks

1. Backend file routes:
   - `GET /api/files/tree`
   - `GET /api/files/content?path=...`
   - `PUT /api/files/content`
2. Path sandbox:
   - resolve absolute path.
   - reject path ngoai `workspace_path`.
   - reject path traversal.
   - gioi han file size.
3. Frontend Monaco editor:
   - file tree
   - open/edit/save
   - autosave debounce 1-2s
   - dirty indicator
4. Ghi audit events cho write.

### Acceptance Criteria

- Doc/ghi file trong workspace thanh cong.
- `../` traversal bi reject.
- Absolute path ngoai workspace bi reject.
- File qua size limit bi reject voi error ro.
- Autosave khong spam backend moi keystroke.

### Codex Checker

- Test path traversal tren Windows path va relative path.
- Review implementation khong dung string prefix check don gian; phai dung resolved absolute path.
- Kiem tra audit event khi ghi file.

## 11. Phase 4 - Skills + Memory

### Antigravity Tasks

1. Skills CRUD:
   - list
   - create
   - update
   - enable/disable
2. Memory CRUD:
   - list by session/global
   - create/update/delete
   - importance score
   - last accessed update khi doc
3. Context injection policy:
   - chi inject enabled skills.
   - memory inject co gioi han so luong va size.
4. Curator job ban dau:
   - sau session, de xuat memory/skill update.
   - can user/Codex approval truoc khi ghi neu noi dung co tac dong dai han.

### Acceptance Criteria

- Skills disabled khong duoc inject.
- Memory entries co importance va last accessed.
- Curator khong tu y ghi memory dai han neu chua duoc approve.
- UI cho phep review memory/skill changes.

### Codex Checker

- Kiem tra context size cap.
- Kiem tra skill content khong duoc execute nhu code.
- Kiem tra audit khi update/delete memory hoac skill.

## 12. Phase 5 - FastMCP Tool Layer

### Antigravity Tasks

Expose toi da 6 tools o ban dau:

1. `read_workspace_file`
2. `write_workspace_file`
3. `search_workspace`
4. `list_skills`
5. `update_memory`
6. `run_safe_task`

Moi tool phai dung schema co mo ta tham so ro bang `Annotated` va `Field`.

### Acceptance Criteria

- Tool schemas co description cho tool va tung parameter.
- Tools validate input nhu backend routes.
- Tools khong bypass permission/audit layer.
- Khong expose toan bo CRUD REST routes thanh MCP tools.

### Codex Checker

- Inspect tool count va tool descriptions.
- Thu invalid path.
- Kiem tra tool write tao audit event.
- Khong duyet neu MCP tool goi thang file system ma bo qua service/policy layer.

## 13. Phase 6 - n8n Sidecar

### Antigravity Tasks

1. Tao `infra/n8n/docker-compose.yml`.
2. Set persistent volume cho `/home/node/.n8n`.
3. Document cach set `N8N_ENCRYPTION_KEY`.
4. Tao backend integration:
   - call webhook URL tu settings.
   - support secret header.
   - timeout va retry gioi han.
5. Tao sample workflow:
   - receive webhook
   - echo/report sample payload

### Acceptance Criteria

- n8n restart khong mat credentials/config.
- Backend khong hardcode webhook secret.
- Webhook external action duoc classify `external_or_destructive`.
- Goi n8n can approval moi lan neu co gui data ra ngoai.

### Codex Checker

- Review env handling.
- Kiem tra version n8n khong duoi ban da fix CVE nghiem trong neu version duoc pin.
- Khong duyet neu webhook secret nam trong source.

## 14. Phase 7 - Diagramming

### Antigravity Tasks

1. Render Mermaid blocks trong chat/editor.
2. Them validate Mermaid syntax.
3. Tich hop Mermaid to Excalidraw neu can edit visual.
4. Export diagram image.

### Acceptance Criteria

- Mermaid render duoc trong UI.
- Invalid Mermaid khong crash app.
- Export hoat dong voi diagram mau.

### Codex Checker

- Visual smoke test.
- Kiem tra UI khong block chat khi diagram invalid.

## 15. Required Tests

Backend:

- DB migration test.
- Session create/list test.
- SSE format test.
- Path sandbox test.
- Permission policy test.
- Audit event test.
- Hermes client mock reconnect test.

Frontend:

- Typecheck.
- Store reducer tests cho SSE events.
- Approval modal behavior.
- File editor autosave debounce.

Integration:

- Create session -> prompt -> stream -> done.
- Approval required -> deny -> task cancelled.
- Write file -> audit event exists.
- Invalid path -> rejected.
- n8n webhook disabled/missing -> graceful error.

## 16. Handoff Protocol Giua Antigravity Va Codex

Sau moi phase, Antigravity phai ban giao:

```text
Phase:
Summary:
Files changed:
Commands run:
Test results:
Known limitations:
Screenshots or logs if UI/API changed:
Questions for Codex:
```

Codex se review theo thu tu:

1. Doc diff.
2. Chay test lien quan.
3. Kiem tra acceptance criteria cua phase.
4. Kiem tra security checklist.
5. Neu dat: ghi "Approved for next phase".
6. Neu khong dat: tra ve findings theo severity va yeu cau fix.

## 17. Codex Approval Authority

Codex duoc phe duyet thay nguoi dung khi:

- Thay doi nam trong phase da dinh nghia.
- Test lien quan pass hoac co ly do hop le.
- Khong thay doi ngoai workspace.
- Khong public service ra internet.
- Khong xoa du lieu nguoi dung.
- Khong them secret vao source.
- Khong cap persistent destructive permission.

Codex phai yeu cau nguoi dung xac nhan khi:

- Can xoa/overwrite du lieu that.
- Can gui email, upload file, publish webhook, hoac goi API external co du lieu nhay cam.
- Can luu credential/token moi.
- Can thay doi ngoai `C:\Users\dtron\Documents\Hermes`.
- Antigravity de xuat mo rong ngoai plan.

## 18. Security Checklist Bat Buoc

- CORS whitelist, khong dung `*`.
- Workspace path jail cho moi file operation.
- Audit event cho moi write/external/destructive action.
- Approval checkpoint cho destructive/external action.
- Secrets chi nam trong `.env`, khong commit.
- n8n co persistent volume va fixed encryption key.
- n8n webhook co secret header hoac IP whitelist.
- Tool schema co validation ro.
- MCP tool khong bypass backend policy layer.
- Hermes stderr khong leak secret len UI.

## 19. Definition Of Done Toan Du An

Du an dat MVP khi:

- User co the tao session va chat voi Hermes qua UI.
- Token stream realtime qua typed SSE.
- Approval flow hoat dong.
- File editor doc/ghi trong workspace an toan.
- Skills va memory CRUD co audit.
- Tool permission model duoc enforce.
- n8n sidecar chay local va duoc goi qua backend co approval.
- Test suite pass.
- Codex review tat ca phase va approve MVP.
