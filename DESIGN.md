# DESIGN.md

## Architecture Snapshot

DIRAP Local Workbench is a local-first single-user assistant. Hermes is its internal agent/runtime.

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
- `app.db` owns Work conversations and Assistant turns visible to the user.
- Hermes owns ACP sessions, reasoning and internal runtime state only; the app never edits Hermes `state.db`.
- n8n owns optional workflow automation and credentials when configured.

## Core Flows

### Chat

1. User creates or opens a Work and selects a conversation.
2. Frontend posts prompt to backend.
3. Backend persists the user-visible turn/run in `app.db`.
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
- No direct read, write or synchronization against Hermes `state.db`.
- No Work mutation from an MCP call: Hermes emits `DIRAP_ACTION_PROPOSAL:`, the user creates an Action Package, then approval/executor applies it once.
- Hermes MCP exposes exactly the nine tools documented in PRD v2.2.
- Memory Hub is never auto-injected and Review remains a projection over source lifecycles.

## Primary References

- PRD: `docs/01_PRD.md`
- Storage: `docs/02_DATA_STORAGE_MODEL.md`
- Security: `docs/04_SECURITY_PERMISSION_POLICY.md`
- Evaluation: `docs/05_ACCEPTANCE_EVALUATION.md`

