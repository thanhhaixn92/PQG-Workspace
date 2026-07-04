# AI Handoff

## Current State

- CP5 is complete and preserved as the current closed gate.
- CP6 Outbox Dispatcher is approved and opened for automation.
- Current state: READY.
- Next agent: codex.
- Human approval required: no for this approved CP6 implementation task.
- Automation infrastructure is ready for use.

## Boundary

- Product code changes are allowed only for CP6 Outbox Dispatcher.
- Do not implement Telegram, CP7+, model fallback, auth, deployment, vector search, or Excalidraw.
- Reuse existing `notification_outbox` schema/repository where possible.
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

- Backend service/repository/tests for notification outbox dispatching.
- Existing checkpoint docs and AI coordination files.
- Avoid frontend files unless validation proves they are required.

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
- CP7+ product files
- frontend source files unless explicitly required by CP6 validation

## Next Action

Run `scripts\ai-auto.ps1`. Codex should implement CP6 only, run relevant backend tests, update AI coordination files, and return control for human/Codex review.
