# AI Task

## Task

Implement CP6 Outbox Dispatcher through the automation workflow.

## Current Checkpoint

- Current checkpoint: CP6 Outbox Dispatcher.
- State: READY.
- CP5 Frontend Migration is complete and preserved.

## Constraints

- Implement only CP6 Outbox Dispatcher.
- Do not implement Telegram, CP7+, model fallback, auth, deployment, vector search, or Excalidraw.
- Prefer backend-only changes; do not touch frontend unless CP6 validation requires it.
- Do not modify secrets, deployment config, billing config, production database settings, database files, or migrations.
- Do not auto commit, push, merge, deploy, reset, clean, or run destructive commands.
- Do not use dangerous automation flags.

## Done When

- Task and outbox write atomically where CP6 dispatch events are created.
- Pending outbox rows remain safe after restart and can be claimed by a dispatcher.
- Duplicate sends are prevented with idempotency keys.
- Dead letter behavior exists after max attempts.
- Focused backend tests cover dispatcher success, retry, restart-safe pending rows, duplicate-send prevention, and dead letter behavior.
- `AI_STATE.json` is valid JSON.
- Relevant backend tests pass.
- AI handoff/verification/changelog/risk files are updated.
