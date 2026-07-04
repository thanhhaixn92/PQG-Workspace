# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP5 - Frontend Migration.

## Status

CP5 Frontend Migration is complete and verified:

- Frontend API client wrapped all public Tasks API endpoints.
- Zustand store supports the legacy session path and the Task API path under `VITE_USE_TASK_API`.
- ChatPanel and Activity Timeline integrate with the Task API conditionally behind the feature flag.
- Warning banners for metadata execution mode and cancellation side effects are present.
- `VITE_USE_TASK_API=false` remains the safe default.
- CP6 is not started.

## Goal

Close CP5 cleanly before any CP6 work begins.

## Context

CP5 migrates the frontend to optionally use the public Task API while preserving the legacy session route fallback. The next checkpoint, CP6 Outbox Dispatcher, must not begin until the user explicitly approves CP6 planning.

## Constraints

- Do not implement CP6 in this checkpoint.
- Keep existing legacy session routes working.
- Keep `VITE_USE_TASK_API=false` fallback intact.
- Do not add Telegram, model fallback, auth, deployment, vector search, or CP7+ scope.

## Required Implementation Shape

- CP5 changes remain behind the feature flag.
- Product code should not be changed unless a CP5 blocker is found.
- Project state and handoff documents must say CP5 is complete and CP6 is pending user approval.

## Done When

- CP5 checklist is complete.
- Backend test suite passes.
- Frontend type-check, tests, and build pass.
- Project state does not instruct agents to start CP6 automatically.

## Review Gate

Human approval is required before opening CP6 planning or implementation.
