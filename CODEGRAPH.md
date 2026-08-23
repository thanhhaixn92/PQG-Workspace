# CODEGRAPH.md — PQG Workspace source map

Use this map after the mandatory state read in `AGENTS.md`. It is a navigation
index, not an acceptance claim. Current v2.2 state remains `PARTIAL`; read
`PROJECT_STATE.md` and `docs/implementation/CURRENT_CHECKPOINT.md` for gates.

## Architecture at a glance

```text
React/Vite UI
  -> typed REST + SSE client
  -> FastAPI policy boundary
      -> SQLite app.db (user-visible Work/Assistant history)
      -> managed workspace sandbox
      -> GyoOrchestrator -> enabled provider/model profiles
      -> governed Memory/Skill learning outbox
      -> optional localhost n8n + exact MCP allowlist
```

The web app must not call a provider, legacy Hermes/ACP runtime, n8n, MCP, raw
filesystem, or SQLite directly. Historical Hermes names in files/docs are not
permission to reintroduce an ACP fallback.

## Start here

| Concern | Read first | Then inspect |
| --- | --- | --- |
| App startup/routers | `backend/app/main.py` | `backend/app/settings.py`, `dependencies.py`, `db/connection.py` |
| Work, plan, conversations | `backend/app/api/works.py` | `api/schemas.py`, `services/work_memory_scope.py`, `tests/test_works.py` |
| GYO turn/SSE/retry/cancel | `backend/app/api/assistant.py` | `services/gyo_orchestrator.py`, `gyo_registry.py`, `frontend/src/api/events.ts`, assistant tests |
| Provider/model/routing | `backend/app/api/model_config.py` | `services/model_resilience.py`, `services/gyo_registry.py`, `tests/test_gyo_provider_core.py` |
| Context/attachments/memory | `backend/app/services/assistant_context.py` | `api/context_preview.py`, `api/gyo_learning.py`, `tests/test_work_memory_learning.py` |
| Learning worker | `backend/app/services/gyo_learning_worker.py` | `services/learning.py`, `tests/test_governed_learning.py` |
| Action proposal/approval | `backend/app/api/action_packages.py` | `api/approvals.py`, `services/action_packages.py`, focused tests |
| Managed files/artifacts/reports | `backend/app/api/files.py`, `api/artifacts.py` | `services/sandbox.py`, `tests/test_files.py`, `test_artifacts.py` |
| Knowledge/Memory/Skills review | `backend/app/api/memory_hub.py`, `api/skills.py` | `api/knowledge_summary.py`, `services/memory_hub.py` |
| UI shell/navigation | `frontend/src/components/AppLayout.tsx` | `frontend/src/index.css`, `AppLayout.test.tsx` |
| GYO workspace/chat | `frontend/src/components/HermesAssistantPanel.tsx` | `api/assistant.ts`, `api/events.ts`, panel tests |
| Work workspace | `frontend/src/components/WorkHub.tsx` | `api/works.ts`, `ActionPackagesPanel.tsx`, `WorkHub.test.ts` |
| Settings/models | `frontend/src/components/SettingsPanel.tsx` | `api/assistant.ts`, Settings tests |

## Backend boundaries

```text
api/* -> services/* -> db/settings
mcp/* -> services/* + db/settings
services/* -X-> frontend/*
db/*       -X-> services/*
```

- `backend/app/main.py` owns FastAPI assembly, lifespan and router inclusion.
- `backend/app/api/schemas.py` is the public REST/SSE schema boundary.
- `backend/app/db/migrations.py` is additive SQLite schema evolution; never edit
  it or a database file without explicit approval.
- `assistant_threads`, `assistant_turns`, parts and run metadata are durable
  Assistant records. Their Work + conversation bindings must be enforced in the
  backend, not just selected in the UI.
- `conversations` and legacy `chat_messages` are Work history surfaces. Treat
  them as compatibility-sensitive; do not merge/rebind records by guessing.
- `work_memory_scopes` and `gyo_learning_jobs` are governed plan-step policy and
  outbox state. Learning creates candidates only, never activated knowledge or
  enabled skills.
- Provider credential values never cross an API response or browser state.

## Frontend boundaries

- `frontend/src/main.tsx` mounts the app; `AppLayout.tsx` owns global navigation,
  responsive shell and theme controls.
- `frontend/src/api/client.ts` owns fetch/error normalization. Feature clients
  stay under `frontend/src/api/`; components do not handcraft privileged calls.
- `HermesAssistantPanel.tsx` is the GYO surface despite its historical filename.
  It must keep Work/thread/conversation/step generations isolated and show a
  proposal as non-mutating until an Action Package is approved.
- `WorkHub.tsx` owns Work tabs and conversation-bound history. Its chat timeline
  must stay scoped to `(work_id, conversation_id)`.
- Shared UI primitives belong under `frontend/src/components/ui/` when reused;
  do not create duplicate dialogs/drawers that bypass focus handling.

## Source-of-truth and safety map

| Topic | Authoritative inputs | Minimum proof |
| --- | --- | --- |
| Active scope/gate | `PROJECT_STATE.md`, `AI_STATE.json`, checkpoint | targeted tests + evidence, no status inference |
| REST/SSE contract | schemas + route + client + focused tests | request/error/stale-response coverage |
| Work mutation | route/service + Action Package lifecycle | no mutation before approval; idempotency test |
| Memory scope | policy route + context builder | wrong Work/step/restricted record excluded |
| Filesystem | file route + sandbox | managed roots and path-escape rejection |
| Provider/model | model-config + registry/orchestrator | no secret response; unavailable fails clearly |
| UI/accessibility | target component + colocated test + browser check | loading/empty/error/success, keyboard/focus/reflow |

## Verification routes

| Change type | Start with |
| --- | --- |
| Backend behaviour | relevant `backend/tests/test_*.py`, then `backend/.venv/Scripts/python.exe -m pytest ...` |
| Frontend behaviour | colocated `*.test.tsx`, then `npm run type-check` when types/contracts change |
| Shared UI/theme/layout | focused Vitest + browser viewport check |
| Schema/migration | migration-specific test, upgrade/idempotency/rollback evidence only if approved |
| Runtime/startup | health/OpenAPI smoke in a temporary or explicitly approved local runtime |
| Any changed files | `git diff --check` and focused diff review |

## Map maintenance

Update this file only when an important entry point, dependency direction,
security boundary or test route changes. Verify paths with `rg --files` first;
do not copy a historical architecture map forward unverified.
