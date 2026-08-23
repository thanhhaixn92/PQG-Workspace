# PQG Workspace - Test Data And Evaluation Scenarios

## 1. Purpose

This file defines reusable scenarios for Antigravity implementation and Codex review. These are not full automated tests by themselves, but they should be converted into tests when practical.

## 2. Sample Workspace

Create a test workspace during tests:

```text
test_workspace/
  README.md
  notes/
    project.md
  reports/
    draft.md
  data/
    sample.csv
```

Sample `README.md`:

```text
# Test Workspace

This workspace is used for PQG Workspace validation.
```

Sample `notes/project.md`:

```text
Project goal: build a local-first Hermes assistant with approval, audit, memory, skills, and n8n automation.
```

Sample `data/sample.csv`:

```csv
name,value
alpha,10
beta,20
```

## 3. Scenario: Basic Chat

Prompt:

```text
Summarize the project goal from notes/project.md.
```

Expected:

- Session exists.
- Prompt creates task_run.
- Stream emits `token` events.
- Any file read remains inside workspace.
- Final answer references project goal.

## 4. Scenario: File Write With Approval

Prompt:

```text
Create reports/summary.md with a concise summary of notes/project.md.
```

Expected:

- Agent requests write approval.
- User/Codex can allow once.
- File is created inside workspace.
- `audit_events` includes approval decision and file write.

## 5. Scenario: Denied Write

Prompt:

```text
Overwrite reports/draft.md with the word denied-test.
```

Action:

- Deny approval.

Expected:

- File unchanged.
- task_run becomes cancelled or failed with clear reason.
- audit includes denial.
- UI does not hang.

## 6. Scenario: Path Traversal Attack

Request path:

```text
..\..\secret.txt
```

Expected:

- Backend rejects request.
- No file is read or written.
- Error is user-readable.
- Security test passes on Windows.

## 7. Scenario: Absolute Path Escape

Request path:

```text
C:\Users\dtron\.ssh\id_rsa
```

Expected:

- Backend rejects request unless workspace explicitly equals or contains that path.
- No content leaked.
- Audit/security log records rejected attempt if implemented.

## 8. Scenario: Memory CRUD

Create memory:

```json
{
  "key": "preferred_report_style",
  "value": "Concise, structured, no marketing language.",
  "kind": "style_rule",
  "importance_score": 0.8
}
```

Expected:

- Memory created.
- Audit event recorded.
- Later read updates `last_accessed_at`.

## 9. Scenario: Skill Disable

Skill:

```text
Name: verbose_reports
Content: Always produce long reports.
Enabled: false
```

Expected:

- Disabled skill is not injected into prompt context.
- Test can assert context builder excludes it.

## 10. Scenario: Optional n8n Webhook Requires Approval

Prompt:

```text
Send the project summary to the configured n8n reporting workflow.
```

Expected:

- Backend classifies as `external_or_destructive`.
- Approval required every time.
- If denied, webhook is not called.
- If approved and configured, backend sends request with secret header.
- If unconfigured, backend returns graceful unavailable; this does not fail the v2.2 product gate.

## 11. Scenario: SSE Error Recovery

Simulate Hermes unavailable.

Expected:

- API returns typed error or SSE `event: error`.
- UI shows error.
- UI remains usable.
- No infinite spinner.

## 12. Scenario: Audit Completeness

Perform:

- create Work and two conversations
- submit prompt
- approve write
- write file
- update memory
- call n8n denied

Expected audit actions include:

- `session.created` (legacy-compatible Work event)
- `prompt.submitted`
- `approval.requested`
- `approval.allowed`
- `file.written`
- `memory.updated`
- `approval.denied`

## 13. Scenario: Proposal-Only Work Update

Perform:

- call `propose_work_update` for an allowlisted `work_plan_step_update`;
- snapshot Work/plan/action-package/audit rows before and after the MCP call;
- create the returned Action Package with an idempotency key, approve, then execute twice;
- repeat with wrong schema, foreign step and archived Work.

Expected:

- MCP returns `DIRAP_ACTION_PROPOSAL:` and changes no application row;
- invalid or out-of-scope input fails closed;
- package creation still requires explicit user action and approval;
- executor changes the intended row once; repeated execution is idempotent.

## 14. Scenario: Persistent Summary Approval

Expected: deny/timeout writes no summary; allow writes one version and metadata-only audit; archiving the Work or conversation during approval fails closed.

