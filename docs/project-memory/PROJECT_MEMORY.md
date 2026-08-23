# PQG Workspace — Current Project Memory

> Mutable cross-session snapshot. Every updated fact must carry its own second-precision timestamp. Live repo/canon overrides this file.

## Memory protocol

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Timestamp format bắt buộc: `[YYYY-MM-DD HH:MM:SS UTC±HH:MM] Nội dung cập nhật`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi fact/decision/status/test/approval/gate/limitation mới hoặc sửa phải có timestamp riêng; không dùng một timestamp cấp file để đại diện cho nhiều facts.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Correction/supersession dùng timestamp mới; không thay timestamp cũ để làm dữ liệu trông mới hơn.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Memory-maintenance writes chỉ để đồng bộ snapshot/ledger không tự kích hoạt vòng lặp cập nhật memory vô hạn; phải ghi underlying project event và commit/evidence liên quan khi biết.

## Current identity

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Repository: `thanhhaixn92/PQG-Workspace`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Default branch: `pqg-workspace`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Active implementation branch: `foundation-v2-r1-durable-agent-run-20260823`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] R1 code-validation baseline HEAD: `2759d8ce9de0256bb4175a99046ec768011aa422` (`ci: validate R1 frontend lifecycle UX`).
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Memory/docs commits sau baseline phải được phân biệt với R1 code-validation HEAD; không tự coi docs-only HEAD mới là R1 CI-validated HEAD.

## Current state and roadmap

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Active state: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Checkpoint: `PARTIAL`; không promote nếu chưa có approval/evidence riêng.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F1 Tokens/CSS — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F2 FoundationShell — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F3 Static Module Registry — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F4 Settings — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F5 Persistent Module Instances — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] F6 Agent Capability Boundary — PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] R1 Durable AgentRun — PASS.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Next planned protected phase: F7 Resource Catalog + Context Broker.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] F7 chưa được mở cho implementation bằng generic continuation language.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] F9 Data Egress CLOSED / NOT APPROVED.

## R1 evidence baseline

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] GitHub Actions `Smoke Test` Run #74, ID `32651648018`, HEAD `2759d8ce9de0256bb4175a99046ec768011aa422`, conclusion `success` đã được independently reverified khi khởi tạo memory.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Backend: 507 passed, 81 skipped, 2 warnings.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] R1 durable focused: 6/6 PASS; frontend focused: 17/17 PASS; frontend lint: 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Startup migration `0038_durable_assistant_runs` PASS; durable Assistant run worker startup PASS; runtime smoke readiness 7 checks PASS; smoke cleanup PASS.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] `smoke-real` = NOT RUN.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] R1 chứng minh local durable lifecycle behavior; không chứng minh remote provider compute cancellation.

## Known residuals

- [2026-08-23 23:51:19 UTC+07:00][imported_at] `npm ci` từng báo 6 dependency vulnerabilities: 3 moderate, 3 high; không chạy `npm audit fix` tự động vì dependency change là protected.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Vite chunk >500 kB warning hiện non-blocking.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Existing React `act(...)` và Python deprecation/settings warnings không được diễn giải thành test failures.

## Current gate rule

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] F7 writes chỉ được bắt đầu sau explicit approval tương đương: `Phê duyệt F7 Resource Catalog + Context Broker, cho phép thay đổi security/data-access boundary theo thiết kế đã khóa; chưa mở F9 Data Egress.`
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Sau F7 approval cần fresh preflight trên đúng branch/worktree, đọc state/checkpoint/canon/security, inspect current context builder/APIs/DB/tests, xác định exact protected scope, thêm leakage/classification/deterministic broker tests và không mở F9.

## Latest documentation/memory governance update

- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `docs/project-memory/PROJECT_CONTEXT.md`, `PROJECT_MEMORY.md` và `PROJECT_CHANGELOG.md` đã được persist trên repo branch hiện tại.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `AGENTS.md` đã được cập nhật để coding agents đọc/cập nhật cross-session Project Memory và bắt buộc timestamp từng nội dung đến giây; governance commit: `9dc4ffbddff067ba43dd94ed44dcafd13133f069`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] `PROJECT_CONTEXT.md` bổ sung non-recursive memory synchronization rule; commit: `a7aa3a2fbcfb6f14b4ddb51a528e6af2ba707447`.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Scope của các thay đổi trên là docs/memory governance only; không thay đổi runtime/schema/security boundary, không mở F7/F9 và không promote checkpoint/state.

## Current remediation session

- [2026-08-24 01:02:43 UTC+07:00][recorded_at] User authorized proceeding with remediation edits derived from the F6/R1 assessment; this authorization is treated as limited to non-protected remediation scope already identified, not auth/security-boundary, migration, dependency/tool-version, F7 or F9 work.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] Remote remediation branch `remediation-r1-ci-module-failclosed-20260824` was created from docs/memory branch HEAD `cbd4d899ca30e8d2585917447858a225574af17a` to isolate intended CI-topology and Module projection fail-closed changes.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] Mandatory preflight `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1` is NOT RUN in this session because the available execution environment lacks PowerShell and `cmd.exe`; repository contract was not bypassed or emulated.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] No application/runtime/test/workflow source remediation has been written; intended focused tests, lint, type-check, build, CI validation and `git diff --check` are NOT RUN.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] Project changelog blocker entry was persisted on the remediation branch via docs-only commit `93c8689ec30c7b0337444eb9f47ae38c657654ab`; this commit is not R1 code-validation evidence.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened and F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 01:02:43 UTC+07:00][recorded_at] Next exact action is to run mandatory preflight from a Windows-capable checkout of `remediation-r1-ci-module-failclosed-20260824`, then implement only CI topology + Module projection fail-closed remediation with focused regression tests and validation before any PASS claim.

## Remediation validation — supersedes the earlier execution blocker

- [2026-08-24 01:34:40 UTC+07:00][recorded_at] User explicitly approved a narrow bootstrap exception allowing only a Windows GitHub Actions workflow to execute `scripts/agent-preflight.ps1` before implementation; this did not authorize protected auth/security/migration/dependency/F7/F9 work.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Windows `Agent Preflight` Run #2, ID `32657803755`, HEAD `738e3c6e48ce7323342fd3c308699190987359b1`, conclusion `success`; preflight reported `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`, `human_approval_required=True`, modified=0, untracked=0 and `diff --check exit: 0` before remediation writes.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Active working branch for this remediation is `remediation-r1-ci-module-failclosed-20260824`; base/merge-base is `cbd4d899ca30e8d2585917447858a225574af17a`.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Remediation source-validation HEAD is `0c096d88f467d57aea19ded31e4cec258844557b`; later memory-only commits must not be confused with this code-validation HEAD unless independently validated.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Module eligibility now fails closed for projection states `idle`, `loading` and `error`: business Module content is not rendered until persisted projection is `ready`; Foundation Home, Settings and GYO focus remain bootable.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Left navigation no longer falls back to static Module definitions while projection is unavailable; when projection is `ready`, persisted attachment/order/display labels remain authoritative.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] `smoke.yml` on the remediation branch now targets PRs to `pqg-workspace` and pushes to `pqg-workspace`, the active R1 branch and the remediation branch; nonexistent `main`/`develop` and the historical F6 branch were removed from the active trigger topology.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Final remediation re-QA: GitHub Actions `Smoke Test` Run #83, ID `32658290306`, HEAD `0c096d88f467d57aea19ded31e4cec258844557b`, conclusion `success`; `pqg/smoke` status = success.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Backend re-QA: 507 passed, 81 skipped, 2 warnings; frontend focused re-QA: 4 files / 30 tests PASS (`ModuleCanvas` 8, `LeftNavigation` 5, `AssistantTurn` 2, `HermesAssistantPanel` 15); lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Runtime re-QA: startup migrations through `0038_durable_assistant_runs` PASS, health/runtime checks PASS, readiness smoke 7 checks PASS and cleanup PASS with 1 smoke session archived.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] `smoke-real` for Run #83 = SKIPPED; it is not PASS evidence.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] The remediation-introduced `ModuleCanvas.test.tsx` React `act(...)` warning was fixed in `0c096d88f467d57aea19ded31e4cec258844557b`; final Run #83 shows ModuleCanvas 8/8 PASS without that warning. Existing `HermesAssistantPanel` act warnings remain and are not newly introduced by this remediation.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Known non-blockers in final CI remain: npm audit reports 6 vulnerabilities (3 moderate, 3 high), Vite >500 kB chunk warning, two existing backend warnings and GitHub Actions Node-20 deprecation warnings for `actions/checkout@v4` / `actions/setup-python@v5`; no dependency/tool-version remediation was attempted.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Scoped compare from `cbd4d899ca30e8d2585917447858a225574af17a` to source-validation HEAD `0c096d88f467d57aea19ded31e4cec258844557b` is ahead 10 / behind 0 with merge-base exactly the base; changed scope is bootstrap/CI workflows, ModuleCanvas/LeftNavigation and focused tests plus memory ledger files.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Final post-edit committed-range `git diff --check` is NOT RUN because available repo writes are connector commits rather than a writable checkout; the mandatory preflight did run `git diff --check` successfully before implementation, and the final GitHub compare was reviewed. Do not misstate the preflight check as a post-edit diff check.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] CI topology remediation is not yet effective on the actual default branch until this remediation is explicitly integrated into `pqg-workspace`; default-branch branch protection/required status checks also remain unconfigured, so the original release-governance finding is PARTIALLY REMEDIATED, not fully closed.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] No merge, deployment, branch-protection change, auth/human-presence hardening, migration, dependency/tool-version change, Capability implementation-binding change, sandbox change or F7/F9 implementation was performed.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened and F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 01:34:40 UTC+07:00][recorded_at] Next gate: explicit approval to integrate the validated remediation into `pqg-workspace`; branch-protection/required-status configuration remains a separate repository-governance action, and protected admin human-presence hardening requires its own explicit approval.

## Integration PR gate

- [2026-08-24 01:42:35 UTC+07:00][recorded_at] User replied `Đồng ý và tiếp tục` to the integration gate; this authorizes proceeding with the integration workflow toward `pqg-workspace`, but does not silently expand into branch protection, auth/security hardening, migration/dependency changes, F7/F9, deployment or checkpoint promotion.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] Live topology check found `pqg-workspace` still at `af58b6f68abcdbe6344d68c126113b7191f0a9a5`, while remediation HEAD before this memory repair was `b6f2e4298a88e0f843b6b70b1024b4a6cd5e4532`; compare is ahead 98 / behind 0 with merge-base exactly `af58b6f68abcdbe6344d68c126113b7191f0a9a5`.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] Because the integration branch contains the accumulated Foundation F1–F6 + R1 implementation and memory governance, a direct merge would integrate substantially more than the narrow remediation files; the agent therefore did not silently merge the default branch under the narrower interpretation.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] Pull request #1 `Integrate Foundation/R1 remediation into pqg-workspace` was opened with base `pqg-workspace`, head `remediation-r1-ci-module-failclosed-20260824`; at creation it contained 98 commits, 53 changed files, 6973 additions and 2198 deletions and later became mergeable=true.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] PR integration CI is NOT RUN / not observed: no PR-triggered workflow run was returned for head `b6f2e4298a88e0f843b6b70b1024b4a6cd5e4532` or synthetic merge commit `a70aba4a4ff63daa59230ab5751a125282ad0705`, and combined status on that merge commit was empty at verification time.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] Merge of PR #1 is WITHHELD pending explicit acceptance of the full accumulated Foundation/F1–F6/R1 + remediation integration scope; source-branch CI evidence remains Run #83 on source-validation HEAD `0c096d88f467d57aea19ded31e4cec258844557b` and must not be mislabeled as PR integration CI.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] QA found the prior memory-maintenance writes had truncated the leading history of `PROJECT_MEMORY.md` and `PROJECT_CHANGELOG.md` by replacing each file with a tail excerpt. This is a docs/memory-only defect; runtime/source code is unaffected. The current memory-maintenance action restores the complete earlier contents and appends the remediation/integration events atomically.
- [2026-08-24 01:42:35 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 unopened; F9 CLOSED / NOT APPROVED.

## End-of-session update requirements

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Sau project-relevant change, phiên hiện tại phải cập nhật branch/HEAD, state/checkpoint, changed scope/files, approvals, tests/results, limitations, gate state, next action và provenance; từng nội dung mới/sửa phải có timestamp riêng đến giây.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Nếu không có persistence capability, không được nói memory đã cập nhật; phải báo `Memory update prepared but not persisted.`

## Current integration validation and merge gate

- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Memory truncation repair was persisted in docs-only commit `0b3af21d319fd36fc41876fa997f116af921d29d`; both `PROJECT_MEMORY.md` and `PROJECT_CHANGELOG.md` were subsequently re-read from line 1 and confirmed to contain their restored leading history.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] PR #1 current validated integration head is `365077d0c751326c6defb3c2ea12556189a9d625`; before this memory-maintenance commit GitHub reported PR #1 open, unmerged, mergeable=true, 100 commits, 53 changed files, base `pqg-workspace` at `af58b6f68abcdbe6344d68c126113b7191f0a9a5`.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Current-head push validation: GitHub Actions Smoke Test Run ID `32659047749` on exact HEAD `365077d0c751326c6defb3c2ea12556189a9d625` completed `success`; combined commit status `pqg/smoke=success`.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Run `32659047749` backend result: 507 passed, 81 skipped, 2 warnings; frontend focused: 4 files / 30 tests PASS; lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Run `32659047749` runtime result: startup migrations through `0038_durable_assistant_runs` PASS; health/runtime checks PASS; readiness smoke 7 checks PASS; cleanup PASS with 1 smoke session archived.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Run `32659047749` `smoke-real` = SKIPPED and is not PASS evidence. Existing HermesAssistantPanel React `act(...)`, npm 6 vulnerabilities (3 moderate, 3 high), Vite >500 kB, two backend warnings and GitHub Actions Node-version warnings remain non-blocking evidence; no dependency/tool-version change was performed.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Validation Run `32659047749` is push-triggered validation of the exact integration-head tree; PR-event CI remains NOT OBSERVED and must not be relabeled as PR CI.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] PR #1 description was updated to disclose the broad scope and current-head validation evidence. Full merge scope is Foundation F1–F6 + R1 + project-memory governance + CI/Module remediation; it is not a narrow remediation-only patch.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] Merge remains WITHHELD pending explicit acceptance of the full accumulated scope. Branch protection/required-status configuration, auth/human-presence hardening, migration/dependency/tool changes, deployment, F7/F9 and checkpoint/state promotion remain outside this gate.
- [2026-08-24 01:50:00 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened; F9 remains CLOSED / NOT APPROVED. Later memory-only HEADs must not be represented as inheriting CI validation from `365077d0c751326c6defb3c2ea12556189a9d625`.

## Post-merge integration completion

- [2026-08-24 01:58:33 UTC+07:00][recorded_at] User explicitly approved merging PR #1 with the full accumulated Foundation F1–F6 + R1 + project-memory governance + CI/Module remediation scope while keeping `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL` and leaving F7/F9 plus branch protection, auth/security, dependency/tool-version and deployment outside scope.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Final drift check immediately before merge: PR #1 open, unmerged, mergeable=true; base `pqg-workspace@af58b6f68abcdbe6344d68c126113b7191f0a9a5`; exact head `78147cf9ee63c6fd1efce02690f3e89934c864b3`; 101 commits / 53 changed files.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] PR #1 was merged with exact-head guard. Merge commit: `0162978c7571eb69f1e869c6087037feda869dc0`; GitHub subsequently reported PR closed/merged and `pqg-workspace` pointing to that commit before this memory-maintenance write.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Post-merge GitHub Actions `Smoke Test` Run #86, ID `32659557944`, event `push`, branch `pqg-workspace`, HEAD `0162978c7571eb69f1e869c6087037feda869dc0`, conclusion `success`; `pqg/smoke=success`.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Post-merge backend QA: 507 passed, 81 skipped, 2 warnings. Frontend focused QA: 4 files / 30 tests PASS; lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Post-merge runtime QA: startup migrations through `0038_durable_assistant_runs` PASS; health/runtime checks PASS; readiness smoke 7 checks PASS; cleanup PASS with 1 smoke session archived.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Post-merge `smoke-real` = SKIPPED and is not PASS evidence. Existing HermesAssistantPanel React `act(...)` warnings, npm audit 6 vulnerabilities (3 moderate, 3 high), Vite >500 kB warning, 2 backend warnings and GitHub Actions Node-version deprecations remain known non-blockers; no protected dependency/tool remediation was performed.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Integration result: Foundation F1–F6 + R1 + project-memory governance + CI/Module remediation is now integrated into `pqg-workspace` and post-merge smoke-validated. This does not promote checkpoint/state and does not open F7/F9.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Repository governance residual remains: `pqg-workspace` branch protection/required status checks are still disabled/unconfigured and were not changed under this approval.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] Next protected gate remains F7 Resource Catalog + Context Broker and requires its separately locked explicit approval plus fresh preflight before implementation. Branch protection and admin human-presence hardening remain separate approvals.
- [2026-08-24 01:58:33 UTC+07:00][recorded_at] This memory-maintenance commit is docs-only and must not be treated as independently inheriting Run #86; the runtime/code validation baseline remains merge commit `0162978c7571eb69f1e869c6087037feda869dc0`.

## Environment-aware preflight governance update

- [2026-08-24 03:06:08 UTC+07:00][recorded_at] User explicitly requested that direct `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1` execution apply only on a local machine/local checkout, while ChatGPT Project/GitHub-connected work must use GitHub-hosted `Agent Preflight` instead.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] This request is treated as a narrow docs-governance bootstrap approval. No fresh preflight was run before these governance-doc edits; the exception does not authorize application/runtime/schema/security/feature implementation, which still requires a fresh successful preflight under the new environment-specific rule.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] `AGENTS.md` was updated by commit `395914f3944a7992bffcb06852ad6280b7c647bc` to define local PowerShell preflight versus GitHub Actions `Agent Preflight` for ChatGPT Project/GitHub environments, require exact target ref evidence, reject `pqg/smoke` as a substitute, and document the manual `workflow_dispatch` path when connected tooling cannot dispatch.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] `docs/14_AGENT_OPERATING_CONTRACT.md` was aligned by commit `bd89c2696236ae687ee88338bb370eed35bf9c6b`; `docs/project-memory/PROJECT_CONTEXT.md` was aligned by commit `bcd5d80034c2bd95b644a81bf725d7e1f120b70a`.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] `.github/workflows/agent-preflight.yml` itself was not changed; it already provides a Windows `workflow_dispatch` path that executes `scripts/agent-preflight.ps1` and publishes `pqg/preflight`.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] Correction: an accidental docs-only file `docs/project-memory/.tmp` was created in commit `9beb6a32dd4679bb3789b90d8267e4891ea8a429` while preparing the update and immediately removed in commit `5920085cc60ae73e5247ea281b5f897618ccd17b`; the resulting tree before governance edits matched the prior tree and no runtime/source file was affected.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] Runtime tests and `git diff --check` are NOT RUN for this connector-only docs-governance change; exact GitHub diff review is required before closing this docs change, and no runtime PASS claim is created by it.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened and F9 remains CLOSED / NOT APPROVED. The next application/runtime write from ChatGPT Project/GitHub requires a fresh successful GitHub `Agent Preflight` on the exact target ref.

## Assistant-operated GitHub preflight and Module config corruption remediation

- [2026-08-24 03:45:42 UTC+07:00][recorded_at] User explicitly instructed that ChatGPT Project should run GitHub preflight itself and persist that rule; manual user triggering is fallback-only when connected tooling cannot dispatch and cannot write the repository trigger file.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] `.github/workflows/agent-preflight.yml` was updated in commit `0b52e673a217a3b4806768e133416d5def66bd38` so pushes on `pqg-workspace` that change the workflow or `.github/agent-preflight-trigger.txt` run the Windows Agent Preflight; trigger file was established in commit `c71589107e82049a624edaecacbbdcd5412b8a56`.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Assistant-operated preflight Run #4, ID `32664825217`, on `pqg-workspace@c71589107e82049a624edaecacbbdcd5412b8a56` completed `success`; the assistant subsequently aligned `AGENTS.md` (`f00f37f17d5b843495a209d517d92c43dac96b7a`), `docs/14_AGENT_OPERATING_CONTRACT.md` (`223110fc022b1962395c91b543373c4af348aad1`) and stable `PROJECT_CONTEXT.md` (`564b778737680abf016d9a5291f408f1b0334ed5`) to require self-triggering when repository write access exists.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Fresh exact-head preflight trigger commit `347b91d88cc04235c9bc8c4f9b114d7c4380357d` produced `pqg/preflight=success` via Agent Preflight Run ID `32664994203`; this is the pre-code receipt for the following non-protected remediation scope.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Module config corruption remediation source-validation HEAD is `ee4d7fe1091e42d65885039ee01b0a0360474a0d`, consisting of service commit `53fcf433698ea3c7c043e6789800fc656c807e87`, API commit `4679df9f81151171e5bb1f7eb0122bb6dfd4402b` and regression-test commit `ee4d7fe1091e42d65885039ee01b0a0360474a0d`.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Invalid JSON and valid non-object `config_json` no longer silently normalize to `{}`; the Module projection returns structured `MODULE_CONFIG_INVALID`, and attach/detach/rename validate the target Module config before write while reorder validates the full projection before its writes.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Regression evidence explicitly covers malformed JSON, JSON array, JSON null and an admin detach attempt against corrupt config; the mutation case verifies `attached`, `revision` and corrupt `config_json` are unchanged after the rejected request.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] GitHub Actions `Smoke Test` Run #96, ID `32665203904`, exact HEAD `ee4d7fe1091e42d65885039ee01b0a0360474a0d`, conclusion `success`; combined status `pqg/smoke=success`.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Run #96 backend: 511 passed, 81 skipped, 2 warnings; all four new Module config regression cases PASS. Frontend focused: 4 files / 30 tests PASS; lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Run #96 runtime: migrations through `0038_durable_assistant_runs` PASS; health/runtime checks PASS; readiness smoke 7 checks PASS; cleanup PASS with 1 smoke session archived. `smoke-real=SKIPPED` and is not PASS evidence.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Exact compare `347b91d88cc04235c9bc8c4f9b114d7c4380357d...ee4d7fe1091e42d65885039ee01b0a0360474a0d` is ahead 3 / behind 0 and changes only `backend/app/services/module_instances.py`, `backend/app/api/modules.py`, and `backend/tests/test_module_admin.py`; exact GitHub patches were reviewed.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Post-edit local `git diff --check` is NOT RUN because this is connector-only work without a writable local checkout; do not mislabel the preflight's pre-edit checks or GitHub patch review as a post-edit `git diff --check`.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] No schema/migration, auth/security-boundary, dependency/tool-version, branch-protection, deployment, F7/F9 or checkpoint/state change was made in this remediation. State remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened and F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 03:45:42 UTC+07:00][recorded_at] Later Project Memory commits are docs-only and must not be represented as inheriting Run #96; runtime/code validation baseline for this remediation remains `ee4d7fe1091e42d65885039ee01b0a0360474a0d`.

## Non-protected completion pass: CI diff evidence and GYO test hygiene

- [2026-08-24 04:02:04 UTC+07:00][recorded_at] User requested `Tiếp tục hoàn thiện`; this continuation was constrained to remaining non-protected quality/process work and did not authorize branch protection, auth/security hardening, migration/schema, dependency/tool-version, capability-boundary changes, sandbox changes, F7/F9, deployment or checkpoint/state promotion.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Assistant self-triggered a fresh preflight with commit `877816f464c8d6f8069141dd5a2674c109336bc1`; Agent Preflight Run #6, ID `32665785977`, on exact `pqg-workspace@877816f464c8d6f8069141dd5a2674c109336bc1` completed `success` and published `pqg/preflight=success`.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] CI process commit `56f02c1c87209c060bfa91644f18a09ff93bb2aa` added `Validate committed diff formatting` to `.github/workflows/smoke.yml`; PR runs execute `git diff --check` from exact PR base to head, push runs execute it from `github.event.before` to `GITHUB_SHA`, and fallback/manual cases use `git show --check` on the head commit.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] GYO test-hygiene commit and source-validation HEAD `71b2b00805092e9adbf590393d4b74341a207e53` imports React Testing Library `act` and wraps fake EventSource token/terminal emissions in `HermesAssistantPanel.test.tsx`; production component behavior was not changed.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Exact compare `877816f464c8d6f8069141dd5a2674c109336bc1...71b2b00805092e9adbf590393d4b74341a207e53` is ahead 2 / behind 0 with exactly two changed files: `.github/workflows/smoke.yml` and `frontend/src/components/HermesAssistantPanel.test.tsx`.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] GitHub Actions `Smoke Test` Run ID `32666013307`, exact HEAD `71b2b00805092e9adbf590393d4b74341a207e53`, completed `success`; `pqg/smoke=success`, while `smoke-real=SKIPPED` and is not PASS evidence.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Final Run `32666013307` committed-diff validation step executed against `BEFORE_SHA=56f02c1c87209c060bfa91644f18a09ff93bb2aa` and `GITHUB_SHA=71b2b00805092e9adbf590393d4b74341a207e53` and PASSed; the preceding workflow commit's own run also showed the new committed-diff validation step PASS. Local checkout `git diff --check` is still NOT RUN in this connector-only session, but committed change formatting is now validated by CI rather than inferred from pre-edit preflight.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Run `32666013307` backend result: 511 passed, 81 skipped, 2 unchanged warnings. Frontend focused result: 4 files / 30 tests PASS (`ModuleCanvas` 8, `LeftNavigation` 5, `AssistantTurn` 2, `HermesAssistantPanel` 15); lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Correction to earlier residual: final Run `32666013307` contains no `HermesAssistantPanel` React `act(...)` warning blocks; the focused GYO panel `act(...)` test-warning residual is now fixed and CI-validated.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Run `32666013307` runtime result: migrations through `0038_durable_assistant_runs` PASS; application and workers start; health/runtime checks PASS; `SMOKE OK — 7 readiness checks, workspace ready`; cleanup PASS with 1 smoke session archived.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Known remaining non-blockers include npm audit 6 vulnerabilities (3 moderate, 3 high), Vite >500 kB chunk warning, two backend warnings, and GitHub Actions Node-version deprecation warnings for `actions/checkout@v4` / `actions/setup-python@v5`; dependency/tool-version remediation remains protected and was not attempted.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] No protected scope was changed. State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains unopened; F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Remaining substantive assessment residuals are separately gated: branch protection/required statuses; true-human admin hardening; capability implementation binding; migration 0037/wrapper debt; sandbox pathname TOCTOU; action/dependency pinning and npm vulnerabilities; F7; F9; checkpoint/state promotion. Generic continuation does not authorize these.
- [2026-08-24 04:02:04 UTC+07:00][recorded_at] Later Project Memory commits are docs-only and must not be represented as inheriting Run `32666013307`; runtime/code validation baseline for this completion pass remains `71b2b00805092e9adbf590393d4b74341a207e53`.

## F7 Resource Catalog + Context Broker — approved and scoped-validated

- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Supersession of earlier unopened-F7 entries: user explicitly approved `Phê duyệt F7 Resource Catalog + Context Broker, cho phép thay đổi security/data-access boundary theo thiết kế đã khóa; chưa mở F9 Data Egress.` This approval opens F7 only; F9 remains CLOSED / NOT APPROVED.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Assistant self-triggered F7 preflight with commit `3f9b254ed152f59e0d5fa8b3b4545a0b09dd1a52`; Agent Preflight Run ID `32666700014` completed success and published `pqg/preflight=success`, with exact checkout, clean tree and pre-edit `diff --check exit: 0`.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 implementation commit `84abd1aaea5c36af98fd7bcf7d1cbc9d47ee333d` introduced the security-first broker but its first Smoke Test Run ID `32667386856` failed backend validation; that run is retained as failure evidence and is not PASS evidence.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Corrective F7 commit and authoritative source-validation HEAD is `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388` (`fix: preserve F7 memory scope exclusion contract`).
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 changes are limited to `backend/app/services/context_broker.py`, compatibility facade `backend/app/services/assistant_context.py`, and `backend/tests/test_context_broker.py`; no schema/migration, provider/network/credential, dependency/tool-version, Action Package semantics, deployment, retention/delete, F9 or checkpoint/state change was made.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 broker pipeline is `discover metadata → SECURITY FILTER → deterministic relevance/ranking → hydrate → pack`; denied descriptors do not reach ranking, hydration or provider context, and denied IDs/titles/backend locators/content are not copied to model-visible catalog/context.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 Resource Catalog uses the locked sensitivity classes `public/internal/sensitive/restricted` and trust classes `canonical_user_data/verified_knowledge/derived_text/external_unverified/agent_generated_draft`; restricted resources fail before ranking.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 never-catalog boundary excludes credentials/env/API keys, raw audit, arbitrary filesystem/backend locators, raw `app.db`, chain-of-thought/internal reasoning, foreign-scope resources and restricted/lifecycle-ineligible memory/knowledge/skills.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Smoke Test Run ID `32667595588` on exact source HEAD `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388` completed success; `pqg/smoke=success` and `smoke-real=SKIPPED` (not PASS evidence).
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Run `32667595588` backend result: 516 passed, 81 skipped, 2 warnings; all 5 F7 broker regressions PASS, including security-filter-before-rank, invalid/foreign artifact exclusion, restricted Memory exclusion, provider-authorized-context-only, and context-manifest denied-ID/path non-leakage.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Run `32667595588` frontend focused result: 4 files / 30 tests PASS; lint 0 warnings/0 errors; TypeScript type-check PASS; production build PASS.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Run `32667595588` runtime result: migrations through `0038_durable_assistant_runs` PASS; startup/health/runtime PASS; `SMOKE OK — 7 readiness checks, workspace ready`; cleanup PASS with 1 smoke session archived.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Fresh closure preflight was self-triggered on exact post-F7 source HEAD lineage by commit `cca8e3f731dcac2fb9e769290bc3b940f95389e0`; Agent Preflight Run ID `32667843198` published `pqg/preflight=success` before the F7 architecture/routing documentation closure.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 routing/docs were aligned in `CODEGRAPH.md` commit `66e852b0f42aa21cd8bfd922cacc1ca9cb7f3646`, `docs/AI_AGENT_ROUTING.md` commit `fe51fffdff0dbdcd9388f7df5c61b7f8b13ef8c8`, and new `docs/implementation/F7_RESOURCE_CATALOG_CONTEXT_BROKER.md` commit `12fe4372bd9e36d1c1308076e53dd5a167370ed0`; these are docs-only successors and do not replace source-validation HEAD `efe0a35a...`.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Final F7 review records one non-blocking semantic distinction: browser-facing `context-manifest.accessible` is provenance compatibility metadata and is not consumed by ranker/model/provider; clients must not infer model use from it. Broker `included/retrieved` and provider context remain the enforced security path.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Conversation history is app-owned durable history, but provider/GYO-authored portions remain untrusted content at the FastAPI/model boundary regardless of descriptor provenance labels.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Exact compare from F7 preflight receipt `3f9b254ed152f59e0d5fa8b3b4545a0b09dd1a52` through F7 docs-head `12fe4372bd9e36d1c1308076e53dd5a167370ed0` is ahead 6 / behind 0 and contains only the F7 trigger process, 3 F7 source/test files, and F7 codegraph/routing/design documentation; no F9/state/schema/provider leakage was found.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 result: **scoped implementation/validation PASS** for Resource Catalog + Context Broker. Overall project state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; no checkpoint promotion is implied.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F9 Data Egress remains CLOSED / NOT APPROVED. Local resource-read authorization does not grant permission for web search, connector send, upload/export, new network destinations or other external data egress.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Known separate protected residuals remain branch protection/required statuses, true-human admin hardening, capability implementation binding, migration 0037/wrapper debt, sandbox pathname TOCTOU, dependency/action pinning and npm vulnerabilities; F7 did not modify those gates.
