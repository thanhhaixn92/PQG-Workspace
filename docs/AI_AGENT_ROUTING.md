# AI Agent Routing

Use this file to decide what to read before editing. Do not load every doc by default.

## Always Read First

- `PROJECT_STATE.md`
- `AGENTS.md`
- `docs/implementation/CURRENT_CHECKPOINT.md` when working on checkpoints

## Task Routing

| Task type | Read these first | Then inspect code |
| --- | --- | --- |
| CP3 legacy adapter | `docs/implementation/CURRENT_CHECKPOINT.md`, `docs/05_ACCEPTANCE_EVALUATION.md`, `docs/06_HANDOFF_REVIEW_PROTOCOL.md` | `backend/app/api/sessions.py`, task service/repository files, characterization tests |
| TaskService/state machine | `docs/implementation/CURRENT_CHECKPOINT.md`, relevant ADR in `docs/adr/` | `backend/app/services/task_service.py`, `backend/app/services/state_machine.py`, `backend/app/repositories/task_repository.py` |
| Idempotency | `docs/02_DATA_STORAGE_MODEL.md`, `docs/04_SECURITY_PERMISSION_POLICY.md` | `backend/app/services/idempotency_service.py`, `backend/app/repositories/idempotency_repository.py`, migrations, tests |
| Approval/security | `docs/04_SECURITY_PERMISSION_POLICY.md`, `docs/06_HANDOFF_REVIEW_PROTOCOL.md` | `backend/app/api/approvals.py`, audit service, approval tests |
| Session/chat routes | `docs/01_PRD.md`, `docs/02_DATA_STORAGE_MODEL.md`, `docs/05_ACCEPTANCE_EVALUATION.md` | `backend/app/api/sessions.py`, frontend chat/session components |
| File/editor | `docs/02_DATA_STORAGE_MODEL.md`, `docs/04_SECURITY_PERMISSION_POLICY.md` | `backend/app/api/files.py`, sandbox service, editor/file explorer components |
| Runtime/Hermes/SSE | `docs/11_FIRST_REAL_CHAT.md`, `docs/12_LOCAL_OPERATIONS.md`, `docs/04_SECURITY_PERMISSION_POLICY.md` | Hermes client, event bus, sessions API, events API |
| n8n/MCP | `docs/04_SECURITY_PERMISSION_POLICY.md`, `docs/12_LOCAL_OPERATIONS.md` | MCP tools, n8n routes, n8n tests |
| Frontend UX only | `DESIGN.md`, `CODEGRAPH.md` | Target component and colocated tests |
| Documentation only | `PROJECT_STATE.md`, target doc | Related source only if statements need verification |

## Rules

- Prefer `CODEGRAPH.md` for navigation before broad file searches.
- Prefer targeted tests over full suites while iterating, then run full gates before approval.
- Do not use long roadmap docs as active implementation scope unless `CURRENT_CHECKPOINT.md` says so.
- If docs conflict, follow `docs/00_PROJECT_CANON.md` and `PROJECT_STATE.md`.

