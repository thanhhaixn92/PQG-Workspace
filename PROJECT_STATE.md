# Project State

## Active coding-operations overlay

- Coding operations plan: [GitHub Issue #13](https://github.com/thanhhaixn92/PQG-Workspace/issues/13).
- Coding operations gate: `OPS-01`.
- Coding operations status: `REVIEW_PENDING` once this package is committed and
  pushed; until then it is `IN_PROGRESS` on its feature branch.
- Completed prerequisite gates: `G0 = PASS`, `M1 = PASS`.
- `CODING_OPERATIONS_READY = false` / not yet reached.
- `P0-04 = BLOCKED` and `MVP Gate = BLOCKED` until OPS-01 through OPS-05 pass.
- Product state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; this
  operations overlay is not a product checkpoint promotion.

> Current routing update (2026-08-14): `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` là trạng thái đang triển khai. Checkpoint `DIRAP_LOCAL_MVP_WORK_HUB_VALIDATED` ngày 2026-08-12 được giữ làm baseline đã kiểm chứng; chưa phải nghiệm thu v2.2. Không được quảng bá v2.2 thành validated khi còn hard-stop hoặc chưa hoàn tất UAT.

> Historical routing update (2026-08-12, superseded as active routing):
> `DIRAP_LOCAL_MVP_REMEDIATION_V1_2_VALIDATED` was the then-current checkpoint.
> It remains historical baseline evidence and does not override the active v2.2
> `PARTIAL` checkpoint or Coding Operations Stabilization.

## Active v2.2 implementation checkpoint

> The dated 2026-08-17 gate narrative below is historical where it says E2 or
> real proposal/package/executor is NOT RUN; it is superseded by the bounded
> E2 receipt recorded in the 2026-08-22 reconciliation. The checkpoint remains
> PARTIAL and this does not constitute Gate PASS.

- Product stage: Local MVP/Pilot có kiểm soát cho một người dùng local.
- Product objective: Công việc → trao đổi với **Trợ lý GYO** → tài liệu/đầu ra → tri thức có nguồn/review → bộ nhớ có lifecycle.
- Reconciliation 2026-08-22: E2 bounded real-provider receipt `package-e2-bounded-20260822-063658` PASS; F1 PASS theo claim hẹp (remote compute stop vẫn NOT PROVEN); G-SYNTHETIC aggregate `package-g-synthetic-aggregate-20260822-0837` PASS nhưng là synthetic agent evaluation, không phải human usability. Giữ checkpoint `PARTIAL`, không promotion.
- Gate 1 technical evidence là **PASS — quyết định độc lập của Codex ngày 2026-08-17**: browser characterization isolated PASS; backend focused **32 passed, 1 Windows symlink skip, 1 warning Pydantic hiện hữu**; frontend ReviewInboxPanel/ActionPackagesPanel/HermesAssistantPanel **21 passed**. `/api/model-config` hiện có 1 provider Opencode, 3 model Free enabled và default model; `credential_configured=true`/`health_status=ready` chỉ chứng minh cấu hình cục bộ, không suy diễn upstream healthy. Bounded real-GYO UAT đã PASS stream/context/source/cancel; real action-proposal không xuất hiện, nên proposal/package/executor thực vẫn **NOT RUN**. P2 cancel routing provenance đã regression-verified nhưng không chứng minh portable process-level compute stop. Full fidelity matrix, usability 5 người và real action-proposal acceptance vẫn PARTIAL/NOT RUN; trạng thái giữ `PARTIAL`, chưa nâng checkpoint.
- Explicit exclusions: deploy/cloud, connector package 2, vector/AI search, automatic Memory Hub injection, legacy cutover, Hub retention/delete và encrypted backup.
- CP12 thuộc worktree Hermes khác và không nằm trong checkpoint này.

> Historical baseline (2026-08-10): `DIRAP_V3_MEMORY_HUB_3A_4_VALIDATED` was the active local MVP checkpoint before remediation v1.2. Controlled Knowledge Search remains an accepted earlier slice. This paragraph is retained as history and does not override the active remediation checkpoint above.

Last updated: 2026-08-26

## Historical checkpoint — Controlled Knowledge Search

- Active track: DIRAP v3.0 Controlled Knowledge Search, trong worktree độc lập `DIRAP-Personal-v3`.
- Current state: `DIRAP_V3_CONTROLLED_SEARCH_ACCEPTED` (Codex, 2026-08-10). The controlled-search slice is accepted within its defined boundary.
- CP5 đến CP10 của Hermes Local Stack V1 là nền tảng đã đóng, được giữ nguyên.
- Mục tiêu hiện tại: tìm kiếm cụm từ (chỉ đọc) trong nội dung/nguồn bản ghi tri thức của đúng một work item, trả về chỉ các bản ghi được chính sách khả dụng v1 cho phép theo mục đích đã chọn.
- Foundation, Extraction, Knowledge Records, Knowledge Review, Usability Read-only và Controlled Search đã được Codex chấp nhận nội bộ. Không tự mở rộng sang AI, agent memory use, deployment hoặc vận hành thực tế.

## Historical Gate Report — CP10 evidence (Antigravity/Checker)

> Đây là bằng chứng **lịch sử từ CP10**, không phản ánh lát Controlled Knowledge Search hiện hành (đã được Codex chấp nhận).

Latest verified by Antigravity (Checker):

- Backend tests after CP10: 269 pass, 1 pre-existing Starlette warning.
- Characterization tests: 76 pass, 1 pre-existing Starlette warning.
- No `PytestUnhandledThreadExceptionWarning` remains.
- Frontend last verified after CP5 implementation: type-check pass, 106 tests pass, build pass.

## Controlled Knowledge Search — acceptance evidence (Codex, 2026-08-10)

- Trạng thái chính thức: `DIRAP_V3_CONTROLLED_SEARCH_ACCEPTED` — accepted by Codex after independent backend/frontend verification. The slice remains limited to deterministic, task-scoped, read-only search with policy filtering before pagination.
- Backend: 6 suite DIRAP = **85 passed, 1 permitted symlink skip**; migrations giữ nguyên **19**; không dependency mới; 0 dòng `authoritative`.
- Frontend: toàn bộ suite = **111 passed**; `DirapPanel.test.tsx` = **5 passed**, gồm async-safety UI và Enter khi đang bận không tạo yêu cầu trùng; type-check đạt; lint **0 errors** (6 warnings pre-existing); build đạt.
- Chỉ đọc tuyệt đối: không audit, không ghi trạng thái, không lưu kết quả tìm kiếm, không migration.
- Chi tiết bằng chứng đầy đủ: `AI_VERIFICATION.md`; checkpoint đã được khóa tại `AI_STATE.json` là `DIRAP_V3_CONTROLLED_SEARCH_ACCEPTED`.

## Historical Decision

Người dùng đã phê duyệt gói thiết kế DIRAP v2.3 và cho phép bắt đầu v3.0 trong worktree riêng.

- Không sửa worktree Hermes chính đang có CP12 dang dở.
- Giữ legacy session routes và `USE_TASK_API=false` fallback.
- Mọi endpoint mới phải có idempotency, approval, audit và test an toàn session/workspace khi áp dụng.

## Do Not Do Now

- Do not add deployment.
- Do not change Hermes model/provider/timeout.
- Do not hard-delete user data.
- Do not weaken approval, audit, or workspace sandbox rules.

## Source Of Truth

Conflict order:

1. Current explicit user request plus platform and safety constraints.
2. `AGENTS.md`.
3. `PROJECT_STATE.md`, `AI_STATE.json`, and
   `docs/implementation/CURRENT_CHECKPOINT.md`.
4. Product canon, security policy, and data model.
5. Current source, contracts, and focused tests.
6. Project Memory.
7. Historical handoffs, plans, chat, and evidence.
