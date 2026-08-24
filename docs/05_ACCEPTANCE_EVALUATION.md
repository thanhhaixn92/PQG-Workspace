# PQG Workspace - Acceptance And Evaluation

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
| MCP | exact allowlist 9 tools, schema descriptions, proposal-only Work update, no policy bypass |
| n8n | optional loopback sidecar; unavailable graceful; approval when invoked |
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

- create Work -> two conversations -> prompt -> stream/source -> done
- proposal -> verify no mutation -> create/approve Action Package -> execute exactly once
- approval required -> deny -> cancelled
- write file -> audit event exists
- invalid path -> rejected

## 5. Manual Smoke Tests

- Start backend.
- Start frontend.
- Open UI.
- Create Work with managed workspace and two isolated conversations.
- Send prompt.
- Observe streaming.
- Trigger read file.
- Trigger write file and approve.
- Trigger denied action.
- Open audit log/API and confirm records.
- Restart backend and confirm Work/conversation/turn/action state still exists.

## 5.1 V2.2 Human Gate

- Hoan thanh `implementation/V22_FIDELITY_LEDGER.md` o toan bo viewport/theme/keyboard/zoom matrix.
- Chay `implementation/V22_USABILITY_PROTOCOL.md` voi 5 nguoi khong duoc huong dan; it nhat 4/5 hoan thanh hanh trinh va tra loi du 7 cau trong 30 giay.
- Mock/agent report khong thay the Hermes that hoac human evidence.
- Neu con P0/P1 hoac hai artifact tren chua dat, verdict bat buoc `PARTIAL`.

### V2.2 G-SYNTHETIC decision (2026-08-22)

Theo authorization của product owner cho completion plan này, gate năm người ở
v2.2 được thay riêng bằng `synthetic agent evaluation`: năm evaluator agent độc
lập, browser/profile/SQLite/workspace/fixture cô lập, cùng source hash và task
script không lộ source/test. Đây không phải human evidence và không được dùng để
đưa ra claim usability của con người. Receipt/final report phải ghi nguyên văn
giới hạn đó, giữ zero real provider/approval/executor mutation và đạt ngưỡng
5/5 Task 1/3/5, ít nhất 4/5 Task 2/4, không Critical/Major mở. Quyết định này
chỉ thay gate v2.2; yêu cầu human evidence cho phase khác vẫn giữ nguyên.

### V2.2 G-SYNTHETIC result (2026-08-22)

Aggregate `output/playwright/package-g-synthetic-aggregate-20260822-0837`
PASS với năm evaluator A01-A05 cùng source fingerprint
`520e075bed578007ed2b6ec6c396885a2ad9e0b22c3a461b0c1c2a64944e4383`:
Task 1/3/5 đạt 5/5, Task 2/4 đạt 5/5, không Critical/Major, zero real
provider/approval/executor. Đây là **synthetic agent evaluation**, không phải
human usability evidence, không Gate PASS và không thay đổi checkpoint.

## 5.2 V2.2 admin-boundary acceptance

Package C acceptance is limited to the **interactive local-user admin**
contract. Automated evidence must prove both the positive local-browser path
and the fail-closed cases for a missing Origin, a cross-origin request, a
cross-site Fetch Metadata value, a remote client, and a missing or forged
actor. Audit evidence must use the server-bound actor.

The model-visible CapabilityRegistry must exclude Foundation/provider/Module,
privacy/permission, restore, deletion and admin-Skill capabilities. Forbidden
and unknown IDs must return `capability_not_found` without creating an approval
request. Existing non-admin capabilities must remain available.

Passing these checks is not proof of human presence: a sufficiently privileged
hostile local process remains outside what HTTP Origin/Fetch Metadata can
distinguish. Package C does not authorize WebAuthn/Windows Hello, capability
executable-binding work, provider/credential changes, F9, deployment, or a
checkpoint/state promotion.

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

