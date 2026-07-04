# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP6 - Outbox Dispatcher.

## Status

CP5 Frontend Migration is complete and verified. CP6 Outbox Dispatcher is now approved for automation:

- Task and outbox writes must be atomic.
- Pending rows must be safe after restart.
- Duplicate sends must be prevented with idempotency keys.
- Dead letter behavior must exist after max attempts.
- CP7+ scope is not approved.

## Goal

Implement CP6 Outbox Dispatcher cleanly without widening scope.

## Context

CP6 implements backend-owned transactional outbox dispatching per ADR-004. Existing outbox schema/repository code may already exist; reuse it where appropriate.

## Constraints

- Do not implement CP7 or Telegram channel behavior.
- Keep existing legacy session routes working.
- Keep `VITE_USE_TASK_API=false` fallback intact.
- Do not add Telegram, model fallback, auth, deployment, vector search, or CP7+ scope.

## Required Implementation Shape

- Keep FastAPI as the policy boundary.
- Keep n8n behind backend-owned dispatching; n8n must not poll SQLite.
- Add focused backend tests for CP6 acceptance criteria.
- Update project/AI state after implementation and verification.

## Done When

- CP6 checklist is complete.
- Backend test suite passes.
- Frontend checks are only required if frontend code is touched.
- Project state documents the CP6 outcome.

## Review Gate

Human review is required before closing CP6.
