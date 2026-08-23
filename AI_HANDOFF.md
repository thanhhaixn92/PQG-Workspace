# AI Handoff

> Cac muc handoff ben duoi la anh chup lich su. Claim cu ve context pack, proposal, conversation ownership hoac MCP surface duoc gan nhan **superseded evidence** neu mau thuan voi muc v2.2 moi nhat va source-of-truth hien hanh.

## PQG Workspace / Trợ lý GYO — current identity, acceptance still partial (2026-08-16)

- **Checkpoint:** giữ `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` và verdict `PARTIAL`; không set `DIRAP_V22_VALIDATED`. Baseline local MVP được giữ nguyên.
- **Đã triển khai:** attachment/context pack deterministic, seven structured parts, proposal provenance/approval part, Review direct lifecycle/deep link, thread–conversation link additive (`0028`), Work Hub, responsive App Shell/primitives, managed-root boundary, exact MCP allowlist 9 tool và approval cho persistent summary. Branding hiển thị hiện hành là **PQG Workspace**; nav agent dùng **Trợ lý GYO**.
- **Bằng chứng đã ghi:** backend **465 passed, 1 skipped**; frontend **172 passed**; lint 0 error (4 Fast Refresh warning); type-check/build và `git diff --check` pass; isolated mock UAT terminal SSE/source/proposal/package/exactly-once/cancel/restart/archive pass. Runtime sau restart đã smoke health và public contract thành công: OpenAPI có Memory theo bước/GYO learning; model-config trả contract mới.
- **Sửa đã được xác nhận ở runtime trước đó:** API client luôn giữ JSON Content-Type khi mutation có Idempotency-Key; mobile composer luôn thấy và không che nút Ngữ cảnh; drawer mở/Escape đóng tại tablet dọc.
- **Bounded real-Hermes trước đó — superseded historical evidence:** snapshot này từng ghi PASS cho prompt/source/retry/proposal/no mutation trước approval/package provenance/executor đúng một lần/cancel late-output/restart. Đây không phải current evidence: bounded real-GYO UAT hiện hành chỉ PASS stream/context/source/cancel; real action_proposal không xuất hiện, proposal/package/executor thực vẫn **NOT RUN**; không suy diễn portable compute stop.
- **Fidelity trước đó:** runner chia năm batch cô lập; năm batch cuối tại `output/playwright/v22-batched-20260815-075743/` PASS với 62 screenshot. Review 403 same-origin được sửa và rerun sạch console. Browser zoom 200% thật trên Chrome 151 PASS tại `output/playwright/v22-brandzoom-20260815-0900/`, dùng profile/SQLite/workspace tạm `uat-codex-`; screenshot có chỉ báo toolbar 200% và log preference quy đổi đúng 200%, không dùng CSS zoom/emulation.
- **Identifier cố ý giữ nguyên:** repository `DIRAP-Personal-v3`, package names, API/public routes, DB/schema, biến môi trường, `hermes.theme`, checkpoint, credential store và các thuật ngữ Hermes ACP/agent. Đây là identifier kỹ thuật hoặc lịch sử, không phải tên hiển thị hiện hành.
- **Current reconciliation (2026-08-17):** claim providers/models rỗng ở các snapshot trên là **superseded**. Model-config hiện có 1 provider Opencode, 3 model Free enabled và default model; credential/ready chỉ là local configuration, không phải upstream health. Bounded real-GYO UAT PASS stream/context/source/cancel; real action-proposal không xuất hiện nên proposal/package/executor thực vẫn **NOT RUN**. Gate 1 technical evidence là **PASS — quyết định độc lập của Codex ngày 2026-08-17**; full fidelity matrix, usability 5 người và real action-proposal acceptance giữ checkpoint `PARTIAL`. P2 cancel provenance regression-verified, không chứng minh process-level compute stop portable.

## Hermes Assistant v2.2 hardening — superseded evidence (2026-08-14)

- **Không chuyển checkpoint:** `PROJECT_STATE.md`/`CURRENT_CHECKPOINT.md` vẫn là evidence của controlled local pilot v1.2. Các thay đổi v2.2 trong worktree chưa được tuyên bố validated.
- **Đã đóng lát race/cancel tối thiểu:** mỗi Assistant thread chỉ có một assistant turn `running`; archive bị chặn khi Hermes đang trả lời; SSE token/done/error có `assistant_turn_id`; UI chỉ ghép token đúng turn đó, tự đăng ký lại stream sau terminal event; có nút **Hủy phản hồi**.
- **Cancel contract:** backend ghi `cancelled`, audit `assistant.turn.cancelled`, đóng stream và bỏ qua mọi completion đến muộn. Hermes ACP có thể chưa dừng process-level ngay vì bridge không có primitive cancel portable, nhưng output muộn không được lưu/hiển thị.
- **Vùng sửa:** `backend/app/api/assistant.py`, `backend/app/api/schemas.py`, `backend/app/services/hermes_client.py`, API/UI Assistant và regression tests. Không sửa migration, state hoặc cấu hình/credential.
- **Evidence:** focused backend **18 passed**; frontend Assistant **10 passed**; type-check pass. Full backend trước regression cuối: **441 passed, 1 skipped**; frontend full trước regression UI cuối: **155 passed**, lint 0 error/4 warning cũ, build pass. Browser `http://localhost:5173`: trang Hermes render, không console error/warning, thao tác mở Ngữ cảnh & nguồn pass.
- **Next:** Gói 2 context pack thật (tài liệu managed, conversation, approved knowledge/skills, budget/provenance) và proposal schema an toàn. Chưa chạy E2E toàn hành trình hoặc human acceptance.

## Local MVP Remediation v1.2 — validated handoff (2026-08-12)

- Current checkpoint: `DIRAP_LOCAL_MVP_REMEDIATION_V1_2_VALIDATED` — sẵn sàng cho **controlled local pilot**, không phải production.
- Runtime người dùng đang chạy tại frontend `http://localhost:5173` và backend `http://127.0.0.1:8000`; n8n optional chưa cấu hình.
- Automated evidence: backend **416 passed, 1 permission-based skip**; frontend **134 passed**; lint/type-check/build pass; diff hygiene được kiểm tra sau đồng bộ state.
- Browser evidence: desktop/mobile navigation, breakpoint reachability, no horizontal overflow, recovery, file/session scoping và approval modal focus/rehydration đều được kiểm tra bằng thao tác thật. UAT dùng SQLite/workspace tạm và đã được dọn sạch.
- Next human step: dùng thử một Công việc thật có giới hạn, xác nhận tên/mục tiêu/tài liệu/đầu ra/báo cáo/hộp duyệt; ghi nhận P2/P3 nếu có. Không nhập credential production hoặc kích hoạt webhook production trong pilot này.

## Controlled Knowledge Search Acceptance (2026-08-10)

- **Accepted by Codex:** `DIRAP_V3_CONTROLLED_SEARCH_ACCEPTED`.
- The accepted boundary is deterministic phrase search scoped to one work item, policy v1 filtering before pagination, and a read-only interface. It excludes AI, vectors, semantic search, search indexes, agent memory, deployment and search-result persistence.
- Codex independently ran six DIRAP backend suites (**85 passed, 1 permitted symlink skip**) and the complete frontend suite (**111 passed**), plus type-check, build, lint and diff hygiene.
- Final direct Codex repair: pressing Enter while a search is already busy cannot dispatch a duplicate request; changing phrase or purpose still invalidates the old response and unlocks a new search immediately.

## Current State

- **DIRAP v3.0 Foundation: ACCEPTED** by Codex on 2026-07-31 (10/10 tests, clean diff).
- **DIRAP v3.0 Extraction slice: ACCEPTED** by Codex on 2026-08-02. Codex independently re-ran the focused suite: 30 passed, 1 permitted symlink skip; `git diff --check` was clean. The 2026-08-01 review found two issues, both fixed:
  1. **Duplicate fresh extractions** — re-extracting unchanged source+version created a new fresh extraction. **FIXED**: `POST .../extract` is now idempotent on `(source_file_id, source_sha256, EXTRACTOR_VERSION)` — returns the existing fresh extraction with HTTP 200, no new extraction/records/`completed` audit.
  2. **Stale only applied on re-extract** — old results stayed `fresh` in list/detail until a new extraction was requested. **FIXED**: `GET .../extractions` and `GET .../extractions/{id}` now re-read the source through the sandbox, recompute SHA-256, mark mismatched fresh runs `stale` (one `dirap.extraction.staled` audit per real change), and never return old data as fresh. Missing/unsupported/sandbox-rejected source → clear HTTP error (404/415/403), never silently fresh.
- The primary Hermes worktree was not modified.
- **DIRAP v3.0 Knowledge Records slice: ACCEPTED** by Codex on 2026-08-08. Codex independently verified 39 focused DIRAP tests passing with one permitted symlink skip, frontend lint/type-check/build, and clean diff hygiene. This is limited to source-grounded `draft` records; it is not verification, usability, AI, search, workflow, deployment or production readiness.
- **DIRAP v3.0 Knowledge Review slice: ACCEPTED** by Codex on 2026-08-09. Codex independently ran the four focused DIRAP suites: **52 passed, 1 permitted symlink skip**; frontend lint/type-check/build and `git diff --check` passed. Acceptance covers the controlled lifecycle, evidence, four dimensions, task scoping, idempotency and audit only; it excludes policy-derived usability, `authoritative` mapping, AI, search, deployment and production.
- **DIRAP v3.0 Usability Read-only slice: ACCEPTED** by Codex on 2026-08-10. Codex independently ran five focused DIRAP suites: **72 passed, 1 permitted symlink skip**; frontend lint/type-check/build and `git diff --check` passed. Acceptance covers six v1 policy rules, scoped read-only calculation, explanations and UI; there is no persistence, migration or audit for policy reads, and `authoritative` remains unused.
- **DIRAP v3.0 Controlled Knowledge Search slice: IMPLEMENTED** by Hermes on 2026-08-10 (CONTROLLED_KNOWLEDGE_SEARCH_DECISION.md — awaiting Codex re-review): deterministic task-scoped phrase matching over `content`/`provenance` (casefold + whitespace normalization), then policy v1 filtering BEFORE pagination; strictly read-only — no audit, no persistence, no migration, no dependency.

## DIRAP v3.0 Knowledge Records slice (this handoff)

### Scope delivered
- **One record per creation**: a knowledge record is created from exactly **one** extraction record that belongs to the work item and is currently `fresh`.
- **Source-grounded provenance stored with each record**: `task_id`, `extraction_id`, `extraction_record_id`, `source_file_id`, `source_sha256` (snapshot at creation), `extractor_version`, `provenance` (line/row/paragraph …), `content`, `status`, `note`, timestamps. No full source-file copies, no chat-history duplication.
- **Status is always `draft`** — the API never auto-verifies/approves; the server hardcodes `draft`, the client cannot override.
- **Stale rejection**: creating from a `stale` extraction returns 409 with a clear message (freshness is re-checked via sandbox re-read + re-hash at creation time, same mechanism as extraction list/detail).
- **ID relation checks**: unknown extraction → 404; extraction belonging to another work item → 404 "does not belong"; record ID not inside the given extraction → 404.
- **Idempotency**: same `Idempotency-Key` + same payload → replays the existing record with HTTP 200 (no duplicate, single audit); same key + different payload → 409 conflict.
- **Audit**: every successful creation writes `dirap.knowledge_record.created` (target = record id, payload includes task/extraction/record/source/hash/version/status); list/view writes `listed`/`viewed` read events.
- **List/detail scoping**: both endpoints are scoped to the work item; a record of another work item is 404.
- **Extraction record IDs now returned**: freshly created extractions return `records[].id` so the UI can create knowledge records without a second lookup.

### Backend (new/changed)
- **Migration 0017** (`dirap_knowledge_records` table + `task_id`/`extraction_id` indexes).
- **`backend/app/api/dirap.py`**: 3 new endpoints:
  - `POST /work-items/{task_id}/knowledge-records` (201; 200 idempotent replay; 409 stale or key-conflict; 404 foreign/unknown IDs)
  - `GET .../knowledge-records` (list, newest first, task-scoped)
  - `GET .../knowledge-records/{knowledge_record_id}` (detail, task-scoped; 404 otherwise)
- **`backend/app/api/schemas.py`**: `DirapKnowledgeRecordCreateRequest`, `DirapKnowledgeRecordResponse`; `DirapExtractionRecordResponse` gained `id`.
- **Extraction create-path**: generated `drec-*` record IDs are now captured and echoed in the 201 response (previously `records[].id` was `null` on the fresh-create path).

### Frontend (changed)
- **`frontend/src/api/dirap.ts`**: `DirapKnowledgeRecord` / create-request types, `createKnowledgeRecord` (with optional `Idempotency-Key`), `listKnowledgeRecords`, `getKnowledgeRecordDetail`; `DirapExtractionRecord.id`.
- **`frontend/src/components/DirapPanel.tsx`**: per-record "→ Tri thức" button inside the extraction preview (disabled for stale extractions, idempotency key = `kr-{recordId}` to prevent double-click duplicates), plus a "Bản ghi tri thức" card listing drafts with DRAFT badge, provenance/version/time line, and an expandable detail (content, extraction/record/source IDs, source hash, extractor version, draft status).

### Tests (new)
- **`backend/tests/test_dirap_knowledge.py`**: 9 tests:
  - Happy path: 201 with full provenance (task/extraction/record/source IDs, correct source hash, extractor version, `provenance`, content, status `draft`, note) + exactly one `dirap.knowledge_record.created` audit
  - Status is always `draft`
  - Stale extraction → 409 (source modified, no record created)
  - Extraction of another work item → 404 "does not belong"
  - Unknown extraction → 404; record ID not in extraction → 404
  - Idempotent replay: same key+payload → 201 then 200, same record id, single row + single audit
  - Idempotency conflict: same key+different payload → 409, nothing extra created
  - List/detail scoping: records invisible under another work item (empty list, 404 detail), visible under their own; unknown record id → 404

## DIRAP v3.0 Knowledge Review slice (this handoff)

### Scope delivered
- **Controlled lifecycle**: `draft → review_pending → active|rejected`. Only these transitions are allowed; anything else is rejected with **409** and a message listing the allowed chain (`test_invalid_transitions_all_rejected`).
- **Four independent verification dimensions** stored per record (server-computed, client cannot write them):
  - `source_verification_state`: `unverified` → `verified` only on approve with a source-evidence reference.
  - `calculation_verification_state`: `verified` **only when** a calculation-evidence reference is supplied at approve; otherwise stays `unverified`.
  - `owner_acceptance_state`: `pending` → `accepted` (approve) or `rejected` (reject). Legacy rows with the pre-fix value `approved` are normalized by migration 0019.
  - `authority_status`: closed vocabulary `none | regulatory | organizational | expert | derived`; approve accepts only the four non-`none` values (server Literal → 422 for anything else; `none` → 400). No `authoritative` label is inferred — policy and lifecycle vocabularies remain distinct.
- **Submit** (`draft → review_pending`): work-item scoped (404 for another work item), audit `dirap.knowledge_record.submitted`, dimensions untouched.
- **Approve** (`review_pending → active`): requires reviewer reference, source-evidence reference, authority status ≠ `none` and authority reference (missing → 422, `none` → 400). Every evidence reference becomes its **own record** in `dirap_knowledge_evidence` (`reviewer`, `source_evidence`, `authority_evidence`, optional `calculation_evidence`); nothing is marked verified without a reference. Audit `dirap.knowledge_record.accepted` records every dimension.
- **Reject** (`review_pending → rejected`): requires reviewer reference + reason (missing → 422); stores `reviewer` + `decision_reason` evidence; sets `owner_acceptance_state='rejected'`; **keeps all source data and audit history** (no deletes). Rejection never marks anything verified.
- **Idempotency**: submit/approve/reject reuse the `Idempotency-Key` mechanism — same key + same payload replays with HTTP 200 (single evidence set, single audit); same key + different payload → 409.
- **No AI / search / workflow / usability claim**: `active` is a review outcome only; the UI explicitly labels it "không ngụ ý có thể sử dụng theo chính sách".
- **Contract fixes (Codex re-review 2026-08-08)**: `owner_acceptance_state` = `accepted` (migration 0019 normalizes legacy `approved` rows; 0018 untouched); `authority_status` = closed 5-value vocabulary enforced server-side (Literal) and in the UI (select, no free text).

### Backend (new/changed)
- **Migration 0018**: 4 `ALTER TABLE` on `dirap_knowledge_records` (the four dimensions, NOT NULL with defaults) + new `dirap_knowledge_evidence` table (`kev-*` records: type, reference, optional note, created_at) + index.
- **Migration 0019**: one-time `UPDATE … SET owner_acceptance_state='accepted' WHERE owner_acceptance_state='approved'` — normalizes legacy data without touching 0018.
- **`backend/app/api/dirap.py`**: 3 new endpoints:
  - `POST .../knowledge-records/{id}/submit` (200; 409 wrong lifecycle; 404 foreign/unknown)
  - `POST .../knowledge-records/{id}/review/approve` (200; 422 missing refs; 400 `none` authority; 409 wrong lifecycle; 404)
  - `POST .../knowledge-records/{id}/review/reject` (200; 422 missing reviewer/reason; 409; 404)
- **`backend/app/api/schemas.py`**: `status` widened to `draft|review_pending|active|rejected`; response gained the four dimensions; new `DirapKnowledgeEvidenceResponse`, `DirapKnowledgeRecordDetailResponse` (detail = record + evidence), submit/approve/reject request models; `DirapOwnerAcceptanceState` is now `pending|accepted|rejected` and `DirapKnowledgeAuthorityStatus` is the closed Literal `none|regulatory|organizational|expert|derived`.
- **Detail endpoint** now returns `evidence[]`; list returns the four dimension fields per record.

### Frontend (changed)
- **`frontend/src/api/dirap.ts`**: `DirapKnowledgeStatus`, dimension fields, `DirapKnowledgeEvidence`, detail type; `submitKnowledgeRecord` / `approveKnowledgeRecord` / `rejectKnowledgeRecord` (with `Idempotency-Key`).
- **`frontend/src/components/DirapPanel.tsx`**: lifecycle badge (DRAFT / CHỜ DUYỆT / ACTIVE / TỪ CHỐI), four dimension chips, "Gửi rà soát" on drafts, inline approve/reject form on `review_pending` (reviewer, source ref, authority status + ref, optional calc ref, reason), evidence list in expandable detail, and an explicit banner on `active`: "phản ánh kết quả rà soát; không ngụ ý có thể sử dụng theo chính sách".

### Tests (new)
- **`backend/tests/test_dirap_knowledge_review.py`**: 13 tests — full happy path with dimension assertions + evidence rows + audit; calculation dimension verified only with calc reference; approve missing required refs → 422 and `none` → 400 with no side effects; reject missing reviewer/reason → 422; all invalid transitions → 409 (approve/reject on draft, double-submit, actions on terminal states); review action scoped to work item → 404 + unknown id → 404; reject preserves source linkage, evidence (`reviewer` + `decision_reason`) and audit, record still listed; idempotent submit/approve replay with single evidence set + single audit, key conflict → 409.

## DIRAP v3.0 Extraction slice (this handoff)

### Scope delivered
- **Supported types**: `.txt`, `.md`, `.csv`, `.json`, `.docx` — Python standard library only (`csv`, `json`, `hashlib`, `zipfile`, `xml.etree`). No new dependencies, no AI, no PDF/OCR.
- **Per-extraction provenance**: source file, SHA-256 of source content, extracted-at timestamp, extractor version (`1.0.0`), file type, status (`fresh`/`stale`), ordered records with `seq` + `provenance` (line N / row N / item[N] / .key / paragraph N).
- **Staleness**: fixed — unchanged source/hash/version returns the existing fresh extraction (HTTP 200, no duplicate); list/detail refresh freshness by re-reading the source via sandbox and marking changed-hash runs `stale` with audit, so old results are never shown as fresh.
- **Audit**: every extraction (`dirap.extraction.completed`), every stale marking (`dirap.extraction.staled`), plus `listed`/`viewed` read events — via the existing audit service.
- **Sandbox**: workspace path is re-validated with `resolve_and_validate_path` before every file read at extraction time.
- **Frontend (minimal)**: per source file — "Trích xuất" button, status badge, record count + file type, hash/version/time line, and a preview pane with provenance + truncated content.

### Backend (new/changed)
- **Migration 0016** (`dirap_extractions` + `dirap_extraction_records` tables + indexes).
- **`backend/app/services/extraction.py`** (new): `EXTRACTOR_VERSION`, `file_type_for`, `sha256_of_file`, `extract` for the 5 supported types.
- **`backend/app/api/dirap.py`**: 3 new endpoints:
  - `POST /work-items/{task_id}/source-files/{source_file_id}/extract` (201; 415 unsupported type; 400 invalid content; 404 missing file; 403 sandbox rejection)
  - `GET .../extractions` (list, newest first)
  - `GET .../extractions/{extraction_id}` (detail + ordered record preview, `limit` param)
- **`backend/app/api/schemas.py`**: extraction summary/record/detail schemas.

### Frontend (changed)
- **`frontend/src/api/dirap.ts`**: extraction types + `extractSourceFile`, `listExtractions`, `getExtractionDetail`.
- **`frontend/src/components/DirapPanel.tsx`**: extraction controls + preview per source file card.

### Tests (updated for the two fixes)
- **`backend/tests/test_dirap_extraction.py`**: 21 tests (20 pass, 1 skip-with-reason when the platform cannot create symlinks):
  - Per-type extraction: `.txt`, `.md`, `.csv`, `.json` (array + object), `.docx` (fixture built with stdlib `zipfile`)
  - Hash / provenance / version / type / status assertions
  - **Regression (fix 1)**: `test_extract_idempotent_unchanged_source` — extract twice with unchanged source/hash/version → same extraction ID, second call HTTP 200, only one extraction + one record set, only one `completed` audit
  - Stale-on-source-change via re-extract (POST path)
  - **Regression (fix 2)**: `test_list_marks_stale_on_source_change`, `test_detail_marks_stale_on_source_change` — list/detail mark the old extraction stale + audit without re-extracting
  - Clear-error freshness checks: missing file on disk → 404 on list/detail; DB-tampered traversal → 403 on list
  - Audit events for completed + staled (verified in the audit table)
  - Unsupported type 415, invalid UTF-8 400, invalid JSON 400, unknown source file 404
  - Sandbox re-check at extraction time: DB-tampered traversal → 403; symlink escape → 403 (or skip with reason)

## Reproducible Backend Test Command

```sh
cd backend
.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py -v
# 48 passed, 1 skipped (symlink unavailable in environment)
```

## DIRAP v3.0 Controlled Knowledge Search slice (this handoff)

### Scope delivered
- **Route**: `GET /api/dirap/work-items/{task_id}/knowledge-records/search?q=...&query_type=...&limit=...&offset=...` — fixed `search` segment declared BEFORE `/{knowledge_record_id}`, so it can never be mistaken for a record id.
- **Matching (deterministic, stdlib-only)**: `casefold()` + whitespace collapse on both sides; phrase matched inside `content` and/or `provenance` (`matched_field`: `content | provenance | both`); no SQL `LIKE` as the main logic, no AI/vector/FTS/index/parallel store.
- **Policy filtering BEFORE pagination** (`evaluate_usability`, policy v1): `official_search`, `analysis_input`, `legal_review`, `context_packaging`, `memory_query` return only `usable`; `exploratory_search` also returns `partial_usable` with the level shown; content of `unusable` records is never returned.
- **Validation**: `q` non-empty after normalization (whitespace-only → 422), max 200 chars; `limit` default 20 / max 100 (ge=1, le=100); `offset` default 0 (ge=0); unknown `query_type` → 422; unknown task → 404.
- **Read-only by contract**: no audit event, no commit, no lifecycle/dimension change, no migration (still 19), no dependency, no result persistence.
- **Response contract**: per result — `record_id`, `content_excerpt` (≤200 chars), `provenance`, `lifecycle_state`, the four original dimensions, `matched_field`, `usability_state`; top-level `query_type`, `total` (after matching + policy filtering, before pagination), `limit`, `offset`.

### Backend (new/changed)
- **`backend/app/services/knowledge_search.py`** (new, pure): `normalize_search_text`, `find_match`, `content_excerpt`, `search_records` (match → policy filter → slice; `total` = filtered count).
- **`backend/app/api/schemas.py`**: `DirapKnowledgeSearchResult` + `DirapKnowledgeSearchResponse`.
- **`backend/app/api/dirap.py`**: `search_knowledge_records` endpoint (registered before the `/{knowledge_record_id}` GET).

### Frontend (changed)
- **`frontend/src/api/dirap.ts`**: `DirapKnowledgeSearchResult`/`DirapKnowledgeSearchResponse` types + `searchKnowledgeRecords` (URLSearchParams).
- **`frontend/src/components/DirapPanel.tsx`**: read-only search block — query input (Enter to search), purpose select (six goals from `DIRAP_USABILITY_QUERY_TYPES`), result cards with usability badge + lifecycle badge + matched-field label + excerpt + provenance + four dimensions, notice that results are policy-filtered ("active" ≠ usable by default; exploratory may include `partial_usable"), and "Tải thêm" pagination (offset += limit).
- **Async-safety fix (post-handoff, 2026-08-10)**: changing the phrase or the purpose immediately invalidates the in-flight request (`searchSeqRef` sequence guard), clears old results, **and releases the busy state** — the “Tìm” button is usable again right away (no permanent lock; the button is disabled only while a query is actually in flight). Stale responses can never overwrite or merge into a newer query nor re-lock the button; “Tải thêm” always runs on the current query (offset restarts at 0 after a change). Single source of truth: `searchBusy` (no parallel state).

### Tests (new)
- **`backend/tests/test_dirap_controlled_search.py`**: 13 tests — content match with casefold + multi-space; provenance match; no-match empty; task scoping (same phrase in two tasks, each sees only its own); unknown task 404; `official_search`/`legal_review` return only `regulatory`; `analysis_input` accepts the four allowed authorities; exploratory returns `partial_usable` while strict goals never do (and `context_packaging`/`memory_query` still return the record as `usable`); pagination AFTER policy filtering (draft never counts); default `limit=20`/`offset=0`; validation errors (empty/blank/201-char q, bogus query_type, limit 0/101, negative offset → 422); strict read-only (records, audit count and table list unchanged after searches); exact response contract fields.
- **`frontend/src/components/DirapPanel.test.tsx`** (new, 4 tests): changing the phrase clears old results (no leftover "Tải thêm") and a new search never merges; changing the purpose invalidates paged results and the next search restarts at `offset=0`; an out-of-order stale response (old phrase resolving after the new one) is dropped and cannot overwrite the new query's results; **regression 6-step async-safety (button unlock)**: query A in flight (button locked) → change the purpose mid-flight → button unlocks immediately → click the button (no Enter) to run query B → B resolves first and renders → A resolves later but never overwrites/merges, notice shows the new purpose, button stays unlocked.

## Known State

- `AI_STATE.json`: state is `DIRAP_V3_CONTROLLED_SEARCH_IMPLEMENTED`, next_agent = `codex` (Hermes implemented the controlled knowledge search slice on 2026-08-10; awaiting Codex re-review; prior state `DIRAP_V3_CONTROLLED_SEARCH_AUTHORIZED` from Codex). Previous slice states are in `AI_CHANGELOG.md`.
- Usability: `overall_usability_state`, `policy_version`, `exclusions`, `usable_for_query_types` are computed per read only; there is no write API and no DB column for them.
- Extraction stores only extracted records + provenance metadata; the original file stays in the workspace.
- No parallel task/session/audit system created; review reuses `tasks`, `dirap_knowledge_records`, `dirap_knowledge_evidence`, audit events, idempotency.
- Full backend suite result for this slice: see `AI_VERIFICATION.md`.

## Historical V1 State

- V1 checkpoints (CP5-CP10) are complete and preserved.

## Forbidden Files And Areas (unchanged)

- `.env`, `.env.local`, `.env.production`, secrets, deployment config, billing config,
  production database settings, database files, unrelated migrations, V1 product code, frontend source files.

## Next Action

- **Codex re-review (2026-08-10, search slice):** independently rerun the backend DIRAP suites (`cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py tests/test_dirap_controlled_search.py -q` — expect 85 passed, 1 skipped), frontend `npx vitest run` (109 passed) + lint/type-check/build, and `git diff --check`. NOTE: applying the UI async-safety fix touched only `DirapPanel.tsx` + `DirapPanel.test.tsx`; backend is unchanged from the IMPLEMENTED state.
- **Codex re-review (2026-08-09):** Hermes applied both contract fixes — `owner_acceptance_state` writes `accepted` (migration 0019 normalizes legacy `approved` rows; 0018 untouched) and `authority_status` is the closed vocabulary `none|regulatory|organizational|expert|derived` enforced by schema Literal (422 for anything else, 400 for `none`) and a select in the UI (no free text) — plus narrow regressions (4 valid authority values, unknown values rejected, migration normalization, idempotent reject replay). Independently rerun: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py -q` (expect 52 passed, 1 skipped), frontend lint/type-check/build, `git diff --check`.
- Preserve the accepted Foundation, Extraction and draft Knowledge Records contracts. Do not implement policy-derived usability or infer an `authoritative` mapping.
- **Codex re-review (2026-08-10, Usability Read-only):** independently rerun `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py -q` (expect **72 passed, 1 skipped**), frontend lint/type-check/build, and `git diff --check`. Boundary: read-only policy computation only — no search, AI, agent, workflow, deployment or production claims.
- **Codex re-review (2026-08-10, Controlled Knowledge Search):** independently rerun `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py tests/test_dirap_controlled_search.py -q` (expect **85 passed, 1 permitted symlink skip**), frontend lint/type-check/build, and `git diff --check`. Boundary: deterministic task-scoped phrase matching + policy v1 filtering only — no AI, vector/FTS, migration, dependency, audit or search data store; no `authoritative` inference.

## Design Task (2026-08-09, Hermes — document only, no code)

- Created `docs/implementation/USABILITY_POLICY_RECONCILIATION_DRAFT.md`: reconciles the policy keyword `authoritative` (used by `usability_policy_spec.md` / `query_policy_matrix.csv`) with the accepted 5-value `authority_status` contract (`none|regulatory|organizational|expert|derived`). Draft defines `authoritative` strictly as a derived policy condition (never a stored label), proposes minimum conditions for the 6 standard query types with explicit value sets per option, presents exactly 3 mapping options (A full-allow, B per-purpose subsets, C direct declarations; in B/C `official_search` and `legal_review` accept only `{regulatory}` in the first policy version — `derived` deferred until provenance data and verification rules exist) without choosing one, specifies the read-only future usability contract (`overall_usability_state`, `policy_version`, `exclusions`, `usable_for_query_types` — no write API), and lists 10 open decisions (Q1–Q10 incl. internal source conflicts Q4/Q5) for Codex/user to settle. Sources quoted: `knowledge_lifecycle_and_verification.md`, `usability_policy_spec.md`, `query_policy_matrix.csv`.
- `AI_STATE.json` untouched (user-owned); no source code, migrations, tests, config or locked design docs changed. Next: Codex reviews the draft and picks the minimal policy; a small read-only usability implementation task may follow only after that decision.
