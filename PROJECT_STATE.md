# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP6 Outbox Dispatcher is approved and opened for automation.
- CP5 Frontend Migration is verified and complete.
- Next work: implement CP6 Outbox Dispatcher only.

## Latest Gate Report

Latest verified by Codex:

- Backend tests: 197 pass, 1 pre-existing Starlette warning.
- Backend tests after CP4/CP5: 203 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified after CP5 implementation: type-check pass, 106 tests pass, build pass.

## Current Decision

CP6 Outbox Dispatcher is approved for implementation through the automation workflow.

- Implement only CP6 Outbox Dispatcher scope; do not implement Telegram, model fallback, or CP7+.
- Keep existing legacy session routes working.
- Keep `USE_TASK_API=false` and legacy UI fallback intact.
- Every new public endpoint must have idempotency, approval, audit, and session/workspace safety tests where applicable.

## Do Not Do Now

- Do not implement CP7-CP10 scope during CP6.
- Do not add Telegram, model fallback, auth, deployment, or vector search.
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
