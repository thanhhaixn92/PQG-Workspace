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

## Current state / gates

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Project state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Checkpoint remains `PARTIAL`; no checkpoint/state promotion is authorized before H6 explicit user approval.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F7 Resource Catalog + Context Broker remains scoped implementation/validation PASS from earlier evidence; A0 did not modify F7 behavior.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F9 Data Egress remains **CLOSED / NOT APPROVED**.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Migration-maintainability package F remains DEFERRED unless separately justified.

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

## Current residuals relevant to next packages

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A1 remains required because current Smoke semantics before A1 cover only four focused frontend test files and do not expose/classify backend skip reasons sufficiently.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Initial frontend chunks >500 kB remain A2 scope.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Sandbox pathname TOCTOU against hostile local process remains package B scope.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Admin boundary wording/characterization remains package C; capability executable binding remains package D.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Dependency/supply-chain residuals remain for E1–E3: npm baseline 6 vulnerabilities (3 moderate, 3 high), backend reproducibility/warnings, GitHub Actions Node-version warnings and mutable action tags.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Legacy `smoke-real` remains Hermes/ACP and can false-green on skip; E4 must replace it with bounded native current-GYO evidence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Branch protection remains deferred until G after A0, A1 and E3 are truthful/stable prerequisites.

## Next exact action

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] After A0 master-plan/context/changelog persistence is verified on live `pqg-workspace`, begin **A1 — full frontend regression + backend skip visibility**.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Before A1 implementation edit, re-fetch live default HEAD, self-trigger a fresh Agent Preflight on that exact ref, require workflow SUCCESS + `pqg/preflight=success`, inspect frontend/backend test commands and skip sources, then state A1 exact scope/validation/forbidden boundaries.
