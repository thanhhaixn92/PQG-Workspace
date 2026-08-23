# AI Verification

## 2026-08-16 — PQG Workspace / Trợ lý GYO identity reconciliation

- Checkpoint giữ `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`; không đổi sang `DIRAP_V22_VALIDATED`.
- Tên hiển thị hiện hành là **PQG Workspace**; trợ lý trong giao diện là **Trợ lý GYO**. `DIRAP` v2.2 và các identifier package/API/public routes/DB/schema/env/`hermes.theme`/checkpoint/credential được giữ nguyên.
- Current reconciliation: `/api/model-config` hiện có 1 provider Opencode, 3 model Free enabled và default model. `credential_configured=true`/`health_status=ready` chỉ là evidence cấu hình cục bộ, không phải provider upstream healthy. Bounded real-GYO UAT PASS stream/context/source/cancel; real action-proposal không xuất hiện, vì vậy proposal/package/executor thực vẫn **NOT RUN**. Gate 1 browser characterization isolated PASS và focused evidence backend **32 passed, 1 Windows symlink skip, 1 warning Pydantic hiện hữu**; frontend ReviewInboxPanel/ActionPackagesPanel/HermesAssistantPanel **21 passed**. **Gate 1 technical evidence PASS — quyết định độc lập của Codex ngày 2026-08-17**; đây không phải promotion checkpoint v2.2: full fidelity matrix, usability 5 người và real action-proposal acceptance vẫn thiếu.
- Các đoạn branding 2026-08-15 bên dưới được giữ là **superseded product-label evidence**; số test và screenshot của chúng là bằng chứng lịch sử, không tự khẳng định trạng thái runtime sau đó.

## 2026-08-15 — superseded DIRAP Local Workbench branding + actual Chrome zoom 200%

- Checkpoint giữ `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`; không đổi sang `DIRAP_V22_VALIDATED`.
- Historical product-label evidence: browser title, App Shell/product eyebrows, FastAPI display title/log, README và tài liệu vận hành khi đó dùng **DIRAP Local Workbench**; nav agent dùng **Trợ lý Hermes**. Nhãn này đã được thay thế bởi PQG Workspace / Trợ lý GYO; package/API/public routes/DB/schema/env/`hermes.theme`/checkpoint/credential contracts vẫn giữ nguyên.
- Regression focused: `backend/.venv/Scripts/python.exe -m pytest tests/test_release_version.py tests/test_sessions.py tests/test_characterization.py -q` → PASS; `npm run test -- --run src/components/AppLayout.test.tsx src/components/OverviewPanel.test.tsx src/components/HermesAssistantPanel.test.tsx` → **19 passed**.
- Fresh full backend: `.venv/Scripts/python.exe -m pytest -q` → **465 passed, 1 skipped, 1 warning**, exit 0.
- Fresh full frontend: `npm run test -- --run` → **33 files, 172 passed**, exit 0.
- Frontend static gates: `npm run lint && npm run type-check && npm run build` → lint **0 error/4 Fast Refresh warnings**, type-check PASS, build PASS; bundle-size warning vẫn là residual đã biết.
- Actual browser zoom: Chrome 151, native `Ctrl+=` đến toolbar `Zoom: 200%`; isolated profile preference host zoom `3.8017840169239308` quy đổi đúng 200%. Dùng frontend `:8872`, backend `:8871`, SQLite/workspace/profile tạm prefix `uat-codex-`; không dùng CSS zoom/device emulation/dữ liệu thật. Evidence: `output/playwright/v22-brandzoom-20260815-0900/chrome-actual-zoom-200.png` và `browser-zoom-200-log.json`.
- Branding browser check: title `DIRAP Local Workbench — Trợ lý công việc cá nhân`, App Shell `DIRAP LOCAL WORKBENCH`, nav `Trợ lý Hermes`, Work tạm `uat-codex-Branding zoom 200%`, bottom navigation và composer đều xuất hiện trong screenshot.
- `NOT RUN/PARTIAL`: full screen×state×viewport cross-product chưa hoàn tất; CSS viewport chính xác của lượt Chrome zoom không được ghi nên không suy diễn vào một ô viewport cụ thể. Usability 5 người thật vẫn `NOT RUN` theo quyết định hoãn hậu v2.2; không dùng agent/mock thay thế.

## DIRAP v2.2 final technical recheck — PARTIAL acceptance (2026-08-15)

- Full backend trên trạng thái code cuối: **464 passed, 1 skipped**; skip là symlink permission fixture đã biết. Hai warning dependency còn lại là Pydantic forward reference và Starlette TestClient deprecation.
- Full frontend: **33 files / 171 tests passed**; `type-check` pass; lint 0 error và 4 warning Fast Refresh; production build pass. Chunk >500 kB tiếp tục là P2 hiệu năng. `git diff --check` exit 0, chỉ có cảnh báo LF/CRLF của dirty worktree.
- Cancellation contract nay ghi outcome an toàn riêng: `cancelled`, `not_active`, `session_starting`, `connection_unavailable`, `adapter_failed`; durable cancel luôn commit trước lời gọi ACP và audit `assistant.turn.cancel_compute` không chứa raw output/path/credential. Focused cancellation/UAT suite **28 passed**; Memory Hub origin/referer regression **10 passed**.
- **Superseded historical runtime evidence — không phải current real-GYO evidence:** Bounded real-Hermes UAT cuối tại `output/playwright/v22-batched-20260815-075743/real-hermes-final.log`: `dev_mock=false`, 4/4 prompt, managed source, retry không nhân user/attachment, proposal hợp lệ không mutation, package approval/executor exactly-once, restart recovery đều PASS. Cancel chờ đủ turn/internal/ACP mapping; adapter trả `cancelled`, API/DB terminal đúng và late output không persist. Trường terminal-event observational vẫn `false` do queue token của harness; terminal ID contract đã có regression/isolated UAT riêng nên không được suy diễn từ trường này. Current bounded real-GYO UAT chỉ PASS stream/context/source/cancel; real action_proposal, package và executor vẫn NOT RUN.
- Fidelity runner `scripts/run-v22-fidelity.ps1` được tách thành năm batch độc lập với cổng/DB/workspace tạm, readiness fail-closed, metadata từng capture và cleanup. Năm batch cuối tại `output/playwright/v22-batched-20260815-075743/` đều PASS: AppShell 10 biên breakpoint + theme; 6 primary surfaces; 7 Work tabs; empty/populated/approval/offline-retry; reduced motion/keyboard/drawer focus restore/reflow tương đương 400%. Có **62 screenshot** trong năm batch PASS. Hai lượt FAIL/INTERRUPTED trước sửa là superseded evidence và không tính.
- Finding runtime được sửa hẹp: browser GET cùng origin qua Vite proxy có thể không gửi `Origin` nhưng có `Referer`; Memory Hub operator giờ chấp nhận đúng origin lấy từ referer allowlisted. Thiếu cả hai hoặc foreign origin/referer vẫn 403; browser Review chạy lại sạch console.
- Acceptance vẫn `PARTIAL`: Playwright headless không cung cấp browser zoom 200% thật mà không dùng mô phỏng sai bản chất, nên ô này giữ `NOT RUN`; usability 5 người được người dùng hoãn hậu v2.2. Không nâng `DIRAP_V22_VALIDATED`.

## DIRAP v2.2 technical completion — PARTIAL pending human acceptance (2026-08-14)

### PRD/Blueprint v2.2 contract closure (2026-08-14)

- MCP Hermes được khóa fail-closed ở exact allowlist **9 tool**. `update_work_progress` đã được thay bằng `propose_work_update`, chỉ trả `DIRAP_ACTION_PROPOSAL:` theo `ActionPackageCreateRequest`; focused regression chứng minh không đổi plan/Work, không tạo package và không ghi mutation audit.
- `save_work_context_summary` nay là `write_internal`: validate Work/conversation/message range trước approval, chấp nhận `allow_once`/`allow_for_session`, revalidate sau approval, archive/deny/timeout fail closed; audit thành công chỉ chứa metadata.
- Release backend/frontend/package-lock/README đồng nhất **2.2.0** bằng regression tự động. App Shell có theme toggle toàn cục, dùng được khi chưa có Work và giữ `hermes.theme` sau reload.
- Attachment contract, retry preservation, seven structured-part persistence, proposal-to-package provenance, Review direct lifecycle/deep-link data contract, exact-nine MCP import safety và shared UI primitives có focused regression. Explicit attachment vẫn được ưu tiên khi cũ hơn general latest-20 query.
- Full validation trên trạng thái cuối: backend **460 passed, 1 skipped**; frontend **33 files / 170 tests passed**; type-check/build pass; lint 0 error và 4 warning Fast Refresh cũ; migration/idempotency/rollback suite **12 passed**. Build còn chunk >500 kB theo dõi P2; `git diff --check` không có lỗi, chỉ cảnh báo LF/CRLF.
- Isolated `uat-codex-` mock UAT **2/2 pass**: terminal SSE có đúng thread/turn ID, attachment/source/context, proposal chưa mutation, provenance/approval part, idempotency conflict, executor `succeeded` và exactly-once, cancel/late-output, report/artifact, archive guard, restart và n8n unconfigured graceful.
- Playwright evidence tại `output/playwright/v22-20260814-213613/` và recheck `v22-20260814-213958/light-390x667.png`: 10 breakpoint không horizontal overflow, dark/light persistence, mobile primary composer visible và console 0 error. Đây chưa phải full state-by-screen/zoom/reflow/reduced-motion matrix.
- Bounded real-Hermes UAT (`V22_REAL_HERMES_UAT_20260814.md`) là **PARTIAL**: prompt hoàn thành, managed source/code, no-mutation, late-output discard và restart recovery pass; không có proposal part hợp lệ, ACP cancel adapter trả `false`, retry thật `NOT RUN`.
- Verdict giữ **PARTIAL**: còn P1 real-Hermes proposal acceptance; fidelity ledger chưa đủ; usability **0/5 NOT RUN**.

### P0/P1 audit reproduction and correction (2026-08-14)

- A browser audit reported that `uat-hermes-v22` could not be created. Root cause: `frontend/vite.config.ts` had a hard-coded proxy target `127.0.0.1:8000`, so an isolated UAT frontend on `:5193` could silently call the non-isolated backend instead of its UAT backend.
- Correction: the proxy now reads the server-only `VITE_API_PROXY_TARGET`; `start-dev.ps1` supplies the backend port it starts. Browser UAT on temporary SQLite/workspace then created `uat-hermes-v22`, selected it, rendered it in the list, and displayed the success notice. With its UAT backend intentionally stopped, the same form retained input and displayed the inline failure message.
- `GET /health` now reports release version `2.2.0` (rather than the obsolete `0.1.0`). Focused health + SessionList tests, frontend type-check/build and `git diff --check` pass. Temporary UAT data/processes were removed. This resolves the reported P0/P1/P2 findings, but does not replace the remaining manual fidelity matrix or 5-person usability gate.
- Fresh full regression after this correction: backend `pytest -q` = **452 passed, 1 skipped**; frontend Vitest = **32 files / 166 tests passed**. Backend emitted only the existing Pydantic forward-reference and Starlette TestClient deprecation warnings.

### Responsive browser recheck (2026-08-14)

- Read-only browser checks at 389/390/391, 767/768/769, 1023/1024/1025 and 1440px found no horizontal overflow and no console errors. At 768px the Context drawer opened as a dialog, locked background scrolling and closed via Escape.
- Browser emulation confirmed `prefers-reduced-motion: reduce` and a 320px reflow equivalent without horizontal overflow. `RuntimeStatusPanel` focused tests (7) pass. The app's light mode is an explicit user choice (`data-theme`), not an automatic OS-color-scheme response; its runtime UI requires an available Work/runtime and remains `NOT RUN` in this empty-state pass.
- This is partial fidelity evidence only. Light/dark runtime interaction, 200% zoom, every async state, visual reference review and the unmoderated 5-person usability test remain `NOT RUN`.

- Backend full: `uv run pytest` → **452 passed, 1 skipped**. Cảnh báo đã biết: Pydantic forward reference trong settings và Starlette TestClient deprecation.
- Frontend full: `npm test -- --run` → **166 passed**; `npm run lint` → 0 error, 4 warning `only-export-components`; `npm run build` (gồm type-check) → pass. Build còn warning chunk >500 kB.
- Regression mới: `apiFetch` giữ `Content-Type: application/json` khi caller thêm `Idempotency-Key`; UAT đã phát hiện lỗi này qua tạo report rồi xác nhận artifact tạo thành công sau sửa. Migration `0028_assistant_conversation_link` có test backfill deterministic cho thread unambiguous và giữ thread ambiguous unbound.
- Isolated runtime/UAT: SQLite và managed workspace tạm, `HERMES_DEV_MOCK=1`, loopback-only. Health **20/20**; tạo Work, phase/step, hai conversation tách biệt, Hermes SSE mock/source, report template/provenance/preview và artifact thành công. Restart smoke giữ **2 conversations**, **2 artifacts** và next step. Môi trường UAT đã được xóa sau kiểm tra.
- Browser: 390×667 composer luôn hiện; 768×1024 drawer Ngữ cảnh mở và Escape đóng; 1024×600 rail 72px; 1440×900 desktop đầy đủ; console không có error ở các lượt kiểm tra. Không tuyên bố full fidelity ledger hoặc toàn bộ matrix 389/390/391… đạt vì chưa chạy/ghi nhận từng trạng thái.
- Verdict: **không có P0/P1 kỹ thuật đã biết trong phạm vi v2.2; checkpoint vẫn `PARTIAL`**. Usability test 5 người (>=4/5) là `NOT RUN`, do đó không nâng `DIRAP_V22_VALIDATED`.

## Hermes Assistant v2.2 hardening — focused verification (2026-08-14)

- Backend focused: `.venv\\Scripts\\pytest.exe tests\\test_assistant_actions_marketplace.py tests\\test_hermes_client.py -q` → **18 passed**, 1 cảnh báo Pydantic settings đã biết.
- Backend full trước regression “late completion discard” cuối: `.venv\\Scripts\\pytest.exe -q` → **441 passed, 1 skipped**, 2 cảnh báo dependency đã biết. Regression cuối đã chạy trong focused suite phía trên; full suite không được tuyên bố chạy lại sau đúng test bổ sung đó.
- Frontend: `npm run test -- --run src/components/HermesAssistantPanel.test.tsx` → **10 passed**; `npm run type-check` → pass. Full frontend trước regression stream-reopen cuối: `npm run test -- --run` → **155 passed**; lint 0 error, 4 warning `only-export-components` có sẵn; `npm run build` → pass.
- Runtime/browser: `http://localhost:5173/` có title Hermes Local, DOM không rỗng, không framework overlay hay console error/warning. Tương tác “Ngữ cảnh & nguồn” hiển thị drawer đúng kỳ vọng.
- Chưa chạy browser E2E Cancel với Work dữ liệu thật trong môi trường SQLite/workspace cô lập; do đó UI runtime Cancel là **PARTIAL**, còn behavior được chứng minh bằng backend/frontend regression.

## Local MVP Remediation v1.2 — Codex validation (2026-08-12)

- Backend full suite: **416 passed, 1 skipped**, 2 dependency deprecation warnings. Skip duy nhất là symlink fixture không có quyền tạo link trên Windows; junction/hardlink sandbox regressions chạy và pass.
- Frontend full suite: **134 passed**; lint sạch; TypeScript type-check pass; production build pass. Build còn cảnh báo chunk lớn hơn 500 kB, được theo dõi như P2 hiệu năng.
- Integrity/security regressions: concurrent approval/callback/activation and operation claims; migration interruption/rollback; archive-then-mutate; revision/hash file conflict; n8n idempotency; Telegram scoped identity; rejected knowledge exclusion; stale extraction durability; DOCX resource limits; CORS/operator local-origin boundary.
- Runtime: backend `:8000` và frontend `:5173` khởi động lại thành công; health/database/Hermes/SSE/workspace/memory-approval checks sẵn sàng; n8n được bỏ qua đúng cấu hình optional.
- Browser UAT bằng in-app browser: desktop 1280/1440; mobile 390; reachability tại 389/390/391, 433, 767/768/769, 1000, 1023/1024/1025, 1191/1192/1193 và 1440; không tràn ngang, navigation luôn có đường truy cập thay thế.
- Recovery UAT: banner backend tạm thời được khôi phục bằng “Kiểm tra lại” mà không tải lại trang. File/session scope và thuật ngữ người dùng cuối được kiểm tra trực quan.
- Approval UAT cô lập: pending approval rehydrate từ SQLite tạm; modal focus trap hoạt động cả hai chiều; action `write_file` được hiển thị thành “Ghi hoặc sửa tệp”; quyết định không có active waiter bị từ chối fail-closed; toàn bộ DB/workspace/process UAT đã xóa sau kiểm tra.
- Verdict: **VALIDATED FOR CONTROLLED LOCAL PILOT** trong boundary hiện hành. Không phải production readiness; không xác nhận webhook/credential production hay live restore.

## Personal Memory Hub Gói 3A + Gói 4 Verification (2026-08-10, validation in progress)

- Backend focused Memory Hub suite: **10 passed**. It covers scope isolation, lifecycle/role matrix, byte cap, provenance validation, duplicate-token fail-closed, explicit global preferences, legacy import idempotency, and the local operator boundary.
- Hermes failure characterization: deterministic client-boundary injection replaces environment-dependent mock spawning; the three focused failure-path tests pass.
- Frontend: the new Memory Hub API/component tests pass (**3 passed**); the complete frontend suite passes (**111 passed**) and production build passes. Browser requests contain no `Authorization` header.
- Dependency lock: `mcp==1.29.0`; `uv sync --frozen --extra dev` passes.
- Full backend suite: **369 passed, 1 skipped**. The two warnings are existing Pydantic-settings and Starlette TestClient deprecation warnings; no test failure remains.
- Fresh local REST smoke E2E: **PASS** on a temporary SQLite database. A Hermes credential created a scoped proposal; Codex verified and activated it; Hermes received the matching capped context pack through `127.0.0.1`. Credential values were neither displayed nor persisted to the workspace.
- Local pilot readiness scripts: **PASS** against an isolated backend. `check-memory-hub.ps1` checked health, Credential Manager presence without revealing tokens, and local operator access. `backup-memory-hub-drill.ps1` created a WAL-consistent backup, restored it to a temporary database, passed `integrity_check`, inspected the Hub table and removed only its temporary restore copy.

## Controlled Knowledge Search Acceptance Verification (2026-08-10)

- Backend: six DIRAP test modules -> **85 passed, 1 permitted symlink skip**.
- Frontend: complete Vitest suite -> **111 passed**; type-check, build and lint passed. Lint retained six pre-existing hook-dependency warnings, with zero errors.
- Direct Codex regression: `DirapPanel.test.tsx` now has **5 passing tests**, including Enter while busy dispatching no second request.
- `git diff --check` passed. No backend, API, schema, migration, dependency, policy or state mutation was introduced by the final direct repair.
- Verdict: **ACCEPTED** for the narrowly defined Controlled Knowledge Search slice only.

## DIRAP v3.0 Controlled Knowledge Search Verification (2026-08-10, Hermes — AWAITING CODEX RE-REVIEW)

### Backend tests
- Command: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py tests/test_dirap_controlled_search.py -q`
- Result: **85 passed, 1 skipped** in ~35s (skip = permitted symlink-escape case, environment cannot create a link).
- `backend/tests/test_dirap_controlled_search.py` (13 tests) covers: content match casefold + multi-space; provenance match; no-match empty; task scoping (không lộ bản ghi nhiệm vụ khác); unknown task 404; `official_search`/`legal_review` chỉ trả `regulatory`; `analysis_input` chấp nhận đủ 4 authority; exploratory trả `partial_usable` và các mục đích khác không trả partial (context_packaging/memory_query vẫn trả bản ghi đó như `usable` — đúng policy v1: sv verified + oa accepted / oa accepted); phân trang SAU lọc chính sách (draft không tính vào total); limit mặc định 20 / offset 0; validation (q rỗng/khoảng trắng/201 ký tự, query_type lạ, limit 0/101, offset âm → 422); **readonly**: records, audit count và bảng không đổi sau tìm; contract đủ field (13 trường, total/limit/offset).

### Frontend (slice + async-safety fix)
- `DirapPanel.test.tsx` = **4 passed** — gồm 3 test hành vi giao diện ban đầu (đổi cụm từ xóa kết quả cũ; đổi mục đích reset offset về 0; phản hồi cũ không ghi đè truy vấn mới) + test hồi quy async-safety: truy vấn A đang chạy (nút “Tìm” khóa) → đổi mục đích giữa chừng → nút “Tìm” được bật lại ngay → bấm nút (không dùng Enter) chạy truy vấn B → B trả trước và hiển thị → A trả sau nhưng không ghi đè/ghép B; notice phản ánh đúng mục đích mới; nút không khóa lại. (Fix: `handleSearchInputChange`/`handleSearchTypeChange` tăng `searchSeqRef` + `setSearchBusy(false)` — vẫn một nguồn trạng thái `searchBusy` duy nhất.)
- `npm.cmd run type-check` ✅, `npm.cmd run build` ✅ (chỉ warning chunk pre-existing), `npm.cmd run lint` → 0 errors (6 warnings exhaustive-deps pre-existing, không do lát này).

### Hygiene
- `git diff --check` → clean (chỉ CRLF warnings benign).
- 0 dòng `authoritative` trong `backend/app` + `frontend/src`; migrations giữ nguyên **19** (không migration mới); không dependency mới.
- `AI_STATE.json` valid JSON: `DIRAP_V3_CONTROLLED_SEARCH_IMPLEMENTED`, next_agent `codex`.
- Primary Hermes worktree not modified.

### Boundary
- Verified only deterministic task-scoped phrase matching + policy v1 filtering before pagination. No claim about AI, vector/FTS/semantic search, agents, automatic memory use, deployment or production readiness; no `authoritative` inference; no write API.

## Codex independent acceptance — Usability Read-only (2026-08-10)

- **Policy/API inspection:** six query types are exact; official_search/legal_review require regulatory; analysis_input accepts four non-none authority values; results are computed without database, audit or migration changes.
- **Backend:** `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py -q` → **72 passed, 1 skipped**. The permitted skip is the symlink-escape case on an environment that cannot create a link.
- **Frontend:** lint passed with 0 errors and six existing exhaustive-deps warnings; type-check and production build passed. `git diff --check` passed.
- **Boundary:** acceptance excludes search, agent use, AI, automatic memory use, deployment and production readiness.

## DIRAP v3.0 Usability Read-only Verification (2026-08-10, Hermes)

### Backend tests
- Command: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py tests/test_dirap_usability.py -q`
- Result: **72 passed, 1 skipped** in ~35s (skip = permitted symlink-escape case, environment cannot create a link).
- `backend/tests/test_dirap_usability.py` (20 tests) covers: policy engine per query type — official_search usable/partial (thiếu calculation hoặc owner)/unusable; exploratory_search partial khi source verified (authority/owner/calc bất kỳ, kể cả `none`) còn lại unusable; analysis_input usable cho cả 4 giá trị authority và partial khi thiếu calculation, unusable khi source chưa verified; legal_review chỉ usable khi đủ 4 điều kiện (không partial); context_packaging source+owner; memory_query chỉ cần owner (không bị chặn bởi source/authority); official_search & legal_review từ chối organizational/expert/derived/none; `none` đạt ở any nhưng không đạt tập cụ thể; `usable_for_query_types` chỉ gồm usable (exploratory không bao giờ usable); đúng 6 query types; query_type lạ → ValueError. API: record active (regulatory+calc) usable for official_search; draft record unusable với đủ 4 exclusion; analysis_input usable cho organizational; official_search từ chối expert với exclusion authority; memory_query usable cho derived; bản ghi khác nhiệm vụ → 404; bản ghi không tồn tại → 404; query_type sai → 422; **readonly**: dims/lifecycle không đổi, không audit event mới, không bảng mới (không migration).

### Frontend
- `npm.cmd run type-check` ✅, `npm.cmd run build` ✅ (chỉ warning chunk pre-existing), `npm.cmd run lint` → 0 errors (6 warnings exhaustive-deps pre-existing, không do lát này).

### Hygiene
- `git diff --check` → clean (chỉ CRLF warnings benign).
- 0 dòng `authoritative` trong `backend/app` + `frontend/src`; migrations giữ nguyên **19** (không migration mới).
- `AI_STATE.json` valid JSON: `DIRAP_V3_USABILITY_READONLY_IMPLEMENTED`, next_agent `codex`.
- No new dependencies; stdlib-only policy engine; primary Hermes worktree not modified.

### Boundary
- Verified only the read-only policy computation: six rule sets, exclusions, usable list, scoping, 404/422, no mutation/audit/migration. No claim about search, AI, agent, query planning, workflow completion, deployment or production readiness. `derived` remains deferred for official_search/legal_review until provenance data + verification rules exist (Q6, decision v1).

## Codex independent acceptance — Knowledge Review (2026-08-09)

- **Contract inspection:** migration 0019 changes only legacy `owner_acceptance_state='approved'` to `accepted`; new API values are `pending|accepted|rejected` and `none|regulatory|organizational|expert|derived`. The UI uses a closed select for the four approvable authority values; no `authoritative` inference exists.
- **Backend:** `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py -q` → **52 passed, 1 skipped**. The permitted skip is the symlink-escape case on an environment that cannot create a link.
- **Frontend:** lint passed with 0 errors and six existing exhaustive-deps warnings; type-check and production build passed.
- **Hygiene:** `git diff --check` passed. Acceptance excludes policy-derived usability, vocabulary reconciliation, AI, search, deployment and production readiness.

## DIRAP v3.0 Knowledge Review Verification (2026-08-08, Hermes)

### Backend tests
- Command: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py tests/test_dirap_knowledge_review.py -q`
- Result: **52 passed, 1 skipped** in ~23s ("skipped" = permitted symlink-escape case, environment cannot create link). Fix iteration 2026-08-09: `owner_acceptance_state` writes `accepted`; `authority_status` closed vocabulary; migration 0019 normalization; 13 review tests incl. reject idempotency.
- `backend/tests/test_dirap_knowledge_review.py` (13 tests) covers: full happy path `draft → review_pending → active` with the four dimensions + evidence rows + audit; calculation dimension `verified` only when a calculation reference is supplied (otherwise `unverified`); approve missing reviewer / source reference → 422 and `authority_status='none'` → 400 with no side effects; reject missing reviewer/reason → 422; every invalid transition → 409 (approve/reject on draft, double-submit, actions on `active`/`rejected`); review actions against another work item → 404 and unknown id → 404; reject keeps source linkage + evidence (`reviewer`, `decision_reason`) + audit and the record stays listed; idempotent submit/approve replay (single evidence set + single audit), key conflict → 409.

### Frontend
- `npm.cmd run type-check` ✅, `npm.cmd run build` ✅, `npm.cmd run lint` → 0 errors (6 pre-existing exhaustive-deps warnings).

### Hygiene
- `git diff --check` → clean (exit 0).
- `AI_STATE.json` valid JSON, state `DIRAP_V3_KNOWLEDGE_REVIEW_IMPLEMENTED`, next_agent `codex`.
- No new dependencies; Python standard library only (migration + endpoints reuse existing aiosqlite/idempotency/audit infra).

### Boundary
- Verified only the controlled review lifecycle: transitions, dimensions, evidence records and audit. No claim about policy-derived usability, `authoritative` mapping (policy and lifecycle vocabularies kept separate deliberately), AI, search, workflow completion, deployment or production readiness.

## Codex independent acceptance — Knowledge Records (2026-08-08)

- **Backend**: `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py -q` → **39 passed, 1 skipped**. The skip is the permitted symlink-escape case when the environment cannot create a link.
- **Frontend**: lint completed with 0 errors and six pre-existing exhaustive-deps warnings; type-check and production build passed.
- **Hygiene**: `git diff --check` passed. Codex read the migration, API contracts, focused tests and frontend creation/list/detail path.
- **Boundary**: accepted only for source-grounded `draft` records. No claim is made for verification, usability, AI, search, workflow completion, deployment or production readiness.

## DIRAP v3.0 Knowledge Records Verification (2026-08-07)

### Backend Tests
- **Command**: `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py tests/test_dirap_knowledge.py -q`
- **Result**: **39 passed, 1 skipped** (symlink-escape test skips with reason on this platform)
- **Knowledge Records coverage (9 new tests in `backend/tests/test_dirap_knowledge.py`)**:
  - `test_create_knowledge_record_happy_path` — 201 with full provenance: task/extraction/record/source IDs, `source_sha256` == SHA-256 of the source bytes, `extractor_version`, `provenance`, `content`, `status=draft`, `note`; exactly one `dirap.knowledge_record.created` audit (verified in audit table)
  - `test_create_knowledge_record_status_always_draft` — status is always `draft` (no auto verify/approve)
  - `test_create_from_stale_extraction_rejected` — source changed → creating from the old fresh extraction returns **409**, message contains "stale", no record created
  - `test_create_foreign_extraction_rejected` — extraction of another work item → **404** "does not belong"
  - `test_create_unknown_extraction_404` / `test_create_record_not_in_extraction_404` — unknown extraction / record not in the extraction → **404**
  - `test_create_idempotent_replay` — same Idempotency-Key + same payload → **201 then 200**, same record id, single row + single audit
  - `test_create_idempotency_conflict` — same key + different payload → **409**, no extra record
  - `test_list_and_detail_scoped_to_work_item` — records invisible under another work item (empty list / 404 detail), visible under their own; unknown record id → **404**

### Frontend Checks
- **Type-check**: `npm.cmd run type-check` passed
- **Build**: `npm.cmd run build` passed (only pre-existing Vite large-chunk warnings)
- **Lint**: `npm.cmd run lint` → **0 errors** (6 pre-existing exhaustive-deps warnings, none introduced by this slice)

### Reproducibility / Hygiene
- `git diff --check` → clean (only benign CRLF warnings)
- Commands used: pytest focused suite, type-check, build, lint — all pass
- Primary Hermes worktree not modified; slice confined to `DIRAP-Personal-v3`

### Security Invariants Verified (Knowledge Records)
1. A knowledge record is created only from a **fresh** extraction record — stale → 409 (freshness re-checked at creation via sandbox re-read + re-hash)
2. Only extraction records **belonging to the work item** can be used — foreign/unknown IDs → 404
3. The server always stores `status='draft'`; the client cannot set verified/in-use/approved
4. Idempotency prevents duplicate records/audits on retry; conflicting payloads on the same key → 409
5. Every successful creation writes an audit event; no new dependency, no AI, no PDF/OCR, no chat-history duplication

## DIRAP v3.0 Extraction Fixes Verification (2026-08-01)

### Backend Tests (after Codex CHANGES_REQUIRED fixes)
- **Command**: `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py -q`
- **Result**: **30 passed, 1 skipped** (symlink-escape test skips with reason when the environment cannot create symlinks/junctions)
- **Regression coverage for the two fixes**:
  - Fix 1 (dedupe): `test_extract_idempotent_unchanged_source` — extract twice with unchanged source/hash/version → same extraction ID, second call **HTTP 200**, exactly one extraction row + one record set, exactly one `dirap.extraction.completed` audit (verified in audit table)
  - Fix 2 (read-time staleness): `test_list_marks_stale_on_source_change` and `test_detail_marks_stale_on_source_change` — after the source file changes, GET list and GET detail both return the old extraction as `stale` and create exactly one `dirap.extraction.staled` audit targeting that extraction
  - Clear errors instead of silent fresh: `test_list_and_detail_missing_file_clear_error` (404 on list and detail when the file is gone), `test_list_sandbox_rejection_clear_error` (403 on list when the stored path escapes the workspace)

### Frontend Checks
- **Not run**: no frontend files were changed in this fix round (QA requirement allows skipping when frontend is untouched).

### Security Invariants Verified (after fixes)
1. Re-extraction never duplicates fresh data (idempotent on source hash + extractor version)
2. Old results are never presented as `fresh` — list/detail refresh staleness before responding
3. Every stale marking produces an audit event (one per actual change)
4. Freshness checks go through the workspace sandbox; missing/unsupported/rejected source → clear HTTP error
5. No new dependency, no AI extraction, no PDF/OCR

## DIRAP v3.0 Extraction Verification (2026-07-31)

### Backend Tests
- **Command**: `.venv/Scripts/python.exe -m pytest tests/test_dirap.py tests/test_dirap_extraction.py -v`
- **Result**: **26 passed, 1 skipped** (symlink-escape test skips with reason when the environment cannot create symlinks/junctions)
- **Extraction coverage (16 new tests)**:
  - Per-type extraction: `.txt`, `.md`, `.csv`, `.json` (array + object), `.docx` (fixture built with stdlib `zipfile`)
  - Hash/provenance: `source_sha256` matches SHA-256 of source bytes; `extractor_version`, `file_type`, `status`, `record_count` correct; records carry `seq` + provenance (line N / row N / item[N] / .key / paragraph N)
  - Stale: source content change → previous extraction becomes `stale`, new one `fresh`; unchanged content keeps all `fresh`
  - Audit: `dirap.extraction.completed` per extraction and `dirap.extraction.staled` per stale marking (verified in audit table)
  - Errors: unsupported type 415, invalid UTF-8 400, invalid JSON 400, missing file on disk 404, unknown source file 404
  - Sandbox re-check: DB-tampered path traversal → 403; symlink escape → 403 (skipped when links unavailable)

### Frontend Checks
- **Type-check**: `npm run type-check` passed
- **Build**: `npm run build` passed (only pre-existing Vite large-chunk warnings)

### Security Invariants Verified (Extraction)
1. Workspace sandbox re-validated before every file read at extraction time
2. Stale extractions are never presented as current data
3. Every extraction and stale marking produces an audit event
4. Only extracted records + provenance stored; original file remains in workspace
5. No new dependency, no AI extraction, no PDF/OCR

## DIRAP v3.0 Foundation Verification

### Backend Tests
- **Command**: `.venv/Scripts/python.exe -m pytest tests/test_dirap.py -v`
- **Result**: **10/10 passed** covering:
  - Create work item (happy path)
  - Create work item idempotency (same payload returns existing)
  - Create work item with unknown session (404)
  - List work items (with and without session_id filter)
  - Work item detail with audit trail
  - Attach source file (happy path with sandbox validation)
  - Attach source file path traversal rejected (`../../etc/passwd`)
  - Attach source file not found (file outside workspace)
  - Work item audit trail endpoint

### V2.2 final technical gate (2026-08-15)

- Backend: **461 passed, 1 skipped** (`python -m pytest backend/tests -q`).
- Frontend: **171 passed**; type-check, lint (0 error, 4 existing Fast Refresh warnings) and production build passed.
- Real Hermes bounded UAT: PASS for managed source, valid proposal, no mutation before approval, package provenance, exactly-once executor, cancellation late-output protection and restart recovery. ACP adapter returned `false` for compute cancellation, retained as P2.
- Browser fidelity: isolated Playwright breakpoint run `output/playwright/v22-20260815-065831/`, console errors 0; full state/zoom/reflow/reduced-motion matrix remains `NOT RUN`.
- Usability launcher: `scripts/start-v22-usability.ps1` smoke-tested with fresh temporary P1/P2 data; five real participant results remain `NOT RUN`.
- `git diff --check`: passed. Checkpoint remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`.

### Full Backend Suite
- **Command**: `.venv/Scripts/python.exe -m pytest tests/ -v`
- **Result**: **281 passed, 2 failed** (2 pre-existing Hermes spawn failures unrelated to DIRAP changes)
- **No regressions from existing tests**

### Frontend Checks
- **Type-check**: `npm run type-check` passed
- **Build**: `npm run build` passed

### Security Invariants Verified
1. Path traversal (`../../`) is rejected by existing `resolve_and_validate_path`
2. Absolute paths outside workspace are rejected
3. Every mutation (create work item, attach source file) produces audit events
4. Idempotency prevents duplicate work items on retry

### File Boundary Verified
- All changes confined to `DIRAP-Personal-v3` worktree
- Primary Hermes worktree (`C:\Users\dtron\Documents\Hermes`) not modified
- No secrets, env files, deployment config, or database files modified
- No commits, pushes, or deployments performed

## V1 Final Sign-Off Verification

- **Command**: `.\\.venv\Scripts\pytest` (full backend suite)
- **Result**: **274 passed, 1 warning** (pre-existing StarletteDeprecationWarning). Zero failures, zero regressions.
- **Frontend Checks**:
  - `npm run lint` passed with 5 existing React hook dependency warnings.
  - `npm run type-check` passed.
  - `npm run test -- --run` passed: 106 tests.
  - `npm run build` passed; Vite reported non-blocking large chunk warnings.
- **Git Diff Check**: No whitespace errors.
- **AI_STATE.json**: Valid, `CP10_COMPLETE`.
- **3 Medium-risk audit findings resolved**:
  1. AGENTS.md Current Gate - Updated from stale CP6 to `CP10_COMPLETE`/V1. Lists CP5-CP10 as verified and closed.
  2. Migration 0014 hardened - Replaced single `executescript` with per-statement callable using `PRAGMA table_info` pre-checks. Added regression test for partial schema recovery.
  3. OutboxDispatcher wired into FastAPI lifespan - Background task with `asyncio.Event` stop signal, configurable poll interval, n8n sender with graceful retry/dead-letter on missing config.
- **Verification Status**: PASSED. All V1 checkpoints (CP5-CP10) verified and closed. Awaiting human final sign-off.

## CP9 Skill Version Verification

- **Result**: 258 passed, 1 warning (Starlette deprecation). 20/20 CP9 specific tests passed.

## CP8 Model Fallback Verification

- **Result**: 239 passed, 1 warning (Starlette deprecation). 15/15 CP8 specific tests passed.

## CP7 Telegram Channel Verification

- **Result**: 224 passed, 1 warning (Starlette deprecation). 12/12 CP7 specific tests passed.

## CP6 Implementation Verification

- Targeted CP6/backend tests: 38 passed (then 39 after `task.cancelled` fix).
- Full backend suite: 209 passed, 1 failed (Hermes spawn), 1 warning.

## Environment Observations

- Python 3.11.2, uv 0.11.30
- Node v24.16.0, npm 11.13.0
- Windows 10 (git-bash shell)
- Hermes ACP process availability: depends on subprocess pipe permissions on Windows

## Validation

- All DIRAP v3.0 tests pass.
- Full backend suite passes except 2 pre-existing environment-dependent Hermes spawn failures.
- Frontend type-check and build pass.
- No whitespace errors in diff.
