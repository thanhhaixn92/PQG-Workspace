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
