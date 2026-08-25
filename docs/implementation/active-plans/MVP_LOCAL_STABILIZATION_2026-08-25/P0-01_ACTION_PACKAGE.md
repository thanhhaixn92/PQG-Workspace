# P0-01 — Action Package Integrity

**Priority:** P0  
**Risk class:** approval/integrity boundary  
**PR lane:** Standard PR  
**Depends on:** planning base only  
**Blocks:** P0-02 and final MVP gate

## 1. Goal

Make the governed frontend decision path use the live backend preflight contract and re-validate the exact package **at click time** before approve/deny.

Required negative scenario:

```text
load package
→ package changes / expires / becomes stale
→ user clicks Approve
→ click-time canonical re-preflight detects stale
→ NO approve request is sent
→ authoritative package state is refreshed
```

## 2. Audited source contract

At planning base:

- backend `GET /api/action-packages/{package_id}/preflight` returns top-level `package_id`, `revision`, `payload_hash`, `expires_at`, `valid` plus canonical targets/preconditions/diffs/snapshot/capabilities;
- frontend `ActionPackagePreflight` incorrectly expects `binding?: { revision; payload_hash }`;
- `ActionPackagesPanel.decide()` currently uses the list-loaded package binding and immediately calls approve/deny.

Implementation must re-check this contract at the package branch's exact source SHA before editing. If backend source no longer matches this shape, stop and re-plan instead of forcing the old audit assumption.

## 3. Planned files

Expected narrow scope:

- `frontend/src/api/actionPackages.ts`
- `frontend/src/components/assistant/GYOAssistant.tsx`
- `frontend/src/components/assistant/GYOAssistant.test.tsx`
- `frontend/src/components/ActionPackagesPanel.tsx`
- `frontend/src/components/ActionPackagesPanel.test.tsx`

No backend schema, migration, dependency, workflow or state file is planned.

## 4. Implementation steps

1. Correct `ActionPackagePreflight` TypeScript shape to mirror the live backend top-level binding fields.
2. Introduce one small helper that extracts a decision binding from **canonical preflight**, not only from the stale list item.
3. On Approve or Deny click:
   - set per-package busy state before any network decision;
   - call `getActionPackagePreflight(item.id)` immediately;
   - require `valid === true`;
   - require integer `revision >= 1` and non-empty `payload_hash`;
   - optionally compare canonical preflight binding against the displayed package binding only for stale-state messaging; canonical preflight remains authoritative;
   - create the decision idempotency key only for the actual decision attempt;
   - send approve/deny using the canonical `revision` and `payload_hash`.
4. On preflight 409/invalid/missing binding/network error:
   - do not call approve/deny;
   - refresh the work Action Package list;
   - surface a clear fail-closed message;
   - clear busy state.
5. Apply the same contract correction to `GYOAssistant` if it reads preflight binding there.
6. Preserve existing server-side approval/idempotency guards; do not add a client fallback to stale binding.

## 5. Required tests

### Negative tests — mandatory

- stale/expired preflight (409) => **zero** approve calls;
- preflight `valid=false` or missing/invalid binding => **zero** decision calls;
- preflight request failure => **zero** decision calls and authoritative refresh attempted;
- package list item has binding but click-time preflight is stale => list binding must not be reused;
- second click while busy => no duplicate preflight/decision submission.

### Positive tests

- valid canonical preflight => approve body contains exact `expected_revision` + `expected_payload_hash` from preflight;
- valid canonical preflight => deny uses the same current binding discipline;
- post-decision authoritative refresh occurs.

## 6. Validation order

1. focused `ActionPackagesPanel` tests;
2. focused `GYOAssistant` tests;
3. frontend type-check/build as required by current repo policy;
4. PR canonical `pqg/smoke`;
5. record `source_head_sha` separately from workflow `validation_sha`.

## 7. Stop / escalation conditions

Stop P0-01 and re-plan if any of the following is required:

- backend response schema change;
- migration/dependency/workflow change;
- weakening server-side binding checks;
- direct-main/admin bypass;
- approval semantics expand beyond freshness/integrity correction.

## 8. Done criteria

P0-01 is done only when the negative stale-click scenario is automated and demonstrates that the decision POST is never sent, positive approve/deny paths use current canonical preflight binding, focused tests pass, canonical CI passes, and the governed PR is merged.
