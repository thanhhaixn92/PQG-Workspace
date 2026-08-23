# PQG Workspace — Project Changelog

> Append-only cross-session ledger. Do not rewrite historical entries; corrections are new timestamped entries.

## Ledger rules

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi entry phải có timestamp chính xác đến giây theo format `[YYYY-MM-DD HH:MM:SS UTC±HH:MM]`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi fact/update trong Project Memory phải tự mang timestamp; timestamp cấp file/section không thay thế timestamp từng nội dung.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi entry nên ghi source/actor, scope, what changed, file/commit/run, evidence/result, limitation, gate effect và provenance.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Correction/supersession phải append entry mới với timestamp mới; không xóa/sửa lịch sử để làm chronology đẹp hơn.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Memory-maintenance writes chỉ để đồng bộ snapshot/ledger không cần tự tạo thêm một vòng recursive log; ledger phải phản ánh underlying project event và relevant commit/evidence khi biết.

## Entries

### [2026-08-23 23:51:19 UTC+07:00] Cross-session project memory system initialized

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Type: documentation / memory governance.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Scope: docs-only; không thay đổi code/runtime/schema/security boundary.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Created `docs/project-memory/PROJECT_CONTEXT.md` via commit `74e2193f27c88e856d2d615d554fe9c4e5e2ffc2`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Created `docs/project-memory/PROJECT_MEMORY.md` via commit `1b88bee7e879f4a9bcba6fed98a9f8d815f3ac1b`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Memory protocol requires second-precision timestamp on every new/modified fact, decision, status, test result, approval, gate and limitation.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Baseline live state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] R1 code-validation baseline remains HEAD `2759d8ce9de0256bb4175a99046ec768011aa422`; docs/memory commits do not inherit that CI validation claim.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] F7 remains not opened for writes by generic continuation language.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] F9 Data Egress remains CLOSED / NOT APPROVED.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Project Memory initialization result: PASS for documentation persistence only; no runtime acceptance claim is created.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Provenance: explicit user request in ChatGPT Project session plus current repo/state evidence read during initialization.

### [2026-08-23 23:53:22 UTC+07:00] Memory governance integrated into agent contract

- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Type: documentation / agent continuity governance.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `docs/project-memory/PROJECT_CHANGELOG.md` persistence commit before this reconciliation: `b583467fa0019193500cd78cf692e2fd317d05db`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `AGENTS.md` updated to require reading `PROJECT_CONTEXT.md`, `PROJECT_MEMORY.md` and latest `PROJECT_CHANGELOG.md` entries for cross-session work; commit `9dc4ffbddff067ba43dd94ed44dcafd13133f069`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `AGENTS.md` now requires each new/modified memory fact, decision, status, test result, approval, gate or limitation to carry `[YYYY-MM-DD HH:MM:SS UTC±HH:MM]` timestamp to seconds.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `PROJECT_CONTEXT.md` updated with non-recursive memory synchronization rule; commit `a7aa3a2fbcfb6f14b4ddb51a528e6af2ba707447`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `PROJECT_MEMORY.md` reconciled with current memory-governance state; commit `6f01deb74dc3d5008deafe8fb12502bb6aabb002`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Result: PASS for docs/memory governance persistence only; no runtime/test/security acceptance claim is introduced.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Gate effect: F7 remains unopened; F9 remains closed; checkpoint/state unchanged.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Provenance: explicit user request in current ChatGPT Project session.

### [2026-08-24 01:02:02 UTC+07:00] Remediation branch created; implementation blocked by mandatory preflight runtime mismatch

- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Source/actor: ChatGPT Project session following explicit user request to proceed with remediation edits.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Intended non-protected scope: CI topology remediation plus Foundation Module projection fail-closed UX/tests; auth/security-boundary, migration, dependency/tool-version, F7 and F9 changes remain outside scope.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Created remote branch `remediation-r1-ci-module-failclosed-20260824` from `cbd4d899ca30e8d2585917447858a225574af17a`; no runtime/source/test file was modified before the blocker was detected.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Mandatory `scripts/agent-preflight.ps1` was NOT RUN because the available execution runtime has neither PowerShell nor `cmd.exe`; the agent did not substitute an emulated check or silently bypass the repository contract.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Result: implementation NOT STARTED; focused tests, lint, type-check, build and `git diff --check` for the intended remediation are NOT RUN.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Gate effect: state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened; F9 remains CLOSED / NOT APPROVED; no checkpoint/state promotion.
- [2026-08-24 01:02:02 UTC+07:00][recorded_at] Next exact action: run the mandatory preflight from a Windows-capable checkout of `remediation-r1-ci-module-failclosed-20260824`, then implement only the approved non-protected remediation scope and validate it before any PASS claim.

### [2026-08-24 01:34:40 UTC+07:00] CI topology and Module projection remediation validated

- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Source/actor: explicit user remediation request plus narrow bootstrap approval; source, commit and GitHub Actions evidence below were independently verified in this session.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Type/scope: non-protected remediation for CI branch topology and Foundation Module projection fail-closed behavior/tests; protected auth/security, migration, dependency/tool-version, deployment, F7 and F9 scopes were not opened.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Bootstrap added `.github/workflows/agent-preflight.yml`; Windows `Agent Preflight` Run #2, ID `32657803755`, HEAD `738e3c6e48ce7323342fd3c308699190987359b1`, conclusion `success`.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Preflight evidence before implementation: state `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`, `human_approval_required=True`, modified=0, untracked=0 and `git diff --check exit: 0`; this is pre-edit evidence, not a post-edit diff check.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Changed implementation scope: `.github/workflows/smoke.yml`, `frontend/src/foundation/shell/ModuleCanvas.tsx`, `ModuleCanvas.test.tsx`, `LeftNavigation.tsx`, `LeftNavigation.test.tsx`; bootstrap workflow and project-memory ledger files are also present on the remediation branch.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Module contract remediation: business Module content fails closed when projection is `idle`, `loading` or `error`; Foundation Home, Settings and GYO focus remain bootable; navigation hides Module entries until persisted projection is `ready`.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] CI topology remediation on this branch: pull requests target `pqg-workspace`; push triggers cover `pqg-workspace`, `foundation-v2-r1-durable-agent-run-20260823` and `remediation-r1-ci-module-failclosed-20260824`; nonexistent `main`/`develop` and historical F6 trigger were removed.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Remediation source-validation HEAD: `0c096d88f467d57aea19ded31e4cec258844557b`; GitHub Actions `Smoke Test` Run #83, ID `32658290306`, conclusion `success`, `pqg/smoke=success`.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Backend final re-QA: 507 passed, 81 skipped, 2 warnings.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Frontend final re-QA: 4 files / 30 tests PASS — ModuleCanvas 8, LeftNavigation 5, AssistantTurn 2, HermesAssistantPanel 15; lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Runtime final re-QA: startup migrations through `0038_durable_assistant_runs` PASS; health/runtime checks PASS; readiness smoke 7 checks PASS; cleanup PASS and archived 1 smoke session.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] `smoke-real` in Run #83 = SKIPPED and is not PASS evidence.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] QA correction: initial remediation CI exposed a newly introduced ModuleCanvas React `act(...)` test warning; commit `0c096d88f467d57aea19ded31e4cec258844557b` fixed it, and final Run #83 shows ModuleCanvas 8/8 PASS without that warning. Existing HermesAssistantPanel act warnings remain.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Known non-blockers: npm reports 6 vulnerabilities (3 moderate, 3 high); Vite >500 kB chunk warning; 2 existing backend warnings; GitHub Actions reports Node-20 deprecation warnings for `actions/checkout@v4` and `actions/setup-python@v5`. No dependency/tool-version change was attempted.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Compare `cbd4d899ca30e8d2585917447858a225574af17a...0c096d88f467d57aea19ded31e4cec258844557b`: ahead 10, behind 0, merge-base exactly the base.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Final post-edit committed-range `git diff --check` = NOT RUN because writes were connector commits rather than a writable checkout; final GitHub compare/diff was reviewed. Do not substitute the preflight diff check for this missing post-edit check.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Result: scoped code/CI remediation validation PASS WITH PROCESS LIMITATION; the original default-branch release-governance finding is only PARTIALLY REMEDIATED repository-wide because these workflow changes are not yet integrated into `pqg-workspace` and branch protection/required status checks remain unconfigured.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] No merge, deployment, branch-protection change, auth/human-presence hardening, migration, dependency/tool-version update, capability implementation-binding change, sandbox change, F7/F9 implementation or checkpoint/state promotion was performed.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened; F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Next gate: explicit approval to integrate the validated remediation into `pqg-workspace`; branch-protection/required-status configuration is a separate repository-governance action, and protected admin human-presence hardening requires separate explicit approval.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Provenance: GitHub Windows preflight Run `32657803755`, Smoke Test Run `32658290306`, exact source commits and branch compare independently read during this session.
