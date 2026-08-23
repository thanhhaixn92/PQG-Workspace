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
