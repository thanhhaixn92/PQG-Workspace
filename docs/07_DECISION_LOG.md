# DIRAP Local Workbench - Decision Log

This file records architecture decisions that should remain stable unless explicitly changed by user approval.

## ADR-001 - Use Hermes ACP As Agent Runtime Boundary

Decision: Use Hermes Agent through ACP instead of custom JSON-RPC parsing where an official protocol/client path is available.

Reason:

- ACP exposes session, streaming, tool activity, approval, and file/terminal events.
- Avoids fragile custom stdout parsing.

Status: Accepted.

## ADR-002 - FastAPI Is The Policy Boundary

Decision: Frontend, MCP tools, and n8n integrations must go through FastAPI/service layer for permission checks and audit.

Reason:

- Centralizes validation.
- Prevents UI-only security.
- Makes Codex review simpler and more reliable.

Status: Accepted.

## ADR-003 - SQLite Stores Business Metadata Only (Superseded by ADR-008)

Decision: App SQLite does not duplicate full Hermes conversation history.

Reason:

- Hermes owns detailed session state.

Status: superseded for user-visible Work conversations by ADR-008. Historical reasoning is retained as evidence.
- Avoids data drift.
- Keeps MVP simple.

Status: Accepted.

## ADR-004 - Local-First MVP

Decision: MVP is local single-user only.

Reason:

- Reduces auth/deployment complexity.
- Focuses on agent control, audit, and useful workflows.

Status: Accepted.

## ADR-005 - No Level 3 Agent Autonomy In MVP

Decision: Agent cannot create arbitrary new tools/tasks without review.

Reason:

- Local assistant needs predictable safety.
- Current value is achieved with controlled Level 2 routing/tools.

Status: Accepted.

## ADR-006 - Approval Required For External/Destructive Actions

Decision: External/destructive actions always require manual approval. No `allow always`.

Reason:

- Prevents accidental data loss or data exfiltration.
- Keeps Codex approval authority bounded.

Status: Accepted.

## ADR-007 - n8n Is A Sidecar

Decision: n8n is used for workflow automation but not as the main application orchestrator.

Reason:

- FastAPI must remain policy/audit boundary.
- n8n is useful for integrations, scheduled tasks, and external workflow execution.

## ADR-008 - app.db Owns User-Visible Work Conversations

Decision: `app.db` owns Work conversations, Assistant turns and structured parts shown to the user. Hermes state owns only ACP sessions, reasoning and internal runtime state. The application does not read, synchronize or edit Hermes `state.db` directly.

## ADR-009 - n8n Is Optional For v2.2

Decision: n8n remains a loopback-only sidecar. Missing configuration must return a clear graceful-unavailable state and does not block `DIRAP_V22_VALIDATED`. Live credentials or an external endpoint are not required for v2.2 acceptance.

## ADR-010 - Hermes MCP Is An Exact Nine-Tool Allowlist

Decision: the Hermes MCP server exposes exactly `propose_work_update`, `save_work_context_summary`, `read_workspace_file`, `write_workspace_file`, `search_workspace`, `list_skills`, `update_memory`, `run_safe_task`, and `call_n8n_webhook`.

`propose_work_update` emits a validated `DIRAP_ACTION_PROPOSAL:` only. It cannot mutate Work state or create an Action Package. Persistent summary is `write_internal` and requires user approval. Adding a tenth tool requires PRD and security review.

Status: Accepted.

