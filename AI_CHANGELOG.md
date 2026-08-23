# AI Changelog

## 2026-08-15 — DIRAP Local Workbench branding and actual Chrome zoom 200%

- Đổi tên sản phẩm hiển thị từ Hermes Local sang **DIRAP Local Workbench** trong browser title, App Shell/product eyebrows, FastAPI display title/log, README và tài liệu vận hành hiện hành. Dùng **Trợ lý Hermes** khi nói về agent; giữ nguyên package/API/DB/env/schema/checkpoint/credential identifiers.
- Thêm regression cho browser title, App Shell branding và FastAPI title; fresh QA đạt backend **465 passed, 1 skipped**, frontend **172 passed**, lint 0 error/4 warning, type-check/build pass.
- Chạy Chrome 151 native zoom 200% bằng profile, SQLite và workspace tạm `uat-codex-`; lưu screenshot/log tại `output/playwright/v22-brandzoom-20260815-0900/`. Không dùng CSS zoom hay device emulation.
- Giữ `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`: full screen×state×viewport cross-product chưa hoàn tất; usability 5 người vẫn `NOT RUN` theo quyết định hoãn hậu v2.2.

## 2026-08-14 — DIRAP v2.2 technical completion (checkpoint remains PARTIAL)

- Hoàn thiện Assistant context pack deterministic/provenance, action proposal idempotent/approval, thread–conversation migration `0028`, Work Hub plan/conversation/report, Knowledge Summary, Review projection, Marketplace và App Shell responsive.
- Sửa runtime: `apiFetch` giữ JSON Content-Type khi mutation có Idempotency-Key; báo cáo tạo thành artifact qua Browser UAT. Composer mobile được cố định phía trên bottom navigation; nút Ngữ cảnh được đặt trên composer và drawer đóng bằng Escape.
- Full evidence: backend **452 passed, 1 skipped**; frontend **166 passed**; lint 0 error/4 warning cũ; type-check/build pass; health 20/20; restart smoke và Browser UAT SQLite/workspace tạm pass, sau đó được dọn.
- Không chuyển `DIRAP_V22_VALIDATED`: fidelity ledger/manual matrix đầy đủ và usability acceptance 5 người (>=4/5) là `NOT RUN`; không commit, push, deploy hoặc đụng credential/dữ liệu thật.

## 2026-08-14 — Hermes Assistant v2.2 hardening (in progress, no checkpoint transition)

- Chặn hai assistant response chạy song song trong cùng thread và chặn archive thread khi response đang chạy.
- Bổ sung `assistant_turn_id` tương thích ngược cho SSE token/done/error; frontend chỉ nối token vào đúng running turn.
- Stream tự đăng ký lại sau terminal event để prompt tiếp theo trong cùng thread vẫn nhận token live.
- Thêm `POST /api/assistant/turns/{id}/cancel`, audit `assistant.turn.cancelled` và UI “Hủy phản hồi”. Completion đến muộn bị discard bởi guarded update, không ghi part hay phát terminal event thứ hai.
- Dọn mapping read-only ACP theo request để tránh tích lũy mapping Python-side.
- Thêm regression cho single-run/archive, cancel audit/idempotency, late completion discard và frontend token foreign-turn/cancel.
- Không migration, dependency, credential, deploy hay checkpoint/state transition.

## 2026-08-12 — Local MVP remediation v1.2 validated

- Đóng các lỗi trust-boundary và integrity trọng yếu: atomic approval/idempotency, sandbox revalidation, external-effect dedupe, archived-session guards, file revisions, extraction limits và audit redaction.
- Đóng cross-session/scope races và recovery cho chat, editor, files, memory, DIRAP, Memory Hub và approvals.
- Thêm trải nghiệm người dùng cuối: Tổng quan, Công việc, Tài liệu/artifacts, Báo cáo, Hộp duyệt, Cài đặt; navigation responsive; loading/error/empty states; semantic keyboard controls và focus trap.
- Hoàn thiện migration 0022–0024, overview/artifact/context/backup APIs, báo cáo Markdown/HTML và công cụ restore offline có dry-run/rollback.
- Kiểm tra cuối: backend 416 pass/1 skip; frontend 134 pass; lint/type-check/build pass; runtime/browser UAT pass. Checkpoint chuyển sang `DIRAP_LOCAL_MVP_REMEDIATION_V1_2_VALIDATED`.

## 2026-08-10 - Controlled Knowledge Search accepted

- Codex accepted the controlled, task-scoped and read-only knowledge search slice after independent backend/frontend verification.
- Fixed a final UI concurrency edge case: Enter cannot start a duplicate search while the active search is busy.
- Added the corresponding frontend regression test; no backend, migration, dependency or policy change was made for this repair.

## 2026-08-10 (Hermes fix: UI async-safety — nút “Tìm” không khóa vô thời hạn; đồng bộ hồ sơ quản trị)

- **Fix (frontend-only, 2 tệp):** `DirapPanel.tsx` — `handleSearchInputChange`/`handleSearchTypeChange` giờ cũng `setSearchBusy(false)`: đổi cụm từ hoặc mục đích giữa chừng truy vấn lập tức vô hiệu phản hồi cũ (qua `searchSeqRef`) VÀ giải phóng nút “Tìm” (vẫn một nguồn trạng thái `searchBusy` duy nhất). Phản hồi cũ về sau không ghi đè, không ghép kết quả, không đổi trạng thái truy vấn mới. `DirapPanel.test.tsx` — test hồi quy 6 bước bằng click nút (không dùng Enter): truy vấn A chưa về → đổi mục đích → nút bật lại → bấm nút chạy B → B về trước hiển thị → A về sau bị bỏ. **4 passed**, type-check đạt; không chạm backend/API/schema/migration/dependency/policy.
- **Đồng bộ hồ sơ quản trị:** `AI_TASK.md` (Done When + QA chỉ còn Controlled Search — bỏ tiêu chí submit/approve/reject/evidence của Knowledge Review); `CURRENT_CHECKPOINT.md` (bỏ `search` khỏi ngoài phạm vi, viết lại Done When/Acceptance boundary — không còn câu “does not authorize search”); `PROJECT_STATE.md` (dán nhãn Gate Report cũ là bằng chứng lịch sử CP10, bổ sung mục bằng chứng hiện hành của lát Controlled Search, giữ IMPLEMENTED chờ Codex re-review).

## 2026-08-10 (Hermes implementation: Controlled Knowledge Search)

- Implemented the DIRAP v3.0 controlled knowledge search slice in the isolated worktree `DIRAP-Personal-v3`; **AWAITING CODEX RE-REVIEW** (state `DIRAP_V3_CONTROLLED_SEARCH_IMPLEMENTED`, next_agent `codex`).
- **Service** (`backend/app/services/knowledge_search.py`, pure, stdlib-only): `normalize_search_text` (casefold + gộp khoảng trắng), `find_match` trên `content`/`provenance` (`matched_field`), `content_excerpt` (≤200 ký tự), `search_records` — đối sánh → lọc chính sách v1 (`evaluate_usability`) → phân trang; `total` = số bản ghi sau lọc; không bao giờ trả `unusable`.
- **Schema** (`backend/app/api/schemas.py`): `DirapKnowledgeSearchResult` (record_id, content_excerpt, provenance, lifecycle_state, bốn chiều gốc, matched_field, usability_state) + `DirapKnowledgeSearchResponse` (query_type, total, limit, offset, results).
- **Endpoint** (`backend/app/api/dirap.py`): `GET /api/dirap/work-items/{task_id}/knowledge-records/search?q=&query_type=&limit=&offset=` — route cố định `search` khai báo TRƯỚC `/{knowledge_record_id}`; `q` không rỗng sau chuẩn hóa (→ 422), tối đa 200 ký tự; limit 1–100 (mặc định 20), offset ≥ 0; query_type lạ → 422; task lạ → 404; tuyệt đối chỉ đọc (không audit, không commit, không lưu kết quả, không migration — vẫn 19).
- **Frontend**: `dirap.ts` types + `searchKnowledgeRecords`; `DirapPanel.tsx` block "Tìm kiếm tri thức (chỉ đọc)" — ô cụm từ, select 6 mục đích, kết quả kèm badge mức khả dụng + badge vòng đời + trường khớp + excerpt + provenance + bốn chiều, dòng ghi chú "kết quả đã lọc theo chính sách v1; active không tự nghĩa là dùng được", nút "Tải thêm" (offset += limit); exploratory hiển thị rõ `partial_usable`.
- **Tests** (`backend/tests/test_dirap_controlled_search.py`, 13 tests): đối sánh casefold/multi-space, provenance, scoping nhiệm vụ, 404/422, official_search & legal_review chỉ trả `regulatory` (unusable bị loại), analysis_input nhận 4 authority, exploratory trả partial (mục đích khác không), phân trang sau lọc, default limit/offset, readonly (records/audit/tables không đổi).
- Full six-suite result: **85 passed, 1 permitted symlink skip**; frontend lint/type-check/build và `git diff --check` đạt; 0 dòng `authoritative`; không dependency mới.

## 2026-08-10 (Codex acceptance: Usability Read-only)

- Codex accepted the v1 read-only usability slice after inspecting the pure policy engine, scoped GET endpoint, response contract, UI and no-mutation regression. Five focused DIRAP suites: **72 passed, 1 permitted symlink skip**; frontend lint/type-check/build and `git diff --check` passed.
- Acceptance is limited to computed policy explanations. Search, agents, AI, automatic memory use, deployment and production remain out of scope.

## 2026-08-10 (Hermes implementation: Usability Read-only)

- Implemented the DIRAP v3.0 read-only usability slice in the isolated worktree `DIRAP-Personal-v3`; **AWAITING CODEX RE-REVIEW** (state `DIRAP_V3_USABILITY_READONLY_IMPLEMENTED`, next_agent `codex`).
- **Policy engine** (`backend/app/services/usability_policy.py`, pure, stdlib-only): six canonical query types; per-type rules of policy v1 (official_search/legal_review require `authority_status='regulatory'`; analysis_input accepts `regulatory|organizational|expert|derived`; exploratory_search partial on verified source; context_packaging needs source+owner; memory_query needs owner only; `none` accepted in any-conditions only). No `authoritative` label used/stored/inferred.
- **Schema** (`backend/app/api/schemas.py`): `DirapUsabilityQueryType` (Literal 6 giá trị), `DirapUsabilityState`, `DirapUsabilityExclusionResponse`, `DirapUsabilityResponse` (`record_id`, `lifecycle_state`, `query_type`, four ground dimensions, `overall_usability_state`, `policy_version='v1'`, `exclusions[]`, `usable_for_query_types[]` — chỉ đọc, không bao giờ lưu).
- **Endpoint** (`backend/app/api/dirap.py`): `GET /api/dirap/work-items/{task_id}/knowledge-records/{knowledge_record_id}/usability?query_type=...` — task-scoped (404 cho bản ghi lạ/khác nhiệm vụ), 422 cho `query_type` sai, không audit, không commit, không migration, không đổi lifecycle/dimension.
- **Frontend**: `dirap.ts` types + `getKnowledgeUsability`; `DirapPanel.tsx` block "Khả dụng theo chính sách (chỉ đọc)" per record — select 6 mục đích, badge usable/partial_usable/unusable, danh sách lý do loại trừ, `usable_for_query_types`, ghi rõ "không lưu; active không phải 'có thể sử dụng' mặc định".
- **Tests** (`backend/tests/test_dirap_usability.py`, 20 tests): từng quy tắc của 6 mục đích (usable/partial/unusable), official_search & legal_review từ chối organizational/expert/derived, analysis_input chấp nhận 4 giá trị, memory_query không bị chặn bởi authority/source khi owner=accepted, `none` trong any, usable_for_query_types chỉ gồm usable, 404 foreign/missing, 422 query_type lạ, readonly: không đổi dims/lifecycle, không audit mới, không bảng mới (không migration).
- **QA**: 5 suite DIRAP = **72 passed, 1 skipped** (skip symlink môi trường được phép); frontend lint 0 errors (6 warnings exhaustive-deps pre-existing), type-check ✅, build ✅; `git diff --check` clean; 0 dòng `authoritative` trong backend/app + frontend/src; migrations giữ nguyên 19.

## 2026-08-09 (Codex acceptance: Knowledge Review)

- Codex independently accepted the controlled Knowledge Review slice after inspecting migration 0019, API contracts, authority select and idempotency behavior. Focused DIRAP tests: **52 passed, 1 permitted symlink skip**; frontend lint/type-check/build and `git diff --check` passed.
- Acceptance is limited to lifecycle review, evidence, four independent dimensions, task scoping, idempotency and audit. Policy-derived usability, `authoritative` mapping, AI, search, deployment and production remain out of scope.

## 2026-08-09 (Codex review: changes required)

## 2026-08-09 (Hermes fixes applied: contract corrections)

- `owner_acceptance_state` now writes `accepted` (migration **0019** normalizes any legacy `approved` rows; 0018 untouched). Audit action renamed to `dirap.knowledge_record.accepted`.
- `authority_status` constrained to the closed vocabulary `none|regulatory|organizational|expert|derived`: schema Literal rejects anything else with 422 and `none` with 400; the UI replaced the free-text input with a select.
- `backend/tests/test_dirap_knowledge_review.py` grew from 9 to 13 tests: every valid authority value on approve; unknown/`'none'`-like values rejected with no side effects; migration 0019 normalization of legacy `approved` rows; idempotent reject replay (no duplicate evidence/audit, different payload → 409).

- Knowledge Review is not accepted. Codex found a mismatch between `approved` in code and `accepted` in the approved owner-acceptance policy, plus an unconstrained `authority_status` input.
- Required repair is deliberately narrow: normalize `approved → accepted`, constrain new authority values to the defined vocabulary, add regressions including reject idempotency, and do not add policy-derived usability.

## 2026-08-08 (Hermes implementation: Knowledge Review)

- Implemented the DIRAP v3.0 Knowledge Review slice in the isolated worktree `DIRAP-Personal-v3`; **AWAITING CODEX RE-REVIEW** (state `DIRAP_V3_KNOWLEDGE_REVIEW_IMPLEMENTED`, next_agent `codex`).
- **Migration 0018**: `dirap_knowledge_records` gained the four independent verification dimensions (`source_verification_state`, `calculation_verification_state`, `owner_acceptance_state`, `authority_status` — NOT NULL with defaults) + new `dirap_knowledge_evidence` table (evidence records with type/reference/note/timestamp) + index.
- **Backend** (`backend/app/api/dirap.py`): 3 new endpoints — `POST .../knowledge-records/{id}/submit` (draft → review_pending), `POST .../knowledge-records/{id}/review/approve` (review_pending → active), `POST .../knowledge-records/{id}/review/reject` (review_pending → rejected). All work-item scoped (404), lifecycle-guarded (409 for every other transition), idempotent via `Idempotency-Key`, and audited (`dirap.knowledge_record.submitted` / `.approved` / `.rejected`).
- **Schemas**: `status` widened to `draft|review_pending|active|rejected`; response carries the four dimensions; detail returns `evidence[]`; approve/reject/submit request models with required references (422 missing, 400 `authority_status='none'`).
- **Guards**: approve computes dimensions only from supplied evidence references — source/calc verified only with their reference, calculation stays unverified without one; no `authoritative` label inferred; reject never marks anything verified and never deletes source/audit history.
- **Frontend**: `dirap.ts` review types + `submitKnowledgeRecord`/`approveKnowledgeRecord`/`rejectKnowledgeRecord`; `DirapPanel.tsx` — lifecycle badges (DRAFT/CHỜ DUYỆT/ACTIVE/TỪ CHỐI), four dimension chips, "Gửi rà soát" on drafts, inline approve/reject form, evidence list, and an explicit banner that `active` is not "có thể sử dụng theo chính sách".
- **Tests**: `backend/tests/test_dirap_knowledge_review.py` — 9 tests (transitions, dims, evidence rows, audit, scoping, idempotency, reject keeps history). Focused DIRAP suite: **48 passed, 1 skipped**; frontend type-check/build/lint (0 errors), `git diff --check` clean.

## 2026-08-08 (Codex authorization: Knowledge Review)

- User authorized controlled review of draft knowledge records: lifecycle submit/approve/reject, evidence references, four independent ground dimensions and audit.
- Policy-derived usability, search and AI remain excluded because the approved policy uses `authoritative` while the lifecycle design defines `regulatory`, `organizational`, `expert` and `derived`; no mapping is inferred in this slice.

## 2026-08-08 (Codex acceptance: Knowledge Records)

- Codex accepted DIRAP v3.0 Knowledge Records after independently running `pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py -q`: 39 passed, 1 permitted symlink skip; frontend lint/type-check/build and `git diff --check` passed.
- Acceptance covers only `draft`, source-grounded records with provenance, stale-source refusal, task scoping, idempotency and audit. It does not imply verification, usability, AI, search, workflow completion, deployment or production readiness.

## 2026-08-07 (Hermes implementation: Knowledge Records)

- Implemented DIRAP v3.0 Knowledge Records slice in the isolated worktree `DIRAP-Personal-v3` (state was `DIRAP_V3_KNOWLEDGE_RECORDS_AUTHORIZED`); **AWAITING CODEX RE-REVIEW**.
- **Migration 0017**: `dirap_knowledge_records` table — one draft record per creation, storing source-grounded provenance: task/extraction/extraction-record/source-file IDs, source SHA-256 snapshot, extractor version, provenance, content, status (always `draft`), note, timestamps.
- **Backend** (`backend/app/api/dirap.py`): 3 new endpoints — `POST .../knowledge-records` (201; 200 idempotent replay; 409 stale / key-conflict; 404 foreign/unknown IDs), `GET .../knowledge-records` (task-scoped list, newest first), `GET .../knowledge-records/{id}` (task-scoped detail).
- **Guards**: create only from a fresh extraction record that belongs to the work item; freshness re-checked at creation (sandbox re-read + re-hash); `draft` hardcoded server-side; idempotency via existing `Idempotency-Key` mechanism; audit `dirap.knowledge_record.created` on every successful creation.
- **Extraction fix**: fresh-create path now returns `records[].id` (previously `null`), so the UI can create knowledge records directly.
- **Frontend**: `dirap.ts` knowledge API + `DirapPanel.tsx` — per-record "→ Tri thức" button (disabled for stale, idempotency key `kr-{recordId}`), "Bản ghi tri thức" list with DRAFT badge + expandable provenance detail.
- **Tests**: new `backend/tests/test_dirap_knowledge.py` — 9 tests (provenance happy path, always-draft, stale 409, foreign extraction 404, unknown IDs 404, idempotent replay 200, key conflict 409, task scoping).
- Combined DIRAP suite: `pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py -q` → **39 passed, 1 skipped**; `git diff --check` clean; frontend type-check/build/lint pass (0 errors).
- No changes to the primary Hermes worktree.

## 2026-08-07 (Codex authorization)

- User authorized the next DIRAP v3.0 slice: source-grounded draft Knowledge Records from fresh extraction records.
- No AI, activation, usability evaluation, search, deployment or production claim is authorized in this slice. Hermes implements; Codex reviews before acceptance.

## 2026-08-02 (Codex acceptance)

- Codex accepted DIRAP v3.0 Extraction after independently re-running `pytest tests/test_dirap.py tests/test_dirap_extraction.py -q`: 30 passed, 1 permitted symlink skip; `git diff --check` clean.
- Acceptance covers deterministic provenance-bearing extraction, idempotent unchanged-source replay, and freshness refresh on list/detail. It does not imply AI extraction, workflow completion, deployment, or production readiness.

## 2026-08-01 (Codex CHANGES_REQUIRED fixes)

- Applied fixes for the two Codex findings on the DIRAP v3.0 Extraction slice (state was `DIRAP_V3_EXTRACTION_CHANGES_REQUIRED`).
- **Fix 1 — duplicate fresh extractions**: `POST .../extract` is now idempotent on `(source_file_id, source_sha256, EXTRACTOR_VERSION)`. Re-extracting unchanged content returns the existing fresh extraction with HTTP 200 — no new extraction row, no new records, no second `dirap.extraction.completed` audit.
- **Fix 2 — stale only applied on re-extract**: `GET .../extractions` (list) and `GET .../extractions/{id}` (detail) now refresh freshness before responding — re-read the source through the sandbox, recompute SHA-256, mark mismatched fresh runs `stale` (one `dirap.extraction.staled` audit per real change). Missing file → 404, unsupported type → 415, sandbox rejection → 403; never silently keeps `fresh`.
- **Tests**: replaced `test_extract_same_hash_keeps_fresh` with `test_extract_idempotent_unchanged_source`; added `test_list_marks_stale_on_source_change`, `test_detail_marks_stale_on_source_change`, `test_list_and_detail_missing_file_clear_error`, `test_list_sandbox_rejection_clear_error`.
- Combined DIRAP suite: `pytest tests/test_dirap.py tests/test_dirap_extraction.py` → **30 passed, 1 skipped**.
- Frontend unchanged in this round (no type-check/build run needed).
- No changes to the primary Hermes worktree.

## 2026-07-31

- Implemented DIRAP v3.0 Extraction slice in isolated worktree `DIRAP-Personal-v3` (awaits Codex review).
- **Migration 0016**: added `dirap_extractions` + `dirap_extraction_records` tables (SHA-256, extracted_at, extractor_version, file_type, status, record_count; ordered records with seq + provenance).
- **New service** `backend/app/services/extraction.py`: deterministic stdlib-only extraction for `.txt`, `.md`, `.csv`, `.json`, `.docx` (no AI, no PDF/OCR, no new dependency).
- **Backend** (`backend/app/api/dirap.py`): 3 new endpoints — `POST .../extract` (creates extraction, marks changed-hash predecessors stale, audit event), `GET .../extractions` (list newest first), `GET .../extractions/{id}` (detail + ordered record preview).
- **Frontend**: per source file — extract button, status badge, record count/type, hash/version/time, preview pane (`frontend/src/api/dirap.ts`, `frontend/src/components/DirapPanel.tsx`).
- **Tests**: new `backend/tests/test_dirap_extraction.py` — 16 pass + 1 skipped (symlink unsupported); per-type extraction incl. stdlib-built .docx fixture, hash/provenance, stale-on-change, audit events, 415/400/404/403 sandbox paths.
- Combined DIRAP suite: `pytest tests/test_dirap.py tests/test_dirap_extraction.py` → **26 passed, 1 skipped**.
- Frontend type-check and build pass.
- No changes to the primary Hermes worktree.

## 2026-07-31 (Foundation)

- Codex accepted DIRAP v3.0 Foundation on 2026-07-31 after independently verifying the pinned compatible `mcp` range, FastMCP import, 10 focused DIRAP tests, and clean diff hygiene.

- Implemented DIRAP v3.0 Foundation vertical slice in isolated worktree `DIRAP-Personal-v3`.
- **Migration 0015**: added `dirap_source_files` table (id, task_id FK to tasks, file_path, file_name, note, attached_at).
- **Backend** (`backend/app/api/dirap.py`): 5 new endpoints for work item CRUD, source file attachment with sandbox path validation, task package view with audit trail.
- **Frontend**: DIRAPPanel component with list/create/detail views; DIRAP tab in sidebar; API client.
- **Tests**: 10 focused backend tests covering creation, idempotency, listing, detail with audit, source file attachment, path traversal rejection, file-not-found safety, and symlink/junction escape.
- Full backend suite: 281/283 pass (2 pre-existing Hermes spawn failures).
- Frontend type-check and build pass.
- No changes to the primary Hermes worktree.

## 2026-07-04

- Completed and verified CP10 Cleanup implementation. All 269 backend tests pass successfully.
- Verified that `X-Deprecated: true` header is returned on legacy routes (`/task-runs/latest`, `/task-runs/{id}`, `/curate`) and metrics endpoint (`GET /api/metrics/deprecated`) works.
- Made the decision to retain the deprecated route handlers for frontend legacy fallback compatibility, cleaning up no dead code without human approval.
- Closed checkpoint CP10 Cleanup and set state to `CP10_COMPLETE` in all coordination files. All checkpoints of Hermes Local Stack V1 are now complete.
- Opened checkpoint CP10 Cleanup following explicit human approval ("CP10 CLEANUP").
- Opened checkpoint CP8 Model Fallback following explicit human approval ("tiếp tục").
- Updated project/checkpoint/AI coordination files from CP7 closed gate to CP8 IN_PROGRESS / manual editing via OpenCode (Writer) and Antigravity (Checker).
- Set scope strictly to CP8 Model Fallback (retry, fallback, cooldown, immediate error aborts).
- Completed CP7 Telegram Channel implementation via OpenCode (Writer) and verified by Antigravity (Checker).
- Verified 12/12 CP7 specific backend tests pass, covering HMAC verification, allowlist, idempotency, and callback token lifecycle. Total backend tests pass: 224/224.
- Closed checkpoint CP7 and set state to `CP7_COMPLETE` with `human_approval_required = true` before CP8.
- Opened checkpoint CP7 Telegram Channel following explicit human approval ("Mở checkpoint mới").
- Updated project/checkpoint/AI coordination files from CP6 closed gate to CP7 IN_PROGRESS / manual editing via OpenCode (Writer) and Antigravity (Checker).
- Set scope strictly to CP7 Telegram webhook security and normalization per ADR-003.
- Completed CP6 Outbox Dispatcher verification and sign-off by Antigravity (Checker) and OpenCode (Writer).
- Added atomic outbox notification for `task.cancelled` in `TaskService` and verified 39/39 backend unit tests pass.
- Moved user operational test file to `workspace_outputs/` to maintain 100% clean git working tree for `backend/`.
- Received explicit Human Reviewer approval to close CP6.
- Updated project/checkpoint/AI state from CP6 review to `CP6_COMPLETE` with `next_agent = human` and `human_approval_required = true` (stopped at gate awaiting CP7 approval).
- Paused/suspended automation runner due to Antigravity CLI timeout.
- Switched workflow to manual editing/review via Antigravity and OpenCode directly.
- Updated `AI_STATE.json` to state `BLOCKED` with standard UTF-8 without BOM (fixing BOM parse errors).
- Updated coordination files (`AI_HANDOFF.md`, `AI_TASK.md`, `AI_VERIFICATION.md`) to reflect manual execution mode.
- Verified that all 38 CP6-related backend tests pass successfully.
- CP6 Outbox Dispatcher implemented by Codex:
  - Added retry-aware outbox claiming with lease recovery and duplicate active-lock protection.
  - Added deterministic outbox `insert_once` for stable idempotency keys.
  - Added `OutboxDispatcher` service with injected sender, idempotency key forwarding, retry/dead-letter handling, and audit events for dispatch sent/error outcomes.
  - Added terminal task success/failure outbox event creation in the same transaction as task status/event writes.
  - Added focused CP6 backend tests for success, retry, restart-safe pending rows, duplicate prevention, atomic rollback, and dead letter behavior.
- CP6 Outbox Dispatcher opened for automation after explicit user request.
- Updated project/checkpoint/AI state from CP5 gate to CP6 READY with `next_agent = codex`.
- CP6 scope limited to backend-owned transactional outbox dispatcher; CP7+ remains out of scope.
- Fixed Codex runner prompt so approved CP6 automation is not blocked by the prior closed-gate wording.
- CP5 Frontend Migration was completed and committed before automation setup.
- Automation infrastructure created from clean/restored state after CP5.
- CP5 gate preserved.
- CP6 not started.
- No product code modified by automation setup.
- Automation runner fixes added after review:
  - Removed unsupported `codex exec --ask-for-approval` flag.
  - Added Antigravity CLI lock/release behavior.
  - Added Antigravity missing-CLI/failure block back to human review.
  - Added loop no-state-change protection.
- Automation runner setup update:
  - Prefer current Antigravity CLI command `agy`.
  - Require non-interactive `-p` or `--prompt` support before invoking Antigravity from scripts.
  - Use Antigravity `--sandbox` when the installed CLI supports it.
  - Keep `antigravity` and `ag` as compatibility fallbacks only.
  - Document forbidden dangerous bypass flags.
- Antigravity CLI readiness:
  - Official installer found `agy.exe` installed at `%LOCALAPPDATA%\agy\bin\agy.exe`.
  - Added the installed `agy` directory to User PATH.
  - Verified `agy 1.0.16` and successful sandboxed non-interactive prompt execution.
  - Added required YAML frontmatter to `.agents/skills/verify-and-handoff/SKILL.md`.

## Files Created Or Updated

- `AGENTS.md`
- `AI_TASK.md`
- `AI_STATE.json`
- `AI_HANDOFF.md`
- `AI_CHANGELOG.md`
- `AI_VERIFICATION.md`
- `AI_RISK_REGISTER.md`
- `PROJECT_STATE.md`
- `docs/implementation/CURRENT_CHECKPOINT.md`
- `backend/app/api/dirap.py` (new)
- `backend/app/api/schemas.py`
- `backend/app/db/migrations.py`
- `backend/app/main.py`
- `backend/tests/test_dirap.py` (new)
- `frontend/src/api/dirap.ts` (new)
- `frontend/src/components/DirapPanel.tsx` (new)
- `frontend/src/components/AppLayout.tsx`
- `frontend/src/index.css`
- `frontend/src/store/store.ts`
- `.agents/skills/verify-and-handoff/SKILL.md`
- `scripts/run-codex.sh`
- `scripts/run-antigravity.sh`
- `scripts/agent-loop.sh`
- `scripts/ai-auto.sh`
- `scripts/run-codex.ps1`
- `scripts/run-antigravity.ps1`
- `scripts/agent-loop.ps1`
- `scripts/ai-auto.ps1`
- `scripts/codex-tick.ps1`
- `PROJECT_STATE.md`
- `docs/implementation/CURRENT_CHECKPOINT.md`
- `docs/implementation/HERMES_LOCAL_STACK_CHECKPOINTS.md`
- `backend/app/repositories/outbox_repository.py`
- `backend/app/services/task_service.py`
- `backend/app/services/outbox_dispatcher.py`
- `backend/tests/test_repositories.py`
- `backend/tests/test_task_service.py`
- `backend/tests/test_outbox_dispatcher.py`
