# Hermes Local Stack - Acceptance And Evaluation

## 1. Evaluation Philosophy

Acceptance is based on observable behavior, tests, and security invariants. A feature is not accepted because it exists in UI; it must satisfy backend policy, storage model, and error handling.

## 2. Global Acceptance Gates

Every phase must pass:

- Build or typecheck.
- Relevant automated tests.
- No hardcoded secrets.
- No unexpected files outside planned scope.
- No violation of security policy.
- Handoff note from Antigravity.

## 3. Phase Acceptance Matrix

| Phase | Must Pass |
|---|---|
| Bootstrap | health route, DB schema, frontend starts, README commands |
| ACP Bridge | session create, prompt submit, typed SSE, reconnect/error handling |
| Frontend Chat | stream rendering, approval modal, activity panel, no reload required |
| Files | workspace jail, read/write, autosave, path traversal rejection |
| Memory/Skills | CRUD, enable/disable, context cap, audit |
| MCP | max 6 tools, schema descriptions, no policy bypass |
| n8n | persistent volume, env secrets, approval for webhook execution |
| Diagram | render valid Mermaid, invalid Mermaid does not crash |

## 4. Required Automated Tests

Backend:

- `test_health`
- `test_db_schema`
- `test_create_session`
- `test_prompt_creates_task_run`
- `test_sse_event_format`
- `test_path_traversal_rejected`
- `test_absolute_path_escape_rejected`
- `test_write_file_creates_audit_event`
- `test_destructive_action_requires_approval`
- `test_memory_crud_audit`
- `test_skill_disable_not_injected`
- `test_n8n_missing_config_graceful_error`

Frontend:

- store reducer handles `token`
- store reducer handles `approval_required`
- store reducer handles `error`
- approval modal hides `allow always` for destructive/external
- autosave debounce test
- typecheck

Integration:

- create session -> prompt -> stream -> done
- approval required -> deny -> cancelled
- write file -> audit event exists
- invalid path -> rejected

## 5. Manual Smoke Tests

- Start backend.
- Start frontend.
- Open UI.
- Create session with workspace path.
- Send prompt.
- Observe streaming.
- Trigger read file.
- Trigger write file and approve.
- Trigger denied action.
- Open audit log/API and confirm records.
- Restart backend and confirm sessions metadata still exist.

## 6. Quality Rubric

Score each phase 0-2:

- Correctness: feature works as specified.
- Security: policy enforced in backend.
- Observability: errors/audit/logs are usable.
- UX: user can complete workflow without confusion.
- Testability: tests cover normal and failure paths.
- Scope control: no unrelated expansion.

Minimum acceptance:

- No category below 1.
- Security must be 2 for phases involving files, MCP, n8n, approvals.

## 7. Codex Review Output Format

Codex should respond with:

```text
Decision: Approved / Changes Required
Phase:
Findings:
Tests Run:
Residual Risk:
Next Step:
```

Findings must include file/line references when code exists.

