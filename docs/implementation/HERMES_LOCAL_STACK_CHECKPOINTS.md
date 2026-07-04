# Checkpoints - Hermes Local Stack V1

Branch: `feature/hermes-local-stack-v1`

Each checkpoint is complete only when:

- Backend tests pass.
- Frontend type-check passes when frontend code is touched.
- Frontend tests pass when frontend code is touched.
- Frontend build passes when frontend code is touched.
- Manual smoke passes for user-facing behavior.

## CP0 Baseline Lock

- [x] Characterization tests pass.
- [x] Backend tests pass.
- [x] Frontend tests pass.

## CP1 Schema

- [x] Migrations 0005-0011 pass.
- [x] Repository tests pass.
- [x] Baseline backup created.

## CP2 TaskService

- [x] TaskStateMachine transition tests pass.
- [x] Idempotency tests pass.
- [x] Request-hash conflict handling exists.
- [x] Follow-up behavior tests pass.
- [x] Global warning suppression removed.

## CP3 Legacy Adapter

- [x] `USE_TASK_API=false` remains the default.
- [x] Existing frontend still works through existing routes.
- [x] Session submit format does not change when flag is off.
- [x] Hermes stream keeps the existing SSE format.
- [x] Approval flow remains compatible.
- [x] Audit behavior remains compatible.
- [x] `USE_TASK_API=true` characterization tests pass against CP0 expectations.
- [x] CP3.1 removes aiosqlite lifecycle warning from characterization tests.

## CP4 Public API

- [x] `POST /api/tasks` is idempotent: same request returns existing result, different payload returns conflict.
- [x] SSE events stream in stable order.
- [x] Cancel marks public tasks cancelled.
- [x] Approval is bound to a specific action.
- [x] Every endpoint writes required audit events.

## CP5 Frontend Migration

- [x] Task creation and streaming UI work through Task API.
- [x] Approval UI works through approval IDs.
- [x] Task cancel is available from UI.
- [x] Session history still displays.
- [x] Frontend tests pass.
- [x] `VITE_USE_TASK_API=false` fallback works.

## CP6 Outbox Dispatcher (Complete)

- [x] Task and outbox write atomically.
- [x] Pending rows are safe after restart.
- [x] Duplicate sends are prevented with idempotency keys.
- [x] Dead letter behavior exists after max attempts.

## CP7 Telegram Channel (Complete)

- [x] Invalid signature returns 401.
- [x] User outside allowlist returns 403.
- [x] Retried updates do not create duplicate tasks.
- [x] Reused callback token returns 409.
- [x] Expired callback token returns 410.

## CP8 Model Fallback (Complete)

- [x] 429/quota can fallback and task succeeds.
- [x] Timeout/5xx can retry/fallback and task succeeds.
- [x] 401/403 stops without fallback.
- [x] Cooldown is respected.
- [x] Task run records the attempt chain.

## CP9 Skill Version (Complete)

- [x] Only approved skills are injected into context.
- [x] Draft skills do not affect runtime.
- [x] Version history is complete.
- [x] Every version mutation is audited.

## CP10 Cleanup (Complete)

- [x] Legacy route metrics show no active consumers.
- [x] `X-Deprecated: true` header is active.
- [x] Dead code is removed only after explicit approval.
