# Local Changelog

This file records local implementation and review checkpoints. Keep entries short.

## 2026-07-04

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

