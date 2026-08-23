# AI Risk Register

> Cac muc cu duoc giu lam bang chung lich su. Claim context pack/proposal chua hoan chinh o cac snapshot thap hon la **superseded evidence**, khong ghi de finding/gate v2.2 hien hanh.

## DIRAP v2.2 residual gate (2026-08-15)

- **Closed audit regression:** isolated UAT could accidentally proxy to the ordinary `:8000` backend. Mitigation verified: Vite proxy target is supplied through `VITE_API_PROXY_TARGET`, and `start-dev.ps1` binds it to the selected backend port. The browser create-Work success and offline-error paths were rerun against temporary SQLite/workspace.

- **P1 residual — real action proposal:** claim bounded real proposal/package/executor PASS ở snapshot cũ là **superseded**. Bounded real-GYO UAT chỉ PASS stream/context/source/cancel; action_proposal thực không xuất hiện, nên proposal/package/executor thực vẫn **NOT RUN**.
- **P2 residual — cancellation provenance:** cancel API/DB terminal và late-output discard có regression evidence; primary routing provenance khi cancel không terminal cũng regression-verified. Điều này không chứng minh portable process-level compute stop trên adapter/nền tảng khác.
- **Deferred acceptance — human usability:** usability **0/5 NOT RUN** được người dùng hoãn hậu v2.2; không dùng agent/mock để thay bằng chứng người thật.
- **P2 residual — visual acceptance:** năm fidelity batch cuối PASS với 62 screenshot cho breakpoint, primary surfaces, Work tabs, async/offline, theme, keyboard/focus, reduced motion và reflow tương đương 400%. Browser zoom 200% thật trên Chrome 151 đã PASS bằng profile/SQLite/workspace tạm `uat-codex-`; không dùng CSS zoom/emulation. Full screen×state×viewport cross-product vẫn chưa hoàn tất và các ô `NOT RUN` không được suy diễn từ lượt zoom.
- **Closed runtime finding — Review Memory Hub 403:** same-origin GET qua Vite proxy thiếu `Origin` nhưng có allowlisted `Referer`; backend nay nhận exact origin từ referer. Thiếu cả hai hoặc foreign origin/referer vẫn fail closed. Backend regression 10/10 và PrimarySurfaces rerun PASS/console sạch.
- **Automated evidence:** backend 465 pass / 1 skip; frontend 172 pass; lint 0 error/4 warning; type-check/build pass. Mock proposal không đổi DB trước package; provenance/idempotency/exactly-once/archive guard đã được kiểm tra lại.
- **Branding/runtime boundary:** tên hiển thị hiện hành là `PQG Workspace`; trợ lý giao diện là `Trợ lý GYO`. Package names, API/public routes, DB/schema, biến môi trường, `hermes.theme`, checkpoint và credential contract được cố ý giữ nguyên. Runtime `model-config` hiện có 1 provider Opencode, 3 model Free enabled và default model. `credential_configured=true`/`health_status=ready` chỉ chứng minh cấu hình cục bộ, không chứng minh upstream healthy. Bounded real-GYO UAT PASS stream/context/source/cancel; real action_proposal không xuất hiện nên proposal/package/executor thực vẫn **NOT RUN**. Tài liệu lịch sử V1 và test kỹ thuật còn chứa tên DIRAP/Hermes như bằng chứng/identifier, không phải nhãn sản phẩm hiện hành.
- **P2 residual — build/dependency warning:** bundle có chunk >500 kB; Pydantic forward reference và Starlette TestClient deprecation vẫn tồn tại. Không có lỗi test/runtime hiện hành, nhưng cần theo dõi trước khi tối ưu hiệu năng hoặc cập nhật dependency.
- **Boundary:** real-Hermes chỉ dùng credential store hiện có trong lượt bounded, không sao chép/in token; deploy/cloud, plugin production, live n8n và dữ liệu thật không được dùng.

## Hermes Assistant v2.2 hardening — superseded evidence (2026-08-14)

- **P1 mitigated — SSE token có thể vào nhầm response khi gửi nhanh:** mỗi thread chỉ nhận một `running` turn và event mang `assistant_turn_id`; frontend chỉ render token cho turn tương ứng. Regression backend/frontend đã pass.
- **P1 mitigated — cancel bị ghi đè bởi completion đến muộn:** `cancelled` là terminal durable state; completion chỉ update từ `running`, vì vậy output muộn bị discard. Regression direct pass.
- **P2 residual — cancel là cooperative:** Hermes ACP bridge hiện chưa có primitive dừng prompt portable. Cancel ngăn persistence/UI nhưng không chứng minh process-level inference đã dừng; cần đóng ở lớp ACP khi protocol hỗ trợ.
- **P2 residual — context pack/proposal chưa hoàn chỉnh:** Assistant mới dùng summary Work tối thiểu, chưa dùng managed documents, conversation history, approved knowledge/skills, provenance hay byte-budget thực; không được suy diễn là trả lời từ toàn bộ dữ liệu Work.
- **P2 residual — final acceptance chưa chạy:** browser Cancel trong SQLite/workspace cô lập, reconnect/cancel race với Hermes thật và E2E Work → proposal → approval → executor → report đều **NOT RUN**.

## Local MVP Remediation v1.2 — residual risk verdict (2026-08-12)

- **P0/P1:** không còn blocker đã biết trong phạm vi local pilot sau full regression và UAT cô lập.
- **P2 — bundle size:** production build pass nhưng còn các chunk trên 500 kB; cần lazy-load thêm Mermaid/Monaco trước khi coi hiệu năng là tối ưu.
- **P2 — dependency warnings:** backend còn cảnh báo Pydantic settings `lifespan` và Starlette TestClient deprecation; chưa gây lỗi runtime/test.
- **P2 — Windows permission variance:** một symlink test bị skip khi máy không có quyền tạo link; junction/hardlink escape tests đã pass. Chạy lại symlink fixture trên máy bật Developer Mode nếu muốn đủ ba dạng link.
- **P3 — legacy data quality:** một tiêu đề cũ trong DB hiện hành có ký tự hỏng; không tự sửa vì chính sách không suy đoán/xóa dữ liệu người dùng.
- **Boundary residual:** n8n production, Telegram production, credential production, live restore và deploy không được chạy; test dùng fixture/mock cô lập. Các mục này không được suy diễn là production-ready.

## Codex Acceptance Update — Controlled Knowledge Search (2026-08-10)

- **Resolved R9 — duplicate keyboard dispatch:** the search input now ignores Enter while `searchBusy` is true. A focused UI regression test verifies that no second request is dispatched. This does not change the accepted behavior that editing phrase or purpose invalidates an old request and immediately enables a new one.

## DIRAP v3.0 Controlled Knowledge Search Slice Risks (2026-08-10)

- **R1 — Route `search` bị hiểu nhầm là `{knowledge_record_id}`** (trả 404/trả sai bản ghi). *Mitigation:* endpoint `search` khai báo trước route detail trong cùng router; test chạm route thật với query params (200) và unknown task 404.
- **R2 — Bản ghi nhiệm vụ khác lọt vào kết quả.** *Mitigation:* SQL `WHERE task_id = ?` + endpoint `_get_task_or_404`; test tạo hai nhiệm vụ cùng cụm từ, mỗi nhiệm vụ chỉ thấy bản ghi của mình.
- **R3 — Lọc chính sách sai nhóm** (trả `partial_usable` cho mục đích nghiêm ngặt, hoặc thiếu nhãn mức khả dụng). *Mitigation:* service dùng chung `evaluate_usability` policy v1; chỉ `exploratory_search` chấp nhận `partial_usable`; test phủ cả 6 mục đích (official/legal chỉ regulatory; analysis 4 giá trị; exploratory partial; context/memory vẫn usable khi đủ điều kiện riêng).
- **R4 — Phân trang trước lọc** khiến `total` sai / bỏ sót kết quả đủ điều kiện. *Mitigation:* `search_records` lọc toàn bộ rồi slice `[offset:offset+limit]`, `total` = số sau lọc; test draft (unusable) không tính vào total dù khớp cụm từ.
- **R5 — Tìm kiếm gây thay đổi dữ liệu/audit/migration** (vi phạm chỉ đọc). *Mitigation:* endpoint không audit, không commit, không đổi lifecycle/dimension; `test_search_is_read_only_no_audit_no_db_change` so sánh records/audit/tables trước-sau; migrations giữ nguyên 19.
- **R6 — Truy vấn rỗng/ký tự lạ gây lỗi không kiểm soát.** *Mitigation:* `q` chuẩn hóa (casefold + gộp khoảng trắng), rỗng sau chuẩn hóa → 422 rõ ràng; max_length 200; limit/offset qua `Query(ge/le)`; test 422 đầy đủ.
- **R7 — `authoritative` lọt vào logic tìm kiếm.** *Mitigation:* hoàn toàn không dùng; 0 dòng `authoritative` trong `backend/app` + `frontend/src` (đã verify); lọc dựa duy nhất 5 giá trị `authority_status` đã chốt.
- **R8 — Nút “Tìm” khóa vô thời hạn khi đổi cụm từ/mục đích giữa chừng truy vấn** (phản hồi cũ bị bỏ qua trong `finally` nên `searchBusy` không được giải phóng). *Mitigation (fix 2026-08-10):* `handleSearchInputChange`/`handleSearchTypeChange` tăng `searchSeqRef` (vô hiệu phản hồi cũ) **và** `setSearchBusy(false)` (giải phóng nút ngay) — vẫn một nguồn trạng thái `searchBusy` duy nhất; phản hồi cũ về sau `seq !== searchSeqRef.current` → bỏ hoàn toàn (không ghi đè/ghép/đổi busy). Đã verify bằng test hồi quy 6 bước trong `DirapPanel.test.tsx` (**4 passed**): nút bị khóa khi busy → đổi mục đích → nút bật lại → bấm nút chạy truy vấn B (không dùng Enter) → B về trước hiển thị → A về sau không ghi đè.

## Active Risks

### DIRAP v3.0 Usability Read-only Slice
- Risk: `overall_usability_state` could be persisted (violating read-only); mitigation: **verified (2026-08-10)** — engine is pure (no DB/HTTP), endpoint performs SELECT-only, no audit event, no commit, no migration; `test_api_readonly_no_db_change_no_audit_no_migration` compares dims/audit/table list before/after.
- Risk: `authoritative` could leak into the policy as a sixth data label; mitigation: **verified** — policy uses only the closed 5-value vocabulary; grep `authoritative` in `backend/app` + `frontend/src` = 0 lines; `usable_for_query_types` includes only `usable` purposes, never partial (test).
- Risk: official_search/legal_review could accept non-regulatory authority (organizational/expert/derived) via inference; mitigation: **verified** — policy v1 allows only `{regulatory}` for both; engine unit tests + API test (`test_api_official_search_rejects_organizational`, `test_policy_official_legal_reject_non_regulatory`) refuse all four other values. `derived` deferred until provenance + verification rules exist (Q6 decision).
- Risk: analysis_input could wrongly refuse valid authorities; mitigation: **verified** — accepts `regulatory|organizational|expert|derived` when source+calculation verified (`test_policy_analysis_input_accepts_four_values`, `test_api_analysis_input_accepts_non_regulatory`).
- Risk: memory_query could be blocked by source/authority even when owner accepted; mitigation: **verified** — owner-only rule; unit + API tests with everything else unset/`none` (usable) and pending/rejected (unusable).
- Risk: partial_usable treated as "dùng được" or `active` lifecycle turned into usable by default; mitigation: **verified** — `usable_for_query_types` excludes partial; UI banner: "kết quả chính sách chỉ đọc… không làm active thành có thể sử dụng mặc định"; exclusions list shown per record.
- Risk: usability computed for a record of another work item or a stale query type; mitigation: **verified** — endpoint reuses `_get_task_or_404` + `_get_knowledge_record_or_404` (404 foreign/missing); `query_type` is a Literal of exactly 6 values (422 otherwise); engine raises ValueError for unknown types.

### DIRAP v3.0 Knowledge Review Slice
- Risk: review could write `owner_acceptance_state=approved` or accept arbitrary authority strings, making records inconsistent with the approved policy; mitigation: **verified (2026-08-09)** — approve writes `accepted`; migration **0019** normalizes legacy `approved` rows (0018 untouched); `authority_status` is a schema-Literal closed vocabulary (422 outside, 400 for `none`); UI select prevents free text; regressions: `test_approve_accepts_all_valid_authority_statuses`, `test_approve_rejects_unknown_authority_statuses`, `test_migration_0019_normalizes_stale_approved_rows`.
- Risk: a record could transition outside the allowed chain (`draft → review_pending → active|rejected`), e.g. approving a draft directly or acting on a terminal state; mitigation: **verified (2026-08-08)** — every transition endpoint guards the exact expected status and returns **409** with the allowed chain for anything else (`test_invalid_transitions_all_rejected`).
- Risk: `verified` could be claimed without evidence (e.g. `authority_status` written by the client); mitigation: **verified** — clients cannot set status or any of the four dimensions; the server computes dimensions only from supplied evidence references. Approve requires reviewer + source reference + authority status ≠ `none` + authority reference (422/400 otherwise); calculation is `verified` only when a calculation reference is supplied; nothing is marked verified without a reference (`test_approve_missing_required_fields_rejected`, `test_approve_with_calculation_reference_sets_verified`).
- Risk: the `authoritative` policy vocabulary could be conflated with the lifecycle's authority dimension; mitigation: **verified** — `authority_status` is a closed vocabulary whose members never include `authoritative` (schema Literal → 422), the UI selects from `regulatory|organizational|expert|derived` only, and no code infers `authoritative`; policy-derived usability stays out of scope until vocabularies are reconciled.
- Risk: rejection could look like verification or delete the record; mitigation: **verified** — reject sets `owner_acceptance_state='rejected'`, keeps source linkage, evidence (`reviewer` + `decision_reason`) and the full audit trail; the record remains listed (`test_reject_sets_owner_rejected_keeps_history`).
- Risk: a reviewer could reject without a reason or approve with `authority_status='none'`; mitigation: **verified** — reject requires reviewer + reason (422); approve with `authority_status='none'` → 400 (`test_reject_requires_reviewer_and_reason`).
- Risk: retries could duplicate evidence or decisions; mitigation: **verified** — submit/approve/reject reuse `Idempotency-Key`; same key + same payload replays with HTTP 200 and a single evidence set + single audit; same key + different payload → 409 (`test_submit_and_approve_idempotent`).
- Risk: review actions could target another work item's record; mitigation: **verified** — submit/approve/reject resolve the record against the work item and return 404 for foreign/unknown ids (`test_review_scoped_to_work_item`).
- Risk: UI could present `active` as "có thể sử dụng"; mitigation: **verified** — the panel shows an explicit banner on `active`: "phản ánh kết quả rà soát; không ngụ ý có thể sử dụng theo chính sách", and labels the lifecycle chain in the expandable detail.

### DIRAP v3.0 Knowledge Records Slice
- Risk: a knowledge record could be created from a **stale** extraction, producing draft tri thức gắn với nội dung nguồn đã thay đổi; mitigation: **verified and accepted (2026-08-08)** — create re-checks freshness at creation (sandbox re-read + SHA-256 recompute) and returns **409** for a stale extraction, so no record is created from outdated source (`test_create_from_stale_extraction_rejected`).
- Risk: a record could be created from an extraction/record ID that belongs to **another work item** (cross-session/cross-task data coupling); mitigation: **verified** — create loads the extraction's source file against the given task and rejects with **404 "does not belong"**; record IDs are validated against the extraction; unknown IDs → 404 (`test_create_foreign_extraction_rejected`, `test_create_unknown_extraction_404`, `test_create_record_not_in_extraction_404`).
- Risk: retries could create **duplicate** knowledge records; mitigation: **verified** — same `Idempotency-Key` + same payload replays the existing record with HTTP 200 (single row + single audit); same key + different payload → 409 conflict (`test_create_idempotent_replay`, `test_create_idempotency_conflict`).
- Risk: a draft could be implicitly presented as **verified/in-use/approved**; mitigation: **verified** — server hardcodes `status='draft'`, client cannot override; UI shows a "DRAFT — bản nháp, chưa xác minh" badge (`test_create_knowledge_record_status_always_draft`).
- Risk: knowledge records could leak across work items; mitigation: **verified** — list/detail are scoped to the task; another work item sees an empty list / 404 detail (`test_list_and_detail_scoped_to_work_item`).
- Risk: unknown provenance (where did this record come from?) undermines traceability; mitigation: **verified** — each record stores task/extraction/record/source IDs, source SHA-256 snapshot, extractor version, provenance, content; every creation writes `dirap.knowledge_record.created` audit (`test_create_knowledge_record_happy_path`).
- Risk: freshly created extractions did not expose record `id`, so the UI could not create knowledge records without a second lookup; mitigation: **FIXED** — `POST .../extract` create path now returns `records[].id`; covered by existing extraction + knowledge tests.

### DIRAP v3.0 Extraction Slice
- Risk: re-extracting unchanged source+version creates duplicate `fresh` extractions; mitigation: **verified and accepted (2026-08-02)** — `POST .../extract` is idempotent on `(source_file_id, source_sha256, EXTRACTOR_VERSION)`; unchanged input returns the existing fresh extraction with HTTP 200 and creates no new rows or `completed` audit (regression test: `test_extract_idempotent_unchanged_source`).
- Risk: old results stay `fresh` in list/detail until a new extraction is requested, so stale data could be presented as current; mitigation: **verified and accepted (2026-08-02)** — GET list/detail refresh freshness before responding (sandbox re-read + SHA-256 recompute) and mark changed-hash runs `stale` with one `dirap.extraction.staled` audit per change (regression tests: `test_list_marks_stale_on_source_change`, `test_detail_marks_stale_on_source_change`).
- Risk: freshness check silently keeps `fresh` when the source file is missing, unsupported, or sandbox-rejected; mitigation: **verified** — clear HTTP errors (404/415/403) in all three cases (`test_list_and_detail_missing_file_clear_error`, `test_list_sandbox_rejection_clear_error`).
- Risk: extraction reads files from disk using a stored path — if the path is tampered in the DB or a symlink replaces the real file, the read could escape the workspace; mitigation: **verified** — `resolve_and_validate_path` re-checks workspace containment before every read (test: DB-tampered traversal → 403, symlink escape → 403/skip-with-reason).
- Risk: extraction provenance could drift (e.g., old records shown for new content); mitigation: each extraction stores `source_sha256` + `extractor_version` + `extracted_at`; stale runs are flagged and never presented as current.
- Risk: `.docx` parsing via stdlib could reject real-world documents (tables, headers); mitigation: accepted limitation for this slice (paragraph-level text via `word/document.xml`); no AI/OCR/dependency expansion authorized.
- Risk: audit coverage for extraction lifecycle could be incomplete; mitigation: `dirap.extraction.completed` (per run), `dirap.extraction.staled` (per stale marking), `listed`/`viewed` read events.

### DIRAP v3.0 Specific
- Risk: `POST /api/dirap/work-items/{id}/source-files` can duplicate attachment rows on retry because it has no idempotency key handling; mitigation: **FIXED** — reuse existing `IdempotencyRepository` with `Idempotency-Key` + SHA256 request hash; same key + same payload returns existing (200), same key + different payload returns 409 conflict.
- Risk: claimed symlink-escape coverage is absent from `backend/tests/test_dirap.py`; mitigation: **FIXED** — added `test_attach_source_file_symlink_escape` that creates a symlink/junction when permitted; skips with explicit reason only when link creation is unavailable (OSError/privileges).
- Risk: `backend/.venv` currently fails to import `mcp.server.fastmcp`; mitigation: **FIXED** — root cause was `pyproject.toml` missing `<2.0.0` upper bound, allowing `mcp==2.0.0` installation. Pin `mcp>=1.2.0,<2.0.0` applied; venv reinstalled with `mcp==1.29.0`; exact commands reproduce 10/10 DIrap tests.
- Risk: trailing whitespace remains in `AI_VERIFICATION.md:28`; mitigation: remove the whitespace and verify with `git diff --check`.
- Risk: the primary Hermes worktree contains unrelated CP12 changes; mitigation: DIRAP work is confined to the isolated `DIRAP-Personal-v3` worktree and must be rebased before integration.

### V1 Residual Risks (Non-Blocking)
- Outbox dispatcher shutdown may be delayed up to `outbox_dispatcher_poll_seconds` (default 5s).
- Migration 0014 callable pattern is the only guarded migration; older migrations still use `executescript`.
- Pre-existing `StarletteDeprecationWarning` from `fastapi.testclient`.
- Frontend build passes with Vite large chunk warnings from heavy diagram/math dependencies.
- 2 pre-existing Hermes spawn test failures on Windows due to subprocess pipe `PermissionError`.

### Historical Risks (Mitigated in Removed Scope)
- Codex quota exhaustion risk was mitigated by using DIRAP worktree instead of primary Hermes worktree.
- CP6-CP10 risks are resolved/closed in their respective checkpoints.

## Mitigations

- DIRAP work is confined to the isolated `DIRAP-Personal-v3` worktree; no changes to primary Hermes worktree.
- `AI_STATE.json` keeps explicit checkpoint state; no auto-commit, push, merge, or deploy.
- Source file attachment uses existing sandbox path validation, not custom logic.
- Every mutation writes an audit event via the existing audit service.
- Idempotency prevents duplicate work items on retry.
- Tests verify path traversal rejection, absolute path rejection, and file-not-found errors.
- No parallel task/session/audit system was created; DIRAP reuses existing tables.
