# PQG Workspace — Current Project Memory

> Mutable cross-session snapshot. Live repo/canon/source/evidence overrides this file. Historical detail belongs in `PROJECT_CHANGELOG.md`; this file intentionally records the current working snapshot.

## Memory protocol

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Every new/modified fact, decision, status, test result, approval, gate and limitation in Project Memory must carry its own second-precision timestamp `[YYYY-MM-DD HH:MM:SS UTC±HH:MM]`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Memory-maintenance writes do not recursively require another memory entry; record the underlying project event and evidence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Never store passwords, API keys/tokens, credential values, raw databases/audit dumps, chain-of-thought or unnecessary sensitive personal data.

## Current identity / live tracking

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Active execution mode: SINGLE AGENT; multi-agent remains paused.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Authoritative remediation tracker: `docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md`; execution context: `docs/project-memory/REMEDIATION_MASTER_PLAN_CONTEXT.md`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 source-validation HEAD: `c6b7d1afab3f066a4aa7f99639104441db1d69fa`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Master-plan A0 tracking commit after source validation: `710355d39bbbd64127e70cfdbaa6e42173dfc692`; this is docs-only tracking evidence and must not be represented as the A0 source-validation HEAD.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 source-validation HEAD: `2c1b8238921bd0e99367802cfb29c5218ef87e6f`.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 master-plan tracking commit: `6354ae1efc7d6761238edae961333c9e92a39138`; it is docs-only tracking evidence and does not replace the A1 source-validation HEAD.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 source-validation HEAD: `5fce3270f26f1cac1ffb9d228c63576a47870bc0`; later documentation/memory tracking commits must remain separate from this exact source-validation receipt.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Package B source-validation HEAD: `140df75e907444437844a1328455e6d1c23c7e51`; later documentation/memory tracking commits must remain separate from this exact source-validation receipt.

## Current state / gates

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Project state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Checkpoint remains `PARTIAL`; no checkpoint/state promotion is authorized before H6 explicit user approval.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F7 Resource Catalog + Context Broker remains scoped implementation/validation PASS from earlier evidence; A0 did not modify F7 behavior.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F9 Data Egress remains **CLOSED / NOT APPROVED**.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Migration-maintainability package F remains DEFERRED unless separately justified.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Package B is **COMPLETE** at source-validation HEAD `140df75e907444437844a1328455e6d1c23c7e51`; Package C and every other protected scope remain closed until separately authorized.

## Locked remediation decisions

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] User locked `Q1=A · Q2=A · Q3=A · Q4=A · Q5=A · Q6=A · Q7=A · Q8=A · Q9=A` and explicitly authorized execution of the bounded master plan in sequence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q1 requires real initial/core code splitting with heavy features lazy-loaded; do not hide bundle size only by raising Vite warning limits.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q2 threat model includes a hostile local process and requires handle/descriptor-bound sandbox I/O including Windows-equivalent TOCTOU defenses.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q3 authoritative admin claim is `interactive local-user admin`, not cryptographic proof-of-human; WebAuthn/Windows Hello is outside this plan.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q4 authorizes minimal server-owned capability executable-binding consistency validation without replacing current executors with a mega dispatcher.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q5 requires dependency inventory before selective remediation, deterministic backend CI constraints, and forbids blind `npm audit fix`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q6 requires bounded local-Windows native current-GYO acceptance using existing Credential Manager configuration and synthetic Work; no new GitHub-hosted credential path by default.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q7 final governance is PR-first, requires `pqg/smoke`, blocks force-push/delete, and does not require `pqg/preflight` as merge status under current semantics.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q8: G-SYNTHETIC is scoped synthetic evidence only, never human-usability evidence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Q9: durable local cancellation/terminal state/late-output discard is the v2.2 boundary; remote upstream provider compute/billing stop remains unproven limitation.

## A0 — completed evidence

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 status: **COMPLETE** — Repair preflight and active branch CI topology.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Session-start drift check found live `pqg-workspace` exactly at handoff HEAD `e84cb0a030f6be54ab9f341b6065f562e301f7b0` before A0; no drift was reconciled because none existed.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Fresh pre-implementation bootstrap HEAD `65b36ebe8342b5f7d3ddcdb478db9bab7be44f12`; Agent Preflight Run #11 / ID `32673592829` = SUCCESS and `pqg/preflight=success`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 changed only `.github/workflows/agent-preflight.yml` and `.github/workflows/smoke.yml` from the fresh-preflight HEAD to source-validation HEAD `c6b7d1afab3f066a4aa7f99639104441db1d69fa`; exact compare ahead 4 / behind 0.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Agent Preflight remains path-scoped to its workflow/trigger file but is no longer restricted to historical branch names, so representative task refs can self-trigger exact-ref preflight.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Smoke active push topology is `pqg-workspace`, `work/**`, `security/**`, `maintenance/**`, `integration/**`; historical foundation/remediation push refs were removed after verification that default had advanced beyond both. No branches were deleted.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] New-task-branch `before=000…` committed-diff handling now deepens one commit, resolves parent and executes `git diff --check parent→HEAD`; earlier failed proof attempts are preserved as failure evidence rather than hidden.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Default-source Smoke Run #115 / ID `32673879015`, exact source HEAD `c6b7d1af…` = SUCCESS; normal smoke steps passed; `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Representative zero-SHA branch-creation Smoke Run #116 / ID `32673886997` on `work/a0-verified-topology-proof-20260824` = SUCCESS, including committed-diff validation; `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Final task-ref proof commit `a4fbaacad3fa46be32a6d38a053dd59995ac5c3a`: Agent Preflight Run #15 / ID `32673916000` = SUCCESS with `pqg/preflight=success`; Smoke Run #117 / ID `32673916078` = SUCCESS; `smoke-real=SKIPPED`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 Smoke still used the pre-A1 focused frontend set, so A0 does **not** prove full frontend regression. Full frontend regression and backend skip visibility remain the A1 acceptance target.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 made no application/runtime, dependency/action-major, schema/migration, branch-protection, provider/credential, F9, deployment or checkpoint/state change.

## A1 — completed evidence

- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 status: **COMPLETE** — full frontend regression in `pqg/smoke` plus backend skip visibility.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Current-session drift reconciliation found `pqg-workspace` at A1 source HEAD `2c1b8238921bd0e99367802cfb29c5218ef87e6f`, 12 commits ahead of the handoff docs HEAD; the drift contained prior A0 completion/tracking and A1 work, not an unrelated competing line.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Fresh A1 bootstrap HEAD `50e3bdb83054b3e27d6c20105bfc4e326ce2dd9e` had exact-SHA `pqg/preflight=success` from Agent Preflight Run ID `32674453029` before A1 implementation.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Exact A1 implementation compare `50e3bdb…→2c1b823…` is ahead 1 / behind 0 and modifies only `.github/workflows/smoke.yml` (4 additions / 4 deletions).
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Smoke Test Run #119 / ID `32674524485` on exact A1 source = SUCCESS with `pqg/smoke=success`; normal smoke passed and `smoke-real=SKIPPED`.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Backend A1 result: 597 collected; **516 passed / 81 skipped / 2 warnings** using `pytest -v -ra --tb=short`; visible reasons account for 80 superseded Hermes/ACP cases plus 1 Windows restore-local-data environment case, with no unexplained backend skip observed.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Frontend A1 result: full suite **50 files / 317 tests PASS**; lint **0 warnings / 0 errors** over 144 files / 103 rules; type-check PASS; build PASS.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] Runtime A1 result: migrations through 0038, startup, health/runtime, 7 readiness checks and cleanup PASS.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 residuals: two backend dependency/version warnings, React `act(...)` test stderr warnings, npm 6 vulnerabilities (3 moderate / 3 high), GitHub Actions Node/action-version warnings, and eager/initial frontend chunks above 500 kB. These remain scoped to later packages rather than silently accepted as fixed.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 changed CI test semantics only; no application/runtime behavior, schema/migration, dependency/tool-version, branch protection, auth/security semantic, provider/credential, F9, deployment or state/checkpoint change occurred.

## A2 — completed evidence

- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 status: **COMPLETE** — module/heavy-feature code splitting with deterministic startup-graph receipt.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Fresh A2 exact-ref Agent Preflight was established by trigger commit `f7750190c3c1744f259fb9ef0b25d9c34ab07eda`; Agent Preflight Run #17 / ID `32676695105` completed SUCCESS and published `pqg/preflight=success`.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 source evolution preserved failed validation evidence rather than hiding it: `3a035ee7…` / Smoke #123 failed reporter identification and still exceeded the eager threshold; `ea874f56…` / Smoke #124 fixed startup size but reporter binding failed; `388cd713…` / Smoke #125 remained fail-closed because the inferred EditorPanel manifest record was not a verified dynamic entry; final source-validation HEAD is `5fce3270f26f1cac1ffb9d228c63576a47870bc0`.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 keeps Foundation/core startup surfaces eager where required while lazy-loading optional module surfaces only after projection/attachment eligibility; Settings keeps its Foundation shell and default GYO model settings eager but lazy-loads Marketplace, Memory Hub, Local Data and Runtime Status only when their tabs are selected.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Documents/editor loading is guarded by Work + active/open-file eligibility. A stable dynamic `EditorSurface` facade isolates `EditorPanel`; runtime source scanning verifies `@monaco-editor/react` is imported only by `src/components/EditorPanel.tsx`.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Final exact Smoke Run #126 / ID `32680074013` on source HEAD `5fce3270…` completed SUCCESS and published `pqg/smoke=success`; `smoke-real=SKIPPED` and is not part of A2 PASS evidence.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Backend final A2 regression: 597 collected; **516 passed / 81 skipped / 2 warnings**. Frontend: **50 files / 321 tests PASS**; `ModuleCanvas` focused suite 11 PASS; `SettingsPanel` 7 PASS; lint **0 warnings / 0 errors** over 147 files / 103 rules; type-check PASS; production build PASS.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Final A2 bundle receipt: initial entry `assets/index-DQn4IEj6.js` = **486,620 bytes / 144,605 gzip bytes**; initial static graph = **5 JS requests / 497,075 bytes / 149,128 gzip bytes**; largest eager = **486,620 bytes**, below the unchanged `500 * 1024 = 512,000` gate; largest lazy = **662,650 bytes / 142,278 gzip bytes**.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Deterministic heavy-feature proof: `EditorSurface` is a dynamic manifest entry, `monacoInInitialGraph=false`, `EditorPanel` is downstream of that boundary and `editorPanelInInitialGraph=false`; `MermaidDiagram` is a dynamic manifest entry with `mermaidInInitialGraph=false`.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] Final A2 runtime evidence: migrations through 0038, backend startup, health, runtime status, seven readiness checks and cleanup PASS on exact source HEAD.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 did **not** raise Vite `chunkSizeWarningLimit`; the remaining >500 kB Vite warning is attributable to a non-startup lazy chunk and is recorded rather than hidden. A2 made no dependency/tool-version, schema/migration, security/provider, F9, deployment or state/checkpoint change.

## Package B — completed evidence

- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Package B status: **COMPLETE** — handle/descriptor-bound sandbox hardening is retained and its route/public-contract integration is validated on source HEAD `140df75e907444437844a1328455e6d1c23c7e51`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Fresh isolated checkout `C:\Users\dtron\Documents\PQG-Workspace-Package-B` began clean at live `pqg-workspace` HEAD `22fb38a72dff4d62b30cf6f13311752486625430`; the old F5 checkout and dirty registered worktree were not modified.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact 422 root cause: FastAPI 0.141 lazy router inclusion rebuilt `Dependant` from the replaced secure endpoint's internal signature, exposing `request`, `response`, `conn`, `settings` and idempotency arguments as public query parameters. The fix retains the secure callable identity and binds its inspection metadata to the original public endpoint via `__wrapped__`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Windows nested-write root cause: directory traversal handles unnecessarily requested `DELETE`, causing `NtSetInformationFile` rename of a child to fail with `NTSTATUS 0xC0000043`; removing only that unnecessary parent-handle access preserved HANDLE-relative/reparse protection and restored nested atomic writes.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Source changes are limited to six Package B files: `sandbox_io_posix.py`, `sandbox_io_windows.py`, `security_artifact_create.py`, `security_dirap.py`, `security_overrides.py`, and `test_sandbox_io_b.py`; exact source diff is 78 insertions / 16 deletions and `git diff --check` PASS.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Local validation: representative direct regression 7 PASS; all eight historically failing suites 112 PASS / 1 platform SKIP / 2 warnings; Package B sandbox 12 PASS / 2 warnings; full backend 609 collected, 527 PASS / 82 SKIP / 2 warnings.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact-source Agent Preflight Run ID `32699303000`, job `97347423658` completed SUCCESS and published `pqg/preflight=success`; no separate receipt commit was required because workflow dispatch validated the SOURCE SHA directly.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact-source Sandbox Windows Run ID `32699302690`, job `97347419706` completed SUCCESS with 12 PASS / 2 warnings and published `pqg/sandbox-windows=success`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Exact-source Smoke Run ID `32699302749`, job `97347420230` completed SUCCESS and published `pqg/smoke=success`: backend Linux 528 PASS / 81 SKIP / 2 warnings; frontend 50 files / 321 tests PASS; lint 0 warnings / 0 errors; type-check, build, startup, health/runtime, seven readiness checks and cleanup PASS; `smoke-real=SKIPPED`.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Package B did not widen roots or change dependencies/tools, schema/migrations, auth/approval semantics, providers/credentials, Action Package semantics, F9, deployment, state or checkpoint.

## Current residuals relevant to next packages

- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1's former limited-frontend/hidden-skip finding is closed; `pqg/smoke` now executes the full frontend suite and backend pytest with visible skip reasons.
- [2026-08-24 08:39:57 UTC+07:00][recorded_at] A2 initial/eager >500 kB finding is closed: final largest eager is 486,620 bytes. A 662,650-byte lazy chunk remains intentionally non-startup and continues to trigger Vite's generic >500 kB warning; this is accepted A2 residual, not an eager/startup regression.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] Sandbox pathname TOCTOU finding is closed by Package B at source HEAD `140df75e907444437844a1328455e6d1c23c7e51`; the two backend dependency/version warnings remain assigned to later dependency work rather than hidden.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Admin boundary wording/characterization remains package C; capability executable binding remains package D.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] The Package C admin wording/characterization residual is closed at source-validation HEAD `fe2ad41052fc4cde3ae49543fd9978d12a692d4c`; capability executable binding remains unopened Package D.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Dependency/supply-chain residuals remain for E1–E3: npm baseline 6 vulnerabilities (3 moderate, 3 high), backend reproducibility/warnings, GitHub Actions Node-version warnings and mutable action tags.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Legacy `smoke-real` remains Hermes/ACP and can false-green on skip; E4 must replace it with bounded native current-GYO evidence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Branch protection remains deferred until G after A0, A1 and E3 are truthful/stable prerequisites.

## Next exact action

- [2026-08-24 13:59:57 UTC+07:00][recorded_at] No further implementation package is authorized in this execution. Preserve the Package B source and docs/memory lineage, verify the docs-only child independently, and stop before Package C or any protected scope.
- [2026-08-24 13:59:57 UTC+07:00][recorded_at] If the user later opens Package C, begin from a fresh live fetch and exact-ref Agent Preflight, then follow the master plan without carrying Package B test claims onto a different SHA.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Package C is **COMPLETE** at source-validation HEAD `fe2ad41052fc4cde3ae49543fd9978d12a692d4c`; preserve its exact-source Preflight/Smoke receipts and the separate docs-only tracking child.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Stop after Package C. Package D and all E/G/H/F/F9 work require their own authorization and fresh exact-ref preflight; state/checkpoint remain unchanged.

## Package C — completed evidence

- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Package C reconciled docs, UI wording and the admin dependency contract to **interactive local-user admin**, explicitly excluding any proof-of-human/WebAuthn/Windows Hello claim and documenting the sufficiently privileged hostile-local-process limitation.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Module attach/detach/rename/reorder continue to require loopback, approved Origin, allowed Fetch Metadata and server-owned actor identity. Remote, missing-Origin, cross-origin, cross-site and forged/missing-actor paths fail closed; audit uses the server actor.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] GYO/model-visible CapabilityRegistry remains free of Foundation/provider/Module/privacy/permission/restore/delete/admin-Skill capabilities. Forbidden/unknown lookup returns `capability_not_found` and does not create an approval request.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Source diff: eight files, 127 insertions / 3 deletions; local focused backend 48 PASS, focused frontend 6 PASS, full backend 537 PASS / 82 SKIP / 2 warnings, full frontend 50 files / 322 tests, lint/type-check/build/diff check PASS.
- [2026-08-24 14:37:06 UTC+07:00][recorded_at] Exact-source Agent Preflight Run `32701981820` / job `97355230052` SUCCESS. Smoke Run `32701968596` / job `97355187719` SUCCESS with `pqg/smoke=success`, backend 538 PASS / 81 SKIP / 2 warnings, frontend 50 files / 322 tests and runtime/readiness/cleanup PASS; `smoke-real` job `97355188770` SKIPPED.
