# AI Task

## Current stage

- Stage: Local MVP/Pilot remediation v1.2.
- State: `DIRAP_LOCAL_MVP_REMEDIATION_V1_2_VALIDATED`.
- Baseline giữ nguyên: Controlled Knowledge Search đã accepted; Memory Hub 4.1 đã validated trong phạm vi local MVP.

## Objective

Hoàn thiện DIRAP Local Workbench thành không gian làm việc đáng tin cho một người dùng local, với Trợ lý Hermes là agent/runtime bên trong: quản lý Công việc, tài liệu, đầu ra, tri thức có nguồn và bộ nhớ có lifecycle; sau đó chứng minh bằng UAT cô lập rằng các luồng ghi, duyệt và scope không làm lộ, ghi nhầm hoặc nhân đôi dữ liệu.

## Gate result (2026-08-12)

1. Canon/state: đạt; các nguồn trạng thái chính cùng trỏ tới remediation v1.2 validated.
2. Atomic idempotency và migration: đạt bằng regression concurrent/interruption.
3. Trust boundary: đạt trong fixture local cô lập cho sandbox, approval, external effects, archive, file revision, CORS/operator và DOCX limits.
4. Session/scope isolation và recovery: đạt bằng component regression và browser UAT.
5. Quality gate: backend 416 pass/1 permission-based skip; frontend 134 pass; lint/type-check/build pass; runtime và browser UAT đạt.

## Boundaries

- Local-first; FastAPI là policy boundary; Hermes ACP là runtime boundary.
- Giữ legacy `memory_entries`; Memory Hub không tự động inject vào chat.
- Không deploy/cloud, connector package 2, vector/AI search, legacy cutover, retention/delete Hub hoặc encrypted backup.
- Browser không nhận Credential Manager bearer token; không commit, push hoặc dùng credential production.

## Done when

- Không còn P0/P1 đã biết trong phạm vi local pilot.
- Atomic/concurrent, sandbox/approval, archived-session và cross-session regressions đạt.
- Browser UAT cô lập đạt cho desktop/mobile, keyboard, recovery, approval và dữ liệu.
- `AI_STATE.json`, `PROJECT_STATE.md`, `CURRENT_CHECKPOINT.md`, risk register và verification khớp bằng chứng hiện hành.

Các điều kiện trên đã đạt ngày 2026-08-12. Bước tiếp theo là người dùng nghiệm thu pilot với dữ liệu thật có kiểm soát; không suy rộng thành production-ready.
