# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP3 Legacy Adapter and CP3.1 lifecycle cleanup are merged on `main`.
- Next proposed work: CP4 Public Task API.
- Before CP4 implementation, agents must read `docs/implementation/CURRENT_CHECKPOINT.md`.

## Latest Gate Report

Latest verified by Codex:

- Backend tests: 197 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified during CP3 review: type-check pass, 93 tests pass, build pass.

## Current Decision

CP3 is approved and merged. CP4 should start with planning and API contract tests before implementation.

Proceed to CP4 only with these guardrails:

- Keep existing legacy session routes working.
- Keep `USE_TASK_API=false` and legacy UI fallback intact.
- Do not start CP5 frontend migration inside CP4.
- Do not implement outbox, Telegram, model fallback, or later checkpoint scope.
- Every new public endpoint must have idempotency, approval, audit, and session/workspace safety tests where applicable.

## Do Not Do Now

- Do not implement CP5-CP10 scope during CP4.
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
