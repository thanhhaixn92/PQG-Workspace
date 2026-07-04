# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP2 TaskService is ready for Codex approval after blocker fixes.
- Next proposed work: CP3 Legacy Adapter behind `USE_TASK_API`.
- Before CP3 implementation, agents must read `docs/implementation/CURRENT_CHECKPOINT.md`.

## Latest Gate Report

Reported by implementer:

- Backend tests: 189 pass, 1 pre-existing Starlette warning.
- Frontend type-check: pass.
- Frontend tests: 93 pass.
- Frontend build: pass.

Codex spot-check in current review:

- `backend/tests/test_task_service.py`: 19 pass.
- `IdempotencyService.execute_idempotent()` now uses request hash checking.
- Global pytest warning filter has been removed from `backend/pyproject.toml`.

## Current Decision

CP2 can be approved if the full gate result is trusted from the implementer run.

Proceed to CP3 only with these guardrails:

- `USE_TASK_API=false` remains the default.
- Flag-off behavior must match the existing legacy session routes.
- Do not delete or rewrite legacy routes in CP3.
- Add characterization tests comparing legacy behavior and adapter behavior.
- Keep frontend behavior unchanged unless explicitly behind a separate frontend flag.
- No public API expansion beyond the adapter scope.

## Do Not Do Now

- Do not implement CP4-CP10 scope during CP3.
- Do not add Telegram, model fallback, public task API, outbox dispatcher, auth, deployment, or vector search.
- Do not change Hermes model/provider/timeout.
- Do not hard-delete user data.
- Do not weaken approval, audit, or workspace sandbox rules.

## Source Of Truth

Conflict order:

1. `docs/00_PROJECT_CANON.md`
2. `AGENTS.md`
3. `PROJECT_STATE.md`
4. `docs/implementation/CURRENT_CHECKPOINT.md`
5. Feature-specific docs routed by `docs/AI_AGENT_ROUTING.md`
6. Long-term roadmap docs

