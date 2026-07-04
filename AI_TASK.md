# AI Task

Finalize CP5 Frontend Migration and stop before CP6.

## Goal

Record a clean CP5 checkpoint after verification.

## Context

- CP5 migrated the frontend to optionally use the public Task API behind `VITE_USE_TASK_API`.
- Legacy session/chat behavior remains the default fallback.
- CP6 Outbox Dispatcher has not started.

## Constraints

- Do not implement CP6.
- Do not add automation agent loops or Antigravity workflow scripts in the CP5 merge candidate.
- Do not modify secrets, deployment config, billing config, or production database settings.
- Do not commit, push, deploy, publish, reset, clean, or drop databases automatically.

## Done When

- CP5 checklist is complete.
- Backend tests pass.
- Frontend type-check, lint, tests, and build pass.
- Project state clearly says CP6 requires a separate human-approved planning step.
