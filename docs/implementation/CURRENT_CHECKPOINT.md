# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP5 - Frontend Migration.

## Status

CP4 backend implementation is complete locally:

- Public Task API route is mounted at `/api/tasks`.
- `POST /api/tasks` supports idempotency replay and conflict.
- Task event listing and SSE stream endpoints exist.
- Task cancel endpoint marks tasks cancelled.
- Task action approval request/decision endpoints bind decisions to `task_actions`.
- Backend validation: 203 passed, 1 pre-existing Starlette warning.

## Goal

Migrate frontend task creation/streaming to the public Task API behind a frontend flag, while preserving the existing legacy fallback.

## Context

The backend now exposes a public Task API, while the existing frontend still uses legacy session/chat routes. CP5 should add a frontend integration path behind `VITE_USE_TASK_API`, without removing the legacy UI path.

## Constraints

- Keep legacy session/chat routes working.
- Keep `USE_TASK_API=false` as the default.
- Keep `VITE_USE_TASK_API=false` as the frontend default.
- Do not remove legacy route code.
- Do not add outbox, Telegram, model fallback, or later checkpoint work.
- Preserve approval, audit, workspace sandbox, and history invariants.
- Frontend must still call FastAPI only.
- Do not call Hermes/MCP/n8n/filesystem directly from frontend.

## Required Implementation Shape

Implement CP5 in small slices:

1. Add frontend API client methods for `/api/tasks`.
2. Add `VITE_USE_TASK_API` feature flag, default false.
3. When flag is false, keep current session prompt flow unchanged.
4. When flag is true, route task creation/streaming through Task API where backend support exists.
5. Keep approval UI compatible with existing approval flow.
6. Add cancel UI only if backend semantics are clear and tested.
7. Preserve session history display.

Do not implement CP6 outbox here.

## Done When

- Backend full tests pass.
- Frontend type-check/tests/build pass.
- `VITE_USE_TASK_API=false` fallback remains working.
- Task API path has targeted frontend tests.
- Legacy session route characterization tests still pass.
- Manual smoke can still create a session, submit a prompt, stream response, approve actions, and refresh history.

## Review Gate

Codex should not approve CP5 if:

- Existing UI flows require the new public Task API.
- Legacy route behavior changes.
- Approval/audit behavior becomes weaker.
- Frontend starts calling TaskService/Hermes/MCP/n8n directly.
- Later checkpoint scope is mixed into CP5.
- `VITE_USE_TASK_API=false` fallback breaks.
