# AI Handoff

## Current State

- CP5 is complete and preserved as the current closed gate.
- CP6 is not approved.
- Current state: CP5_COMPLETE.
- Next agent: human.
- Human approval required: yes.
- Automation infrastructure has been created for future use.

## Boundary

- No product code changes are allowed for the automation task.
- No CP6 planning or implementation is allowed.
- If human later approves CP6, a new explicit task must be written into `AI_TASK.md` and `AI_STATE.json` must be changed intentionally.
- Antigravity CLI may be unavailable; GUI fallback must be supported.
- Bash may be unavailable in Windows PowerShell.
- PowerShell scripts are the primary Windows entrypoints.
- Codex CLI is invoked with currently supported `codex exec --sandbox workspace-write`; approval behavior must be enforced by human gate/state rules and any local Codex profile config available at runtime.
- Antigravity wrappers must lock before CLI execution and block to human review if the CLI is unavailable or fails.
- Agent loops must stop when no state transition occurs.

## Allowed Files

- `AGENTS.md`
- `AI_TASK.md`
- `AI_STATE.json`
- `AI_HANDOFF.md`
- `AI_CHANGELOG.md`
- `AI_VERIFICATION.md`
- `AI_RISK_REGISTER.md`
- `.agents/skills/verify-and-handoff/SKILL.md`
- `scripts/run-codex.sh`
- `scripts/run-antigravity.sh`
- `scripts/agent-loop.sh`
- `scripts/ai-auto.sh`
- `scripts/run-codex.ps1`
- `scripts/run-antigravity.ps1`
- `scripts/agent-loop.ps1`
- `scripts/ai-auto.ps1`
- `scripts/codex-tick.ps1`

## Forbidden Files And Areas

- `.env`
- `.env.local`
- `.env.production`
- secrets
- deployment config
- billing config
- production database settings
- database files
- database migrations
- CP6 product files
- frontend source files
- backend source files

## Next Action

Human reviews the automation diff. Do not start CP6 until explicit human approval.
