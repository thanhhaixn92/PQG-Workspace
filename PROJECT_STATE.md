# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP4 Public Task API backend implementation is complete locally.
- Next proposed work: Codex review/merge CP4, then plan CP5 Frontend Migration.
- Before CP5 implementation, agents must read `docs/implementation/CURRENT_CHECKPOINT.md`.

## Latest Gate Report

Latest verified by Codex:

- Backend tests: 197 pass, 1 pre-existing Starlette warning.
- Backend tests after CP4: 203 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified during CP3 review: type-check pass, 93 tests pass, build pass.

## Current Decision

CP4 backend implementation is complete locally and should be reviewed before merge.

Proceed to CP5 only after CP4 review/merge, with these guardrails:

- Keep existing legacy session routes working.
- Keep `USE_TASK_API=false` and legacy UI fallback intact.
- Do not implement outbox, Telegram, model fallback, or later checkpoint scope.
- Every new public endpoint must have idempotency, approval, audit, and session/workspace safety tests where applicable.

## Do Not Do Now

- Do not implement CP6-CP10 scope during CP5.
- Do not add Telegram, model fallback, outbox dispatcher, auth, deployment, or vector search.
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
