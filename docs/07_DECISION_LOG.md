# Hermes Local Stack - Decision Log

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

## ADR-003 - SQLite Stores Business Metadata Only

Decision: App SQLite does not duplicate full Hermes conversation history.

Reason:

- Hermes owns detailed session state.
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

Status: Accepted.

