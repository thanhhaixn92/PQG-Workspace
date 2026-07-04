# DESIGN.md

## Architecture Snapshot

Hermes Local Stack is a local-first single-user assistant.

```text
React/Zustand UI
  -> FastAPI REST + typed SSE
  -> Hermes ACP process
  -> workspace sandbox

FastAPI
  -> SQLite app.db
  -> selected MCP/FastMCP tools
  -> n8n sidecar webhooks
```

## Design Principles

- FastAPI owns validation, permissions, audit, and process boundaries.
- UI owns presentation and interaction state only.
- Hermes owns agent reasoning and detailed conversation state.
- SQLite owns app-visible metadata only.
- n8n owns workflow automation and credentials.

## Core Flows

### Chat

1. User creates or opens a session.
2. Frontend posts prompt to backend.
3. Backend creates `task_run`.
4. Backend sends prompt to Hermes ACP.
5. Backend emits typed SSE events.
6. Frontend routes events into Zustand reducers.
7. Backend writes audit events for key actions.

### Approval

1. Hermes/tool requests risky action.
2. Backend classifies risk.
3. Backend emits `approval_required`.
4. User/Codex reviewer chooses allowed option.
5. Backend records decision.
6. Action proceeds or is cancelled.

### Files

1. Request includes session and path.
2. Backend resolves canonical absolute path.
3. Backend rejects paths outside `workspace_path`.
4. Read is allowed if safe.
5. Write requires policy check and audit.

## Non-Negotiable Boundaries

- No direct frontend-to-filesystem access.
- No direct frontend-to-n8n access.
- No direct frontend-to-Hermes process access.
- No MCP tool bypassing backend policy.
- No duplicate full chat history in app.db.

## Primary References

- PRD: `docs/01_PRD.md`
- Storage: `docs/02_DATA_STORAGE_MODEL.md`
- Security: `docs/04_SECURITY_PERMISSION_POLICY.md`
- Evaluation: `docs/05_ACCEPTANCE_EVALUATION.md`

