# PQG Workspace — Project Changelog

> Append-only cross-session ledger. Do not rewrite historical entries; corrections are new timestamped entries.

## Ledger rules

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi entry phải có timestamp chính xác đến giây theo format `[YYYY-MM-DD HH:MM:SS UTC±HH:MM]`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi fact/update trong Project Memory phải tự mang timestamp; timestamp cấp file/section không thay thế timestamp từng nội dung.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mỗi entry nên ghi source/actor, scope, what changed, file/commit/run, evidence/result, limitation, gate effect và provenance.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Correction/supersession phải append entry mới với timestamp mới; không xóa/sửa lịch sử để làm chronology đẹp hơn.

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
