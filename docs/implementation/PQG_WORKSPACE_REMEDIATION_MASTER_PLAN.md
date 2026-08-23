# PQG Workspace — Remediation & Final Acceptance Master Plan

> Status: **ACTIVE — TRACK UNTIL COMPLETION**
>
> Created from live `pqg-workspace` audit and explicit user decisions on 2026-08-24.
>
> This plan is the execution tracker for the remaining v2.2 remediation/final-acceptance work. It does **not** override live canon, `PROJECT_STATE.md`, `AI_STATE.json`, `CURRENT_CHECKPOINT.md`, security contracts, or newer source/test evidence.

## 0. Plan persistence and change-control rule

- This file MUST remain in the repository while any package below is `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `PARTIAL`, or awaiting final acceptance.
- Do **not** delete this plan merely because one phase/package is complete.
- Normal user requests to revise the plan MUST update this file in place and preserve the execution/history ledger.
- Deletion/replacement is allowed only when either:
  1. all in-scope packages and final acceptance are complete and the user explicitly accepts plan closure; or
  2. the user explicitly requests that this plan be deleted/replaced.
- Historical completed rows/receipts must not be silently removed. Mark them `COMPLETE`, `SUPERSEDED`, or `DEFERRED` with evidence.
- Plan completion is **not** checkpoint/state promotion. Promotion remains a separate explicit user approval.

## 1. Locked user decisions

The user selected the recommended option for all nine audit decisions:

| Decision | Locked choice | Execution meaning |
| --- | --- | --- |
| Q1 | **A** | Initial/core bundle target <500 kB where practical; Monaco/Mermaid/heavy features load on demand; a large lazy vendor chunk may remain if not initial-load critical. Never hide the problem by only raising `chunkSizeWarningLimit`. |
| Q2 | **A** | Sandbox must defend against a hostile local process: implement true handle/descriptor-bound I/O and close pathname check-then-use races, including Windows semantics. |
| Q3 | **A** | v2.2 admin claim is `interactive local-user admin`, not cryptographic proof-of-human. Keep current boundary unless a future threat-model change explicitly opens WebAuthn/Windows Hello work. |
| Q4 | **A** | Add a minimal server-owned capability binding/consistency validator; do not rewrite the system into a mega central dispatcher. |
| Q5 | **A** | Dependency remediation is selective/batched: inventory first, patch/minor where sufficient, major only when required; add deterministic backend CI dependency constraints. Never run blind `npm audit fix`. |
| Q6 | **A** | Current-GYO real acceptance is a bounded local Windows run using existing Credential Manager configuration and synthetic Work; no new CI secret path by default. |
| Q7 | **A** | Final governance is PR-first for implementation changes; require `pqg/smoke`; disallow force-push/delete; do not require `pqg/preflight` as merge status unless trigger semantics are redesigned. |
| Q8 | **A** | Keep G-SYNTHETIC accepted for v2.2 scope, but never represent it as human-usability evidence. |
| Q9 | **A** | Local durable cancellation + late-output discard is the v2.2 gate; upstream provider compute-stop remains a documented provider limitation, not a v2.2 blocker. |

### Approval interpretation

The decision set above plus the user's instruction to execute this plan authorizes implementation of the **selected, bounded packages described here**, including the explicitly selected sandbox/security, capability-binding, dependency/tool-version, current-GYO acceptance, and repository-governance work.

This authorization does **not** open or authorize:

- F9 Data Egress;
- schema/migration refactoring outside a separately justified migration package;
- changing Action Package execution semantics beyond the capability-binding validation described here;
- deployment/public exposure;
- use of real user data;
- arbitrary provider/credential mutation;
- checkpoint/state promotion.

Any material scope expansion beyond this plan requires a new explicit user decision.

## 2. Live audit baseline used to create this plan

Authoritative audit/source receipt before this plan's docs-only commit:

- Branch: `pqg-workspace`
- Audit HEAD: `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`
- Agent Preflight: Run #10 / ID `32671953420` — **SUCCESS**, `pqg/preflight=success`
- Smoke Test: Run #106 / ID `32671953411` — **SUCCESS**, `pqg/smoke=success`
- Backend: **516 passed / 81 skipped / 2 warnings**
- Frontend in Smoke: **4 files / 30 tests PASS** — this is focused coverage, **not** the full frontend suite
- Lint: **0 warnings / 0 errors**, 144 files / 103 rules
- TypeScript: PASS
- Production build: PASS
- Runtime: migrations through `0038_durable_assistant_runs`, startup, health/runtime, readiness and cleanup PASS
- Readiness: **7 checks PASS**
- `smoke-real`: **SKIPPED — NOT PASS**
- Branch protection: OFF (`protected=false`, required-status enforcement off)
- State/checkpoint: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`
- F7: implemented/scoped-validated
- F9: **CLOSED / NOT APPROVED**

The audit-trigger commit changed only `.github/agent-preflight-trigger.txt` relative to the preceding docs-only HEAD. Later plan/memory commits are documentation-only and must not be represented as inheriting independent runtime/source validation.

## 3. Global execution rules

### 3.1 Single-agent execution

Multi-agent execution is paused. Execute packages sequentially unless the user later explicitly re-enables multi-agent work.

### 3.2 Mandatory preflight before implementation edits

Before the first implementation write of every package:

1. re-fetch live target branch/ref;
2. run a **fresh Agent Preflight on the exact target ref**;
3. require workflow/job success and `pqg/preflight=success`;
4. read in order:
   - `PROJECT_STATE.md`
   - `AI_STATE.json`
   - `docs/implementation/CURRENT_CHECKPOINT.md`
   - `CODEGRAPH.md`
   - `docs/AI_AGENT_ROUTING.md`
   - task-specific canon/security/data model
   - target source/public contract/focused tests
   - `docs/14_AGENT_OPERATING_CONTRACT.md`
   - `docs/project-memory/PROJECT_CONTEXT.md`
   - this master plan;
5. state active gate, allowed scope, planned files, validation, and forbidden scope before editing.

A successful `pqg/smoke` is not a substitute for Agent Preflight.

### 3.3 Evidence discipline

- Unrun means **NOT RUN**.
- Skipped means **SKIPPED**, never PASS.
- `smoke-real` must never be reported PASS when the job or actual provider acceptance was skipped.
- Exact source-validation HEAD must be separated from later docs-only HEADs.
- No checkpoint/state promotion without separate user approval.
- No F9 work under this plan.

### 3.4 Change sizing

Prefer one bounded package at a time with:

`fresh preflight → inspect → focused implementation → focused tests → proportionate regression → exact diff review → Smoke/current acceptance receipt → update this plan + Project Context`.

Do not combine unrelated security, dependency, migration, or governance changes into one unreviewable change.

## 4. Master status board

| Package | Scope | Priority | Status | Protected? | Completion evidence |
| --- | --- | --- | --- | --- | --- |
| A0 | CI/preflight topology repair | P0 | **NOT STARTED** | CI/process | exact-head preflight + workflow trigger tests + Smoke |
| A1 | Full frontend regression in `pqg/smoke` + backend skip visibility | P0 | **NOT STARTED** | CI/process | full frontend suite + `pqg/smoke` exact HEAD |
| A2 | Module/heavy-feature code splitting | P0 | **NOT STARTED** | No new security/schema/dependency | focused lazy/fail-closed tests + full frontend + build bundle receipt + Smoke |
| B | Sandbox hostile-local-process TOCTOU hardening | P1 | **NOT STARTED** | **Security boundary** | Linux + Windows focused race/path suites + full backend + Smoke |
| C | Admin boundary claim/contract reconciliation | P1 | **NOT STARTED** | Auth/security documentation/contract | tests preserve current local-browser boundary + docs explicitly avoid proof-of-human claim |
| D | Capability implementation binding validator | P1 | **NOT STARTED** | **Capability/security boundary** | startup/setup fail-closed drift tests + full backend + Smoke |
| E1 | npm vulnerability exact inventory | P2 | **NOT STARTED** | Dependency analysis | advisory/path/reachability matrix |
| E2 | Dependency remediation + backend reproducibility/warnings | P2 | **NOT STARTED** | **Dependencies/tool versions** | selective updates + constraints + matrix/full tests + Smoke |
| E3 | GitHub Actions major upgrade + immutable SHA pinning | P2 | **NOT STARTED** | **Tool/supply-chain** | workflow runs on pinned SHAs + preflight/Smoke |
| E4 | Replace legacy `smoke-real` with bounded current-GYO acceptance | P1 evidence | **NOT STARTED** | **Provider/network/credential use** | isolated local Windows real-provider receipt; no skip-as-success |
| F | Migration registry maintainability | P3 | **DEFERRED** | **Migration** | only reopen if a real migration need justifies it |
| G | Branch protection / PR-first governance | P1 governance | **NOT STARTED** | **Repository governance** | branch protection verification + required `pqg/smoke` behavior |
| H1 | Authoritative evidence normalization | P1 acceptance | **NOT STARTED** | Docs/evidence | source-SHA/evidence matrix |
| H2 | Final exact-head automated acceptance | P1 acceptance | **NOT STARTED** | validation | full backend/frontend/lint/type/build/runtime/security |
| H3 | Final exact-head browser/UAT | P1 acceptance | **NOT STARTED** | acceptance | primary-surface current-source receipt |
| H4 | Final current-GYO receipt | P1 acceptance | **BLOCKED BY E4** | provider/network | bounded real-provider receipt if E4 completed |
| H5 | State/risk/checkpoint documentation reconciliation | P1 acceptance | **NOT STARTED** | state docs; no promotion | explicit current/superseded evidence |
| H6 | Checkpoint/state promotion decision | Final gate | **WAITING — USER APPROVAL REQUIRED** | **State promotion** | explicit user approval after final gate report |
| F9 | Data Egress | Future gate | **CLOSED / NOT APPROVED** | **Security/data egress** | separate future design gate only |

---

# Phase A — CI quality and frontend performance

## A0 — Repair preflight and active branch CI topology

### Goal

Ensure the repository can create a task branch and still self-trigger the mandatory exact-ref Agent Preflight, while removing stale historical active push triggers from Smoke.

### Current finding

`agent-preflight.yml` push-trigger is limited to `pqg-workspace` and one historical remediation branch. A new `work/**`/`security/**` branch cannot self-trigger preflight by modifying `.github/agent-preflight-trigger.txt` under the current contract.

Smoke still contains historical R1/remediation push branches even though live `pqg-workspace` is ahead of both.

### Intended changes

Primary files:

- `.github/workflows/agent-preflight.yml`
- `.github/workflows/smoke.yml`

Preferred topology:

- Agent Preflight: retain path filter for `.github/agent-preflight-trigger.txt` and the workflow itself, but allow the trigger on any task branch (or remove the branch filter entirely).
- Smoke:
  - PRs targeting `pqg-workspace`;
  - pushes to `pqg-workspace` and active task branch conventions such as `work/**`, `security/**`, `maintenance/**`, `integration/**`;
  - `workflow_dispatch` retained;
  - remove historical R1/remediation branch push triggers after verifying no active work depends on them;
  - do not delete branches.

### Forbidden scope

- no application/runtime change;
- no dependency/action-major change yet;
- no branch deletion;
- no branch protection change yet.

### Acceptance

- fresh preflight on exact implementation ref before edits;
- create/update trigger on a representative task ref and prove Agent Preflight runs there;
- verify `pqg/preflight` exact SHA;
- verify Smoke topology on allowed task/default refs;
- committed-diff validation remains active;
- exact diff contains only intended workflow/process files.

### Rollback point

Revert only the topology change if task-branch triggers are over-broad or status publication is broken; do not alter application source.

## A1 — Make `pqg/smoke` a truthful frontend regression gate

### Goal

Stop representing 4 files / 30 frontend tests as broad frontend validation.

### Intended changes

In `.github/workflows/smoke.yml`:

- replace the four-file Vitest invocation with the full `npm run test` suite;
- rename outdated `Validate R1 frontend` step to a current generic frontend regression name;
- retain lint, type-check, production build;
- run backend pytest with skip-reason visibility (`-ra`/equivalent) so 81 skips are classifiable.

### Backend skip inventory

Classify skips into:

- intentional legacy characterization;
- platform/environment-specific;
- real-provider protected acceptance;
- restore/destructive isolated acceptance;
- unknown/unexplained — investigate before final acceptance.

Do not automatically turn intentional skips into failures.

### Acceptance

Exact-head `pqg/smoke=success` must mean:

- full backend suite completed;
- full frontend Vitest suite completed;
- lint PASS;
- type-check PASS;
- production build PASS;
- migrations/startup PASS;
- health/runtime PASS;
- readiness PASS;
- cleanup PASS.

Real provider is explicitly separate and not implied.

## A2 — Module/heavy-feature code splitting

### Goal

Reduce initial/core frontend bundle and load Monaco/Mermaid/other heavy features only when the authorized UI path actually needs them.

### Current baseline

Fresh build around audit HEAD reported approximately:

- entry `index-*.js`: ~667.45 kB;
- another large chunk: ~662.65 kB;
- Cytoscape: ~435.38 kB;
- KaTeX: ~258.88 kB.

`ModuleCanvas.tsx` eagerly imports many module surfaces. `EditorPanel` directly imports `@monaco-editor/react`; Mermaid already uses a dynamic `import('mermaid')` inside its renderer.

### Locked Q1 acceptance

Use option A:

- target initial/core bundle below 500 kB where practical;
- heavy lazy chunks may exceed 500 kB if they are not part of startup and are justified;
- measure startup/initial graph, not just Vite warning count;
- never solve only by increasing `chunkSizeWarningLimit`.

### Intended design

Preserve eager Foundation/core surfaces where startup UX depends on them. Lazy-load business/heavy surfaces such as Documents/Knowledge/Reports/Review/Memory/Local Data/DIRAP as appropriate.

For Documents, use a wrapper so the import graph containing `EditorPanel`/Monaco is reached only when Documents is actually rendered.

Critical order:

`resolve definition → projection must be ready → attached/eligible must be true → then start lazy import → Suspense/error boundary → render`.

Detached/error/loading projection states must not trigger business-module loading.

### Focused tests

At minimum:

- projection idle/loading/error does not load business module;
- ready + detached does not load;
- ready + attached begins load;
- authorized pending import renders loading state;
- lazy import failure renders visible recoverable error;
- stale late import after module switch cannot render the old module;
- Documents without correct scope does not load Monaco/editor surface;
- existing fail-closed Foundation behavior remains intact.

### Bundle receipt

Record before/after:

- initial entry JS and gzip;
- largest eagerly loaded chunk;
- largest lazy chunk;
- initial JS request count;
- proof Monaco is not initial-load content;
- proof Mermaid stays on-demand.

### Acceptance

Focused tests + **full frontend suite** + lint 0/0 + type-check + build + bundle comparison + exact-head Smoke.

---

# Phase B — Sandbox hostile-local-process TOCTOU hardening

## Goal

Close the real residual where a validated pathname can be replaced between validation and actual read/write by another local process.

## Locked Q2 threat model

A hostile local process is in scope. Pathname-only revalidation is not sufficient closure evidence.

## Architectural target

Move trusted filesystem operations behind a handle/descriptor-bound sandbox API rather than returning a trusted `Path` and letting callers open it later.

Target service shape may include:

- `safe_open_read`
- `safe_read_text`
- `safe_stat`
- `safe_hash`
- `safe_iter_files`
- `safe_atomic_write`

Naming is implementation-specific; security invariant is authoritative.

### POSIX

Prefer directory descriptor + relative open semantics such as `dir_fd`/`openat` with no-follow controls and post-open identity verification.

### Windows

Use handle-based semantics that validate reparse/junction/link identity at open/use time. Do not claim closure from `Path.resolve()` loops alone. Avoid a large ad-hoc ctypes implementation unless necessary; isolate Windows-specific low-level code behind a narrow tested adapter.

### Write invariant

- create/write temp file inside a verified trusted directory;
- verify target/parent semantics at operation time;
- atomic replace within the same trusted directory;
- preserve existing hard-link fail-closed behavior;
- never widen workspace roots.

## Required caller audit

Inspect and migrate all security-relevant file users, including at least:

- `backend/app/api/files.py`
- `backend/app/mcp/tools.py`
- artifact imports/managed output publishing
- DIRAP source extraction/read paths
- workspace/local search paths
- F7 context-broker artifact hydration paths.

Do not close B after fixing only one caller.

## Test matrix

Must include deterministic and race/swap cases:

- relative traversal;
- absolute/drive/UNC escape;
- symlink leaf and parent;
- Windows junction/reparse parent;
- hard-link leaf;
- parent replacement after validation;
- leaf replacement after validation;
- replacement during approval wait;
- new-file creation under swapped parent;
- atomic-write target swap;
- read/hash race;
- iteration/search swap;
- post-authorization artifact swap.

Windows-specific evidence must run on a Windows runner/environment; Linux tests do not prove Windows junction/reparse behavior.

## Acceptance

- focused Linux/POSIX behavior PASS where relevant;
- Windows hostile-swap suite PASS;
- existing sandbox traversal/link/hard-link tests PASS;
- full backend PASS;
- F7 artifact authorization/leakage regression PASS;
- Smoke exact HEAD PASS;
- no root widening, F9, schema, or provider change.

---

# Phase C — Admin boundary contract reconciliation

## Goal

Keep the current strong local-browser/CSRF/server-actor boundary while removing any unsupported claim that it is cryptographic proof of a human.

## Locked Q3 decision

Use option A for v2.2:

- authoritative wording: **interactive local-user admin boundary**;
- loopback + approved Origin/Fetch-Metadata + server-owned actor remain enforcement controls;
- do not add token theater and call it proof-of-human;
- WebAuthn/Windows Hello is a future threat-model package, not part of current v2.2.

## Work

- review admin dependency and all constitutional admin routes;
- verify no client/model-provided actor can create admin identity;
- verify remote/cross-origin/missing required local-browser context fails closed according to the existing contract;
- reconcile canon/risk/acceptance wording so it says what is actually proven;
- explicitly document that a sufficiently privileged hostile local process is not distinguished from the local user by current HTTP-header checks.

## Acceptance

- existing admin security tests PASS;
- add/adjust characterization tests only where wording/behavior is ambiguous;
- no broad auth system, WebAuthn, biometric, user database, session redesign, or new credential store;
- docs no longer claim cryptographic human presence.

---

# Phase D — Capability executable-binding consistency

## Goal

Prevent semantic drift between CapabilityRegistry metadata/exposure and actual MCP/Action-Package/read-inline implementation routes.

## Locked Q4 decision

Implement a minimal server-owned binding/consistency validator. Do not replace the existing executors with a central mega dispatcher.

## Intended contract

A binding record should associate at least:

- `capability_id`
- execution surface (`READ_INLINE`, `MCP`, `ACTION_PACKAGE`, or equivalent existing vocabulary)
- authoritative implementation/handler key
- expected execution mode/risk invariants.

At startup/setup/tests, validate:

- every model-visible capability has exactly one valid implementation binding for its declared execution mode;
- executable model bindings have registry entries;
- MCP compatibility names cannot create an unregistered bypass;
- Action Package capability IDs map only to the existing AP executor semantics;
- an `ACTION_PACKAGE` metadata entry cannot bind to inline mutation;
- a read-only declared capability cannot bind to a mutation handler;
- admin-risk capability IDs have no executable model binding;
- duplicate/orphan bindings fail closed;
- handlers cannot override server-owned risk/execution/replay metadata.

## Forbidden scope

- no new model-visible admin capabilities;
- no change to Action Package approval/idempotency semantics;
- no F9/network capability;
- no provider credential administration through the model.

## Acceptance

Focused negative drift tests + existing capability registry/MCP/AP tests + full backend + startup + Smoke exact HEAD.

---

# Phase E — Dependency, supply chain, and current-GYO acceptance

## E1 — npm vulnerability exact inventory

### Goal

Turn the current `6 vulnerabilities (3 moderate, 3 high)` summary into an actionable advisory matrix before changing versions.

### Required inventory

Run/read exact `npm audit --json` data and record for each finding:

- advisory/package;
- severity;
- direct/transitive path;
- runtime vs dev-only;
- affected version;
- fixed version/range;
- whether exploitability is established in PQG usage;
- owning top-level dependency;
- semver/behavioral risk of remediation.

`npm audit fix` is forbidden as an automatic blanket action.

### Output

Commit an audit/remediation matrix or update this plan with exact findings before E2 updates begin.

## E2 — Selective dependency remediation + backend reproducibility/warnings

### Locked Q5 policy

- patch/minor updates first where sufficient;
- major updates only when advisory/API compatibility requires them;
- validate each small group;
- add deterministic backend CI dependency constraints.

### Backend reproducibility

`pyproject.toml` currently contains broad lower-bound ranges for several important runtime/dev packages. Establish a validated deterministic CI set, preferably:

- `pyproject.toml` remains compatibility/declaration intent;
- a committed constraints/lock mechanism captures exact validated CI versions.

Exact tool/file format should be selected after checking existing repository conventions; avoid unnecessary package-manager migration.

### Backend warnings

Investigate the two repeat warnings separately:

1. Pydantic Settings unresolved forward-reference warning around `lifespan`;
2. Starlette TestClient/httpx deprecation interaction.

Use a minimal repro/version matrix to identify whether the owner is PQG code or a transitive/version interaction before changing app code.

### Acceptance

- advisory-targeted updates only;
- deterministic install proof from a clean CI environment;
- backend full suite;
- frontend full suite;
- lint/type/build;
- runtime/migrations;
- Smoke exact HEAD;
- document remaining accepted advisories/warnings if any.

## E3 — GitHub Actions upgrade and immutable pinning

### Goal

Remove Node20 compatibility warnings and reduce supply-chain risk from mutable action tags.

### Work

For each official action used by active workflows:

1. resolve the current appropriate major at implementation time;
2. verify runner compatibility;
3. validate the major upgrade;
4. pin to an immutable commit SHA;
5. keep a human-readable comment noting the corresponding release/major.

Do not copy SHA values from this plan; resolve them fresh at implementation time.

Primary workflows include at least:

- `.github/workflows/smoke.yml`
- `.github/workflows/agent-preflight.yml`

### Acceptance

Fresh Agent Preflight and Smoke must run successfully using the pinned action SHAs; no Node20-target deprecation warning from those actions should remain unless upstream provides no compatible replacement and the residual is explicitly documented.

## E4 — Retire legacy `smoke-real`; add bounded native current-GYO acceptance

### Current defect

Active `smoke-real` still installs/authenticates `hermes-agent` and starts legacy ACP semantics, despite the current GYO runtime being provider-neutral/native. It can also exit `0` after printing `SKIP` when Hermes is not ready, making success unsuitable as real-provider evidence.

### Locked Q6 execution

Use a **bounded local Windows acceptance** with existing Credential Manager configuration and synthetic Work. Do not create a new GitHub-hosted credential path by default.

### New acceptance contract

- isolated temporary SQLite;
- isolated temporary workspace;
- synthetic Work/context only;
- existing approved/current provider and model profile only;
- bounded model/cost/request count;
- no real user data;
- no credential copy into logs/artifacts;
- no raw provider response bodies containing secrets;
- provider/model/source SHA provenance receipt;
- no fallback after first token according to current runtime contract;
- cleanup receipt;
- explicit result `PASS`, `FAIL`, or `NOT RUN/SKIPPED` — never success-by-skip.

The workflow/script may validate a read-only GYO run; Action Package real proposal/execution is only included if the acceptance contract explicitly says so and remains inside existing AP semantics.

### Legacy job disposition

Retire or clearly remove the legacy Hermes/ACP job from the active acceptance path while preserving Git history. Do not retain a misleading job name/green status as native GYO evidence.

### Acceptance

Bounded current-source receipt on the exact source revision, with provider/model/redacted evidence and cleanup. This is not F9 authorization.

---

# Phase F — Migration maintainability

## Status: DEFERRED

Migration 0037/0038 and the registry wrapper are currently regression-valid. The compatibility export/0022 bridge is maintainability debt, not a demonstrated correctness blocker.

Do **not** refactor migrations merely for cleanliness under this plan.

Reopen only when:

- a real new migration requires touching the registry; or
- a concrete migration correctness/maintainability failure is demonstrated; or
- the user explicitly opens a dedicated migration-maintenance package.

Any reopened migration work requires a fresh explicit scope review because migration/schema remains protected.

---

# Phase G — Repository governance / branch protection

## Goal

Make the default branch enforce the technical gate only after the technical gate is truthful/stable.

## Dependency order

Do not enable final protection until at least A0, A1 and E3 are complete and `pqg/smoke` is stable on the intended topology.

## Locked Q7 model

PR-first for implementation changes:

- protect `pqg-workspace`;
- require `pqg/smoke` before merge;
- disallow force pushes;
- disallow branch deletion;
- do not require `pqg/preflight` as merge status under current semantics;
- retain a practical single-user emergency/admin path only if GitHub settings require it, and document any bypass.

`pqg/preflight` remains an agent execution prerequisite, not product verification, unless redesigned later.

## Acceptance

Verify live GitHub branch rules after applying them and demonstrate a representative PR cannot merge with missing/failing `pqg/smoke` but can merge after the required check passes. Do not delete historical branches as part of this package.

---

# Phase H — Final evidence, UAT, and state reconciliation

## H1 — Authoritative evidence normalization

Create/update an authoritative matrix containing:

- feature/gate;
- exact source SHA;
- receipt/run/artifact ID;
- `PASS` / `PARTIAL` / `NOT RUN` / `SKIPPED`;
- what it proves;
- what it does not prove;
- superseded evidence link;
- current applicability.

At minimum normalize:

- E1/current-GYO stream/context/source/cancel;
- E2 real proposal/AP/executor evidence;
- F1 cancellation;
- F3 fidelity;
- G-SYNTHETIC;
- R1 durable runs;
- F7 broker;
- B/C/D security remediation;
- dependency/supply-chain acceptance.

Do not delete historical evidence; mark it superseded.

## H2 — Final exact-head automated acceptance

On the final source revision:

1. fresh exact-head Agent Preflight;
2. complete backend suite with skip reasons reviewed;
3. complete frontend suite;
4. lint;
5. type-check;
6. production build + bundle receipt;
7. migration/startup;
8. health/runtime/readiness/cleanup;
9. sandbox/security focused suites including Windows evidence;
10. capability binding regressions;
11. final committed-diff review;
12. `pqg/smoke=success`.

Anything not run remains explicitly NOT RUN.

## H3 — Final current-source browser/UAT

Revalidate current primary surfaces rather than relying only on historical screenshots that predate later source changes.

Minimum journeys/surfaces:

- Home/Overview;
- Work selection and Work Hub;
- GYO panel/Assistant;
- Documents/editor loading;
- Knowledge/Review;
- Memory/Memory Hub;
- Settings;
- Module attached/detached/projection error/loading behavior;
- offline/recovery;
- conflict/409 behavior;
- approval staging;
- keyboard/focus;
- reduced motion;
- reflow/native zoom evidence appropriate to current acceptance contract.

Use isolated synthetic data. Do not claim a full screen×state×viewport cross-product unless it is actually executed.

## H4 — Final current-GYO exact-source receipt

If E4 is implemented (planned: yes), run the bounded current-GYO acceptance against the final source revision so the provider evidence is source-aligned.

Never use old Hermes/ACP evidence as native GYO current-source proof.

## H5 — Documentation/state reconciliation

After H1–H4, reconcile without silently rewriting history:

- `PROJECT_STATE.md`
- `AI_STATE.json`
- `docs/implementation/CURRENT_CHECKPOINT.md`
- `AI_RISK_REGISTER.md`
- acceptance documentation
- `docs/project-memory/PROJECT_CONTEXT.md`
- this plan status board/ledger.

Locked Q8 wording:

- G-SYNTHETIC may remain accepted for scoped v2.2 evaluation;
- it is **not human usability evidence**;
- do not relabel synthetic results as human testing.

Locked Q9 wording:

- durable local cancellation, terminal state, provenance and late-output discard can satisfy v2.2 acceptance;
- upstream provider compute/billing termination is not proven and remains a documented provider/platform limitation.

## H6 — Final promotion decision

Produce a final gate report with:

- exact source HEAD;
- closed findings;
- remaining accepted residuals;
- NOT RUN/SKIPPED items;
- explicit out-of-scope items;
- F9 status;
- recommendation: `READY FOR PROMOTION = YES/NO`.

Then stop and request explicit user approval before modifying state/checkpoint to a promoted/final value.

---

# F9 — Data Egress remains closed

F9 is not part of this execution plan.

No package above authorizes:

- web-search queries containing Work/user data;
- new connector sends;
- upload/export to a new destination;
- external destination allowlists;
- broad provider data egress beyond the bounded Q6 native-GYO acceptance already covered by the current provider architecture.

Future F9 design gate should independently cover:

`data classification → destination allowlist → minimization/redaction → per-egress authorization → audit → deny-by-default`.

---

# 5. Package execution order

Locked recommended order:

```text
A0  Preflight/CI topology
 ↓
A1  Full frontend + backend skip visibility in pqg/smoke
 ↓
A2  Frontend code splitting/bundle receipt
 ↓
B   Sandbox handle-bound TOCTOU hardening
 ↓
C   Admin boundary contract reconciliation
 ↓
D   Capability executable-binding validator
 ↓
E1  npm advisory inventory
 ↓
E2  Dependency remediation + backend reproducibility/warnings
 ↓
E3  GitHub Actions upgrade + immutable SHA pins
 ↓
E4  Native current-GYO bounded acceptance
 ↓
G   Branch protection / PR-first governance
 ↓
H1  Evidence normalization
 ↓
H2  Final exact-head automated acceptance
 ↓
H3  Final browser/UAT
 ↓
H4  Final current-GYO receipt
 ↓
H5  State/risk/checkpoint documentation reconciliation
 ↓
H6  STOP → explicit user promotion decision
```

`F` remains deferred unless separately justified. `F9` remains closed.

## 6. Per-package completion template

When a package is finished, update its board row and append a ledger entry with:

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

A package is not `COMPLETE` merely because source was edited; acceptance evidence must satisfy that package's section.

## 7. Execution ledger

### [2026-08-24 06:09:16 UTC+07:00] Master plan initialized

- Status: **ACTIVE**.
- User locked decisions: `Q1=A · Q2=A · Q3=A · Q4=A · Q5=A · Q6=A · Q7=A · Q8=A · Q9=A`.
- Audit/source baseline: `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- Baseline Agent Preflight: Run #10 / `32671953420` SUCCESS, `pqg/preflight=success`.
- Baseline Smoke Test: Run #106 / `32671953411` SUCCESS, `pqg/smoke=success`; backend 516 passed / 81 skipped / 2 warnings; frontend focused 30/30; lint 0/0; type/build/runtime/readiness/cleanup PASS; `smoke-real=SKIPPED`.
- Multi-agent execution is paused; next execution is single-agent and begins at **A0**.
- No implementation/security/dependency/governance/state change was performed by creating this plan.
- F9 remains CLOSED / NOT APPROVED.
