# Project State

Last updated: 2026-07-04

## Current Checkpoint

- Active track: Hermes Local Stack V1 checkpoints.
- Current state: CP10 Cleanup is complete, verified, and closed.
- CP5, CP6, CP7, CP8, CP9, and CP10 are verified and complete.
- Next work: Hermes Local Stack V1 implementation is fully complete. Awaiting human confirmation.
- Automation runner: paused/suspended.
- Next execution mode: manual review.

## Latest Gate Report

Latest verified by Antigravity (Checker):

- Backend tests after CP10: 269 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified after CP5 implementation: type-check pass, 106 tests pass, build pass.

## Current Decision

CP10 Cleanup implementation has been verified and approved by human review. Gate closed at `CP10_COMPLETE`.

- V1 implementation is complete. Do not add any new feature scope.
- Keep existing legacy session routes working.
- Keep `USE_TASK_API=false` and legacy UI fallback intact.
- Every new public endpoint must have idempotency, approval, audit, and session/workspace safety tests where applicable.

## Do Not Do Now

- Do not implement CP11 scope during CP10.
- Do not add deployment.
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
