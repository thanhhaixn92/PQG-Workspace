# AGENTS.md

## Project Identity

Hermes Local Stack is a local-first AI office assistant.

Canonical docs:

- `docs/00_PROJECT_CANON.md` - source of truth and conflict order.
- `docs/01_PRD.md` - product scope and MVP.
- `docs/02_DATA_STORAGE_MODEL.md` - data ownership and schema rules.
- `docs/03_EXECUTION_PRINCIPLES.md` - engineering rules.
- `docs/04_SECURITY_PERMISSION_POLICY.md` - security, approval, audit.
- `docs/05_ACCEPTANCE_EVALUATION.md` - acceptance gates and tests.
- `docs/06_HANDOFF_REVIEW_PROTOCOL.md` - review protocol.
- `docs/07_DECISION_LOG.md` - accepted architecture decisions.
- `docs/08_TEST_DATA_SCENARIOS.md` - reusable validation scenarios.
- `docs/ANTIGRAVITY_IMPLEMENTATION_PLAN.md` - phased build plan.

Read only the docs needed for the current task. Do not load every file by default.

## Agent Roles

- Codex role: implementation engineer and reviewer when explicitly assigned by the user.
- Antigravity role: coordinator and verifier for approved handoff workflows.
- One-agent-at-a-time rule: only one agent may edit product code at a time.
- State-file rule: agents must obey `AI_STATE.json`.
- Handoff rule: agents must update `AI_HANDOFF.md`, `AI_CHANGELOG.md`, `AI_VERIFICATION.md`, and `AI_RISK_REGISTER.md` as applicable.
- User approval is required for external/destructive actions, credentials, public exposure, scope expansion, and any checkpoint transition.

## Current Gate

- V1 implementation is complete. State: `CP10_COMPLETE`.
- CP5 (Frontend Migration), CP6 (Outbox Dispatcher), CP7 (Telegram Channel),
  CP8 (Model Fallback & Resilience), CP9 (Skill Version), and CP10 (Cleanup)
  are all verified and closed.
- Awaiting human final sign-off before V1 packaging.
- Do not expand to CP11, deployment, vector search, Excalidraw, auth expansion,
  or any new feature scope without human approval and doc update.
- Keep existing legacy session routes and `USE_TASK_API=false` fallback intact.
- Keep automation state in `AI_STATE.json`; only one agent may run at a time.

## Hard Rules

- FastAPI is the policy boundary.
- Frontend must not call Hermes, n8n, MCP tools, or the file system directly.
- SQLite `app.db` stores business metadata only; do not duplicate full Hermes conversation history.
- Every write, external action, destructive action, approval, and policy decision must create an audit event.
- All file operations must stay inside the session `workspace_path`.
- Treat Hermes/LLM/MCP/n8n input as untrusted.
- No hardcoded secrets.
- No `allow always` for `external_or_destructive` actions.
- Do not expand beyond MVP without updating docs and getting user approval.
- Never auto commit, push, merge, or deploy.
- Never run destructive commands.

## Protected Files And Areas

Do not edit without explicit human approval:

- `.env`
- `.env.local`
- `.env.production`
- secrets
- deployment config
- billing config
- production database settings
- database files
- database migrations

## Safe Commands

- `git status --short`
- `git diff`
- `git diff --check`
- `python -m json.tool AI_STATE.json`
- `codex --version`
- `agy --version`
- `agy --help`
- `antigravity --version`
- `ag --version`
- `bash --version`
- `node --version`
- `npm --version`
- `python --version`

Frontend checks only when explicitly needed:

- `cd frontend; npm run lint`
- `cd frontend; npm run type-check`
- `cd frontend; npm run test -- --run`
- `cd frontend; npm run build`

Backend checks only when explicitly needed:

- `cd backend; .\.venv\Scripts\pytest`

## Approval-Required Commands

- Package installation.
- Dependency changes.
- Database migration changes.
- Docker or container changes.
- Network-heavy commands.
- Any command that modifies project state outside automation files.
- `git commit`
- `git push`
- merge
- deploy

## Forbidden Commands

- `git reset --hard`
- `git clean -fdx`
- `rm -rf`
- `del /s /q`
- `rmdir /s /q`
- deploy or publish commands
- database drop/reset
- editing env/secrets/billing/deployment/production database files
- `codex --dangerously-bypass-approvals-and-sandbox`
- `agy --dangerously-skip-permissions`

## Implementation Defaults

- Backend: Python 3.11+, FastAPI, Pydantic, SQLite WAL.
- Frontend: Vite, React, TypeScript, Zustand.
- Agent runtime: Hermes ACP.
- MCP: FastMCP, selected tools only.
- Automation: n8n sidecar, called through backend only.
- Editor: Monaco.
- Diagrams: Mermaid first; Excalidraw conversion later.

## Work Pattern

1. Read `PROJECT_STATE.md` first for the current checkpoint, gates, and blockers.
2. If the task is checkpoint-related, read `docs/implementation/CURRENT_CHECKPOINT.md`.
3. Use `docs/AI_AGENT_ROUTING.md` to choose the smallest relevant doc/code set.
4. Do not treat long-term roadmap docs as active scope unless the current checkpoint says so.
5. Inspect existing files before editing.
6. Make scoped changes only.
7. Add or update tests for behavior changed.
8. Run relevant checks.
9. Report commands, results, risks, and next step.

## Review Pattern

When reviewing output:

1. Compare against PRD, data model, security policy, and phase acceptance criteria.
2. Prioritize findings by severity.
3. Include file/line references when code exists.
4. Approve only when acceptance criteria pass and security invariants hold.

## Context Budget

- Keep this file small and stable.
- Put long procedures in `docs/` or future skills, not here.
- Use `CODEGRAPH.md` to navigate code once implementation exists.
- Use `HEADROOM.md` to decide what to load, summarize, or ignore.
