# DESIGN.md

## Architecture Snapshot

PQG Workspace is a local-first single-user assistant. Trợ lý GYO is its
user-facing assistant surface, backed by the provider-neutral GyoOrchestrator.

```text
React/Zustand UI
  -> FastAPI REST + typed SSE
  -> GyoOrchestrator provider boundary
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
- GyoOrchestrator owns provider routing and internal runtime state; legacy Hermes/ACP data, if present, is compatibility-only and the app never reads, edits, synchronizes, or uses it as a fallback.
- n8n owns optional workflow automation and credentials when configured.

## Core Flows

### Chat

1. User creates or opens a Work and selects a conversation.
2. Frontend posts prompt to backend.
3. Backend persists the user-visible turn/run in `app.db`.
4. Backend sends the prompt to GyoOrchestrator.
5. Backend emits typed SSE events.
6. Frontend routes events into Zustand reducers.
7. Backend writes audit events for key actions.

### Approval

1. GYO/tool requests risky action.
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
- No direct frontend-to-GYO provider/runtime access.
- No MCP tool bypassing backend policy.
- No direct read, write or synchronization against legacy Hermes `state.db`.
- No Work mutation from an MCP call: GYO may propose an Action Package, then explicit approval and the idempotent executor apply it once.
- The MCP layer exposes only its configured allowlist; changing that allowlist requires a PRD/security review and matching regression coverage.
- Memory Hub is never auto-injected and Review remains a projection over source lifecycles.

## Primary References

- PRD: `docs/01_PRD.md`
- Storage: `docs/02_DATA_STORAGE_MODEL.md`
- Security: `docs/04_SECURITY_PERMISSION_POLICY.md`
- Evaluation: `docs/05_ACCEPTANCE_EVALUATION.md`

