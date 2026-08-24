# PQG Workspace — Remediation & Final Acceptance Master Plan

> Status: **ACTIVE — TRACK UNTIL COMPLETION**
>
> This file is the authoritative execution tracker for the remaining v2.2 remediation/final-acceptance work. It does not override live canon, `PROJECT_STATE.md`, `AI_STATE.json`, `docs/implementation/CURRENT_CHECKPOINT.md`, current security contracts, source, tests, or newer evidence.

## 0. Persistence and change control

- The master plan remains in the repository while any package is unfinished, deferred, blocked, or awaiting final acceptance.
- Normal revisions update this file in place and preserve the execution ledger/history.
- Delete/replace only after all in-scope work is complete and the user accepts closure, or when the user explicitly requests deletion/replacement.
- Package completion is not checkpoint/state promotion. Promotion remains H6 and requires separate explicit user approval.
- Source-validation HEAD and later docs/memory-only tracking HEAD must always be distinguished.

## 1. Locked user decisions

| Decision | Locked choice | Execution meaning |
| --- | --- | --- |
| Q1 | **A** | Optimize initial/core frontend bundle; lazy-load Monaco/Mermaid/heavy features. Never hide the issue only by increasing `chunkSizeWarningLimit`. |
| Q2 | **A** | Sandbox threat model includes a hostile local process; implement real handle/descriptor-bound I/O and Windows-equivalent TOCTOU defenses. Pathname-only revalidation is insufficient closure. |
| Q3 | **A** | v2.2 admin claim is **interactive local-user admin**, not cryptographic proof-of-human. Do not introduce WebAuthn/Windows Hello under this plan. |
| Q4 | **A** | Add minimal server-owned capability executable-binding/consistency validation; do not rewrite execution into a mega dispatcher. |
| Q5 | **A** | Inventory dependency findings first; remediate in small validated batches; add deterministic backend CI constraints; never run blind `npm audit fix`. |
| Q6 | **A** | Replace legacy real-smoke semantics with bounded native current-GYO acceptance on local Windows using existing Credential Manager configuration and synthetic Work; no new GitHub-hosted credential path by default. |
| Q7 | **A** | After technical gates are truthful/stable, move to PR-first default-branch governance requiring `pqg/smoke`, blocking force-push/delete, without making `pqg/preflight` a required merge status under current semantics. |
| Q8 | **A** | G-SYNTHETIC may remain scoped v2.2 synthetic evidence; never call it human usability evidence. |
| Q9 | **A** | Durable local cancellation + terminal state + late-output discard is the v2.2 acceptance boundary; remote provider compute/billing stop remains a documented limitation. |

### Authorization boundaries

The locked decisions plus the user's explicit instruction to execute authorize the bounded packages in this plan, including the selected sandbox/security, capability-binding, dependency/tool-version, current-GYO acceptance, and repository-governance packages.

Still not authorized under this plan:

- F9 Data Egress;
- arbitrary schema/migration refactor;
- Action Package semantic expansion beyond package D binding validation;
- deployment/public exposure;
- real user data;
- arbitrary provider/credential mutation;
- checkpoint/state promotion before H6 explicit approval.

## 2. Audit/source baseline before plan docs

- Audit/source HEAD: `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- Agent Preflight Run #10 / ID `32671953420`: **SUCCESS**, `pqg/preflight=success`.
- Smoke Test Run #106 / ID `32671953411`: **SUCCESS**, `pqg/smoke=success`.
- Backend: **516 passed / 81 skipped / 2 warnings**.
- Frontend in baseline Smoke: **4 focused files / 30 tests PASS** — not the full frontend suite.
- Lint: **0 warnings / 0 errors** over 144 files / 103 rules; type-check PASS; production build PASS.
- Runtime: migrations through `0038_durable_assistant_runs`, startup, health/runtime, 7 readiness checks and cleanup PASS.
- `smoke-real=SKIPPED` — never treat as PASS.
- Branch protection: OFF at baseline.
- State/checkpoint: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.
- F7: scoped implementation/validation PASS.
- F9: **CLOSED / NOT APPROVED**.

## 3. Global execution rules

### 3.1 Single-agent sequencing

Multi-agent execution remains paused. Execute packages sequentially in the locked order unless the user explicitly changes that decision.

### 3.2 Fresh exact-ref preflight before each implementation package

Before the first implementation write of every package:

1. re-fetch live target branch/ref;
2. run a **fresh Agent Preflight on the exact target ref**;
3. require workflow success and `pqg/preflight=success`;
4. read current state/checkpoint, `AGENTS.md`, `CODEGRAPH.md`, routing, operating contract, Project Memory/context, this master plan, and task-specific canon/security/source/tests;
5. explicitly state active package/gate, exact allowed scope, inspected files, expected files to change, validation plan, and forbidden/out-of-scope boundaries.

A successful `pqg/smoke` is not a substitute for Agent Preflight.

### 3.3 Evidence discipline

- NOT RUN = NOT RUN.
- SKIPPED = SKIPPED, never PASS.
- A job exiting 0 after real validation skipped is not real-provider PASS.
- Do not transplant source validation from one SHA onto a later docs-only SHA.
- Focused tests do not equal full acceptance.
- Local cancel transition does not prove upstream provider compute stopped.
- No checkpoint/state promotion before H6 explicit approval.
- F9 remains closed throughout this plan.

### 3.4 Per-package completion discipline

For every material package:

`fresh preflight → inspect → implement bounded scope → focused validation → proportionate/full regression → exact diff review → CI/current acceptance receipt → update this plan + execution ledger + Project Memory`.

Do not advance to the next package until the current package meets its acceptance criteria or is explicitly marked PARTIAL/BLOCKED with the blocker recorded.

## 4. Master status board

| Package | Scope | Priority | Status | Protected? | Completion evidence |
| --- | --- | --- | --- | --- | --- |
| A0 | CI/preflight topology repair | P0 | **COMPLETE** | CI/process | source `c6b7d1af…`; Preflight #11/#15; Smoke #115/#116/#117 |
| A1 | Full frontend regression in `pqg/smoke` + backend skip visibility | P0 | **COMPLETE** | CI/process | source `2c1b823…`; Preflight bootstrap `50e3bdb…`; Smoke #119 / `pqg/smoke=success`; frontend 50 files / 317 tests |
| A2 | Module/heavy-feature code splitting | P0 | **NOT STARTED** | No new security/schema/dependency | focused lazy/fail-closed tests + full frontend + bundle receipt + Smoke |
| B | Sandbox hostile-local-process TOCTOU hardening | P1 | **NOT STARTED** | **Security boundary** | Linux/POSIX + Windows hostile-swap suites + full backend + Smoke |
| C | Admin boundary contract reconciliation | P1 | **NOT STARTED** | Auth/security contract | current controls characterized; docs avoid proof-of-human claim |
| D | Capability executable-binding validator | P1 | **NOT STARTED** | **Capability/security boundary** | negative drift tests + full backend/startup/Smoke |
| E1 | npm vulnerability exact inventory | P2 | **NOT STARTED** | Dependency analysis | advisory/path/reachability matrix |
| E2 | Selective dependency remediation + backend reproducibility/warnings | P2 | **NOT STARTED** | **Dependencies/tool versions** | selective updates + deterministic constraints + full validation |
| E3 | GitHub Actions major upgrade + immutable SHA pins | P2 | **NOT STARTED** | **Tool/supply-chain** | pinned action SHAs + fresh Preflight/Smoke |
| E4 | Bounded native current-GYO acceptance | P1 evidence | **NOT STARTED** | **Provider/network/credential use** | local Windows native GYO receipt; no skip-as-success |
| F | Migration registry maintainability | P3 | **DEFERRED** | **Migration** | reopen only if separately justified |
| G | Branch protection / PR-first governance | P1 governance | **NOT STARTED** | **Repository governance** | live protection verification + required `pqg/smoke` behavior |
| H1 | Authoritative evidence normalization | P1 acceptance | **NOT STARTED** | Docs/evidence | source-SHA/evidence matrix |
| H2 | Final exact-head automated acceptance | P1 acceptance | **NOT STARTED** | Validation | full backend/frontend/lint/type/build/runtime/security + Smoke |
| H3 | Final current-source browser/UAT | P1 acceptance | **NOT STARTED** | Acceptance | primary-surface current-source receipt |
| H4 | Final current-GYO exact-source receipt | P1 acceptance | **BLOCKED BY E4** | Provider/network | bounded real-provider receipt on final source |
| H5 | Documentation/state evidence reconciliation | P1 acceptance | **NOT STARTED** | State docs; no promotion | current/superseded evidence reconciled |
| H6 | Checkpoint/state promotion decision | Final gate | **WAITING — USER APPROVAL REQUIRED** | **State promotion** | stop and request explicit approval |
| F9 | Data Egress | Future gate | **CLOSED / NOT APPROVED** | **Security/data egress** | separate future design gate only |

---

# Phase A — CI quality and frontend performance

## A0 — Repair preflight and active branch CI topology

### Goal

Make `.github/agent-preflight-trigger.txt` able to self-trigger Agent Preflight on task refs while preserving path scoping; clean Smoke active branch topology; preserve committed-diff validation.

### Implemented contract

- Agent Preflight push trigger retains path filters for `.github/workflows/agent-preflight.yml` and `.github/agent-preflight-trigger.txt`, with no historical branch allowlist.
- Smoke PR target remains `pqg-workspace`.
- Smoke push topology covers `pqg-workspace`, `work/**`, `security/**`, `maintenance/**`, and `integration/**`.
- Historical R1/remediation push refs were removed only after proving live `pqg-workspace` had advanced beyond both; no branches were deleted.
- New-branch push events with `before=000…` deepen the shallow checkout by one commit and run `git diff --check parent→HEAD`, preventing a false scan of historical snapshot whitespace while retaining committed-diff validation.

### Acceptance — COMPLETE

- Fresh pre-implementation exact-ref Agent Preflight: PASS.
- Representative task-ref trigger proved Agent Preflight runs and publishes exact-SHA `pqg/preflight=success`: PASS.
- Default-ref Smoke topology: PASS.
- Representative `work/**` branch-creation Smoke topology: PASS.
- Zero-SHA committed-diff validation path: PASS.
- Exact final source diff contains only intended workflow/process files: PASS.
- `smoke-real`: SKIPPED; not PASS evidence.
- Full frontend regression remains A1 and was not claimed by A0.

## A1 — Make `pqg/smoke` a truthful frontend regression gate

### Goal

Stop representing four focused frontend files / 30 tests as broad frontend validation and expose/classify backend skips.

### Intended changes

Primary workflow: `.github/workflows/smoke.yml`.

- replace the four-file Vitest invocation with the full `npm run test` suite;
- rename outdated `Validate R1 frontend` step to a current generic frontend regression name;
- retain lint, type-check, production build;
- run backend pytest with skip-reason visibility (`-ra` or equivalent).

### Backend skip inventory

Classify skips into:

- intentional legacy characterization;
- platform/environment-specific;
- real-provider protected acceptance;
- restore/destructive isolated acceptance;
- unknown/unexplained — investigate before final acceptance.

Do not automatically turn intentional skips into failures.

### Acceptance — COMPLETE

- Fresh pre-implementation A1 bootstrap HEAD `50e3bdb83054b3e27d6c20105bfc4e326ce2dd9e` had `pqg/preflight=success` (Run ID `32674453029`) before the implementation commit.
- A1 source-validation HEAD is `2c1b8238921bd0e99367802cfb29c5218ef87e6f`; exact implementation diff from the bootstrap HEAD changes only `.github/workflows/smoke.yml` (4 additions / 4 deletions).
- Smoke Test Run #119 / ID `32674524485` on exact source HEAD completed SUCCESS and published `pqg/smoke=success`.
- Backend command is `pytest -v -ra --tb=short`: 597 collected; **516 passed / 81 skipped / 2 warnings**. Skip reasons are visible: 80 are superseded Hermes/ACP characterization/runtime/UAT cases and 1 is the Windows-only restore-local-data environment case; no unexplained backend skip was observed in this run.
- Frontend command is the full `npm run test`: **50 test files / 317 tests PASS**. Lint is **0 warnings / 0 errors** over 144 files / 103 rules; type-check PASS; production build PASS.
- Migrations through 0038, backend startup, health/runtime checks, 7 readiness checks and cleanup PASS.
- `smoke-real` job is **SKIPPED** and remains explicitly separate from A1 PASS evidence.
- Known non-blocking residuals remain: two backend dependency/version warnings, React test `act(...)` stderr warnings, npm 6 vulnerabilities (3 moderate / 3 high), GitHub Actions Node/action-version warnings, and initial/eager frontend chunks above 500 kB. These belong to later packages and were not hidden or remediated in A1.

## A2 — Module/heavy-feature code splitting

### Goal

Reduce initial/core frontend bundle and load Monaco/Mermaid/other heavy features only when the authorized UI path needs them.

### Locked Q1 acceptance

- target initial/core bundle below 500 kB where practical;
- large lazy chunks may remain if they are not initial-load critical and are justified;
- measure the startup graph, not only Vite warning count;
- never solve only by increasing `chunkSizeWarningLimit`.

### Intended design and tests

Preserve eager Foundation/core surfaces where startup UX requires them. Lazy-load business/heavy surfaces as appropriate. Documents must not pull the Monaco/editor graph until Documents is actually authorized/rendered. Preserve fail-closed order:

`resolve definition → projection ready → attached/eligible → start lazy import → Suspense/error boundary → render`.

Focused tests must cover idle/loading/error, detached, attached load start, pending state, recoverable import failure, stale late import after module switch, Monaco non-load without scope, and existing fail-closed Foundation behavior.

### Bundle receipt / acceptance

Record before/after initial entry JS+gzip, largest eager chunk, largest lazy chunk, initial JS request count, proof Monaco is not startup content, and proof Mermaid remains on-demand. Require focused tests + full frontend + lint + type-check + build + bundle comparison + exact-head Smoke.

---

# Phase B — Sandbox hostile-local-process TOCTOU hardening

## Goal / threat model

A hostile local process is in scope. Close pathname check-then-use races with handle/descriptor-bound trusted filesystem operations; pathname-only revalidation is insufficient.

### Architecture target

Move security-relevant file operations behind a narrow sandbox API such as safe open/read/stat/hash/iterate/atomic-write helpers. POSIX should use directory-descriptor/relative-open semantics with no-follow/post-open identity checks. Windows must use handle-based semantics that validate reparse/junction/link identity at open/use time.

### Required caller audit

At minimum inspect/migrate:

- `backend/app/api/files.py`;
- `backend/app/mcp/tools.py`;
- artifact imports/managed-output publishing;
- DIRAP source extraction/read paths;
- workspace/local search paths;
- F7 context-broker artifact hydration.

### Test matrix / acceptance

Cover traversal, absolute/drive/UNC escape, symlink leaf/parent, Windows junction/reparse parent, hard-link leaf, parent/leaf swap after validation, approval-wait replacement, creation under swapped parent, atomic-write target swap, read/hash race, iteration/search swap, and post-authorization artifact swap.

Require relevant POSIX tests, Windows hostile-swap suite, existing sandbox/link/hard-link tests, full backend, F7 leakage regression, exact-head Smoke; no root widening/F9/schema/provider changes.

---

# Phase C — Admin boundary contract reconciliation

## Goal

Keep the current local-browser/CSRF/server-owned-actor boundary while making the claim truthful: **interactive local-user admin**, not cryptographic human-presence proof.

### Work / acceptance

Review admin dependency and constitutional admin routes; verify actor identity is server-derived; preserve fail-closed remote/cross-origin/missing-browser-context behavior; reconcile canon/risk/acceptance wording; document that a sufficiently privileged hostile local process is not distinguished from the local user by current HTTP-header checks.

Require existing/admin characterization tests. Do not introduce WebAuthn, biometrics, user DB/session redesign, or a new credential store.

---

# Phase D — Capability executable-binding consistency

## Goal

Prevent drift between CapabilityRegistry exposure metadata and actual MCP/Action-Package/read-inline implementation routes.

### Minimal server-owned binding contract

Associate capability ID, execution surface, authoritative handler key, and expected risk/execution invariants. Validate at startup/setup/tests that model-visible capabilities have exactly one valid binding; executable bindings have registry entries; compatibility names cannot bypass registration; Action Package IDs preserve current AP semantics; read-only/action-package modes cannot bind to incompatible handlers; admin-risk IDs have no model executable binding; duplicate/orphan bindings fail closed; handlers cannot override server-owned risk/execution/replay metadata.

### Forbidden / acceptance

No new model-visible admin capability, no AP approval/idempotency semantic change, no F9/network capability, no provider credential administration through the model.

Require focused negative drift tests + existing registry/MCP/AP tests + full backend + startup + exact-head Smoke.

---

# Phase E — Dependency, supply chain, and current-GYO acceptance

## E1 — npm vulnerability exact inventory

Run/read exact `npm audit --json` findings and record advisory/package, severity, direct/transitive path, runtime/dev-only status, affected/fixed range, established PQG exploitability, owning top-level dependency and remediation semver/behavioral risk. `npm audit fix` blanket remediation is forbidden. Commit an actionable matrix before E2.

## E2 — Selective dependency remediation + backend reproducibility/warnings

- patch/minor updates first where sufficient; major only when required;
- validate each small group;
- establish deterministic backend CI dependency constraints while retaining `pyproject.toml` as compatibility/declaration intent;
- investigate Pydantic Settings forward-reference warning and Starlette TestClient/httpx warning with a minimal repro/version matrix before app-code changes.

Acceptance: advisory-targeted updates only; deterministic clean install; full backend/frontend; lint/type/build; runtime/migrations; exact-head Smoke; document accepted residual advisories/warnings.

## E3 — GitHub Actions upgrade and immutable pinning

For each active official action: resolve appropriate current major at implementation time, verify runner compatibility, validate upgrade, pin immutable commit SHA, and retain human-readable release/major comment. Resolve SHAs fresh; do not copy stale pins from this plan.

Acceptance: fresh Agent Preflight + Smoke on pinned actions and no avoidable Node20-target deprecation warning.

## E4 — Retire legacy real-smoke; bounded native current-GYO acceptance

Replace legacy Hermes/ACP active acceptance semantics with bounded local Windows native GYO acceptance using existing Credential Manager configuration and synthetic Work.

Contract: isolated temp SQLite/workspace, synthetic context only, approved/current provider/model profile, bounded request/cost count, no real user data, no credential leakage, redacted provenance receipt, no fallback after first token, cleanup receipt, explicit PASS/FAIL/NOT RUN-SKIPPED. Never green-by-skip.

Retire/remove misleading legacy Hermes/ACP active acceptance while preserving Git history. This package is not F9 authorization.

---

# Phase F — Migration maintainability

## Status: DEFERRED

Migration 0037/0038 and registry compatibility debt are not a demonstrated blocker. Reopen only for a real new migration, demonstrated correctness/maintainability failure, or explicit user instruction. Reopened migration work requires fresh scope review because schema/migration remains protected.

---

# Phase G — Repository governance / branch protection

## Dependency / locked model

Do not enable final protection until at least A0, A1 and E3 are complete and `pqg/smoke` is stable on intended topology.

Then protect `pqg-workspace`; require `pqg/smoke`; disallow force-push/delete; do not require `pqg/preflight` as merge status under current semantics; document any practical single-user emergency/admin bypass GitHub requires.

Acceptance requires live branch-rule verification and a representative PR showing missing/failing `pqg/smoke` blocks merge and passing required check permits it. Do not delete historical branches.

---

# Phase H — Final evidence, UAT, and state reconciliation

## H1 — Authoritative evidence normalization

Create/update an authoritative matrix with feature/gate, exact source SHA, receipt/run/artifact ID, PASS/PARTIAL/NOT RUN/SKIPPED, what it proves/does not prove, superseded evidence and current applicability. Normalize current-GYO stream/context/source/cancel, AP/executor evidence, F1 cancellation, F3 fidelity, G-SYNTHETIC, R1 durable runs, F7 broker, B/C/D remediation and dependency/supply-chain acceptance. Preserve historical evidence as superseded rather than deleting it.

## H2 — Final exact-head automated acceptance

On final source: fresh exact-head Agent Preflight; complete backend with skip reasons reviewed; full frontend; lint; type-check; production build + bundle receipt; migration/startup; health/runtime/readiness/cleanup; sandbox/security including Windows evidence; capability-binding regressions; final committed-diff review; `pqg/smoke=success`. Anything unrun remains NOT RUN.

## H3 — Final current-source browser/UAT

Revalidate Home/Overview, Work selection/Hub, GYO panel, Documents/editor loading, Knowledge/Review, Memory Hub, Settings, module attached/detached/projection loading/error behavior, offline/recovery, 409 conflict, approval staging, keyboard/focus, reduced motion and reflow/native zoom as appropriate. Use isolated synthetic data. Never claim an unexecuted screen×state×viewport cross-product.

## H4 — Final current-GYO exact-source receipt

After E4, run bounded native current-GYO acceptance against the final source revision. Do not use old Hermes/ACP evidence as current native GYO proof.

## H5 — Documentation/state evidence reconciliation

Reconcile state/risk/checkpoint/acceptance docs, Project Context and this tracker without silently rewriting history. Q8 remains synthetic-not-human-evidence; Q9 remains local-cancel boundary with remote provider stop unproven.

## H6 — Final promotion decision

Produce final gate report with exact source HEAD, closed findings, accepted residuals, NOT RUN/SKIPPED, out-of-scope items, F9 status and `READY FOR PROMOTION = YES/NO`. Then **STOP** and request explicit user approval before modifying project state/checkpoint.

---

# F9 — Data Egress remains closed

F9 is not part of this execution plan. No package authorizes Work/user-data web-search queries, new connector sends, upload/export, external destination allowlists, or broad new provider egress. Any future F9 gate must separately cover classification → destination allowlist → minimization/redaction → per-egress authorization → audit → deny-by-default.

---

# 5. Locked execution order

```text
A0 → A1 → A2 → B → C → D → E1 → E2 → E3 → E4 → G → H1 → H2 → H3 → H4 → H5 → H6
```

`F` remains deferred unless separately justified. `F9` remains closed.

## 6. Per-package completion template

```text
### [timestamp] Package <ID> — <title>
Status: COMPLETE / PARTIAL / BLOCKED / SUPERSEDED
Preflight exact HEAD/run:
Source-validation HEAD:
Changed files:
Focused tests:
Full regression:
Smoke/preflight statuses:
Platform-specific evidence:
Known residuals:
NOT RUN/SKIPPED:
Scope not changed:
Next package:
```

A package is not COMPLETE merely because source was edited; package acceptance evidence must be satisfied.

## 7. Execution ledger

### [2026-08-24 06:09:16 UTC+07:00] Master plan initialized

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Status: **ACTIVE**.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] User locked `Q1=A · Q2=A · Q3=A · Q4=A · Q5=A · Q6=A · Q7=A · Q8=A · Q9=A`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Audit/source baseline: `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Baseline Agent Preflight Run #10 / ID `32671953420` SUCCESS, `pqg/preflight=success`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Baseline Smoke Run #106 / ID `32671953411` SUCCESS, `pqg/smoke=success`; backend 516 passed / 81 skipped / 2 warnings; frontend focused 30/30; lint/type/build/runtime/readiness/cleanup PASS; `smoke-real=SKIPPED`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Multi-agent paused; execution begins at A0; F9 CLOSED / NOT APPROVED.

### [2026-08-24 06:39:02 UTC+07:00] Package A0 — Repair preflight and active branch CI topology

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Status: **COMPLETE**.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Handoff HEAD `e84cb0a030f6be54ab9f341b6065f562e301f7b0` was re-fetched live at session start and had no drift before A0 execution.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Fresh pre-implementation exact-ref bootstrap HEAD `65b36ebe8342b5f7d3ddcdb478db9bab7be44f12`; Agent Preflight Run #11 / ID `32673592829` completed SUCCESS and published `pqg/preflight=success`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 source-validation HEAD is `c6b7d1afab3f066a4aa7f99639104441db1d69fa`; this source receipt must remain distinct from later docs/memory-only tracking commits.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Source changes from the fresh-preflight HEAD to A0 source-validation HEAD are only `.github/workflows/agent-preflight.yml` and `.github/workflows/smoke.yml`; exact compare is ahead 4 / behind 0.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] `agent-preflight.yml` now keeps path-scoped triggering but no historical branch allowlist, allowing `.github/agent-preflight-trigger.txt` to self-trigger on representative task refs.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Smoke push topology now covers `pqg-workspace`, `work/**`, `security/**`, `maintenance/**`, `integration/**`; obsolete historical foundation/remediation push refs were removed after proving `pqg-workspace` was ahead of each. No branch was deleted.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Initial zero-SHA task-branch proof exposed a committed-diff bug: shallow checkout could not resolve parent and historical snapshot whitespace caused failure. This failure is preserved as evidence; it was not mislabeled PASS.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Final zero-SHA handling deepens the task branch by one commit, resolves `HEAD^`, and runs `git diff --check parent→HEAD`, preserving committed-diff validation without scanning unrelated historical whitespace.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Default-source Smoke Run #115 / ID `32673879015` on exact source HEAD `c6b7d1afab3f066a4aa7f99639104441db1d69fa` completed SUCCESS; all normal smoke steps passed and `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Representative zero-SHA branch-creation Smoke Run #116 / ID `32673886997` on `work/a0-verified-topology-proof-20260824` at source HEAD `c6b7d1af…` completed SUCCESS, `Validate committed diff formatting` passed and `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Final task-trigger proof commit `a4fbaacad3fa46be32a6d38a053dd59995ac5c3a` produced Agent Preflight Run #15 / ID `32673916000` SUCCESS with exact-SHA `pqg/preflight=success` and Smoke Run #117 / ID `32673916078` SUCCESS; `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 does not prove full frontend regression: the active Smoke semantics during A0 still ran the pre-A1 focused frontend set. Full frontend regression + backend skip visibility remains A1.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] No application/runtime, schema/migration, dependency/action-major, branch-protection, auth/security semantic, provider/credential, deployment, F9, or checkpoint/state change occurred in A0.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED. Next package is **A1** after this tracking/memory persistence is verified.

### [2026-08-24 07:20:44 UTC+07:00] Package A1 — Full frontend regression + backend skip visibility

- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Status: **COMPLETE**.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Session-start drift reconciliation found live `pqg-workspace` at `2c1b8238921bd0e99367802cfb29c5218ef87e6f`, 12 commits ahead of handoff `e84cb0a030f6be54ab9f341b6065f562e301f7b0`; the drift contained completed A0 tracking plus the A1 bootstrap and implementation rather than unrelated divergence.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Fresh A1 pre-implementation bootstrap HEAD `50e3bdb83054b3e27d6c20105bfc4e326ce2dd9e` had `pqg/preflight=success` from Run ID `32674453029`; `pqg/smoke` also succeeded on that bootstrap HEAD.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 source-validation HEAD is `2c1b8238921bd0e99367802cfb29c5218ef87e6f`; exact compare from bootstrap HEAD is ahead 1 / behind 0 and changes only `.github/workflows/smoke.yml` (4 additions / 4 deletions).
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Smoke Test Run #119 / ID `32674524485` on exact A1 source completed SUCCESS and published exact-SHA `pqg/smoke=success`; normal `smoke` job passed, while `smoke-real` was **SKIPPED**.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Backend A1 evidence: `pytest -v -ra --tb=short`, 597 collected, **516 passed / 81 skipped / 2 warnings**. Visible skip summary accounts for 80 superseded Hermes/ACP characterization/runtime/UAT cases and 1 Windows restore-local-data environment case; no unexplained backend skip was observed.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Frontend A1 evidence: full `npm run test` = **50 files / 317 tests PASS**; lint = **0 warnings / 0 errors** over 144 files / 103 rules; type-check PASS; production build PASS.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Runtime A1 evidence: migrations through `0038_durable_assistant_runs`, startup, health/runtime, 7 readiness checks and cleanup all PASS.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Residuals were preserved, not hidden: two backend dependency/version warnings; React `act(...)` test stderr warnings; npm reports 6 vulnerabilities (3 moderate / 3 high); GitHub Actions Node/action-version warnings; Vite build still reports eager/initial chunks `chunk-KEIR6QF5…` 662.65 kB and `index-BcNgI1tV.js` 667.45 kB. Bundle remediation remains A2.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 made no application/runtime behavior, schema/migration, dependency/tool-version, branch-protection, auth/security semantic, provider/credential, F9, deployment or checkpoint/state change.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED. Next package is **A2 — Module/heavy-feature code splitting** after A1 tracking/memory persistence and a fresh exact-ref A2 Agent Preflight.
