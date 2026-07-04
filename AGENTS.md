# AGENTS.md

## Mission

Build Hermes Local Stack as a local-first AI office assistant.

Canonical docs:

- `docs/00_PROJECT_CANON.md` - source of truth and conflict order.
- `docs/01_PRD.md` - product scope and MVP.
- `docs/02_DATA_STORAGE_MODEL.md` - data ownership and schema rules.
- `docs/03_EXECUTION_PRINCIPLES.md` - engineering rules.
- `docs/04_SECURITY_PERMISSION_POLICY.md` - security, approval, audit.
- `docs/05_ACCEPTANCE_EVALUATION.md` - acceptance gates and tests.
- `docs/06_HANDOFF_REVIEW_PROTOCOL.md` - Antigravity -> Codex review protocol.
- `docs/07_DECISION_LOG.md` - accepted architecture decisions.
- `docs/08_TEST_DATA_SCENARIOS.md` - reusable validation scenarios.
- `docs/ANTIGRAVITY_IMPLEMENTATION_PLAN.md` - phased build plan.

Read only the docs needed for the current task. Do not load every file by default.

## Roles

- Antigravity implements.
- Codex checks implementation quality, runs relevant tests, and approves phases only when acceptance criteria pass.
- User approval is still required for external/destructive actions, credentials, public exposure, or scope expansion.

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

When reviewing Antigravity output:

1. Compare against PRD, data model, security policy, and phase acceptance criteria.
2. Prioritize findings by severity.
3. Include file/line references when code exists.
4. Approve only when acceptance criteria pass and security invariants hold.

## Context Budget

- Keep this file small and stable.
- Put long procedures in `docs/` or future skills, not here.
- Use `CODEGRAPH.md` to navigate code once implementation exists.
- Use `HEADROOM.md` to decide what to load, summarize, or ignore.
