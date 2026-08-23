# PQG Workspace — Trợ lý GYO

PQG Workspace là không gian làm việc cá nhân chạy trên máy của bạn. Ứng dụng giúp
tạo Công việc, trao đổi với Trợ lý GYO, quản lý tài liệu/đầu ra, duyệt tri thức và
kiểm soát bộ nhớ trong từng phạm vi rõ ràng.

Đây là Local MVP cho một người dùng, không phải dịch vụ cloud hoặc hệ thống
doanh nghiệp nhiều người dùng. FastAPI là ranh giới chính sách, SQLite lưu
metadata nghiệp vụ và GYO là runtime tác nhân trung lập provider.

## Prerequisites

| Tool | Minimum version | Check |
|------|-----------------|-------|
| Python | 3.11 | `py --version` |
| Node.js | 18 | `node --version` |
| npm | 9 | `npm --version` |

---

## Quick Start

For the first end-to-end chat path, see `docs/11_FIRST_REAL_CHAT.md`.

### 1. Clone & enter the repo

```powershell
cd C:\Users\dtron\Documents\DIRAP-Personal-v3
```

### 2. Backend

```powershell
cd backend

# Create virtual environment
py -3.11 -m venv .venv
.venv\Scripts\activate

# Install with dev extras
pip install -e ".[dev]"

# Copy env template (edit values if needed)
copy .env.example .env
```

Start the development server:

```powershell
uvicorn app.main:app --reload
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting PQG Workspace backend v2.2.0
INFO:     DB path: C:\...\<project>\backend\app.db
INFO:     DB ready.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Verify:

```powershell
curl http://localhost:8000/health
```

**Expected response:**
```json
{"status":"ok","version":"2.2.0","db":"ok","timestamp":1750000000}
```

### 3. Frontend

```powershell
cd ..\frontend
npm install
npm run dev
```

**Expected output:**
```
  VITE v8.x.x  ready in XXX ms

  -> Local:   http://localhost:5173/
```

Open `http://localhost:5173` in a browser. The first screen should identify the
product as **PQG Workspace — Trợ lý công việc cá nhân chạy trên máy của bạn** and
offer these user-facing areas:

```
Tổng quan · Công việc · Tài liệu · Tri thức · Báo cáo · Hộp duyệt · Cài đặt
```

### One-command local startup

After backend and frontend dependencies are installed, you can start both dev servers from the repo root:

```powershell
.\start-dev.ps1
```

The script checks for `backend\.venv`, `frontend\node_modules`, and port availability before launching the servers. See [`docs/10_UX_SMOKE_TEST.md`](docs/10_UX_SMOKE_TEST.md) for the first-run product walkthrough.

Use `\.\check-dev.ps1` to verify backend, database, GYO configuration and frontend.
Technical diagnostics are intentionally kept out of the normal user journey.

## Current product boundary

- Controlled Knowledge Search is deterministic, task-scoped and read-only.
- Memory Hub uses proposal/review/activation lifecycle and is not automatically
  injected into chat.
- Browser operator routes do not receive Credential Manager bearer tokens.
- No cloud deployment, vector/AI search, connector package 2, legacy cutover,
  Hub retention/delete or encrypted backup is included in this checkpoint.

---

## Backend Tests

```powershell
cd backend
.venv\Scripts\activate
pytest tests/ -v
```

**Expected output (all passing):**
```
tests/test_db_schema.py::test_all_required_tables_exist       PASSED
tests/test_db_schema.py::test_wal_mode_enabled                PASSED
tests/test_db_schema.py::test_foreign_keys_on_per_connection  PASSED
tests/test_db_schema.py::test_schema_migrations_version_recorded PASSED
tests/test_db_schema.py::test_indexes_exist                   PASSED
tests/test_db_schema.py::test_migration_is_idempotent         PASSED
tests/test_health.py::test_health_returns_200                 PASSED
tests/test_health.py::test_health_status_ok                   PASSED
tests/test_health.py::test_health_contains_version            PASSED
tests/test_health.py::test_health_db_ok                       PASSED
tests/test_health.py::test_health_has_timestamp               PASSED

11 passed
```

Tests write to a **temporary directory** (via `tmp_path` fixture) and never touch `app.db`.

---

## Frontend Type Check

```powershell
cd frontend
npm run type-check
```

**Expected output:**
```
(no output = no errors)
```

Exit code 0 means clean.

`npm run type-check` runs `tsc -b` and validates all TypeScript project references.
Production source is checked via `tsconfig.app.json`; tests are checked separately
via `tsconfig.test.json` so `*.test.*` files do not enter the production bundle.
Use `import type` for type-only imports when `verbatimModuleSyntax` is enabled.

## Frontend Tests And Build

```powershell
cd frontend
npm run test -- --run
npm run build
```

`npm run build` runs the full type check before producing the Vite production bundle.

## Frontend Lint

```powershell
cd frontend
npm run lint
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `./app.db` | Path to SQLite database file |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

**Never commit `.env` to source control.** The `.gitignore` excludes it.

To configure frontend API base URL, create `frontend/.env.local`:

```ini
VITE_API_BASE_URL=http://localhost:8000
```

---

## Project Structure

```
backend/
  app/
    main.py           FastAPI app factory + lifespan
    settings.py       Pydantic Settings (env-configurable)
    dependencies.py   Dependency injection providers
    db/
      connection.py   aiosqlite connection factory (FK + WAL per connection)
      migrations.py   Idempotent schema migrations
  tests/
    conftest.py       Shared fixtures (temp DB path, test client)
    test_health.py    GET /health tests
    test_db_schema.py Schema, WAL, FK, migration version tests
  pyproject.toml
  .env.example

frontend/
  src/
    api/
      client.ts       Base fetch wrapper (all backend calls go here)
      health.ts       GET /health typed client
    App.tsx           Root component (health status display)
    App.css

infra/
  n8n/               n8n docker-compose will live here (Phase 6)

docs/                Project canon and implementation plans
```

---

## Security Notes

- CORS: exact origin whitelist only, no `*` wildcard.
- Secrets in `.env` only, never in source.
- SQLite `app.db` excluded from git.
- All file operations in later phases are sandboxed to `workspace_path`.
- Audit log required for write/external/destructive actions (Phase 1+).

---

## Phase Status

| Phase | Status |
|-------|--------|
| 0 - Project Bootstrap | OK Complete |
| 1 - Hermes ACP Bridge | OK Complete |
| 2 - Frontend Chat + Approval | OK Complete |
| 3 - Workspace Files + Monaco | OK Complete |
| 4 - Skills + Memory | OK Complete |
| 5 - FastMCP Tool Layer | OK Complete |
| 6 - n8n Sidecar | OK Complete |
| 7 - Diagramming | OK Complete |
| 8 - UX Runtime Experience Pack | OK Complete |
| 9-18 - Runtime, daily workflow, local data, n8n status, polish | OK Complete |
| UX Pass - File cards, activity timeline, daily checklist | OK Complete |

See [`docs/ANTIGRAVITY_IMPLEMENTATION_PLAN.md`](docs/ANTIGRAVITY_IMPLEMENTATION_PLAN.md) for full details.

Latest local validation snapshot:

- Backend tests: `79 passed`
- Frontend tests: `91 passed`
- Frontend type-check: passed
- Frontend build: passed, with a known non-blocking Mermaid lazy chunk warning
- Daily acceptance checklist: [`docs/13_DAILY_ACCEPTANCE_CHECKLIST.md`](docs/13_DAILY_ACCEPTANCE_CHECKLIST.md)

Runtime hardening notes:

- Approval decisions are committed to SQLite and audit log before any waiting tool is released.
- Local DB backups use SQLite backup semantics, so WAL data is included consistently.
- n8n echo testing requires an active session so approval can be shown in the UI.
- Keep generated documents/scripts in a session workspace or output folder instead of the backend app directory.
