# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP3 - Legacy Adapter behind `USE_TASK_API`.

## Status

CP2 is ready for approval after the latest fixes:

- Request-hash idempotency is implemented in `IdempotencyService`.
- Global warning suppression was removed from `backend/pyproject.toml`.
- Task service targeted tests pass.

## Goal

Introduce a legacy adapter path that can use the new TaskService infrastructure without changing the existing user-facing session API by default.

## Context

The app currently relies on legacy session routes for chat, SSE, approvals, audit, history, and UI behavior. CP3 must preserve that behavior unless the new flag is explicitly enabled.

## Constraints

- `USE_TASK_API=false` must be the default.
- With the flag off, existing route behavior must remain unchanged.
- With the flag on, behavior must match CP0 characterization expectations.
- Do not remove legacy route code.
- Do not change frontend behavior unless behind a separate explicit flag.
- Do not add CP4 public Task API scope.
- Do not add outbox, Telegram, model fallback, or later checkpoint work.
- Preserve approval, audit, workspace sandbox, and history invariants.

## Required Implementation Shape

1. Add settings support for `USE_TASK_API`, default `false`.
2. Add an adapter layer that maps legacy session submit behavior to TaskService when enabled.
3. Keep legacy implementation path intact when disabled.
4. Add characterization tests for:
   - flag off keeps legacy behavior;
   - flag on creates/updates task state through TaskService;
   - SSE event format remains compatible;
   - approval flow remains compatible;
   - audit events remain compatible;
   - chat history remains compatible.
5. Avoid broad refactors in `sessions.py`; extract only where necessary to keep paths testable.

## Done When

- Backend full tests pass.
- Frontend type-check/tests/build pass if frontend files are touched.
- New CP3 tests prove flag-off compatibility and flag-on adapter behavior.
- Manual smoke can still create a session, submit a prompt, stream response, approve actions, and refresh history.

## Review Gate

Codex should not approve CP3 if:

- `USE_TASK_API=true` becomes required for existing UI flows.
- Legacy route behavior changes when flag is false.
- Approval/audit behavior becomes weaker.
- Frontend starts calling TaskService/Hermes/MCP/n8n directly.
- Later checkpoint scope is mixed into CP3.

