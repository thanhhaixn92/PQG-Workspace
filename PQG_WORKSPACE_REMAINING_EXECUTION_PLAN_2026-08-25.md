# PQG Workspace — Remaining Execution Plan after E3

**Audit date:** 2026-08-25 (UTC+07:00)  
**Repository:** `thanhhaixn92/PQG-Workspace`  
**Default branch:** `pqg-workspace`  
**Live tracking HEAD at audit:** `e5885bed15c5636254b468f11341d0c7b72df805` — `docs: close E3 tracking receipt`  
**Full-validated E3 source anchor:** `b11120749a13334456ce409cd5ecab6a2b731bdc` — `ci: pin GitHub Actions toolchain`  
**State/checkpoint:** `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`  
**F9 Data Egress:** `CLOSED / NOT APPROVED`  
**Branch protection:** OFF / unprotected at audit  
**Purpose:** define the smallest, fail-closed execution path from the post-E3 baseline through E4, G and H1–H6 without widening scope.

---

## 1. Authority and evidence discipline

Before every package, follow the live repository authority order rather than this plan if a conflict appears:

1. `docs/00_PROJECT_CANON.md`
2. `AGENTS.md`
3. `PROJECT_STATE.md`
4. `AI_STATE.json`
5. `docs/implementation/CURRENT_CHECKPOINT.md`
6. `docs/AI_AGENT_ROUTING.md`
7. task-specific canon/security/data model
8. current source/public contracts/focused tests
9. `docs/14_AGENT_OPERATING_CONTRACT.md`
10. Project Memory/Context
11. historical handoffs/chat

This file is a planning artifact. It does **not** authorize protected operations and does not override live authority.

Evidence labels are exact: `PASS`, `FAIL`, `SKIPPED`, `NOT RUN`, `BLOCKED-UPSTREAM`, `PARTIAL`.  
Never convert:

- tracking equivalence into runtime execution on a tracking SHA;
- `smoke-real=SKIPPED` into provider PASS;
- old source receipts into validation of a newer source SHA;
- synthetic evaluator results into human-usability evidence;
- local cancellation into proof that remote provider compute/billing stopped.

For source changes:

`fresh fetch → exact-ref Agent Preflight → read authority/source/tests → bounded mutation → focused validation → proportional/full validation → exact diff review → exact-source CI/acceptance → material docs/memory closeout → STOP at next protected gate`.

---

## 2. Audited baseline and completed work

The following packages are accepted as completed under their existing evidence:

- A0, A1, A2
- B, C, D
- E1
- E2-A, E2-C, E2-D, E2-E
- P-TRACK
- P-MEM
- E3

E2 remains `IN PROGRESS` only because:

- **E2-B — Monaco bundled DOMPurify = BLOCKED-UPSTREAM.**

Current E3 evidence chain:

- E3 source: `b11120749a13334456ce409cd5ecab6a2b731bdc`
- Agent Preflight: `32749299759` — PASS
- Windows Sandbox: `32749299689` — PASS
- full Smoke: `32749299548` — PASS
- exact source status: `pqg/smoke-full=success`, `pqg/smoke=success`
- source payload: backend `551 passed / 81 skipped / 2 warnings`; frontend `54 files / 334 tests PASS`; lint/type/build/runtime/readiness/cleanup PASS
- docs tracking child: `e5885bed15c5636254b468f11341d0c7b72df805`
- tracking run: `32756972978`
- exact child status: `pqg/tracking-integrity=success`, `pqg/smoke=success`; `smoke-full=SKIPPED` as expected

No package receipt promotes project state by itself.

---

## 3. Critical audit findings that constrain the remaining plan

### 3.1 E4 legacy `smoke-real` is not an acceptable current-GYO gate

Current `.github/workflows/smoke.yml` still has a `smoke-real` job that:

- is Hermes/ACP based, not `GyoOrchestrator`;
- installs backend dependencies via unconstrained `pip install -e ".[dev]"`;
- installs `hermes-agent`;
- configures auth from GitHub secrets;
- starts legacy Hermes ACP;
- exits success with `SystemExit(0)` when Hermes authentication is not ready.

Therefore E4 must **retire the active semantic**, not merely rename it. A credential-unavailable path must never look like a green real-provider acceptance result.

Normal provider-independent CI may keep historical compatibility keys such as the `hermes` readiness field if current public/API tests still depend on them. E4 must not opportunistically rename that compatibility contract.

### 3.2 Native current GYO already has the necessary policy seams

Current source confirms:

- `GyoOrchestrator` is provider-neutral.
- Supported adapters: `openai_responses` and `openai_compatible`.
- Provider credentials come from the OS keyring/Windows Credential Manager.
- provider output is untrusted;
- Work mutation remains Action Proposal → server validation → Action Package → explicit approval → idempotent executor;
- cancellation is cooperative locally and durable state rejects late output;
- routing metadata is persisted without credentials;
- the F7 Context Broker applies `discover metadata → SECURITY FILTER → rank → hydrate → pack`.

E4 should exercise the existing Assistant REST/SSE API boundary rather than call provider adapters directly except for narrow instrumentation.

### 3.3 Existing E2 real-provider runner is valuable and should remain historical evidence

`scripts/run-package-e2-bounded-real-provider.py` already implements several correct patterns:

- reads provider/model metadata only from the current local configuration;
- reuses only an opaque credential reference through the keyring;
- does not copy credential values into evidence;
- creates a newly migrated temporary SQLite DB and temporary workspace;
- uses a free model and disables fallback in the disposable DB;
- sets one provider request budget;
- records source hashes and a runner hash;
- uses synthetic Work data;
- does not mutate Work before approval;
- advances into Action Package execution only when the provider emits one valid proposal;
- verifies idempotency, approval hash binding, exactly-once execution and expected audit events;
- returns `NOT_RUN` rather than fabricating proposal success.

Do **not** rewrite or relabel old E2 evidence. E4 should reuse these design patterns in a new E4 harness.

### 3.4 Existing browser/fidelity harness should be reused for H3

`scripts/start-package-f-native-fidelity.ps1` and its finalizer already provide:

- temporary DB/workspace;
- ephemeral loopback ports;
- provider disabled;
- no credential access;
- immutable evidence roots;
- source fingerprint;
- screenshots/artifact manifests;
- reduced-motion, keyboard/focus, reflow, 409, offline/retry, pending approval and native Chrome 200% zoom scenarios.

H3 should extend/reuse this infrastructure only as necessary. Do not create a second generic browser testing framework.

### 3.5 Fidelity is still technically PARTIAL

`V22_FIDELITY_LEDGER.md` has strong representative evidence, including native Chrome 200% zoom, but many screen × state × viewport cells remain `NOT RUN`. H3 must freeze a finite required matrix and close those required rows explicitly; no inference from representative screenshots.

### 3.6 Five-person human usability remains deferred

`V22_USABILITY_PROTOCOL.md` explicitly says `DEFERRED POST-V2.2`. It remains `0/5 NOT RUN` and cannot be called human evidence. The existing G-SYNTHETIC result is synthetic evidence only.

### 3.7 E2-B remains upstream-blocked at audit time

At this audit, npm still marks `monaco-editor 0.56.0` as latest stable. Upstream issue `microsoft/monaco-editor#5454` remains open and states that the shipped 0.56.0 artifacts bundle DOMPurify 3.4.8, which cannot be fixed by a downstream consumer override/dedupe.

Therefore:

`E2-B = BLOCKED-UPSTREAM`

Do not add an npm override or claim closure. Recheck immediately before H1/H2.

### 3.8 Current docs contain stale/superseded narratives

Material reconciliation belongs in H5, not in standalone cleanup commits. Known examples:

- `PQG_GYO_PROVIDER_CORE.md` still says no real provider is configured.
- `AI_RISK_REGISTER.md` contains older proposal/fidelity/dependency narratives.
- `V22_REQUIREMENTS_TRACEABILITY.md` contains superseded branding/Hermes evidence rows.
- current Memory/Master Plan were written before the E3 docs child received its own tracking receipt.

Do not create receipt-only recursion. Fold these into the next material package where appropriate and the comprehensive H5 reconciliation.

---

# 4. Locked remaining execution order

```text
E4 → G → PRE-H1 E2-B RECHECK → H1 → H2 → H3 → H4 → H5 → H6
```

`F` remains **DEFERRED**.  
`F9` remains **CLOSED / NOT APPROVED**.

If an H3 or H4 finding requires a source correction, the final candidate SHA is invalidated:

```text
bounded corrective PR
→ fresh exact-head H2
→ H3
→ H4
```

Do not carry PASS evidence from an older source onto a corrected source.

---

# 5. Protected approval map

| Gate | May do read-only discovery without new approval? | Protected approval required before mutation/run? |
|---|---:|---|
| E4 discovery | YES | — |
| E4 source changes + credential/keyring/network acceptance | limited planning only | **YES — fresh E4 approval** |
| G governance discovery | YES | **YES — branch protection/repository governance** |
| Pre-H1 Monaco recheck | YES | only if an upstream-fixed dependency update is proposed |
| H1 evidence matrix | YES | normally no protected approval |
| H2 automated validation | YES | approval only for any protected corrective mutation |
| H3 synthetic browser/UAT | YES | no provider/real-data approval; protected fix scope still gated |
| H4 final provider run | discovery yes | **YES — provider/network/credential rerun** unless prior E4 approval explicitly covers H4 |
| H5 docs reconciliation | YES | no state promotion |
| H6 readiness report | YES | **explicit approval required before state/checkpoint mutation** |

The user request that produced this plan is **not itself E4 provider/network/credential approval**, **not G governance approval**, and **not H6 promotion approval**.

---

# 6. Package E4 — Retire legacy real-smoke and establish native current-GYO acceptance

## E4.0 — Fresh discovery / hard-stop preparation

Before any implementation write:

1. Re-fetch `pqg-workspace`.
2. Expected current HEAD is `e5885bed15c5636254b468f11341d0c7b72df805`; if it differs, inspect/reconcile drift before using this plan.
3. Obtain a fresh exact-ref Agent Preflight success.
4. Read:
   - `AGENTS.md`
   - `PROJECT_STATE.md`
   - `AI_STATE.json`
   - `docs/implementation/CURRENT_CHECKPOINT.md`
   - `docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md`
   - `docs/project-memory/PROJECT_CONTEXT.md`
   - `PROJECT_MEMORY.md`
   - latest changelog
   - `CODEGRAPH.md`
   - `docs/04_SECURITY_PERMISSION_POLICY.md`
   - `backend/app/api/assistant.py`
   - `backend/app/services/gyo_orchestrator.py`
   - `backend/app/services/gyo_registry.py`
   - `backend/app/services/context_broker.py`
   - `.github/workflows/smoke.yml`
   - `scripts/run-package-e2-bounded-real-provider.py`
   - focused Assistant/provider/AP tests.
5. Inventory provider/model metadata through safe DB/API reads only:
   - IDs/display names/provider types/model identifiers/cost class/enabled/default state;
   - do not print base URLs if not needed;
   - do not read/resolve credential values during discovery;
   - do not make outbound provider requests.
6. Confirm current fallback setting and candidate free model metadata.
7. Produce an E4 implementation diff proposal.

Then **STOP for explicit E4 approval** before:
- keyring/credential availability lookup;
- provider network request;
- source mutation that establishes the protected E4 acceptance path;
- any real-provider run.

## E4 approval wording to request

Use a bounded request substantially equivalent to:

> Phê duyệt Package E4 — native current-GYO acceptance. Cho phép retire active legacy Hermes/ACP `smoke-real` job from canonical Smoke; add a local Windows native-GYO acceptance harness using only temporary SQLite/workspace and synthetic Work; read existing provider/model metadata and resolve the existing Credential Manager credential by opaque reference without printing/copying/mutating it; send a bounded number of real requests only through the current GYO/Assistant path; select an existing enabled free model manually and disable fallback in the disposable DB; record only redacted provenance. No new GitHub-hosted secret/provider path, no provider/profile/default/credential mutation, no real user data, no F9, no schema/migration, no deploy, no state/checkpoint promotion. Provider-generated Action Proposal is NOT RUN if absent within the fixed request budget; do not retry merely to hunt a proposal. Stop after E4 before G.

## E4.1 — Source changes after approval

Expected minimal source scope:

1. `.github/workflows/smoke.yml`
   - remove/retire active legacy `smoke-real`;
   - do not replace it with GitHub-hosted real-provider secrets;
   - keep normal provider-independent Smoke intact;
   - preserve P-TRACK classification/aggregate semantics;
   - keep runtime compatibility fields unless separately approved.

2. Add a dedicated local E4 runner, recommended:
   - `scripts/run-e4-native-gyo-acceptance.py`
   - optional narrow PowerShell wrapper only if required for reliable Windows lifecycle.

3. Focused test changes only where needed to lock:
   - legacy `smoke-real` no longer exists as an active success semantic;
   - E4 receipt schema/redaction;
   - bounded request count/fallback disabled;
   - source SHA/fingerprint binding;
   - credential value never serialized;
   - `NOT_RUN` remains non-zero/explicit where appropriate.

Do not mutate:
- E2 historical runner unless a demonstrated correctness defect requires it;
- provider profile/default;
- stored credential;
- Action Package semantics;
- schema/migrations;
- E3 action pins/tool versions;
- F9.

## E4.2 — Native acceptance harness contract

The new runner must:

- require exact source identity (`git rev-parse HEAD` plus source hashes/fingerprint);
- create a fresh temp DB by running current migrations;
- create a fresh temp workspace;
- use synthetic Work/Conversation/Thread only;
- seed only the chosen provider/model metadata into the temp DB;
- use the same OS keyring service and opaque credential reference;
- never print or persist the credential;
- accept only an existing enabled free model for the bounded gate;
- use `route_mode=manual`;
- set `auto_fallback_enabled=0` in the disposable DB;
- one process owner, deterministic cleanup;
- evidence under a new immutable root such as:
  `output/e4-native-gyo/package-e4-native-<timestamp>/`;
- never reuse an evidence directory;
- capture only redacted metadata, hashes, IDs needed for provenance and pass/fail assertions;
- return distinct non-zero codes for `FAIL` and `NOT_RUN`.

### Recommended real-request budget

Use at most **3 provider requests**:

**R1 — Stream + context/source + persistence**
- create synthetic Work with a unique harmless sentinel;
- preferably create/register one structurally validated synthetic `.md`/`.txt` artifact through existing APIs if possible without widening scope;
- create/resolve the conversation-bound Assistant thread;
- subscribe to `/api/assistant/threads/{thread_id}/stream`;
- call `/api/assistant/threads/{thread_id}/runs` with the selected model manually;
- prove at least one token event or a completed real provider turn;
- prove terminal durable status;
- inspect returned persisted parts and `/api/assistant/context-manifest`;
- prove expected Work/context/source inclusion;
- prove no raw local path, credential or denied-resource metadata is present;
- prove exactly one provider dispatch for R1.

**R2 — Cancellation + late-output discard**
- start a bounded response through the normal `/runs` path;
- cancel the running Assistant turn through the existing cancel endpoint;
- terminal DB state must be `cancelled`;
- cancel audit/provenance must be present;
- after a bounded grace window, no late provider text may replace the cancelled durable terminal state;
- receipt must explicitly state:
  - local durable cancellation/late-output discard = PASS when observed;
  - remote provider compute/billing stop = `NOT PROVEN`.

If the provider completes before cancellation can be issued, report the cancellation scenario `NOT RUN`/inconclusive rather than falsifying a cancel PASS. A retry is allowed only when it stays within the fixed R2 budget and is designed to execute the same scenario, not to hunt a favorable response.

**R3 — Proposal-intent**
- one synthetic Work-update request only;
- no fallback;
- no repeated prompt variations solely to hunt an Action Proposal.

If one contract-valid provider-generated proposal appears:
- prove the proposal is inert;
- optionally continue through the existing safe Action Package lifecycle in the disposable DB:
  - package creation;
  - idempotent replay;
  - no mutation before approval;
  - explicit approval/hash binding;
  - exactly-once executor;
  - expected audit events.

If no valid proposal appears:
- set `provider_generated_action_proposal=NOT RUN`;
- this does not fail E4 by itself;
- retain automated AP/executor tests as separate evidence.

## E4.3 — E4 validation

Before source commit:
- Python compile for new runner;
- focused E4/Assistant/provider/AP tests;
- focused security/redaction tests;
- `git diff --check`;
- exact diff review;
- no secret/base64/token output;
- full backend if E4 changes Python source/tests;
- full frontend only if frontend touched.

After source publish:
- exact-source Agent Preflight PASS;
- exact-source full `pqg/smoke-full=success`;
- canonical `pqg/smoke=success`;
- Windows Sandbox PASS if its trigger/scope changes or E4 touches relevant shared backend/security files;
- local Windows E4 real-provider receipt on the **same source SHA**.

`smoke-real` must no longer be an active legacy acceptance job.

## E4.4 — E4 closeout

Update Master Plan + Project Memory + append-only Changelog once, materially.

Record:
- exact E4 source SHA;
- exact normal CI runs;
- exact local E4 receipt;
- provider/model profile IDs only as safe provenance;
- request counts;
- stream/context/source/cancel outcomes;
- AP outcome `PASS` or `NOT RUN`;
- remote compute stop `NOT PROVEN`;
- cleanup result;
- excluded scope.

Then STOP before G.

---

# 7. Package G — PR-first repository governance

## G.0 — Discovery

Requires fresh explicit G approval before mutation.

Read-only discovery:
- confirm branch still unprotected;
- confirm repository permissions/features;
- confirm exact canonical required status name remains `pqg/smoke`;
- confirm PR events always take full mode under P-TRACK;
- identify GitHub plan/API constraints for a single-user public repository.

Do not add extra controls just because GitHub supports them.

## G approval wording to request

> Phê duyệt Package G — PR-first branch governance cho `pqg-workspace`. Cho phép require pull request before merge, require canonical `pqg/smoke`, block force-push and branch deletion, while not requiring `pqg/preflight`, `pqg/smoke-full`, or `pqg/tracking-integrity` directly. Preserve a workable single-owner merge path; do not add CODEOWNERS, mandatory approving-review count, signed commits, merge queue, deployment environments or unrelated repository policy unless a live GitHub constraint makes one unavoidable and it is reported first. Prove behavior with one representative non-destructive PR. Do not open H source work until G acceptance is complete.

## G.1 — Target rule

Target:

```text
branch: pqg-workspace
require pull request: YES
required check: pqg/smoke
force push: DISABLED
branch deletion: DISABLED
pqg/preflight required: NO
pqg/smoke-full required: NO
pqg/tracking-integrity required: NO
```

Do not require 1 approval if that would deadlock a single-user repository unless the user separately asks for it.

## G.2 — Proof PR

Use a tiny non-destructive proof branch/change.

Prove:
1. before `pqg/smoke` completes, merge is blocked;
2. PR uses full mode;
3. `pqg/smoke-full=success`;
4. canonical `pqg/smoke=success`;
5. merge eligibility becomes allowed once required checks pass.

Do not test force-push/delete by performing destructive operations; inspect the live rule.

After G, all H material source/docs mutations use:
`feature branch → PR → full pqg/smoke → governed merge`.

---

# 8. Mandatory PRE-H1 E2-B recheck

Immediately before H1/H2:

1. Query latest stable `monaco-editor`.
2. Inspect npm manifest.
3. Inspect **actual shipped ESM artifact**.
4. Inspect actual min/distributed artifact.
5. Resolve the then-current DOMPurify safe floor/advisories.
6. Check upstream issue/fix/release state.
7. Run current PQG npm audit/inventory.

### Branch A — still bundled-vulnerable
Record:
`E2-B = BLOCKED-UPSTREAM`
with exact versions/artifact evidence, conditional reachability, mitigations and limitations. Continue H1 only under existing residual policy.

### Branch B — stable upstream release fixes the distributed sanitizer
STOP before H1 and request dependency/security approval for the smallest Monaco upgrade. Do not silently upgrade inside H1.

Never:
- close E2-B with npm override/dedupe;
- vendor-patch without separate approval;
- call a manifest-only version bump proof of distributed-artifact remediation.

---

# 9. H1 — Authoritative evidence normalization

Create:
`docs/implementation/V22_FINAL_EVIDENCE_MATRIX.md`

This is evidence normalization, not product implementation.

Required columns:

| Gate/Feature | Source SHA | Tracking/docs SHA | Run/artifact | Status | Proves | Does not prove | Supersedes | Residual/owner |
|---|---|---|---|---|---|---|---|---|

At minimum cover:
- A0/A1/A2
- B/C/D
- E1 and E2-A/B/C/D/E
- P-TRACK / P-MEM
- E3
- E4
- F7
- durable Assistant runs/SSE/cancel
- AP/executor automated evidence
- real provider/native GYO
- fidelity/browser
- G-SYNTHETIC
- Windows Sandbox
- canonical full Smoke
- branch governance.

Hard rules:
- Source runtime SHA and docs/tracking SHA are separate.
- `pqg/smoke-full`, `pqg/tracking-integrity` and aggregate `pqg/smoke` are separate evidence kinds.
- Historical evidence is marked `SUPERSEDED`, not erased.
- 5-person usability remains deferred/NOT RUN.
- E2-B remains exact current status after recheck.

H1 should not change runtime behavior or state/checkpoint.

---

# 10. H2 — Final exact-head automated acceptance

## H2.0 — Freeze final candidate

After H1 merges through governed PR, define one candidate source SHA.

From this point:
- H3 and H4 must test that same source tree.
- any source correction invalidates the candidate and restarts H2.

## H2.1 — Backend

Run:
- full backend pytest with skip reasons;
- classify every skip;
- inventory warnings/stderr;
- startup/import compile;
- fresh temp DB migration/startup;
- health/runtime/readiness/cleanup;
- Action Package/idempotency/security regressions;
- capability executable-binding regressions;
- F7 Context Broker security/leakage tests;
- sandbox tests including Windows hostile-swap evidence.

Current two backend warnings may remain only if the exact same upstream provenance is reproduced:
- MCP/pydantic-settings `IncompleteFieldDefinitionWarning`;
- FastAPI/Starlette TestClient `StarletteDeprecationWarning`.

No silent suppression, MCP v2 migration or `httpx2` just to make output quiet.

## H2.2 — Frontend

Run:
- full Vitest;
- lint;
- type-check;
- production build;
- A2 bundle/startup graph receipt;
- full `npm audit --json`;
- production `npm audit --omit=dev --json`.

Review every remaining React `act(...)` stderr warning:
- fix test scheduling/await semantics where it is a real test-hygiene defect;
- otherwise classify with exact provenance and justification.
Do not create a separate P-TEST package.

## H2.3 — Dependency/supply-chain

- backend constraints validator;
- exact pip bootstrap/`pip check` in canonical CI;
- verify E3 official Action pins remain immutable and expected;
- no Node20-target action deprecation;
- fresh E2-B status recorded.

## H2.4 — Exact-source CI

Require:
- exact-head Agent Preflight success;
- exact source full Smoke;
- `pqg/smoke-full=success`;
- `pqg/smoke=success`;
- Windows security/sandbox evidence success.

No unexplained warning, stderr or skip may be silently ignored.

---

# 11. H3 — Final current-source technical browser/UAT

H3 is **not** the deferred five-person study.

## H3.0 — Reuse existing infrastructure

Start from the Package-F native fidelity harness and finalizer. Extend only the missing finite matrix needed to cover current-source primary surfaces and required states.

Freeze the matrix in the ledger **before execution**. Do not grow it opportunistically after seeing results unless a defect demands a targeted rerun.

## H3.1 — Breakpoint edge shell/navigation

Validate shell/navigation at:
- 389 / 390 / 391
- 767 / 768 / 769
- 1023 / 1024 / 1025

These rows only need shell/navigation expectations unless a specific defect requires full-content testing.

## H3.2 — Representative full-content viewports

Use:
- 390×667
- 1024×600
- 1440×900

Primary surfaces:
- Home/Overview
- Work list
- Work dashboard
- Plan
- Conversations
- GYO
- Documents/editor
- Reports
- Knowledge
- Review
- Memory Hub
- Capabilities
- Settings

Applicable states:
- empty
- populated
- loading
- error
- offline/retry
- approval pending
- long content
- 409 stale/scope conflict
- attached/detached/projection loading/error where applicable.

Each required row is:
`PASS`, `FAIL`, or `N/A + rationale`.
No blanks.

## H3.3 — Accessibility/reflow

Required:
- keyboard-only navigation;
- visible focus;
- Escape close;
- drawer/modal focus trap and restore;
- body-scroll behavior where applicable;
- reduced motion;
- 320px reflow / 400%-equivalent;
- native Chrome 200% zoom on the current candidate.

## H3.4 — Isolation/evidence

- temp SQLite;
- temp workspace;
- loopback only;
- no real user data;
- provider disabled for H3;
- source fingerprint;
- browser/version;
- console errors;
- overflow/clipping;
- screenshot hash/manifest;
- cleanup/ports closed.

If H3 finds a product bug that needs source change:
- create one bounded corrective PR;
- merge under G;
- restart H2 → H3.

---

# 12. H4 — Final current-GYO exact-source receipt

H4 uses the same source candidate that passed H2/H3.

Fresh provider/network/credential approval is required unless the E4 approval explicitly stated that it also authorizes this final exact-source rerun.

Reuse the E4 harness and constraints:
- temp DB/workspace;
- existing free model;
- manual selection;
- fallback disabled;
- bounded request count;
- redacted evidence;
- no credential mutation;
- no real data.

Prove:
- real provider dispatch;
- stream/token behavior;
- context/source provenance;
- durable persistence;
- cancellation and late-output discard if the bounded scenario can exercise it;
- exact source SHA;
- cleanup.

Provider-generated Action Proposal:
- `PASS` only if naturally emitted within the fixed request budget;
- otherwise `NOT RUN`;
- never retry merely to hunt it.

Always state:
`remote provider compute/billing stop = NOT PROVEN`.

If H4 reveals a runtime defect requiring source mutation:
- bounded corrective PR;
- restart H2 → H3 → H4.

---

# 13. H5 — Documentation/state-evidence reconciliation

One material docs PR. Do not promote state.

Review and reconcile at minimum:

- `PROJECT_STATE.md`
- `AI_STATE.json`
- `docs/implementation/CURRENT_CHECKPOINT.md`
- `AI_RISK_REGISTER.md`
- `docs/05_ACCEPTANCE_EVALUATION.md`
- `docs/implementation/PQG_GYO_PROVIDER_CORE.md`
- `docs/implementation/V22_FIDELITY_LEDGER.md`
- `docs/implementation/V22_REQUIREMENTS_TRACEABILITY.md`
- `docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md`
- `docs/implementation/V22_FINAL_EVIDENCE_MATRIX.md`
- `docs/project-memory/PROJECT_CONTEXT.md`
- `docs/project-memory/PROJECT_MEMORY.md`
- append-only `PROJECT_CHANGELOG.md`.

Reconcile:
- E3 tracking child accepted;
- current provider/model claims;
- legacy Hermes acceptance marked superseded;
- E4/H4 actual native-GYO results;
- AP exact status;
- cancellation limitation;
- E2-B current status;
- H3 final fidelity status;
- G-SYNTHETIC synthetic-only;
- five-person usability deferred/NOT RUN;
- current live branch protection;
- exact final candidate source.

Keep:
- `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`
- `PARTIAL`
- `human_approval_required=true`

H5 is **not** state promotion.

---

# 14. H6 — Final promotion decision

## H6-A — Read-only final gate report

Produce a final report containing:

- exact final source HEAD;
- exact governed docs HEAD if different;
- complete evidence matrix;
- completed packages;
- current P0/P1 findings;
- accepted residuals;
- every `NOT RUN` / `SKIPPED`;
- deferred items;
- five-person usability limitation;
- E2-B current status;
- native-GYO AP status;
- cancellation limitation;
- branch governance state;
- F9 status;
- out-of-scope list.

End with exactly one verdict:

```text
READY FOR PROMOTION = YES
```

or

```text
READY FOR PROMOTION = NO
```

Do not lower a P1 severity solely to make the verdict pass.

If E2-B remains a P1 `BLOCKED-UPSTREAM` and current authority does not explicitly permit promotion with that accepted residual, verdict must remain `NO` until the user explicitly accepts the residual or upstream closure occurs.

## H6-B — Explicit promotion approval

Only after the user explicitly approves promotion:

- update coordinated project state/checkpoint documents;
- update `AI_STATE.json`;
- update Memory/Changelog;
- use governed feature branch + PR;
- run full exact-source `pqg/smoke`;
- verify live post-merge state.

Never open F9 as part of promotion.

---

# 15. F and F9

## F — Migration registry maintainability

Remain `DEFERRED`.

Reopen only if:
- a new migration becomes necessary;
- an actual correctness failure appears;
- current registry debt blocks a required remaining gate;
- or the user explicitly opens it.

Do not “clean up” migration infrastructure during H packages.

## F9 — Data Egress

Remain `CLOSED / NOT APPROVED`.

No remaining package authorizes:
- Work/user-data web-search queries;
- connector sends;
- external upload/export;
- new destination allowlists;
- external email/message;
- broad provider egress beyond the narrowly approved GYO provider request;
- automatic Memory/Skill transmission.

---

# 16. Commit/receipt strategy to minimize evidence recursion

Recommended:

```text
E4
  source commit
  → exact-source CI + local native-GYO receipt
  → one material docs/memory closeout
  → STOP

G
  governance configuration + proof PR
  → one material reconciliation
  → STOP

PRE-H1
  read-only Monaco recheck
  → no receipt-only commit unless material state/evidence changes

H1
  one governed evidence-matrix PR

H2
  validation only
  → if source correction needed, one bounded PR and restart H2

H3
  evidence only where possible
  → source fix invalidates candidate and restarts H2

H4
  validation only
  → source fix invalidates candidate and restarts H2

H5
  one comprehensive docs reconciliation PR

H6
  read-only verdict
  → explicit approval
  → one promotion PR
```

Avoid:
`docs receipt → receipt of receipt → correction of receipt → another receipt`.

---

# 17. Per-package final report format

Every package report should state:

```text
Package:
Status:
Starting branch/HEAD:
Preflight exact HEAD/run:
Source-validation HEAD:
Tracking/docs HEAD if any:
Files changed:
Protected approval used:
Focused tests:
Full regression:
Linux evidence:
Windows evidence:
Provider/network evidence:
PASS:
FAIL:
SKIPPED:
NOT RUN:
Warnings/residuals:
What this proves:
What this does NOT prove:
Scope explicitly not changed:
Next gate:
```

No package may silently advance into the next protected gate.

---

# 18. Immediate next action

The next executable action is **E4 discovery only**:

1. verify live HEAD;
2. fresh exact-ref Agent Preflight;
3. read current authority and E4 source/tests;
4. inventory safe provider/model metadata without resolving credentials or making network requests;
5. prepare exact bounded E4 diff/validation proposal;
6. **STOP and request explicit E4 provider/network/credential approval**.

Do not start G, H1 or state promotion from the current generic continuation request.
