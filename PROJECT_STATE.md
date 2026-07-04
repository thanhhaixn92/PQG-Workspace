# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP5 Frontend Migration is verified and complete.
- Next proposed work: wait for human approval before planning CP6 Outbox Dispatcher.
- CP6 is not started. Do not implement CP6 until the user explicitly approves a CP6 plan.

## Latest Gate Report

Latest verified by Codex:

- Backend tests: 197 pass, 1 pre-existing Starlette warning.
- Backend tests after CP4/CP5: 203 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified after CP5 implementation: type-check pass, 106 tests pass, build pass.

## Current Decision

CP5 frontend implementation is complete and verified. Stop at the CP5 gate until the user approves CP6 planning.

- Do not implement CP6 yet.
- If the user approves CP6 later, implement only CP6 Outbox Dispatcher scope; do not implement Telegram, model fallback, or CP7+.
- Keep existing legacy session routes working.
- Keep `USE_TASK_API=false` and legacy UI fallback intact.
- Every new public endpoint must have idempotency, approval, audit, and session/workspace safety tests where applicable.

## Do Not Do Now

- Do not implement CP7-CP10 scope during CP6.
- Do not plan or implement CP6 until the user explicitly asks.
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
