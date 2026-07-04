# AI Handoff

## Current State

- CP5, CP6, CP7, CP8, CP9, and CP10 are complete and preserved as closed gates.
- Current state: CP10_COMPLETE / manual review
- Next execution mode: manual review.
- Next agent: human (V1 implementation is complete).
- Human approval required: true (final project sign-off).
- Automation infrastructure: suspended/paused.

## Boundary

- No code changes are allowed; V1 implementation is complete.
- Do not implement any new features or start CP11+.
- Keep FastAPI as the policy/audit boundary.
- Preserve FastAPI as the policy/audit boundary and do not let n8n poll SQLite.
- Keep legacy session routes and `USE_TASK_API=false` fallback intact.
- Antigravity CLI may be unavailable; GUI fallback must be supported.
- Bash may be unavailable in Windows PowerShell.
- PowerShell scripts are the primary Windows entrypoints.
- Codex CLI is invoked with currently supported `codex exec --sandbox workspace-write`; approval behavior must be enforced by human gate/state rules and any local Codex profile config available at runtime.
- Antigravity wrappers must prefer `agy`, then `antigravity`, then `ag`; they must verify `-p` or `--prompt` support from `--help` before non-interactive execution.
- On Windows, PowerShell wrappers also check `%LOCALAPPDATA%\agy\bin\agy.exe` when `agy` has been installed but the current shell has not refreshed PATH.
- Antigravity wrappers must invoke `agy --sandbox -p "<prompt>"` when `--sandbox` is supported, otherwise `agy -p "<prompt>"`; they must lock before CLI execution and block to human review if the CLI is unavailable, lacks `-p`, or fails.
- Agent loops must stop when no state transition occurs.
- Do not use `agy --dangerously-skip-permissions` or `codex --dangerously-bypass-approvals-and-sandbox`.

## Expected Code Areas

- Backend verification tests and final audit coordination files.

## Codex Implementation Summary

- Added backend `OutboxDispatcher` service that claims backend-owned outbox rows, dispatches via an injected sender, passes stable idempotency keys, audits sent/error outcomes, retries failures, and dead-letters rows after max attempts.
- Updated `OutboxRepository` with deterministic `insert_once`, retry-aware lease claiming, active-lock protection, sent lock cleanup, and status lookup.
- Updated `TaskService` so terminal task success/failure enqueues deterministic n8n outbox events in the same DB transaction as the task status/event writes.
- Added focused backend tests for atomic task/outbox behavior, restart-safe pending/retrying rows, duplicate row/send prevention, dispatcher success, retry, and dead letter behavior.

## Forbidden Files And Areas

- `.env`
- `.env.local`
- `.env.production`
- secrets
- deployment config
- billing config
- production database settings
- database files
- unrelated database migrations
- Any code modification (V1 is frozen)
- frontend source files

## Next Action

- Final human review of the V1 local stack.
- Check deprecation metrics and ensure headers are returned on legacy endpoints.
- Automation runner remains suspended. No loops may be run.
