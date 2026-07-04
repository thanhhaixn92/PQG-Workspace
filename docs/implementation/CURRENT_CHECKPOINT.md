# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP4 - Public Task API.

## Status

CP3 and CP3.1 are complete on `main`:

- `USE_TASK_API=false` remains the default.
- Legacy route behavior is preserved when the flag is off.
- `USE_TASK_API=true` links legacy task runs to TaskService.
- Adapter errors no longer corrupt legacy task status.
- Aiosqlite lifecycle warning cleanup is complete.

## Goal

Expose the first public Task API surface on top of the TaskService foundation without breaking existing legacy session/chat behavior.

## Context

The app currently has legacy session routes and a TaskService-backed adapter behind `USE_TASK_API`. CP4 adds public task endpoints for programmatic task creation, streaming, cancellation, and action-bound approvals. Existing UI behavior must remain unchanged.

## Constraints

- Keep legacy session/chat routes working.
- Keep `USE_TASK_API=false` as the default.
- Do not migrate frontend to Task API in CP4.
- Do not remove legacy route code.
- Do not add outbox, Telegram, model fallback, or later checkpoint work.
- Preserve approval, audit, workspace sandbox, and history invariants.
- Treat public Task API input as untrusted.
- Idempotency conflicts must return a clear conflict response.

## Required Implementation Shape

Implement CP4 in small slices:

1. Define schemas and route skeleton for public task API.
2. Add `POST /api/tasks` with idempotency:
   - same idempotency key and same payload returns existing result;
   - same key and different payload returns 409.
3. Add task detail/list endpoints only if needed for acceptance tests.
4. Add SSE task event stream with stable ordering.
5. Add cancel endpoint that marks the task cancelled and stops a running Hermes run where supported.
6. Bind approvals to concrete task actions.
7. Audit every public endpoint and policy decision.

Do not implement CP5 frontend migration here.

## Done When

- Backend full tests pass.
- Frontend type-check/tests/build pass if frontend files are touched.
- Public Task API tests pass for idempotency, streaming order, cancel, approvals, and audit.
- Legacy session route characterization tests still pass.
- Manual smoke can still create a session, submit a prompt, stream response, approve actions, and refresh history.

## Review Gate

Codex should not approve CP4 if:

- Existing UI flows require the new public Task API.
- Legacy route behavior changes.
- Approval/audit behavior becomes weaker.
- Frontend starts calling TaskService/Hermes/MCP/n8n directly.
- Later checkpoint scope is mixed into CP4.
- Idempotency accepts key reuse with different payloads.
- Cancel leaves tasks in an ambiguous non-terminal state.
