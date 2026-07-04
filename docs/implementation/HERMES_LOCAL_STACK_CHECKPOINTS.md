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

- [ ] `POST /api/tasks` is idempotent: same request returns existing result, different payload returns conflict.
- [ ] SSE events stream in stable order.
- [ ] Cancel stops the Hermes run.
- [ ] Approval is bound to a specific action.
- [ ] Every endpoint writes required audit events.

## CP5 Frontend Migration

- [ ] Task creation and streaming UI work through Task API.
- [ ] Approval UI works through approval IDs.
- [ ] Task cancel is available from UI.
- [ ] Session history still displays.
- [ ] Frontend tests pass.
- [ ] `VITE_USE_TASK_API=false` fallback works.

## CP6 Outbox Dispatcher

- [ ] Task and outbox write atomically.
- [ ] Pending rows are safe after restart.
- [ ] Duplicate sends are prevented with idempotency keys.
- [ ] Dead letter behavior exists after max attempts.

## CP7 Telegram Channel

- [ ] Invalid signature returns 401.
- [ ] User outside allowlist returns 403.
- [ ] Retried updates do not create duplicate tasks.
- [ ] Reused callback token returns 409.
- [ ] Expired callback token returns 410.

## CP8 Model Fallback

- [ ] 429/quota can fallback and task succeeds.
- [ ] Timeout/5xx can retry/fallback and task succeeds.
- [ ] 401/403 stops without fallback.
- [ ] Cooldown is respected.
- [ ] Task run records the attempt chain.

## CP9 Skill Version

- [ ] Only approved skills are injected into context.
- [ ] Draft skills do not affect runtime.
- [ ] Version history is complete.
- [ ] Every version mutation is audited.

## CP10 Cleanup

- [ ] Legacy route metrics show no active consumers.
- [ ] `X-Deprecated: true` header is active.
- [ ] Dead code is removed only after explicit approval.
