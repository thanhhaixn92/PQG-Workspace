# Hermes Local Stack - Handoff And Review Protocol

## 1. Antigravity Handoff Template

After each phase, Antigravity must provide:

```text
Phase:
Summary:
Files changed:
Commands run:
Test results:
Acceptance criteria status:
Security notes:
Known limitations:
Screenshots/logs if UI/API changed:
Questions for Codex:
```

## 2. Codex Review Steps

Codex should:

1. Confirm phase and scope.
2. Inspect changed files.
3. Run relevant commands/tests.
4. Compare against PRD and phase acceptance criteria.
5. Check security permission policy.
6. Report findings by severity.
7. Approve only if acceptance criteria pass.

## 3. Severity Definitions

### Critical

- Data loss risk.
- Secret leak.
- Workspace escape.
- Destructive/external action without approval.
- App cannot start.

### High

- Missing audit for write/external/destructive action.
- Broken session/prompt flow.
- SSE protocol incompatible with frontend.
- MCP tool bypasses policy layer.

### Medium

- Missing test for important path.
- Poor error handling.
- UX blocks common workflow.
- DB schema mismatch that is fixable without data migration risk.

### Low

- Naming inconsistency.
- Minor docs mismatch.
- Non-blocking cleanup.

## 4. Approval Rules

Codex may approve when:

- Scope matches plan.
- Tests pass or failures are unrelated and documented.
- Security invariants hold.
- No user approval is needed.

Codex must request user approval when:

- Antigravity asks to expand scope.
- A secret/credential must be created or stored.
- Any service will be exposed beyond localhost.
- Data will be deleted, overwritten, uploaded, or emailed.
- Work requires changes outside project workspace.

## 5. Review Decision Format

```text
Decision: Approved for next phase
Phase:
Tests run:
Notes:
```

or

```text
Decision: Changes required
Phase:
Findings:
Required fixes:
Tests run:
```

## 6. Rework Protocol

When changes are required:

- Antigravity fixes only listed findings unless Codex/user expands scope.
- Antigravity includes a short "Fix response" mapping each finding to files changed.
- Codex reruns only relevant tests plus any previously failing tests.

## 7. Record Keeping

Each approved phase should append a short note to `docs/07_DECISION_LOG.md` or a separate checkpoint file if the change is large.

