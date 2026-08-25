# Audit Baseline — Four Mandatory P0 Packages

**Audited source:** `pqg-workspace@75ce89efe0fc7da11e597d7c87b9796ad0335182`  
**Audit mode:** read-only source review.  
**External audit inputs:** `PQG_WORKSPACE_AUDIT_3_ROUNDS_CONSOLIDATED_2026-08-25.md` and `kien-truc-webapp-mvp-fixed-shell-pluggable-modules-2026-08-25.md` were used as planning inputs; current repository source is the authority for implementation details.

## 1. Verdict

PQG Workspace does not need a rewrite. The current local-first architecture is viable, but four blocking integrity/acceptance gaps should be closed before calling the current project a controlled stable local MVP.

Risk order for execution remains locked by dependency and blast radius, not by severity alone:

1. P0-01 — Action Package integrity.
2. P0-02 — Native GYO integrated journey.
3. P0-03 — provenance/restore safety.
4. P0-04 — artifact atomicity (**highest data-integrity risk**).
5. Stop feature/refactor work and run the MVP gate.

## 2. P0-01 audit — Action Package contract and decision freshness

### Current source evidence

- `backend/app/api/action_packages.py` returns canonical package preflight fields at the top level, including `package_id`, `revision`, `payload_hash`, `expires_at`, and `valid`.
- `frontend/src/api/actionPackages.ts` currently models preflight as `binding?: { revision; payload_hash }`, which does not match that backend response shape.
- `frontend/src/components/ActionPackagesPanel.tsx` currently derives the decision binding from the list-loaded package and sends approve/deny directly. It does **not** call canonical preflight again at user click time.

### Consequence

A package can become stale between render/load and click. Backend may still reject a stale request, but the governed UI does not currently prove freshness immediately before the decision and its preflight TypeScript contract is structurally wrong.

### Required closure

At click time, obtain canonical preflight and use only its current top-level `revision`/`payload_hash` if valid. Any stale/expired/409/mismatch/error path must fail closed and refresh authoritative state without sending approve/deny.

## 3. P0-02 audit — acceptance still contains legacy Hermes path

### Current source evidence

- Root `smoke-dev.ps1` uses `/api/sessions/{id}/prompt` and `/api/sessions/{id}/events` and reports legacy runtime labels such as Hermes.
- `backend/tests/test_uat_p0_local_pilot.py` is explicitly skipped as a superseded Hermes ACP mock journey and still imports/uses `HermesClientManager` and legacy mock seams.
- The current product canon requires durable GYO/Assistant behavior, not Hermes/ACP compatibility as the acceptance path.

### Consequence

Focused GYO tests may verify individual components, but there is no active deterministic integrated test proving the whole canonical journey on current GYO semantics.

### Required closure

Replace the skipped/legacy acceptance journey with one provider-independent current-GYO journey that persists source/action-proposal parts and proves proposal-before-mutation, Action Package approval binding, exactly-once execution and restart persistence.

## 4. P0-03 audit — dev-state is not provenance

### Current source evidence

`start-dev.ps1` currently writes only:

- backend port;
- frontend port;
- backend PID;
- frontend PID;
- one `startedAt` timestamp.

It may reuse a busy port when an HTTP health endpoint responds, without proving that process belongs to the same repository, source SHA, command or DB.

`check-dev.ps1` mainly checks dependencies, optional Hermes configuration and HTTP health. It does not verify recorded process identity/source/DB binding.

`stop-dev.ps1` kills the recorded PID/process tree if that PID exists, without proving PID start-time/command/source identity before killing.

`restore-local-data.ps1` has useful manifest/hash/integrity/staging/safety-copy behavior, but the default-target offline guard only checks fixed ports `8000` and `8100`; it does not prove whether another dynamic-port process is using the target DB.

### Consequence

PID reuse, stale state or a different checkout/process can cause unsafe reuse, unsafe kill or restore while a backend still has the target DB open.

### Required closure

`.dev/dev-state.json` must carry sufficient non-secret provenance to prove repository, exact SHA, process identity/start-time/command/working directory, ports and DB binding. If proof fails, reuse/kill/restore must refuse.

## 5. P0-04 audit — split commit boundary in filesystem workflows

### Current source evidence

`backend/app/services/security_artifact_create.py` and `security_artifact_import.py` follow this general pattern:

1. atomically claim idempotency operation; `claim_operation()` intentionally commits;
2. publish file into managed filesystem;
3. insert artifact/validation rows;
4. log audit event;
5. finalize operation claim;
6. mark completed; otherwise rollback and delete published file.

`backend/app/services/audit.py::log_audit_event(..., commit=True)` commits by default.

`backend/app/repositories/idempotency_repository.py::finalize_operation()` also commits unconditionally.

### Failure window

If audit logging commits artifact metadata/audit rows, then `finalize_operation()` fails, the exception handler's rollback cannot undo the already committed DB rows. The finally block can delete the file, leaving DB success metadata without the file and without a completed idempotency record.

### Required closure

Do not refactor the global transaction layer. Keep the initial idempotency claim commit, then make the post-filesystem DB unit — artifact metadata/validation + audit + idempotency finalization — commit once under one narrow transaction owner. Failure injection at the finalize boundary must prove rollback of DB rows and cleanup of the file.

## 6. Explicit non-findings / non-goals

This audit does not authorize or require:

- backend schema migration for P0-01;
- a real provider for P0-02;
- new secrets in dev-state for P0-03;
- global connection/autocommit refactor for P0-04;
- workflow/ruleset/branch-protection changes;
- dependency upgrade or Monaco workaround;
- state/checkpoint/F9 promotion.
