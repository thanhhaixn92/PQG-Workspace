# Kế hoạch hoàn thiện Trợ lý GYO — Điều phối và bằng chứng

## Trạng thái điều hành

- Repository: `C:\Users\dtron\Documents\DIRAP-Personal-v3`
- Checkpoint bắt buộc giữ nguyên: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`
- Product: **PQG Workspace**; trợ lý trong web: **Trợ lý GYO**.
- Phạm vi sản phẩm: Local MVP/Pilot có kiểm soát cho một người dùng.

Tài liệu này là kế hoạch điều phối và ghi nhận tiến độ. Nó không promotion
checkpoint, không phải Gate PASS, và không thay thế `PROJECT_STATE.md`,
`AI_STATE.json` hoặc `docs/implementation/CURRENT_CHECKPOINT.md`.

## Mục tiêu sản phẩm

Luồng người dùng cần hoàn thiện là:

```text
Work -> trao đổi với Trợ lý GYO -> tài liệu/đầu ra
     -> tri thức có nguồn/review -> bộ nhớ có lifecycle
```

Các ranh giới không được phá vỡ:

- FastAPI là policy boundary; browser chỉ gọi REST/SSE backend.
- Work, Conversation, Assistant Thread và plan step là các scope riêng.
- `app.db` sở hữu dữ liệu Work và lịch sử Assistant hiển thị cho người dùng.
- GYO chỉ đề xuất; mutation Work chỉ đi qua Action Package, approval rõ ràng và
  executor idempotent.
- Memory/Skill chỉ là candidate reviewable, không tự kích hoạt.
- Không đưa provider secret, raw filesystem hoặc database access vào browser.

## Vai trò

### Codex — Coding Executor duy nhất

- Đọc contract/source/test, sửa trong scope đã được user cho phép và chạy
  validation sau source change.
- Không tự mở rộng sang backend, migration, provider, credential, checkpoint,
  deploy hoặc package khác.
- Không commit, push, reset, clean hoặc xóa dirty worktree.

### Hermes — Orchestrator và Independent Checker

- Không sửa production source, test, migration, config, credential, database
  hoặc state/checkpoint.
- Lập checker brief cho Codex, kiểm tra độc lập receipt/diff/full-file và báo
  evidence thật.
- Không promotion checkpoint. Chỉ đề xuất package tiếp theo khi user cấp scope
  riêng.

## Nguồn sự thật và thứ tự đọc

Trước mọi package, đọc theo thứ tự:

1. `PROJECT_STATE.md`
2. `AI_STATE.json`
3. `docs/implementation/CURRENT_CHECKPOINT.md`
4. `AGENTS.md`
5. `CODEGRAPH.md`
6. Contract, route/source và test trực tiếp của package.

Chạy `scripts/agent-preflight.ps1` trước khi sửa. Nếu lệnh validation của
package exit khác `0`, dừng package đó, báo evidence và không tự mở rộng scope.

## Tiến độ package

| Package | Nội dung | Trạng thái | Evidence/giới hạn |
| --- | --- | --- | --- |
| A | Scope resolver tuple mismatch | PASS — focused | Audit 2026-08-21: 4 resolver tests nằm trong nhóm backend 7/7 PASS. Wrong Work/Conversation/Thread fail-closed; 409 không tạo thread mới. |
| B1 | Archived Conversation guard | PASS — focused | Audit 2026-08-21: 3 mutation-guard tests nằm trong nhóm backend 7/7 PASS; không tạo turn/run/audit side effect mới. |
| B | Shared SSE registry | PASS — focused | Audit 2026-08-21: registry/shared-surface 2 files, 9/9 PASS. Registry sở hữu EventSource theo `assistant_thread_id`; Sidebar/WorkHub dùng shared subscription và scope/generation guard. |
| C | Phân loại 409 theo entry point | PASS — component | Audit 2026-08-21: canonical Vitest 5 files, 33/33 PASS; type-check PASS. Không phải browser/Gate PASS. |
| D0 | Native UAT runner và tiến trình | PASS — scoped | Run `package-d-native-20260822-046000`: lifecycle start/ready/browser/finalize/cleanup PASS; listener frontend/backend dừng và hai port đóng. |
| D1 | Browser UAT 2x2 và dual-surface scope/SSE | PASS — scoped | Run `046000`: 32/32 receipt, 12 artifact; desktop/mobile Sidebar + WorkHub, scope switch, exactly-one SSE, late-token isolation, terminal persistence, loopback diagnostics và zero unintended mutation. Review độc lập không còn blocker/major. Không phải Gate PASS. |
| E0 | Đối soát evidence current real-GYO | COMPLETE — provenance PARTIAL | State ghi PASS stream/context/source/cancel, nhưng artifact runtime current-GYO gốc không còn truy xuất được. Giữ `PASS theo state / provenance PARTIAL`; cần quyết định riêng nếu muốn rerun E1. |
| E1 | Current real-GYO stream/context/source/cancel | PASS theo state | `CURRENT_CHECKPOINT.md` ghi bounded UAT PASS và late output không persist; chỉ rerun nếu source/provider/evidence không còn tương thích. |
| E2 | Real proposal -> Action Package -> executor | PASS — bounded real provider | Authoritative receipt `output/e2-real-provider/package-e2-bounded-20260822-063658`; không thay historical E0 provenance PARTIAL. |
| F1 | Cancel correctness/provenance | PASS hẹp | Terminal cancel, late-output discard và audit/routing provenance; remote provider/process compute stop vẫn NOT PROVEN. |
| F2 | Fidelity đã có | PASS lịch sử / SUPERSEDED branding | 5 batch cô lập, 62 screenshot và Chrome native zoom 200% có giá trị geometry lịch sử; nhãn DIRAP/Hermes đã superseded, không tự chứng minh current-GYO fidelity. |
| F3 | Full screen x state x viewport cross-product | PASS — scoped current-GYO | Run `package-f-native-20260822-065000`: F01-F14 PASS cho viewport/theme/state, keyboard/focus, reduced-motion, reflow, 409, offline/recovery, staged approval và native Chrome zoom 200%. Không phải E2/Gate PASS. |
| G-SYNTHETIC | Synthetic agent evaluation | PASS — scoped | Aggregate `output/playwright/package-g-synthetic-aggregate-20260822-0837`; không phải human usability evidence và không promotion checkpoint. |

### Cập nhật thực thi ngày 2026-08-22

- Package D đạt scoped PASS tại
  `output/playwright/package-d-native-20260822-046000`.
- Finalizer exit `0`; metadata `PASS`, `32/32` assertion, `12/12` artifact và
  `failure_count=0`.
- D13 lưu server snapshot đúng một SSE active cho B1 ở từng viewport. D14 chỉ
  được recorder chấp nhận khi đúng synthetic B1 turn của viewport có DB status
  `completed`; ảnh `b1-done` được chụp sau khi marker tương ứng mất trạng thái
  running/cancel.
- Console không có error/warn; 155 network request đều loopback. Final
  observation có zero product POST, zero Action Package, zero approval và đúng
  bốn synthetic turn.
- Review độc lập xác nhận scoped Package D PASS. Checkpoint vẫn giữ
  `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; E0 reconciliation và F gap
  audit đã hoàn tất read-only, E1/E2 provider và G usability chưa được mở.

#### Package F — current-GYO fidelity

- Runner Package F đã được harden và review độc lập PASS-to-run. Dry lifecycle
  `output/playwright/package-f-native-dry-20260822-031001` xác nhận start/stop
  exit `0`, seed F13 trước F12 bị từ chối `409`, cleanup hoàn tất và port đóng.
- Run `output/playwright/package-f-native-20260822-033000` kết thúc `FAIL` sau
  F12 vì F13 phát hiện ApprovalModal còn copy Hermes. Run này được giữ nguyên
  làm evidence thất bại; không được nâng thành PASS.
- Remediation hẹp đổi copy hiển thị của ApprovalModal sang `Trợ lý GYO`, giữ
  nguyên technical identifier `hermes.permission` và approval semantics.
  `ApprovalModal.test.tsx` PASS `9/9`; canonical frontend 5 file PASS `33/33`;
  type-check PASS, đều exit `0`.
- Run authoritative
  `output/playwright/package-f-native-20260822-042000` có metadata `PARTIAL`,
  F01-F13 PASS và F14 native zoom 200% `NOT_RUN`. Có 14 receipt duy nhất, 13
  JPEG decode đúng geometry, manifest artifact/source kiểm hash, 226 request
  đều loopback, hai console error dự kiến `409/503` được allowlist và
  `unexpected_error_count=0`.
- Observer ghi `provider_bound_run_attempts=0`, `controlled_409=1`, zero Action
  Package mutation, zero approval decision và zero executor. Fixture F13 chỉ
  được seed sau receipt recovery F12 hợp lệ; không approve/deny fixture.
  Finalizer trả non-zero cho trạng thái PARTIAL (lớp thực thi quan sát exit
  `1`), metadata không có failure object; frontend/backend listener dừng và hai
  port đóng.
- Review độc lập xác nhận không còn blocker/major trong evidence F01-F13. F14
  không được thay bằng CSS/CDP emulation; Computer Use không thể rehydrate đúng
  cửa sổ Chrome nên không gửi phím zoom và giữ `NOT_RUN`.
- Chẩn đoán tiếp theo xác nhận native Windows `Ctrl + +` có thể điều khiển đúng
  một cửa sổ Chrome thử cô lập: zoom tăng 100% -> 110%, innerWidth `929 -> 845`
  và DPR `1 -> 1.1`. Đây chỉ là capability proof, chưa phải receipt F14.
- Run mới `output/playwright/package-f-native-20260822-055000` dừng ở F02 vì
  sidebar phủ lên nút đổi theme, khiến Playwright click bị timeout. Finalizer
  exit `1`, metadata `FAIL`, `1/14` receipt; cleanup dừng toàn bộ listener và
  port `53962/53963` đóng. Evidence root này bất biến và không được tái sử dụng.
- Copy user-visible trong `ActivityInspector` cũng đã đổi sang `Trợ lý GYO`, giữ
  raw `hermes.permission` chỉ trong chế độ Kỹ thuật. Focused test PASS `8/8`,
  type-check PASS và full-file review độc lập PASS; copy `waiting_approval` chưa
  có assertion trực tiếp là residual coverage nhỏ.
- Run current authoritative
  `output/playwright/package-f-native-20260822-065000` đạt metadata `PASS` và
  `14/14` receipt. F14 dùng Chrome native `Ctrl + +` tới 200%, đo DPR `2`, CSS
  inner/client/scroll width `720` và JPEG capture `1440x900`; không dùng CSS,
  device-scale hay CDP emulation. Có 20 artifact immutable, 409 request đều
  loopback, `unexpected_error_count=0`; observer vẫn ghi provider-bound run `0`,
  Action Package mutation `0`, approval decision `0`, executor `0`, synthetic
  turn `2` và controlled 409 `1`. Finalizer exit `0`; frontend/backend cleanup
  hoàn tất, port `56351/56352` đóng.
- Review độc lập read-only xác nhận `065000` PASS scoped: 14 receipt và 20
  artifact là duy nhất, SHA-256/byte count/JPEG geometry đều khớp, source manifest
  current `22/22` khớp. F11 giữ prompt sau controlled 409; F12 -> F13 staging
  đúng thứ tự. Residual của F3: F08/F09/F10 cùng visible fixture hash chỉ chứng
  minh state-visible fidelity, không phải một cancel end-to-end mới.

### E0 — Ledger provenance current real-GYO

- `PROJECT_STATE.md`, `AI_STATE.json` và
  `docs/implementation/CURRENT_CHECKPOINT.md` đều ghi bounded real-GYO
  stream/context/source/cancel PASS và late output không persist.
- Không tìm thấy artifact runtime current-GYO gốc có đủ path, timestamp,
  provider/model ID, source hash, assertion receipt, cleanup và identity môi
  trường cô lập. Kết luận bắt buộc: `PASS theo state / provenance PARTIAL`.
- `output/playwright/v22-batched-20260815-075743/real-hermes-final.json` là
  evidence Hermes/ACP lịch sử, đã bị `AI_VERIFICATION.md` đánh dấu superseded;
  không được dùng làm E1/E2 current-GYO evidence.
- Không rerun E1 nếu chưa có quyết định và authorization provider/cost riêng.
  E2 vẫn `NOT RUN`.

#### Package E2 — bounded real-provider attempt ngày 2026-08-22

- User đã cho phép acceptance cô lập: chỉ model free hiện có, dữ liệu Work
  tổng hợp, SQLite/workspace tạm, không đổi profile/credential/default hay
  fallback. Runner chỉ tiến tới Action Package khi proposal thật đạt contract;
  mọi temp root được xóa sau receipt đã redaction.
- `output/e2-real-provider/package-e2-bounded-20260822-054625/`: MiMo V2.5
  Free HTTP 200, một provider stream, không có `action_proposal`.
- `output/e2-real-provider/package-e2-bounded-20260822-054906/`: cùng model,
  prompt nghiệp vụ khác, HTTP 200 và vẫn không có proposal.
- `output/e2-real-provider/package-e2-bounded-20260822-054957/`: MiMo HTTP
  429; fallback 0, assistant thất bại và không có mutation.
- `output/e2-real-provider/package-e2-bounded-20260822-055241/`: Nemotron 3
  Ultra Free HTTP 200, part `text`/`source`, không có proposal. Prompt sau đó
  được làm rõ: scope Work/Conversation do server gắn, không yêu cầu model bịa
  ID; regression control-plane 36/36 PASS.
- `output/e2-real-provider/package-e2-bounded-20260822-055446/`: Nemotron
  sau source clarification HTTP 200 nhưng persist `text`/`source`/`tool_result`,
  không có proposal hợp lệ. Đây là provider-adherence/format hiện hành, không
  được thay bằng fake proposal.
- `output/e2-real-provider/package-e2-bounded-20260822-055729/`: DeepSeek V4
  Flash Free trả HTTP 400; fallback 0, assistant persist `error`/`source` và
  Work vẫn inert.
- Read-only Zen catalog ngày 2026-08-22 trả HTTP 200, xác nhận `hy3-free` và
  `laguna-s-2.1-free` là free qua credential Opencode hiện có. Raw catalog có
  `muse-spark-1.2` và `muse-spark-1.2-contributor-free`, nhưng catalog an toàn
  ban đầu chưa allow-list hai identifier này. User đã xác nhận chính xác bản
  `muse-spark-1.2-contributor-free`; identifier này được thêm vào allow-list
  Zen Free với regression provider-core 8/8 PASS. Model chỉ được seed vào
  SQLite tạm, không được thêm vào profile/default sản phẩm.
- `output/e2-real-provider/package-e2-bounded-20260822-060301/`: HY3 Free
  HTTP 200, `text`/`source`/`tool_result`, không có proposal hợp lệ.
- `output/e2-real-provider/package-e2-bounded-20260822-060352/`: Laguna S
  2.1 Free HTTP 200, cùng kết quả và Work vẫn inert.
- `output/e2-real-provider/package-e2-bounded-20260822-060801/`: Muse Spark
  1.2 Contributor Free HTTP 200, `text`/`source`/`tool_result`, không có
  proposal hợp lệ và Work vẫn inert.
- **Kết luận:** E2 vẫn `NOT RUN`; không có Action Package, approval decision
  hay executor attempt nào. Checkpoint tiếp tục `PARTIAL`. Attempt mới chỉ mở
  khi user cấp ngân sách/điều kiện provider mới hoặc waive/defer E2 rõ ràng.

### F1/F2/F3 — Ledger cancel và fidelity

- Claim cancel hẹp đạt PASS giới hạn: API persist `cancelled`, late model
  text/parts bị discard, audit và routing provenance được giữ. Claim mạnh về
  portable provider/process compute cessation vẫn `NOT PROVEN` vì adapter cancel
  là best-effort.
- Năm batch lịch sử dưới
  `output/playwright/v22-batched-20260815-075743/` có 62 screenshot; native
  Chrome zoom 200% tại `output/playwright/v22-brandzoom-20260815-0900/` PASS cho
  geometry đã ghi. Branding/naming cũ đã superseded.
- Package D `046000` và Package F `042000` cùng bổ sung current-GYO evidence cho
  Sidebar/WorkHub tại 320/390/1024/1440, dark/light theme, populated/running/
  cancelled, keyboard/focus, reduced-motion/reflow, 409, offline/recovery và
  staged pending approval.
- Matrix Package F đã đủ 14/14 receipt current-GYO tại run `065000`. Staged
  approval F13 chỉ chứng minh fidelity của UI inert; không được dùng làm real E2
  evidence.

## Audit độc lập ngày 2026-08-21

### Kết luận

- A, B1, B và C vẫn xanh ở phạm vi focused/component; audit chạy lại backend
  `7/7`, shared SSE `9/9`, canonical frontend `33/33` và type-check, đều exit
  `0`.
- Package D chưa thực hiện UAT. Có 11 thư mục run mang trạng thái `FAIL`; run
  native cuối chỉ đạt readiness `READY`, `completed_at=null`, `cleanup=null`,
  không có assertion receipt hay screenshot.
- Runner native hiện kết thúc ngay sau khi seed fixture và ghi `READY`; success
  path không có pha browser, không chờ finalize và không bảo đảm cleanup. Vì
  vậy `assertion_count=32` chỉ là số dự kiến, không phải số PASS.
- E và F trong bản kế hoạch trước bị phân loại quá thô. State hiện hành đã ghi
  PASS giới hạn cho real-GYO stream/context/source/cancel, cancellation
  correctness/provenance, năm fidelity batch và native zoom 200%; phần còn thiếu
  là real action flow, portable process stop claim và các ô fidelity chưa chạy.
- Tất cả target implementation A-D đang là file untracked trong worktree rất
  bẩn. Git diff không cung cấp baseline đáng tin cho chúng; mỗi package phải lưu
  manifest `path + SHA-256` và full-file review các file `??`.

### Thứ tự ưu tiên evidence

1. `PROJECT_STATE.md`, `AI_STATE.json`, `CURRENT_CHECKPOINT.md` hiện hành.
2. Artifact runtime có timestamp, hash, receipt và trạng thái hoàn tất.
3. Test output tái chạy trên source hash hiện hành.
4. Handoff/checker report.
5. Artifact lịch sử hoặc superseded chỉ dùng tham khảo, không dùng promotion.

`AI_VERIFICATION.md` xác định `real-hermes-final.json` là evidence Hermes ACP
lịch sử đã superseded, không phải current real-GYO evidence. Tuyệt đối không dùng
artifact này để claim E2 PASS.

## Package C — bằng chứng hiện hành

`AssistantChatSidebar` đã có regression cho `ApiError(409)` từ chat/run:

- Notice scope/run render ở composer đang mount với `role="alert"`.
- Prompt và persisted timeline được giữ trong scope/generation của snapshot.
- Không retry run.
- Không tạo Conversation, Assistant Thread hoặc Action Package.
- Không gọi approval flow/reload.
- Regression deferred `A -> B -> A -> 409` không restore draft/notice cũ vào
  thế hệ scope mới.

Canonical command đã PASS:

```text
npm test -- src/components/ApprovalModal.test.tsx \
  src/components/ActionPackagesPanel.test.tsx \
  src/components/ReviewInboxPanel.test.tsx \
  src/components/AssistantChatSidebar.test.tsx \
  src/components/WorkHub.test.tsx

5 files passed; 33 tests passed; exit 0
```

`npm run type-check` cũng PASS. Điều này chỉ xác minh component scope Package C;
không thay thế browser/runtime/UAT và không thay đổi checkpoint.

## Khoảng trống v2.2 còn lại

- Package D đã scoped PASS; kết quả này chưa phải Gate PASS và không giải quyết
  các quyết định provider/usability còn lại.
- Current real-GYO đã đối soát E0 nhưng provenance runtime gốc vẫn PARTIAL;
  muốn tái lập cần authorization rerun E1 riêng.
- Real action-proposal -> Action Package -> executor chưa có acceptance thực;
  nếu proposal không xuất hiện, phải báo `NOT RUN`, không giả lập evidence.
- Package F3 current-GYO đã đạt scoped PASS `14/14`; kết quả không thay thế E2,
  strong cancel claim hoặc usability gate.
- P2 cancel có regression proof nhưng chưa chứng minh portable process-level
  compute stop.
- Usability 5 người đang hoãn và chưa có waiver khỏi promotion gate.

Các nội dung ngoài phạm vi v2.2 hiện hành: deploy/cloud, connector package 2,
vector/AI search, automatic Memory Hub injection, legacy cutover, Hub
retention/delete và encrypted backup.

## Quy tắc mở package tiếp theo

Authorization thực thi hiện tại đã mở và hoàn tất D, E0 read-only và F gap audit
read-only. Không tự mở E1/E2 real provider, strong cancel contract hoặc G
usability. Khi user cấp authorization mới, Hermes phải gửi Codex một brief có:

1. Mục tiêu quan sát được.
2. Scope file/surface được phép sửa.
3. Invariants, non-goals và rủi ro.
4. Exact validation command và điều kiện PASS/PARTIAL/FAIL/NOT RUN.
5. Quyền external action, nếu có.

Hermes review độc lập sau receipt của Codex. Browser UAT và real provider không
được suy ra từ component/unit test.

## Kế hoạch thực hiện phần còn lại

### Phase 0 — Khóa baseline và xử lý tồn dư Package D — COMPLETE

**Mục tiêu:** đưa môi trường về trạng thái biết rõ trước mọi UAT mới.

1. Ghi manifest path, SHA-256 và trạng thái tracked/untracked của toàn bộ file
   A-D và script D.
2. Ghi PID, parent PID, port, command line và evidence directory của tiến trình
   D còn sống; không xóa artifact.
3. Chỉ sau authorization cleanup, dừng đúng các PID/port thuộc run D orphan;
   xác nhận port đóng và source/hash không đổi.
4. Đánh dấu run `package-d-native-20260821-220000` là
   `ABORTED_READY_ONLY` hoặc tương đương trong receipt mới; không sửa artifact
   lịch sử để biến thành PASS.

**Done:** không còn orphan D; artifact cũ được bảo tồn; baseline hash có thể
đối chiếu. Nếu không được phép cleanup, dừng ở `BLOCKED`, không chạy D1.

### Phase 1 — Remediation runner Package D — COMPLETE

**Mục tiêu:** runner có vòng đời `start -> ready -> browser run -> finalize ->
cleanup`, không thể thoát success ở `READY`.

Scope dự kiến chỉ gồm `scripts/start-package-d-native-uat.ps1` và driver/evidence
helper trực tiếp nếu source chứng minh bắt buộc. Trước khi sửa helper phải nêu lý
do.

Yêu cầu bắt buộc:

- `READY` là trạng thái trung gian; PASS chỉ sau đủ receipt bắt buộc.
- Có max duration/heartbeat và phát hiện parent chết.
- Success, failure và interruption đều đi qua `finally` cleanup.
- Metadata tách `planned_assertion_count` khỏi `passed_assertion_count`.
- Completion receipt chứa source hash, browser/profile, ports, timestamps,
  screenshots, console diagnostics và cleanup result.
- Không `setTimeout`, fake receipt, dummy PASS hoặc mutation sản phẩm để tạo
  bằng chứng.

Validation: preflight; parser/lint phù hợp; dry-run lifecycle cô lập; xác nhận
failure path và interruption path đều cleanup. Lệnh exit khác `0` thì dừng.

### Phase 2 — Package D browser UAT thật — COMPLETE / scoped PASS

**Mục tiêu:** kiểm tra desktop/mobile, Sidebar/WorkHub và dual-surface SSE trên
browser thật, không dùng real provider.

Thực hiện bằng Browser capability với profile/workspace/SQLite cô lập:

1. Chạy matrix desktop và mobile cho scope Work/Conversation.
2. Mở đồng thời Sidebar và WorkHub trên cùng thread; xác nhận đúng một
   EventSource/thread/tab.
3. Chuyển scope A -> B và A -> B -> A trong khi event deferred; late event
   không được rò vào generation mới.
4. Xác nhận persisted timeline giữ nguyên ở terminal/error; 409 hiển thị notice
   tại surface còn mount và giữ prompt đúng generation.
5. Quan sát endpoint và network: không Conversation/thread/Action Package/
   approval/product mutation ngoài fixture dự kiến.
6. Thu đủ assertion receipt, screenshot, console/network log và final cleanup.

**PASS:** toàn bộ assertion bắt buộc PASS, không console error ngoài allowlist,
không mutation ngoài ý định, không orphan, evidence hash ổn định. Nếu thiếu một
nhóm bằng chứng: `PARTIAL` hoặc `FAIL`, không mở rộng source ngoài scope.

### Phase 3 — Đối soát và hoàn tất real-GYO

#### E0 — Evidence reconciliation

Tìm và lập chỉ mục artifact gốc cho bounded real-GYO PASS đã được state ghi nhận:
path, timestamp, provider/model, source hash, assertions và cleanup. Nếu artifact
không còn truy xuất được, giữ claim là `PASS theo state / provenance PARTIAL` và
xin quyết định rerun; không tự hạ hay nâng checkpoint.

#### E1 — Giữ bằng chứng đã đạt

Không rerun stream/context/source/cancel nếu source/provider và artifact vẫn
tương thích. Nếu buộc rerun, cần authorization real provider, giới hạn số lượt,
chi phí, dữ liệu gửi ra ngoài và điều kiện dừng.

#### E2 — Real action flow còn thiếu

**Đã được user authorization để triển khai.** Kiểm tra bounded flow:

`real proposal -> inert proposal -> idempotent Action Package -> explicit
approval -> executor runs once -> audited result`.

Không tự ép model tạo proposal, không giả proposal làm real evidence. Mỗi attempt
chỉ dùng một provider call, manual routing, fallback 0, SQLite/workspace tạm và
dữ liệu tổng hợp. Không thay provider config hoặc credential thật. Lần chạy đầu
dùng OpenCode Zen `muse-spark-1.2-contributor-free`; lỗi transport/quota mới
được chuyển sang `mimo-v2.5-free`, rồi HY3/Laguna S 2.1 Free qua Hermes API nếu
profile/credential đã tồn tại. Không lặp lại attempt giống hệt; mỗi attempt mới
phải dựa trên diagnostic đã làm sạch, remediation tương ứng hoặc provider rotation.

Parser giữ diagnostic tương thích `missing_marker`, `invalid_json`,
`invalid_schema`, `valid` và chỉ thêm reason code allow-list không chứa raw model
output. Cho phép đúng một JSON object thuần hoặc nằm trọn trong một JSON Markdown
fence; từ chối trailing prose, nhiều marker hoặc nhiều proposal. Schema Pydantic
không alias/coerce trường sai. Receipt E2 chỉ lưu diagnostic, reason code, model,
call count, mutation ledger, hash và cleanup.

E2 chỉ PASS khi real provider tạo đúng một proposal `work_status_update`
`in_progress/1`, proposal inert/server-scoped, Action Package idempotent,
approval hash-bound, executor production entry point xử lý một lần, audit đầy đủ
`proposed -> approved -> executing -> succeeded`, Work đổi đúng hai scalar và
toàn bộ fixture tạm được cleanup. Nếu toàn bộ provider miễn phí hết quota, không
cấu hình hoặc không tương thích, E2 là `BLOCKED`; checkpoint giữ `PARTIAL`, không
tự dùng model trả phí hoặc tạo credential.

### Phase 4 — Cancel và fidelity còn thiếu

#### F1 — Chốt claim cancellation

**Quyết định user đã chốt: claim hẹp.** API terminal cancellation, late output
discarded và routing provenance persisted là phạm vi acceptance. Không cần mở
rộng adapter/provider cancellation; không được tuyên bố remote compute/process
dừng portable. Residual risk phải nêu rằng provider có thể vẫn tiếp tục request
hoặc compute từ xa.

#### F2/F3 — Gap-ledger fidelity

1. **COMPLETE:** giữ run `065000` làm baseline immutable cho 14 ô current-GYO
   đã PASS, gồm native Chrome zoom 200%.
2. Nếu source hiển thị liên quan đổi, đánh giá impact theo manifest/hash và chỉ
   rerun các ô bị ảnh hưởng; không mặc định lặp toàn bộ suite.
3. Không dùng CSS zoom, device scale factor hoặc CDP emulation làm thay thế cho
   native Chrome zoom trong evidence tương lai.

**Done:** không còn ô bắt buộc ở trạng thái missing, hoặc có waiver cụ thể được
ghi trong source-of-truth.

### Phase 5 — G-SYNTHETIC (thay thế gate người dùng thật cho v2.2)

**Quyết định user ngày 2026-08-22:** Gate usability năm người thật được thay
bằng đánh giá năm agent độc lập. Kết quả bắt buộc ghi `synthetic agent evaluation`;
nó không phải và không được suy ra là bằng chứng usability của con người.

- Chạy năm evaluator `A01`-`A05`, tối đa ba phiên song song rồi hai phiên còn lại.
  Mỗi phiên có browser profile, SQLite, workspace, port và fixture tổng hợp riêng.
- Agent chỉ nhận task script, không được đọc source/test hoặc nhận hướng dẫn thao
  tác. Không real provider, approval thật, executor hoặc dữ liệu sản phẩm.
- Task 1/3/5 không có hint; Task 2/4 tối đa một standardized neutral prompt.
  Các task vẫn là chọn/giải thích scope, nhận biết run và History & Context bằng
  bàn phím, đổi Conversation, recovery scope/run/offline không mất draft, và
  hiểu proposal/approval inert.
- Receipt gồm evaluator ID, agent/model version, source hash, fixture ID,
  browser/profile, kết quả/thời lượng từng task, hint count, issue IDs, screenshot
  và cleanup. Không lưu credential, raw provider output, source/test transcript
  hoặc dữ liệu sản phẩm.
- PASS khi 5/5 đạt Task 1/3/5, ít nhất 4/5 đạt Task 2/4, không còn Critical/Major,
  và Minor/Cosmetic có owner/trạng thái. Source thay đổi sau bất kỳ phiên nào làm
  receipt hash cũ không hợp lệ; phải chạy lại đủ năm agent trên final hash.

#### Historical Protocol G — superseded for v2.2

Chuẩn bị protocol, consent/privacy, task script, success metrics và severity
rubric cho năm người thật. Protocol này được giữ nguyên như lịch sử, không bị
thực hiện hoặc diễn giải là evidence của G-SYNTHETIC.

#### Protocol G đã chuẩn bị — chưa thực hiện

**Mục tiêu quan sát được:** xác minh năm người dùng thật có thể hiểu phạm vi
Công việc/Phiên trao đổi, dùng Trợ lý GYO và recovery UI mà không nhầm lẫn quyền
thực thi hay mất nội dung đã nhập.

**Điều kiện trước khi mời:** product owner phê duyệt protocol này; mỗi người
tham gia được biết đây là local pilot, không gửi prompt bí mật/nhạy cảm, có thể
dừng bất kỳ lúc nào và không có real provider, approval decision hay executor
trong phiên test. Lưu tối thiểu mã `P01`–`P05`, kết quả task và issue đã được
đồng ý; không mặc định ghi âm/quay màn hình hoặc thu định danh cá nhân.

**Môi trường và mutation:** mỗi buổi dùng browser profile, SQLite, workspace,
Work/Conversation và fixture tổng hợp cách ly; người tham gia chỉ thao tác dữ
liệu mẫu đã seed. Không tạo/sửa Work, Conversation, Action Package, approval
decision, executor hoặc dữ liệu bền trong môi trường sản phẩm. Chỉ facilitator
được bật fixture/recovery có kiểm soát; cleanup profile, DB và workspace cách
ly sau từng người/buổi, sau khi đã lưu evidence đã đồng ý.

**Consent và lưu evidence:** trước khi bắt đầu, facilitator giải thích mục tiêu,
loại dữ liệu ghi nhận, người có quyền xem (facilitator và Hermes checker), vị trí
local do product owner phê duyệt và thời hạn lưu đề xuất 30 ngày. Mapping giữa
người thật và `P01`–`P05` không đặt trong evidence; quote phải biên tập/ẩn danh.
Người tham gia có thể rút consent qua facilitator; khi đó mapping và mọi note,
quote hoặc capture có thể liên kết bị xóa khỏi evidence local theo quy trình đã
được product owner duyệt, trừ dữ liệu bắt buộc phải giữ theo luật/chính sách áp
dụng.

**Kịch bản cố định cho mỗi người:**

1. Chọn một Công việc và một Phiên trao đổi, giải thích ngắn phạm vi dữ liệu
   đang dùng.
2. Gửi một yêu cầu mẫu không nhạy cảm, nhận biết trạng thái đang chạy/kết thúc
   và mở Lịch sử & ngữ cảnh bằng bàn phím.
3. Chuyển Phiên trao đổi rồi quay lại; xác nhận lịch sử hiện đúng phạm vi.
4. Xử lý notice scope/run và offline/recovery mẫu; xác nhận bản nháp không mất
   và biết cách thử lại.
5. Quan sát một đề xuất/approval inert; diễn giải đúng rằng GYO chỉ đề xuất và
   không tự thay đổi Công việc khi chưa có phê duyệt rõ ràng.

**Nhắc trung tính đã chốt trước:** facilitator không nhắc, chỉ tay, gọi tên
button, mô tả kết quả mong đợi hoặc trả lời thay cho người tham gia. Task 1/3/5
không dùng nhắc. Với Task 2 hoặc 4, được dùng nhiều nhất một câu tương ứng,
đúng nguyên văn: (2) “Bạn hãy nói to điều bạn đang tìm và thao tác theo cách
bạn cho là phù hợp.”; (4) “Bạn hãy nói to điều bạn mong đợi sẽ xảy ra tiếp
theo.” Nếu người tham gia hỏi cách làm, chỉ trả lời: “Tôi không thể hướng dẫn
thao tác; bạn hãy chọn cách bạn cho là phù hợp.” Ghi `neutral_prompt_used`
(`none`, `task_2`, hoặc `task_4`) vào receipt; dùng thêm câu, đổi câu hoặc gợi
ý thao tác làm task đó fail theo ngưỡng coaching.

**Dữ liệu ghi nhận:** thời gian hoàn thành từng task, hoàn thành/không hoàn
thành, số lần cần hỗ trợ, trích dẫn phản hồi đã được đồng ý và issue ID. Không
gộp điểm hoặc suy ra thông tin định danh từ người tham gia.

**Receipt tối thiểu mỗi buổi:** `participant_id` (`P01`–`P05`), ngày/phiên
fixture, build/source hash, xác nhận consent (`yes`/`withdrawn`),
`neutral_prompt_used`, kết quả và thời lượng Task 1–5, số coaching, issue ID,
và xác nhận cleanup SQLite/workspace/profile. Không ghi tên thật, email, prompt
thô, mapping định danh hay media chưa được đồng ý. Nếu consent bị rút, receipt
chỉ giữ trạng thái `withdrawn` và tham chiếu cleanup; xóa mọi note/quote/capture
có thể liên kết theo quy trình PO đã duyệt.

**Bản ghi quyết định PO trước khi mời:** owner phải ghi ngày, một trong
`approve_protocol` / `defer` / `waive_gate`, phạm vi user/data cho phép, nơi
lưu evidence, retention, owner xử lý issue và điều kiện retest. `waive_gate`
phải nêu rõ G không còn chặn promotion; `defer` không thay cho waiver và giữ
checkpoint `PARTIAL`.

**Success metrics đề xuất trước khi mời:** mỗi task được chấm pass/fail. Task
1/3/5 chỉ pass nếu người tham gia giải thích đúng scope hoặc approval boundary
và hoàn thành không coaching; Task 2/4 pass nếu hoàn thành flow với tối đa một
nhắc trung tính. G chỉ có thể PASS khi 5/5 pass Task 1/3/5, ít nhất 4/5 pass Task
2/4, không có Critical/Major mở và mọi Minor/Cosmetic còn lại có issue/owner.
Mọi task fail hoặc cần coaching vượt ngưỡng phải mở remediation; các ngưỡng này
cần product owner phê duyệt trước khi tuyển người dùng.

**Rubric severity:** Critical = hiểu sai có thể dẫn tới lộ dữ liệu hoặc thực thi
không mong muốn; Major = không thể hoàn thành task cốt lõi không có hỗ trợ;
Minor = hoàn thành được nhưng có ma sát/lời giải thích thiếu rõ ràng; Cosmetic =
chỉ ảnh hưởng trình bày. Critical/Major phải có remediation và retest cùng
scenario trước khi coi G hoàn tất.

**Tiêu chí hoàn tất đề xuất:** đủ năm người thật, không còn Critical/Major mở,
mọi issue có owner/trạng thái, remediation đã retest nếu phát sinh, và Hermes
review độc lập evidence đã ẩn danh. Nếu không triển khai, cần waiver/defer rõ
ràng của user ghi vào source-of-truth; không thay bằng agent, mock hay UAT tự
động.

Review độc lập đã PASS protocol chuẩn bị này: không scope creep/tự cấp quyền;
ba lớp isolation, consent/retention và success metrics đã đủ để chờ product
owner phê duyệt. Khi phê duyệt thực thi, facilitator phải chốt trước bằng văn
bản các câu “nhắc trung tính” được phép dùng để áp dụng nhất quán.

### Phase 6 — Reconciliation và đề nghị promotion riêng

Chỉ sau khi D PASS, E2 PASS, F1 claim hẹp được reconcile và G-SYNTHETIC PASS:

1. Chạy validation tổng hợp phù hợp và review toàn file untracked trong scope.
2. Đối chiếu không còn orphan, credential leak, product mutation hoặc artifact
   thiếu provenance.
3. Hermes lập checker report độc lập.
4. User cấp authorization riêng nếu muốn cập nhật state/checkpoint.

Kế hoạch này không tự cho phép promotion và không tự thay đổi
`DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

## Khung Package D — Browser UAT

Chỉ thực hiện khi được user cấp quyền và Phase 0-1 đạt Done.

Mục tiêu:

- Kiểm tra scope Work/Conversation trên Sidebar và WorkHub.
- Xác nhận một EventSource trên một Assistant Thread trong một tab.
- Late SSE event sau đổi scope không xuất hiện ở scope mới.
- Persisted timeline không bị xóa khi terminal/error.
- Không phát sinh mutation hoặc approval ngoài ý định.

Ràng buộc:

- Không dùng real provider.
- Không sửa backend/API/migration/provider/credential/checkpoint nếu không có
  scope rõ.
- Dùng workspace, SQLite, browser profile và evidence tạm biệt lập; giữ evidence
  cho review.

## Khung Package E — Bounded real-GYO UAT

E0 là read-only evidence reconciliation. E1/E2 chỉ thực hiện khi user phê duyệt
real provider nếu có phát sinh request mới.

- Kiểm tra real stream, context, source và cancel trong giới hạn đã duyệt.
- `credential_configured=true` hoặc `health_status=ready` chỉ là local
  configuration, không chứng minh upstream healthy.
- Không có real action proposal/package/executor thì báo `NOT RUN`.

## Khung Package F — Fidelity và cancel

Gap ledger và browser current-GYO đã thực hiện sau D PASS. Run authoritative
`package-f-native-20260822-065000` PASS `14/14` ô scoped fidelity.

- Phân biệt terminal `cancelled` với SSE error.
- Không claim process-level compute stop nếu chỉ có client/network cancellation
  evidence.
- Giữ artifact native zoom 200% làm baseline; không dùng emulation để thay thế
  khi rerun evidence bị ảnh hưởng.

## Khung Package G — Synthetic evaluation

Triển khai năm agent độc lập theo Phase 5, sau E2 PASS và trên cùng final source
hash. Đây là synthetic agent evaluation, không thay thế hoặc giả mạo nghiên cứu
người dùng thật.

## Handoff bắt buộc

Mỗi package phải báo:

1. Objective và permission/scope đã dùng.
2. Files thực sự đổi bởi Codex.
3. Commands, exit code, test count và evidence path.
4. Kết quả review độc lập của Hermes.
5. PASS/PARTIAL/FAIL/NOT RUN.
6. Residual risk và package kế tiếp chỉ khi user cho phép.
7. Xác nhận checkpoint vẫn `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.
