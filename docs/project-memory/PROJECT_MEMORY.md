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

## End-of-session update requirements

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Sau project-relevant change, phiên hiện tại phải cập nhật branch/HEAD, state/checkpoint, changed scope/files, approvals, tests/results, limitations, gate state, next action và provenance; từng nội dung mới/sửa phải có timestamp riêng đến giây.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Nếu không có persistence capability, không được nói memory đã cập nhật; phải báo `Memory update prepared but not persisted.`
