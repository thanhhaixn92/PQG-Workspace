# Local Changelog

This file records local implementation and review checkpoints. Keep entries short.

## 2026-07-04

### CP4 Public Task API

- Added backend public Task API at `/api/tasks`.
- Added idempotent task creation, task event list/stream, cancel, and task action decision routes.
- Added CP4 backend tests for idempotency, streaming order, cancel conflict, approval/action binding, audit, and legacy safety.
- Backend validation: 203 passed, only pre-existing Starlette warning remains.
- Next checkpoint: CP5 Frontend Migration behind `VITE_USE_TASK_API`.

### CP3 merge and CP3.1 cleanup

- CP3 Legacy Adapter merged to `main` at `37e6f37`.
- CP3.1 cleanup committed at `647f40b`.
- Backend validation after CP3.1: 197 passed, only pre-existing Starlette warning remains.
- Next checkpoint: CP4 Public Task API.

### CP2 review hardening

- OpenCode reported CP2 gates green after blocker fixes.
- Codex verified:
  - `IdempotencyService.execute_idempotent()` now calls `check_key(key, request_hash=...)`.
  - `backend/pyproject.toml` no longer ignores `PytestUnhandledThreadExceptionWarning` globally.
  - `backend/tests/test_task_service.py` passes.
- Decision: CP2 is acceptable to approve if the reported full gate is trusted.
- Next: CP3 Legacy Adapter behind `USE_TASK_API`, with strict flag-off compatibility.

### Project control files

- Added short state and routing docs so AI agents do not need to reread the whole roadmap.
- Updated `AGENTS.md` to load `PROJECT_STATE.md` and `docs/implementation/CURRENT_CHECKPOINT.md` first.
