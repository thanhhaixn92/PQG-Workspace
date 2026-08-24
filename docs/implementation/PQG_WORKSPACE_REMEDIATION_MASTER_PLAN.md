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

### 3.1 Sequential writes; bounded parallel review

Package writes, integration and final validation remain sequential under one
owner. Independent read-only research, review and test lanes may run in
parallel when their scopes do not overlap; no parallel agent may change shared
state or the same implementation flow.

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
| A2 | Module/heavy-feature code splitting | P0 | **COMPLETE** | No new security/schema/dependency | source `5fce3270…`; Preflight #17; Smoke #126; eager 486,620 bytes; Monaco/Mermaid outside initial graph |
| B | Sandbox hostile-local-process TOCTOU hardening | P1 | **COMPLETE** | **Security boundary** | source `140df75…`; preflight/sandbox-windows/Smoke success; backend + F7 + route-contract regression |
| C | Admin boundary contract reconciliation | P1 | **COMPLETE** | Auth/security contract | source `fe2ad41…`; Preflight/Smoke success; focused admin/capability/UI proof |
| D | Capability executable-binding validator | P1 | **COMPLETE** | **Capability/security boundary** | source `36b2fef…`; negative drift + backend/startup/Preflight/Smoke success |
| E1 | npm vulnerability exact inventory | P2 | **COMPLETE** | Dependency analysis | exact 6-node / 32-advisory inventory + four proposed E2 batches |
| E2 | Selective dependency remediation | P2 | **IN PROGRESS — E2-A COMPLETE** | **Dependencies/tool versions** | E2-A source `dc1a462…`; remaining fault domains are separately gated below |
| P-TRACK | Bounded tracking-equivalence CI | P1 process | **COMPLETE** | CI/process | source `2ac0e831…` full receipt; T1 `42b16fcb…` tracking receipt |
| P-MEM | Project Memory/Context normalization | P2 docs | **PARTIAL — full-recovery candidate** | Docs/evidence | T2 failed closed on shallow ancestry; recovery requires exact full Smoke |
| E2-B | Monaco bundled DOMPurify | P1 security | **NOT STARTED — upstream-aware** | Dependency/security evidence | fresh artifact discovery; fixed upstream release or explicit BLOCKED-UPSTREAM |
| E2-C | Vite/PostCSS/Nanoid dev toolchain | P2 | **NOT STARTED** | Dependencies/tool versions | targeted same-major resolution + frontend/full Smoke |
| E2-D | jsdom/Undici test chain | P2 | **NOT STARTED** | Dependencies/tool versions | targeted Undici resolution without default jsdom-major upgrade |
| E2-E | Backend deterministic constraints + warning closure | P2 | **NOT STARTED** | Dependency/test environment | clean Linux/Windows install, `pip check`, warning disposition |
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

### Acceptance — COMPLETE

- Fresh exact-ref A2 preflight: trigger commit `f7750190c3c1744f259fb9ef0b25d9c34ab07eda`; Agent Preflight Run #17 / ID `32676695105` completed SUCCESS and published `pqg/preflight=success`.
- Final source-validation HEAD: `5fce3270f26f1cac1ffb9d228c63576a47870bc0`.
- Failed intermediate validation remained fail-closed and is preserved: `3a035ee7…` / Smoke #123 failed reporter source binding and eager threshold; `ea874f56…` / Smoke #124 reduced eager size below threshold but reporter binding failed; `388cd713…` / Smoke #125 failed because the EditorPanel record was not a verified dynamic manifest entry.
- Final Smoke Run #126 / ID `32680074013` on exact source HEAD completed SUCCESS and published `pqg/smoke=success`; `smoke-real=SKIPPED` and is not A2 PASS evidence.
- Backend final regression: 597 collected; **516 passed / 81 skipped / 2 warnings**.
- Frontend final regression: **50 files / 321 tests PASS**; ModuleCanvas focused 11 PASS; SettingsPanel 7 PASS; EditorPanel 8 PASS; lint **0 warnings / 0 errors** over 147 files / 103 rules; type-check PASS; production build PASS.
- Runtime/migrations/startup/health/runtime status/seven readiness checks/cleanup PASS.
- Final bundle receipt: entry `assets/index-DQn4IEj6.js` = **486,620 bytes / 144,605 gzip bytes**; initial static graph = **5 JS requests / 497,075 bytes / 149,128 gzip bytes**; largest eager = **486,620 bytes**; largest lazy `assets/chunk-KEIR6QF5-DNzq6p3w.js` = **662,650 bytes / 142,278 gzip bytes**.
- Monaco proof: runtime source import isolated to `src/components/EditorPanel.tsx`; dynamic facade `src/foundation/shell/EditorSurface.tsx`; `monacoInInitialGraph=false`; EditorPanel chunk is downstream of EditorSurface and outside the initial graph.
- Mermaid proof: `src/components/MermaidDiagram.tsx` is a dynamic manifest entry with `mermaidInInitialGraph=false`.
- `chunkSizeWarningLimit` remained unchanged at `500 * 1024 = 512,000`; the remaining generic Vite >500 kB warning belongs to a non-startup lazy chunk and is an explicit residual rather than hidden.
- A2 changed no dependency/tool version, schema/migration, auth/security/provider/F9/deployment/state/checkpoint scope.

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

### Acceptance — COMPLETE

- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Source-validation HEAD is `140df75e907444437844a1328455e6d1c23c7e51`; it is distinct from the later docs/memory-only tracking child.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact-source Agent Preflight Run `32699303000` / job `97347423658`, Sandbox Windows Run `32699302690` / job `97347419706`, and Smoke Run `32699302749` / job `97347420230` all completed SUCCESS and published their matching exact-SHA status contexts.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] The FastAPI 0.141 lazy included-router regression was fixed without changing secure endpoint identity: inspection follows the original public contract while execution remains bound to the secure callable.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Windows nested atomic writes were restored by removing unnecessary `DELETE` access from traversed parent-directory handles; HANDLE-relative rename, reparse rejection, hard-link rejection, hostile-swap checks and object-identity assertions remain enforced.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Local direct regression 7 PASS; eight historical suites 112 PASS / 1 environment SKIP / 2 warnings; local Package B sandbox 12 PASS / 2 warnings; local full backend 527 PASS / 82 SKIP / 2 warnings.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Canonical Windows sandbox is 12 PASS / 2 warnings. Canonical Smoke is backend 528 PASS / 81 SKIP / 2 warnings, frontend 50 files / 321 tests PASS, lint 0/0, type-check/build/startup/health/runtime/seven readiness checks/cleanup PASS; `smoke-real=SKIPPED`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] No root widening, dependency/tool, schema/migration, auth/approval, provider/credential, Action Package, F9, deployment, checkpoint or state change occurred.

---

# Phase C — Admin boundary contract reconciliation

## Goal

Keep the current local-browser/CSRF/server-owned-actor boundary while making the claim truthful: **interactive local-user admin**, not cryptographic human-presence proof.

### Work / acceptance

Review admin dependency and constitutional admin routes; verify actor identity is server-derived; preserve fail-closed remote/cross-origin/missing-browser-context behavior; reconcile canon/risk/acceptance wording; document that a sufficiently privileged hostile local process is not distinguished from the local user by current HTTP-header checks.

Require existing/admin characterization tests. Do not introduce WebAuthn, biometrics, user DB/session redesign, or a new credential store.

### Acceptance — COMPLETE

- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Source-validation HEAD `fe2ad41052fc4cde3ae49543fd9978d12a692d4c` reconciles the claim to interactive local-user administration and explicitly records that loopback/Origin/Fetch Metadata are not cryptographic proof of human presence.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Constitutional Module attach/detach/rename/reorder routes retain loopback, approved-Origin, Fetch Metadata, server-owned actor, revision and audit controls; new tests prove remote-client and valid-Origin/cross-site denial.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Model-visible admin-risk capabilities remain absent; the negative inventory covers Foundation/provider/Module/privacy/permission/restore/delete/admin-Skill classes and verifies `capability_not_found` without creating an approval request.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Local focused evidence: backend 48 PASS / 1 existing warning; frontend Modules Settings 6 PASS. Local full backend: 537 PASS / 82 platform/legacy SKIP / 2 existing warnings. Full frontend: 50 files / 322 tests PASS; lint, type-check and production build PASS; `git diff --check` PASS.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Exact-source Agent Preflight Run `32701981820` / job `97355230052` completed SUCCESS and published `pqg/preflight=success`.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Exact-source Smoke Run `32701968596` / job `97355187719` completed SUCCESS and published `pqg/smoke=success`: backend 538 PASS / 81 SKIP / 2 warnings; frontend 50 files / 322 tests; lint 0 warnings / 0 errors; type-check/build/startup/health/runtime/seven readiness checks/cleanup PASS. `smoke-real` job `97355188770` was SKIPPED, not PASS.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] No schema/migration, provider/credential, dependency/tool, Action Package semantic, executable-binding D, F9, deployment, checkpoint or state change occurred.

---

# Phase D — Capability executable-binding consistency

## Goal

Prevent drift between CapabilityRegistry exposure metadata and actual MCP/Action-Package/read-inline implementation routes.

### Minimal server-owned binding contract

Associate capability ID, execution surface, authoritative handler key, and expected risk/execution invariants. Validate at startup/setup/tests that model-visible capabilities have exactly one valid binding; executable bindings have registry entries; compatibility names cannot bypass registration; Action Package IDs preserve current AP semantics; read-only/action-package modes cannot bind to incompatible handlers; admin-risk IDs have no model executable binding; duplicate/orphan bindings fail closed; handlers cannot override server-owned risk/execution/replay metadata.

### Forbidden / acceptance

No new model-visible admin capability, no AP approval/idempotency semantic change, no F9/network capability, no provider credential administration through the model.

Require focused negative drift tests + existing registry/MCP/AP tests + full backend + startup + exact-head Smoke.

### Completed evidence

- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Package D is **COMPLETE** at source-validation HEAD `36b2fef6817dff9b97e15ee58d1004ab9a067ce6`; the following plan/memory update is a distinct tracking-only child.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] The server-owned immutable binding table now associates all 11 model-visible capabilities with exactly one execution surface, route key, authoritative Python handler key and expected risk/execution/replay metadata. FastAPI startup validates the post-hardening MCP callable inventory and the existing two-entry Action Package handler inventory fail closed.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Action Package dispatch was factored into an immutable map for the existing `work_plan_step_update` and `work_status_update` handlers without changing payload, approval, revision, idempotency, execution budget or mutation semantics.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Local evidence: capability/binding 41 PASS; existing MCP + Action Package 27 PASS; full backend 547 PASS / 82 explicit SKIP / 2 warnings; compile, fresh temporary-DB migrations/startup/health and `git diff --check` PASS.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Exact-source Agent Preflight Run `32704348381` / job `97362194625`, Sandbox Windows Run `32704336190` / job `97362155343`, and Smoke Run `32704336226` / job `97362155302` all completed SUCCESS and published `pqg/preflight`, `pqg/sandbox-windows`, and `pqg/smoke` success. Smoke recorded backend 548 PASS / 81 SKIP / 2 warnings, frontend 50 files / 322 tests, lint 0 warnings / 0 errors, type-check/build/startup/health/runtime/seven readiness checks/cleanup PASS; `smoke-real` job `97362155978` was SKIPPED.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] No E/G/H/F/F9, schema/migration, dependency/tool, provider/credential, deployment or checkpoint/state scope was opened.

---

# Phase E — Dependency, supply chain, and current-GYO acceptance

## E1 — npm vulnerability exact inventory

Run/read exact `npm audit --json` findings and record advisory/package, severity, direct/transitive path, runtime/dev-only status, affected/fixed range, established PQG exploitability, owning top-level dependency and remediation semver/behavioral risk. `npm audit fix` blanket remediation is forbidden. Commit an actionable matrix before E2.

Completed inventory: `docs/implementation/PACKAGE_E1_NPM_VULNERABILITY_INVENTORY.md`.

- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Root npm project is clean. Frontend full audit reports six vulnerable package nodes (`3 moderate / 3 high`) aggregating 32 advisory records; `--omit=dev` leaves three moderate runtime nodes and zero high nodes.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Runtime inventory is Mermaid `11.16.0` + DOMPurify `3.4.11` with established untrusted-diagram reachability, and Monaco `0.55.1` + DOMPurify `3.2.7` with conditional internal-sanitizer reachability. Dev-only inventory is PostCSS `8.5.16`, Nanoid `3.3.15` and Undici `7.28.0` through Vite/jsdom.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Proposed E2 batches are separated into reachable Mermaid runtime, compatibility-sensitive Monaco/DOMPurify, Vite/PostCSS/Nanoid dev toolchain and jsdom/Undici test-chain remediation. None was executed in E1.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Both package-lock SHA-256 values remained unchanged; no package, dependency/tool version, lockfile, schema, provider, credential, F9, deployment, checkpoint or state mutation occurred.

## E2 — Selective dependency remediation + backend reproducibility/warnings

- patch/minor updates first where sufficient; major only when required;
- validate each small group;
- establish deterministic backend CI dependency constraints while retaining `pyproject.toml` as compatibility/declaration intent;
- investigate Pydantic Settings forward-reference warning and Starlette TestClient/httpx warning with a minimal repro/version matrix before app-code changes.

Acceptance: advisory-targeted updates only; deterministic clean install; full backend/frontend; lint/type/build; runtime/migrations; exact-head Smoke; document accepted residual advisories/warnings.

### E2-A — Mermaid/runtime DOMPurify remediation

- [2026-08-24 16:15:15 UTC+07:00][recorded_at] **COMPLETE** at source-validation HEAD `dc1a46280a006c2214a301557284fbbbd476ed27`. Mermaid is pinned from `^11.16.0` to exact `11.16.1`; only its nested DOMPurify resolution changed, from `3.4.11` to `3.4.14`.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Deterministic dependency and runtime regressions lock the approved floors, preserve Monaco's separately gated `dompurify@3.2.7` branch, parse bounded flowchart/XY/radar/architecture inputs under `securityLevel: strict`, and reject malformed input.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Live audit moved from six to five vulnerable nodes: full `2 moderate / 3 high`; production `2 moderate / 0 high`. Mermaid and Mermaid-owned DOMPurify are absent from the remaining findings. Remaining nodes are exactly Monaco/DOMPurify (E2-B), PostCSS/Nanoid (E2-C), and Undici (E2-D).
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Focused 19 PASS; full frontend 52 files / 330 tests, lint, type-check and build PASS. A2 bundle receipt remains fail-closed and confirms `mermaidIsDynamicEntry=true`, `mermaidInInitialGraph=false`.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Exact-source Agent Preflight `32710121468` / `97379518811` and Smoke `32710112957` / `97379488765` SUCCESS. Smoke backend 548 PASS / 81 SKIP / 2 existing warnings; frontend 52 files / 330 tests; runtime/readiness/cleanup PASS; `smoke-real` `97379490095` SKIPPED.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] E2 overall remains **IN PROGRESS**. E2-B/C/D/E and backend reproducibility/warning remediation were neither authorized nor executed; no `npm audit fix`, schema/migration, provider/credential, E3/E4/G/H/F/F9, deployment or state/checkpoint change occurred.

## P-TRACK — Fail-closed tracking equivalence gate

**Status: COMPLETE.**

P-TRACK may optimize only the normal Smoke decision path. It keeps every
existing trigger active and defaults to full validation. Pull requests remain
full; PR topology is not solved by this package. A tracking candidate must be a
single direct-child push to `pqg-workspace` that modifies only existing files
in the exact tracking allowlist. New-branch and multi-commit pushes,
rename/delete/add operations, classifier uncertainty and every path outside the
allowlist remain full Smoke.

Tracking ancestry is non-recursive and bounded to at most two consecutive
tracking commits: `S(full) -> T1(P-TRACK completion) -> T2(P-MEM)`. T1 verifies
the dedicated `pqg/smoke-full` receipt and completed Actions run on S. T1 also
carries the short `PROJECT_CONTEXT.md` aggregate/full/tracking invariant as a
completion candidate; that wording becomes durable only when exact T1 itself
passes `pqg/tracking-integrity` and `pqg/smoke`, without a T1.5 receipt commit. T2
verifies both the `pqg/tracking-integrity` run on T1 and the full run on S; the
cumulative first-parent diff `S..T2` must still contain only modifications to
allowlisted existing files. A third consecutive tracking commit or any later
source/runtime commit resets to full validation.

Status fields alone are insufficient provenance. The run ID extracted from the
canonical status target URL must resolve through the Actions API to this exact
repository, validation SHA and `.github/workflows/smoke.yml`, with a completed
successful run and the exact expected `smoke-full`, `tracking-integrity` and
`smoke-result` job conclusions. The final `always()` aggregator publishes
`pqg/smoke` only when exactly one expected current path succeeds and the other
is skipped; every other combination fails closed. A P-TRACK completion
candidate is COMPLETE only when its exact HEAD itself has successful
`pqg/tracking-integrity` and `pqg/smoke`; no extra receipt commit is required.

Acceptance requires focused classifier/receipt negative tests, workflow syntax
validation, `git diff --check`, scope review and an exact-source full Smoke on
the workflow/script change. The following allowlisted tracking child must then
prove the tracking path without relabeling runtime tests as executed on that
child. Until both live receipts exist, P-TRACK remains PARTIAL / NOT PROVEN.
External-fork PR compatibility is not yet evidenced: PRs remain full, but a
fork token can lack permission for custom commit-status publication. Treat that
case as NOT RUN and resolve it only if the repository's contributor topology
requires it; do not weaken the canonical internal PR/full-path gate.

P-TRACK excludes parallel jobs, Node/action upgrades, dependency caching,
concurrency, product/runtime behavior, Project Memory normalization, state and
checkpoint changes. Its SOURCE may append only minimal receipt/provenance facts
to `PROJECT_MEMORY.md` and `PROJECT_CHANGELOG.md`; full normalization remains
P-MEM. Package G must later reconcile the accepted P-TRACK model with PR-first
integration topology; that residual is recorded, not solved here.

## P-MEM — Project Memory normalization

**Status: PARTIAL — T2 FAILED CLOSED; FULL-RECOVERY CANDIDATE.**

P-MEM must not be folded into P-TRACK. It will define one canonical home per
fact while preserving historical receipts in the changelog and Git history.
Its exact rewrite/retention scope requires a fresh preflight and focused review
after P-TRACK acceptance and before E2-B begins. `PROJECT_CONTEXT.md` retains
only durable authority, architecture, security, state-promotion and CI evidence
semantics; `PROJECT_MEMORY.md` becomes a current snapshot; and
`PROJECT_CHANGELOG.md` remains append-only owner of historical receipts. The
historical `REMEDIATION_MASTER_PLAN_CONTEXT.md` is not deleted, but P-MEM must
mark it superseded for current continuity and point to these three live files.

## E2-B — Monaco bundled DOMPurify

**Status: NOT STARTED — DISCOVERY-FIRST / UPSTREAM-AWARE.**

At execution, re-resolve the Monaco release and inspect the installed shipped
artifact, not only the consumer lock graph. The current upstream issue reports
that `monaco-editor@0.56.0` bundles DOMPurify `3.4.8` into shipped artifacts,
so a consumer npm override alone does not prove remediation. If a compatible
upstream release fixes the bundle, make the smallest upgrade and prove editor
lazy-load, edit/save, markdown/hover sanitization, malformed/error recovery,
A2 bundle invariants, audit and full frontend/Smoke. If not, mark
**BLOCKED-UPSTREAM** with practical conditional reachability and retained
internal-sanitizer boundary; vendor patching requires separate user approval.

## E2-C — Vite/PostCSS/Nanoid dev toolchain

**Status: NOT STARTED.**

Resolve the current compatible Vite 8.x patch only at execution, with
PostCSS `>=8.5.23` and Nanoid `>=3.3.18`. Require a clean install, `npm ls vite
postcss nanoid`, audit, full frontend test/lint/type-check/build, unchanged
Mermaid/Monaco lazy boundaries and A2 bundle receipt. Do not use `npm audit
fix`, raise `chunkSizeWarningLimit`, or broaden the dependency update.

## E2-D — jsdom/Undici test chain

**Status: NOT STARTED.**

Prefer the smallest compatible Undici `>=7.29.0` resolution within the existing
jsdom 29 line; do not default to a jsdom major upgrade merely to clear the
advisory. Acceptance requires `npm ls jsdom undici`, audit, the full frontend
suite with async/race-sensitive coverage, lint/type-check/build and exact-source
Smoke.

## E2-E — Backend deterministic constraints and warning closure

**Status: NOT STARTED.**

First select and validate one canonical CI resolution authority: the committed
`uv.lock` with its matching installer, or generated `backend/constraints-ci.txt`
for pip. Do not introduce constraints while leaving `uv.lock` independently
authoritative. If pip constraints are selected, generate them only from a clean
validated Python 3.11 environment; `pyproject.toml` remains compatibility/
declaration intent, and Smoke and Sandbox Windows install with `python -m pip
install -c constraints-ci.txt -e ".[dev]"` followed by `python -m pip check`.
Preserve valid platform markers rather than forcing one wheel graph across Linux
and Windows.

Investigate warnings with a minimal version/reproduction matrix before changing
app code: retain the PQG Settings model unchanged for the MCP FastMCP
`lifespan` upstream issue; do not use a PQG `model_rebuild()` workaround, MCP
v2 migration, or silent suppression. Inventory the broad actual TestClient
surface before proposing `httpx2`; add it only if a clean reproduction and
compatibility regression prove it appropriate. Runtime `httpx` remains for
GYO/provider traffic. Acceptance is deterministic clean Linux and Windows
installation, `pip check`, full backend and runtime/startup, with each warning
either closed or explicitly recorded as upstream residual.

## E3 — GitHub Actions upgrade and immutable pinning

For each active official action: resolve appropriate current major at implementation time, verify runner compatibility and known regressions, validate upgrade, pin immutable commit SHA, and retain a human-readable release/major comment. Resolve SHAs fresh; do not copy stale pins from this plan. Add an explicit project-compatible Node environment and npm download cache while retaining `npm ci`; do not cache `node_modules`, parallelize Smoke, or add cancellation concurrency without later measured bottleneck evidence.

Acceptance: fresh Agent Preflight + Smoke on pinned actions and no avoidable Node20-target deprecation warning.

## E4 — Retire legacy real-smoke; bounded native current-GYO acceptance

Replace legacy Hermes/ACP active acceptance semantics with bounded local Windows native GYO acceptance using existing Credential Manager configuration and synthetic Work. Retire the active legacy `smoke-real` semantic so credential-unavailable/skip can never appear as a green real-provider acceptance result. The normal provider-independent CI may retain public historical runtime/readiness keys where compatibility requires them; changing those API/test contracts is a separately reviewed E4 decision, not an implicit job deletion.

Contract: isolated temp SQLite/workspace, synthetic context only, approved/current provider/model profile, bounded request/cost count, no real user data, no credential leakage, redacted provenance receipt, no fallback after first token, stream/context/source/cancel/late-output-discard at API/durable-run layer and cleanup receipts, explicit PASS/FAIL/NOT RUN-SKIPPED. Never green-by-skip. A real provider-generated Action Proposal is NOT RUN if absent; automated Action Package/executor evidence remains separately evaluated. Provider credential use/network request is protected: obtain fresh explicit authorization at E4 and never print, copy or mutate a credential.

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

Create/update an authoritative matrix with feature/gate, exact source SHA, receipt/run/artifact ID, PASS/PARTIAL/NOT RUN/SKIPPED, what it proves/does not prove, superseded evidence and current applicability. It must distinguish old `pqg/smoke`, `pqg/smoke-full`, `pqg/tracking-integrity`, canonical aggregate `pqg/smoke`, source SHA and tracking SHA. Normalize current-GYO stream/context/source/cancel, AP/executor evidence, F1 cancellation, F3 fidelity, G-SYNTHETIC, R1 durable runs, F7 broker, B/C/D remediation and dependency/supply-chain acceptance. Preserve historical evidence as superseded rather than deleting it.

## H2 — Final exact-head automated acceptance

On final source: fresh exact-head Agent Preflight; complete backend with skip reasons and unexpected stderr/warning inventory reviewed; full frontend; lint; type-check; production build + bundle receipt; migration/startup; health/runtime/readiness/cleanup; sandbox/security including Windows evidence; capability-binding regressions; dependency/audit checks; final committed-diff review; `pqg/smoke-full` and canonical `pqg/smoke=success`. Each remaining React `act(...)` warning must be fixed or classified expected; do not create a separate P-TEST package. Anything unrun remains NOT RUN.

## H3 — Final current-source browser/UAT

Revalidate Home/Overview, Work selection/Hub, GYO panel, Documents/editor loading, Knowledge/Review, Memory Hub, Settings, module attached/detached/projection loading/error behavior, offline/recovery, 409 conflict, approval staging, keyboard/focus, reduced motion and reflow/native zoom as appropriate. Use isolated synthetic data. Never claim an unexecuted screen×state×viewport cross-product.

## H4 — Final current-GYO exact-source receipt

After E4, run bounded native current-GYO acceptance against the final source revision. Do not use old Hermes/ACP evidence as current native GYO proof.

## H5 — Documentation/state evidence reconciliation

Reconcile state/risk/checkpoint/acceptance docs, Project Context and this tracker without silently rewriting history: mark superseded evidence, point to H1, reconcile Risk Register and remove contradictory next-action prose. Keep `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL` and `human_approval_required=true`; H5 is not promotion. Q8 remains synthetic-not-human-evidence; Q9 remains local-cancel boundary with remote provider stop unproven.

## H6 — Final promotion decision

Produce final gate report with exact source HEAD, closed findings, accepted residuals, NOT RUN/SKIPPED, out-of-scope items, F9 status and `READY FOR PROMOTION = YES/NO`. Then **STOP** and request explicit user approval before modifying project state/checkpoint.

---

# F9 — Data Egress remains closed

F9 is not part of this execution plan. No package authorizes Work/user-data web-search queries, new connector sends, upload/export, external destination allowlists, or broad new provider egress. Any future F9 gate must separately cover classification → destination allowlist → minimization/redaction → per-egress authorization → audit → deny-by-default.

---

# 5. Locked execution order

```text
A0 → A1 → A2 → B → C → D → E1 → E2-A → P-TRACK → P-MEM → E2-B → E2-C → E2-D → E2-E → E3 → E4 → G → H1 → H2 → H3 → H4 → H5 → H6
```

`F` remains deferred unless separately justified. `F9` remains closed.
If E2-B is **BLOCKED-UPSTREAM**, record the exact blocker and continue
E2-C/D/E, E3, E4 and G; re-check E2-B immediately before H1/H2 rather than
calling it complete from a consumer override.

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

### [2026-08-24 09:19:24 UTC+07:00] Package A2 — Module/heavy-feature code splitting

- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Status: **COMPLETE**.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Fresh A2 exact-ref preflight trigger HEAD `f7750190c3c1744f259fb9ef0b25d9c34ab07eda`; Agent Preflight Run #17 / ID `32676695105` completed SUCCESS and published `pqg/preflight=success` before implementation writes.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Source-validation HEAD: `5fce3270f26f1cac1ffb9d228c63576a47870bc0`; later docs/memory tracking commits must not inherit this source-validation claim.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Failed validation evidence is preserved: `3a035ee7…` / Smoke #123 failed reporter identification and eager threshold; `ea874f56…` / Smoke #124 reached eager <500 KiB but reporter binding still failed; `388cd713…` / Smoke #125 failed closed because the inferred EditorPanel record was not a verified dynamic entry.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Final implementation introduces deterministic lazy module boundaries, dynamic `EditorSurface` isolation for Monaco/EditorPanel, on-demand Mermaid, optional Settings-section lazy loading and a bundle reporter that verifies startup graph rather than hiding warnings.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Exact Smoke Run #126 / ID `32680074013` on source HEAD completed SUCCESS and published `pqg/smoke=success`; normal smoke PASS and `smoke-real=SKIPPED`.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Backend: 597 collected, **516 passed / 81 skipped / 2 warnings**. Frontend: **50 files / 321 tests PASS**; ModuleCanvas 11 PASS; SettingsPanel 7 PASS; EditorPanel 8 PASS; lint **0 warnings / 0 errors** over 147 files / 103 rules; type-check PASS; production build PASS.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Runtime: migrations through 0038, startup, health/runtime, seven readiness checks and cleanup PASS.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Bundle receipt: initial entry `assets/index-DQn4IEj6.js` **486,620 bytes / 144,605 gzip**; initial JS **5 requests / 497,075 bytes / 149,128 gzip**; largest eager **486,620 bytes**; largest lazy `assets/chunk-KEIR6QF5-DNzq6p3w.js` **662,650 bytes / 142,278 gzip**.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Startup proof: `monacoInInitialGraph=false`, EditorPanel is downstream of the dynamic EditorSurface boundary and outside the initial graph; Mermaid is a dynamic entry with `mermaidInInitialGraph=false`.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Known residuals: generic Vite >500 kB warning remains for the 662,650-byte lazy chunk; backend Pydantic Settings and Starlette/httpx warnings, React `act(...)` stderr warnings elsewhere, npm 6 vulnerabilities and GitHub Actions Node/action-version warnings remain for later packages. `chunkSizeWarningLimit` was not raised.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] NOT RUN/SKIPPED: `smoke-real=SKIPPED`; no real-provider acceptance is claimed.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] Scope not changed: no dependency/tool-version, schema/migration, sandbox/security/provider, F9, deployment, branch-protection or checkpoint/state change occurred in A2.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED. Next package is **B — Sandbox hostile-local-process TOCTOU hardening** after this tracking/memory persistence is verified and B receives a fresh exact-ref Agent Preflight.

### [2026-08-24 13:59:57 UTC+07:00] Package B — Sandbox hostile-local-process TOCTOU hardening

- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Status: **COMPLETE** at source-validation HEAD `140df75e907444437844a1328455e6d1c23c7e51`; subsequent docs/memory tracking is a distinct child and does not replace the source receipt.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Fresh isolated execution began clean at live HEAD `22fb38a72dff4d62b30cf6f13311752486625430`; the old F5 checkout and abnormal dirty worktree registration were not modified.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact 422 cause was FastAPI lazy route inclusion rebuilding dependency metadata from internal secure signatures after endpoint replacement; binding `__wrapped__` to the original public endpoint fixed request/body/header/dependency classification while keeping the secure endpoint executable identity.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] A second Windows-only defect was closed: nested-directory HANDLEs requested unnecessary `DELETE` access and caused child rename sharing violations. The access was removed without weakening HANDLE-relative/reparse/hostile-swap protections.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Changed source/test files: `backend/app/services/sandbox_io_posix.py`, `sandbox_io_windows.py`, `security_artifact_create.py`, `security_dirap.py`, `security_overrides.py`, and `backend/tests/test_sandbox_io_b.py`; source diff 78 insertions / 16 deletions; `git diff --check` PASS.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Local evidence: representative 7 PASS; eight historical suites 112 PASS / 1 SKIP / 2 warnings; Package B sandbox 12 PASS / 2 warnings; full backend 527 PASS / 82 SKIP / 2 warnings.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact-source CI: Agent Preflight `32699303000` / `97347423658` SUCCESS; Sandbox Windows `32699302690` / `97347419706` SUCCESS with 12 PASS; Smoke `32699302749` / `97347420230` SUCCESS with backend 528 PASS / 81 SKIP, frontend 50 files / 321 tests, lint/type/build/runtime/readiness/cleanup PASS. `smoke-real=SKIPPED`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Scope remained Package B only. State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; C/D/E/G/H/F9, migrations/schema, dependencies/tools, providers/credentials, Action Package expansion and deployment remain CLOSED.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact next action: commit and independently verify this docs/memory-only tracking child, then stop; no Package C implementation is authorized in this execution.

### [2026-08-24 14:37:06 UTC+07:00] Package C — Admin boundary contract reconciliation

- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Status: **COMPLETE** at source-validation HEAD `fe2ad41052fc4cde3ae49543fd9978d12a692d4c`; the following tracker/memory write is a distinct docs-only child.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Fresh execution began clean at live HEAD `a35b4cc5027ef30864522e8eec25a21414b88dd3`; local preflight PASS and preimplementation Agent Preflight Run `32700713627` / job `97351465720` SUCCESS before the first Package C write.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Exact gap was claim/characterization drift: current HTTP controls prove an approved interactive local-browser path, not human presence; remote and valid-Origin/cross-site failure modes plus the complete forbidden admin-capability classes were not directly locked by regression tests.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Changed eight source/contract/test files with 127 insertions / 3 deletions; the Package C source does not implement capability executable binding or alter provider/credential semantics.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Local evidence: backend focused 48 PASS; Modules Settings 6 PASS; full backend 537 PASS / 82 SKIP / 2 warnings; full frontend 50 files / 322 tests; lint/type-check/build and diff check PASS.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Exact-source CI: Agent Preflight `32701981820` / `97355230052` SUCCESS; Smoke `32701968596` / `97355187719` SUCCESS with backend 538 PASS / 81 SKIP / 2 warnings, frontend 50 files / 322 tests, lint/type/build/runtime/readiness/cleanup PASS; `smoke-real` `97355188770` SKIPPED.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED; D/E/G/H/F remain closed in this execution. Stop after Package C.

### [2026-08-24 15:07:32 UTC+07:00] Package D — Capability executable-binding validator

- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Explicit user approval opened only Package D capability/security binding work. Live fetch began clean/current at tracking HEAD `cce087fec20a0f957278fbc88f047b130602f289`; local preflight PASS and preimplementation exact-ref Agent Preflight `32703253047` / `97358945387` SUCCESS.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Exact gap: CapabilityRegistry owned exposure metadata and startup checked the nine MCP names, but no fail-closed contract tied capability IDs and invariants to the actual post-security-override MCP callables or the two Action Package executor routes.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Source commit `36b2fef6817dff9b97e15ee58d1004ab9a067ce6` changes four source/test files, 389 insertions / 64 deletions. Negative drift coverage rejects missing/orphan/duplicate bindings, compatibility aliases, incompatible surfaces, metadata changes, handler replacement and Action Package allowlist drift.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Exact-source Preflight `32704348381` / `97362194625`, Sandbox Windows `32704336190` / `97362155343`, and Smoke `32704336226` / `97362155302` completed SUCCESS with all three combined statuses green; `smoke-real` `97362155978` was SKIPPED, not PASS.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Result: Package D **COMPLETE**. State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED; E/G/H/F remain unopened. Stop before the next package.

### [2026-08-24 15:21:55 UTC+07:00] Package E1 — npm vulnerability exact inventory

- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Explicit user approval opened inventory-only E1. Live checkout was clean/current at `322c1009405c5cb09ebe6b04a5e0c66c5e8b253c`; local preflight PASS and exact-ref Agent Preflight `32705514343` / `97365648952` SUCCESS before the first documentation write.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Live npm audit with Node `24.16.0` / npm `11.13.0`: repository root 0 findings; frontend full tree 6 vulnerable nodes (`3 moderate / 3 high`) and 32 advisory records; frontend production view 3 moderate nodes and no high nodes.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] The exact advisory/path/fixed-range/reachability/owner/risk matrix and four proposed E2 batches are recorded in `PACKAGE_E1_NPM_VULNERABILITY_INVENTORY.md`. No remediation command or dependency mutation was performed.
- [2026-08-24 15:21:55 UTC+07:00][recorded_at] Result: Package E1 inventory is **COMPLETE**. E2/E3/E4/G/H/F/F9 remain unopened; state/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`. Stop and request separate E2 approval.

### [2026-08-24 16:15:15 UTC+07:00] Package E2-A — Mermaid/runtime DOMPurify remediation

- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Explicit approval opened E2-A only. Clean/current baseline was E1 tracking HEAD `6fe0db6cd85cea81f11b358d0402e5eef9baaba9`; local preflight PASS and preimplementation exact-ref Agent Preflight `32709269035` / `97376992586` SUCCESS.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Source commit `dc1a46280a006c2214a301557284fbbbd476ed27` changes only `frontend/package.json`, `frontend/package-lock.json`, and two focused dependency/runtime regression tests. Mermaid is exact `11.16.1`; Mermaid-owned DOMPurify is `3.4.14`; Monaco's `3.2.7` branch and all E2-C/D nodes remain unchanged.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Audit after remediation: full frontend five vulnerable nodes (`2 moderate / 3 high`), production two moderate nodes and no high nodes. Neither Mermaid nor its nested DOMPurify remains in the findings; no blanket audit remediation was used.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Local focused 19 PASS; full frontend 52 files / 330 tests, lint, type-check, build and A2 lazy-boundary gate PASS. Exact-source Preflight `32710121468` / `97379518811` and Smoke `32710112957` / `97379488765` SUCCESS; Smoke backend 548 PASS / 81 SKIP / 2 warnings; `smoke-real` `97379490095` SKIPPED.
- [2026-08-24 16:15:15 UTC+07:00][recorded_at] Result: E2-A **COMPLETE**, E2 overall **IN PROGRESS**. Stop before separately gated E2-B/C/D, backend reproducibility/warnings, E3/E4/G/H/F/F9, schema/migration, provider/credential, deployment or state/checkpoint promotion.

### [2026-08-24 16:34:28 UTC+07:00] Package P-TRACK — approved start

- [2026-08-24 16:34:28 UTC+07:00][recorded_at] Explicit user approval inserts only P-TRACK before E2-B and applies risk-based local validation immediately. P-MEM is approved as a separate docs package after P-TRACK.
- [2026-08-24 16:34:28 UTC+07:00][recorded_at] P-TRACK scope is fail-closed tracking equivalence with a dedicated full-source receipt, exact tracking allowlist, bounded non-recursive ancestry, distinct tracking receipt and final `pqg/smoke` aggregator.
- [2026-08-24 16:34:28 UTC+07:00][recorded_at] Parallel Smoke, setup-node/action upgrade, dependency caching, concurrency, Project Memory normalization, product/runtime behavior and state/checkpoint changes remain outside P-TRACK.
- [2026-08-24 16:34:28 UTC+07:00][recorded_at] P-TRACK is **IN PROGRESS**. No completion or live GitHub receipt is claimed until the changed workflow/script passes exact-source full Smoke and a following allowlisted docs child proves tracking integrity.

### [2026-08-24 17:57:29 UTC+07:00] Remaining-roadmap research amendment

- [2026-08-24 17:57:29 UTC+07:00][recorded_at] The locked order is refined to `P-TRACK -> P-MEM -> E2-B -> E2-C -> E2-D -> E2-E -> E3 -> E4 -> G -> H1..H6`; no downstream package is opened before exact P-TRACK S/T1 live receipts.
- [2026-08-24 17:57:29 UTC+07:00][recorded_at] E2-B is discovery-first and may be **BLOCKED-UPSTREAM**: [Monaco upstream issue #5454](https://github.com/microsoft/monaco-editor/issues/5454) reports that `0.56.0` bundles DOMPurify `3.4.8` into shipped artifacts, so a consumer override is not a closure proof. E2-E is a separate reproducibility/warning package and must choose one CI resolution authority before changing installers or lock/constraint files.
- [2026-08-24 17:57:29 UTC+07:00][recorded_at] E3 remains the only action/toolchain package; no parallel Smoke or concurrency package is authorized without measured post-E3 bottleneck. E4 must preserve or explicitly review historical runtime-contract compatibility and requires fresh provider/credential/network authorization before any native real-GYO request.
- [2026-08-24 17:57:29 UTC+07:00][recorded_at] This amendment changes planning/evidence wording only. It does not change dependencies, lockfiles, runtime/API behavior, provider credentials, branch protection, state/checkpoint or F9.

### [2026-08-24 18:58:09 UTC+07:00] P-TRACK SOURCE full receipt; T1 completion candidate

- [2026-08-24 18:58:09 UTC+07:00][recorded_at] SOURCE `2ac0e83184e891bd61f5543084b5d26868e10636` is full-validated by Smoke run `32724184829`: `classify=success`, `smoke-full=success`, `tracking-integrity=skipped`, `smoke-result=success`, exact `pqg/smoke-full=success` and canonical `pqg/smoke=success`.
- [2026-08-24 18:58:09 UTC+07:00][recorded_at] Full-source run evidence is backend 548 PASS / 81 SKIP / 2 warnings; frontend 52 files / 330 tests, lint/type-check/build, startup, health/runtime, seven readiness checks and cleanup PASS; `smoke-real` SKIPPED. Existing Node 20 action annotation remains E3 scope.
- [2026-08-24 18:58:09 UTC+07:00][recorded_at] T1 is this one direct child and is restricted to allowlisted docs plus the `PROJECT_CONTEXT` conditional aggregate/full/tracking invariant. P-TRACK remains **PARTIAL** until exact T1 returns `tracking-integrity=success`, `smoke-full=skipped`, `smoke-result=success`, `pqg/tracking-integrity=success` and canonical `pqg/smoke=success`.

### [2026-08-24 19:03:27 UTC+07:00] P-TRACK accepted; P-MEM T2 completion candidate

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] P-TRACK is **COMPLETE**: SOURCE `2ac0e83184e891bd61f5543084b5d26868e10636` has the canonical full receipt, and direct child T1 `42b16fcb2394528f0b73ebb2812a4c8ff5274953` has exact `pqg/tracking-integrity=success` and canonical `pqg/smoke=success`. The tracking receipt proves bounded equivalence only; it does not relabel runtime validation as executed on T1.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] P-MEM is this one remaining bounded tracking child T2. Its scope is the existing five-file tracking allowlist only: Master Plan, Project Context, Project Memory, Project Changelog and `REMEDIATION_MASTER_PLAN_CONTEXT.md`; no add/delete/rename, state/checkpoint or runtime change is permitted.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] T2 becomes **COMPLETE** only if its exact SHA publishes `pqg/tracking-integrity=success` and canonical `pqg/smoke=success`, with `smoke-full=skipped`; there is no T2.5 receipt commit. A correction after T2 must fall back to full Smoke. E2-B remains unopened until that receipt exists.

### [2026-08-24 19:09:01 UTC+07:00] P-MEM T2 fail-closed receipt and full-recovery candidate

- [2026-08-24 19:09:01 UTC+07:00][recorded_at] Exact T2 `603fdd19139e5cd3c76797e6576c25a746f79e40` failed closed in Smoke run `32725233242`: classifier reported T1 `42b16fcb…` as a depth-one anchor and tracking integrity correctly rejected it because it has no `pqg/smoke-full` receipt. No runtime validation was falsely claimed and P-MEM remains PARTIAL.
- [2026-08-24 19:09:01 UTC+07:00][recorded_at] Root cause is workflow shallow-fetch poisoning: `git fetch --depth=1` on push `before` truncated T1's parent relation to SOURCE `2ac0e831…`. The correction preserves ancestry and makes incomplete ancestry fall back to full validation. This recovery commit is intentionally outside the tracking allowlist and therefore must complete exact full Smoke before P-MEM can be accepted.
