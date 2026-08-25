# P0-02 — Native GYO Integrated Journey

**Priority:** P0  
**Risk class:** acceptance/runtime integrity  
**PR lane:** Standard PR  
**Depends on:** P0-01 merged  
**Blocks:** P0-03 and final MVP gate

## 1. Goal

Replace the active P0 acceptance evidence that still depends on legacy session/Hermes semantics with one deterministic, provider-independent **current durable GYO** journey.

Focused tests remain valuable but **must not be accepted as a substitute** for this integrated journey.

## 2. Canonical journey to prove

One isolated run must prove, in order:

```text
create Work
→ create at least two conversations
→ prompt through current Assistant/GYO API
→ stream durable assistant output
→ persist text + source + action_proposal parts
→ prove proposal itself did not mutate Work
→ create immutable Action Package from proposal
→ canonical preflight
→ approval with current binding
→ execute exactly once
→ create/read artifact or report evidence
→ reopen the same isolated DB
→ prove durable state remains correct
```

The test should also demonstrate Work scoping and no cross-Work leakage where practical.

## 3. Audited current gap

- `smoke-dev.ps1` still submits through `/api/sessions/{id}/prompt` and consumes `/api/sessions/{id}/events`, with Hermes-oriented runtime output.
- `backend/tests/test_uat_p0_local_pilot.py` is skipped as a superseded Hermes ACP mock journey and still imports/uses legacy Hermes code.

Therefore the current repo lacks one active integrated current-GYO P0 journey even though narrower GYO tests exist.

## 4. Planned files

Primary scope:

- `smoke-dev.ps1`
- `backend/tests/test_uat_p0_local_pilot.py`

A small test-only helper may be added only if it materially reduces duplication. Do not create a second orchestration framework.

No real provider, credential, network, dependency, migration, workflow or production data is required.

## 5. Test architecture

Use a fresh temporary SQLite DB and temporary workspace, migrated using current migrations. Exercise the real FastAPI surface with current Assistant/GYO orchestration, but inject a deterministic provider-neutral/fake generation seam so the journey is stable and offline.

The deterministic assistant output must include enough structured content to persist:

- assistant text;
- at least one source reference tied to a managed input artifact;
- one `action_proposal` part that can be turned into the canonical Action Package.

The test must not call legacy Hermes/ACP as its acceptance path.

## 6. Mandatory assertions

### Work and conversation isolation

- Work created with expected local scope;
- two explicit conversations coexist in the same Work;
- source/artifact selected for this Work is persisted and not visible as another Work's source.

### Durable GYO

- Assistant thread/run created through current API;
- stream reaches terminal success;
- persisted assistant turn contains expected `text`, `source`, and `action_proposal` parts;
- source identity/reason remains durable after stream completion.

### Proposal-before-mutation

Before Action Package creation/approval:

- target plan step/status remains unchanged;
- no Work mutation has occurred merely because the model returned a proposal.

### Action Package

- package is created from the persisted proposal;
- idempotent duplicate create replays the same package;
- same idempotency key + different payload is rejected;
- canonical preflight succeeds;
- stale binding negative path is covered by P0-01 and may be reasserted here at journey level when inexpensive;
- approval uses exact current revision/payload hash;
- executor applies the action **exactly once**.

### Restart durability

Close the app/client, reopen using the same isolated DB and workspace, then prove:

- Work/conversations/assistant turns remain;
- package/execution status remains terminal;
- resulting Work state remains correct;
- artifact/report evidence remains addressable.

## 7. `smoke-dev.ps1` target behavior

The local smoke should stop presenting legacy Hermes prompt/event flow as the product journey. It should either invoke or mirror the same current Assistant/GYO path in a bounded way and clearly label provider-independent/offline acceptance.

Do not turn local smoke into a real-provider test. Real-provider availability is not a controlled local MVP prerequisite.

## 8. Validation order

1. focused native GYO/UAT test;
2. related assistant/action-package focused tests;
3. PowerShell smoke syntax/static checks as available;
4. canonical `pqg/smoke` on PR;
5. after merge, use the package merge SHA as the new planning anchor for P0-03.

## 9. Stop / escalation conditions

Stop and re-plan if the integrated journey would require:

- real provider/network/credential access;
- re-enabling Hermes/ACP as canonical acceptance;
- schema migration unrelated to an already-current migration path;
- workflow change;
- user `app.db` or user workspace data.

## 10. Done criteria

P0-02 is done only when an active, deterministic current-GYO integrated journey passes end-to-end and the previous skipped/legacy path is no longer the evidence used to claim the controlled local pilot journey.
