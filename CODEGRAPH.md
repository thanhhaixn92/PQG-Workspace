# CODEGRAPH.md

## Purpose

Lightweight repository map for agents. Use this before opening broad file trees.

## Current Repository Shape

```text
backend/
  app/
    main.py                 FastAPI app factory, CORS, routers, MCP mount
    settings.py             Pydantic Settings for DB, Hermes, n8n, CORS
    dependencies.py         get_settings / get_db / get_hermes_client
    api/
      approvals.py          pending approval registry and decisions
      files.py              session-scoped workspace file API
      local_data.py         local DB summary and timestamped backup API
      memory.py             global memory CRUD
      n8n.py                safe n8n status and workflow allowlist API
      sessions.py           session CRUD, prompt submit, SSE, curator route
      skills.py             skills CRUD
      schemas.py            REST and SSE Pydantic schemas
    db/
      connection.py         aiosqlite connection factory, FK + WAL
      migrations.py         idempotent SQLite schema migrations
    mcp/
      server.py             FastMCP server, session context var
      tools.py              workspace, memory, safe task, n8n tools
    services/
      audit.py              audit event writer
      context.py            skill/memory context injection
      event_bus.py          per-session SSE queues
      hermes_client.py      ACP subprocess manager and event bridge
      sandbox.py            workspace path validation
  tests/                    backend pytest suite
  pyproject.toml            backend deps and pytest config

frontend/
  src/
    api/
      client.ts             apiFetch base wrapper, ApiError, 204 handling
      approvals.ts          approval decisions
      events.ts             SSE subscription lifecycle
      files.ts              file tree/content API
      health.ts             health API
      localData.ts          local DB summary and backup API
      memory.ts             memory API
      n8n.ts                n8n status and workflow allowlist API
      runtime.ts            runtime readiness and safe smoke check API
      sessions.ts           session/prompt API
      skills.ts             skills API
    components/
      AppLayout.tsx         primary three-column app shell
      ChatPanel.tsx         prompt input and markdown token rendering
      MarkdownRenderer.tsx  safe markdown renderer, Mermaid code routing
      MermaidDiagram.tsx    strict Mermaid render, fallback, SVG/PNG export
      ActivityInspector.tsx execution telemetry panel grouped by task/audit
      ApprovalModal.tsx     approval decision modal
      EditorPanel.tsx       Monaco editor, autosave, save state, conflict handling
      FileExplorer.tsx      workspace file tree
      LocalDataPanel.tsx    local DB stats and backup panel
      MemoryPanel.tsx       memory CRUD/search panel
      SessionList.tsx       session selection/creation
      SkillsPanel.tsx       skills CRUD/search/toggle panel
    store/
      store.ts              Zustand app state and token aggregation
  tsconfig.app.json         production TS config, excludes tests
  tsconfig.test.json        test TS config
  package.json              dev/build/test/type-check scripts

infra/
  n8n/
    docker-compose.yml      localhost-only pinned n8n sidecar
    README.md               n8n setup and required secrets
    Sample_Webhook_Echo.json safe sample workflow

docs/                       project canon, PRD, security, acceptance
start-dev.ps1               local backend + frontend startup helper
```

## Dependency Direction

Allowed:

```text
backend/api -> backend/services -> backend/db/settings
backend/mcp -> backend/services/db/settings
frontend/components -> frontend/store + frontend/api
frontend/api -> backend REST/SSE only
```

Forbidden:

```text
frontend -> filesystem / Hermes process / n8n webhook
mcp -> raw path access without sandbox validation
backend/db -> backend/services
backend/services -> frontend
```

## Context Loading Guide

- Startup/health: `backend/app/main.py`, `backend/app/db/connection.py`, `backend/app/db/migrations.py`
- Settings/env: `backend/app/settings.py`, `backend/.env.example`, `infra/n8n/README.md`
- Security-sensitive changes: `docs/04_SECURITY_PERMISSION_POLICY.md`
- Approvals/MCP/n8n: `backend/app/api/approvals.py`, `backend/app/mcp/tools.py`
- Workspace files: `backend/app/api/files.py`, `backend/app/services/sandbox.py`
- Skills/memory/context: `backend/app/api/skills.py`, `backend/app/api/memory.py`, `backend/app/services/context.py`
- Frontend chat/streaming: `frontend/src/api/events.ts`, `frontend/src/store/store.ts`, `frontend/src/components/ChatPanel.tsx`
- Diagram rendering: `frontend/src/components/MarkdownRenderer.tsx`, `frontend/src/components/MermaidDiagram.tsx`
- Test failures: start with `backend/tests/conftest.py` or frontend failing `*.test.*`

## Verification Commands

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests -v

cd ..\frontend
npm run type-check
npm run test -- --run
npm run build
```
