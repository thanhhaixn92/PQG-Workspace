# PQG Workspace — Controlled Local MVP Stabilization Plan

**Plan date:** 2026-08-25 (UTC+07:00)  
**Repository:** `thanhhaixn92/PQG-Workspace`  
**Planning base:** `pqg-workspace@75ce89efe0fc7da11e597d7c87b9796ad0335182`  
**Base tree:** `a0922b7656717401c6f0a9765c7c1af329dc87a0`  
**Project state at planning base:** `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`  
**Purpose:** track and govern the shortest path to call PQG Workspace a **controlled, stable local MVP** without widening architecture or claiming production readiness.

> This folder is an **active implementation plan**, not a state/checkpoint promotion. It does not authorize provider/network/credential work, deployment, schema migration, baseline mutation, GitHub settings changes, or direct-main delivery.

## 1. Locked execution order

```text
P0-01 Action Package integrity
  -> P0-02 Native GYO integrated journey
  -> P0-03 Local provenance / restore safety
  -> P0-04 Artifact atomicity
  -> STOP feature/refactor work
  -> Controlled Local MVP Gate
  -> only if GATE = PASS: open P1-05 Foundation pilot
```

The four P0 packages are mandatory. Focused tests are supporting evidence only; they do not replace the integrated journey or the final MVP gate.

## 2. Non-negotiable boundaries

- Keep the current stack: React/Vite frontend, FastAPI backend, SQLite local-first.
- No new project, rewrite, PostgreSQL, Nx, NestJS, general plugin platform, cloud or multi-user expansion.
- Every agent write uses **feature branch + PR**. Agent direct-push to `pqg-workspace` and admin/bypass delivery are prohibited.
- Keep canonical `pqg/smoke`; this plan does not change workflow semantics, branch protection, rulesets or CI configuration.
- Do not change `PROJECT_STATE.md`, `AI_STATE.json`, `docs/implementation/CURRENT_CHECKPOINT.md` or F9 in P0 implementation PRs.
- No real provider/network/credential access is required to close these P0 packages.
- No user `app.db`, baseline database or user workspace may be used for tests. Use isolated temporary DB/workspace only.
- Preserve exact evidence semantics: `source_head_sha` is not automatically the same as the SHA actually validated by a PR workflow.

## 3. Active package tracker

| Package | Risk | Planning status | Implementation status | Merge prerequisite | Acceptance anchor |
|---|---|---|---|---|---|
| P0-01 Action Package | approval/integrity | AUDITED / PLAN READY | NOT STARTED | fresh exact-source review + governed PR | stale click-time re-preflight must block decision POST |
| P0-02 Native GYO journey | acceptance/runtime | AUDITED / PLAN READY | NOT STARTED | P0-01 merged | one deterministic current-GYO integrated journey |
| P0-03 Provenance/restore | local process/data safety | AUDITED / PLAN READY | NOT STARTED | P0-02 merged | unable to prove identity => no reuse/kill/restore |
| P0-04 Artifact atomicity | **highest data-integrity risk** | AUDITED / PLAN READY | NOT STARTED | P0-03 merged | failure injection proves no split DB/file success |
| MVP Gate | release-control evidence | PLAN READY | NOT RUN | all four P0 merged | all required evidence on one final default SHA |
| P1-05 Foundation pilot | architecture refinement | DEFERRED | BLOCKED BY MVP GATE | MVP Gate PASS | separate plan/PR; use `reports` or `review`, not Work/GYO |

Status vocabulary for this folder: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `READY FOR REVIEW`, `MERGED`, `PASS`, `FAIL`.

## 4. Child plans

- [`AUDIT_BASELINE.md`](./AUDIT_BASELINE.md) — current-source findings that make the four P0 packages mandatory.
- [`P0-01_ACTION_PACKAGE.md`](./P0-01_ACTION_PACKAGE.md) — frontend contract correction and click-time re-preflight.
- [`P0-02_NATIVE_GYO_JOURNEY.md`](./P0-02_NATIVE_GYO_JOURNEY.md) — deterministic current durable GYO integrated acceptance journey.
- [`P0-03_PROVENANCE_RESTORE.md`](./P0-03_PROVENANCE_RESTORE.md) — process/source/DB provenance and fail-closed restore rules.
- [`P0-04_ARTIFACT_ATOMICITY.md`](./P0-04_ARTIFACT_ATOMICITY.md) — narrow transaction ownership for idempotent filesystem workflows.
- [`MVP_GATE.md`](./MVP_GATE.md) — final same-SHA controlled-local-MVP gate.

## 5. PR governance for each P0 package

Each implementation package is a separate **Standard PR** because it touches an approval boundary, acceptance runner, process/data safety, or data-integrity transaction semantics.

For every P0 PR record:

```text
package_id
planning_base_sha
feature_branch
writer_owner
ownership_start_sha
source_head_sha
preflight_ref / preflight_result (when required by live governance)
focused_validation
canonical_ci_run
validation_sha
changed_paths
negative_tests
known_residuals
review_verdict
merge_sha
```

If remote branch HEAD moves unexpectedly, if live source contradicts this audit, or if a package requires dependency/schema/workflow/state changes, stop and re-plan rather than widening the PR.

## 6. Controlled-MVP claim boundary

Passing this plan may support the narrow statement: **“PQG Workspace controlled local MVP gate passed on exact SHA X.”**

It does **not** by itself support claims of production readiness, cloud readiness, multi-user readiness, real-provider readiness, complete dependency remediation, Monaco upstream closure, human usability validation, DIRAP state promotion, F9 approval or deployment readiness.
