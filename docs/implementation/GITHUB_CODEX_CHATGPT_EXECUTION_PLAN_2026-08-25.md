# Kế hoạch vận hành GitHub - Codex Desktop - ChatGPT

> **Trạng thái:** thiết kế vận hành được đề xuất; chưa thay đổi checkpoint sản phẩm,
> chưa thay thế governance hiện hành và chưa tự cấp quyền implementation mới.
>
> **Hiệu lực của tài liệu:** việc review/merge tài liệu này chỉ phê duyệt thiết kế
> và roadmap. Luồng ChatGPT Web + GitHub connector trở thành đường write/implementation
> thông thường **chỉ sau khi OP-1 governance reconciliation được review và merge**.
> Trước mốc đó, `AGENTS.md`, canon, state/checkpoint, operating contract, routing và
> workflow governance hiện hành tiếp tục là authority thực thi.
>
> **Định hướng tạm thời:** GitHub là canonical source/PR/merge authority. GitLab và
> GitLab Duo được đề xuất cô lập khỏi coding/merge/acceptance thường ngày; tài liệu
> này không xóa dự án GitLab, không đổi mirror/token/schedule/settings và không biến
> GitLab thành second writer hoặc second acceptance authority.

## 1. Mục tiêu và giới hạn

Mục tiêu là giảm chi phí điều phối khi hạn mức Codex Desktop hạn chế nhưng vẫn
bảo toàn exact-SHA evidence, branch ownership, local Windows proof và human
approval. Thiết kế đích là:

```text
Yêu cầu / task
      |
      +--> ChatGPT Web + GitHub connector: research / implementation nặng
      |          |                         trên scoped feature branch
      |          v
      +--> GitHub Actions: Agent Preflight trước edit + canonical CI trên source SHA
      |          |
      |          v
      +--> Codex Desktop: coordinator/verifier + Windows/local/browser proof khi cần
      |          |
      |          v
      +--> GitHub PR: independent review + user approval + governed merge
```

Không thuộc phạm vi của kế hoạch này:

- thay đổi `PROJECT_STATE.md`, `AI_STATE.json`, checkpoint, F9 hoặc release state;
- deploy/publish, credential/provider/2FA/visibility, migration hoặc dữ liệu thật;
- coi ChatGPT, Codex Cloud, Codespaces, GitLab hoặc scanner là authority thay cho
  repository contract, deterministic test, exact-SHA evidence và user approval;
- cài MCP/memory agent, agent loop tự động, dependency/tool mới hoặc CI mới chỉ vì
  có nhiều tính năng;
- thay đổi GitLab/GitHub settings chỉ để chứng minh mô hình này được áp dụng.

State gốc vẫn là `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`,
`human_approval_required=true`; F9 vẫn `CLOSED / NOT APPROVED`. Tài liệu hoặc
package completion không tự promote gate.

## 2. Lựa chọn vận hành

| Phương án | Điểm mạnh | Vấn đề với PQG hiện tại | Quyết định |
| --- | --- | --- | --- |
| Codex Desktop đơn lẻ | Windows, terminal, browser | Hạn mức không phù hợp cho mọi phân tích/code nặng | Coordinator + local verifier |
| ChatGPT Web + GitHub connector đơn lẻ | Repo-scale analysis, GitHub diff/PR | Không chứng minh Windows/local runtime | Remote executor sau activation gate |
| GitHub-only Minimal Plus | Một source/merge authority, exact-SHA Actions | Cần governance reconciliation và handoff chặt | **Thiết kế chọn** |
| GitHub + GitLab song song | Thêm scanner/board | Mirror lag/SHA drift/điều phối dư | GitLab advisory quarantine |
| Codespaces mặc định | Linux shell tái lập | Không thay Windows proof; chưa có ROI/prebuild case | Fallback theo yêu cầu |
| MCP/memory/agent loop mới | Tự động hóa thêm | Trùng authority/memory, khó audit | Không đưa vào mặc định |

Nguyên tắc tối giản: dùng repository docs + GitHub + Actions + Codex Desktop trước;
chỉ thêm tool/process khi có bottleneck đo được, owner, rollback và acceptance test.

## 3. Authority, writer ownership và trách nhiệm

| Thành phần | Được làm trong mô hình đích | Không được tự làm | Evidence |
| --- | --- | --- | --- |
| User | Chọn scope, approve protected/risky work, duyệt merge | Không phải chạy lại check agent có thể tự chạy | Approval rõ |
| GitHub | Canonical source, branch, PR, Actions, merge history | Không chứng minh Windows chỉ vì CI xanh | URL/run + SHA |
| ChatGPT Web + GitHub connector | Research; scoped branch write sau OP-1; draft PR/handoff khi được phép | Direct-push default, merge, protected-state/credential changes | Receipt + ownership SHA + diff/evidence |
| Codex Desktop | Điều phối, independent verification, Windows/local/browser work | Merge/deploy/protected change thay user | Local receipt + SHA/process/browser proof |
| GitHub Actions | Agent Preflight, canonical `pqg/smoke`, scoped existing jobs | Human approval/state promotion | Workflow run + exact SHA |
| Codespaces | Fallback Linux khi user yêu cầu | Second simultaneous writer, Windows PASS claim | SHA + Linux-only output |
| GitLab/GitLab Duo | Historical/advisory reference ngoài ordinary path | Code write/merge/approval/acceptance | Exact SHA nếu tham chiếu |

### 3.1 Một branch một writer — optimistic exact-SHA ownership

Không tạo lock service, MCP coordinator hay state database mới. Mỗi writer epoch
được khóa bằng ba giá trị:

- `writer_owner`;
- `ownership_start_sha`;
- `expected_remote_head`.

Quy tắc:

1. Trước **mỗi write**, đọc remote branch HEAD.
2. Nếu HEAD khác `expected_remote_head`, dừng `BLOCKED`; không overwrite, rebase,
   force-push hay tự đoán thay đổi của writer khác.
3. Sau commit do chính writer tạo, cập nhật `expected_remote_head` sang commit mới.
4. Chuyển ChatGPT <-> Codex chỉ bằng handoff tại một exact SHA; writer mới phải
   xác nhận remote HEAD đó trước khi edit.
5. Read-only reviewer có thể làm việc song song; không được write branch đang có owner khác.

Đây là concurrency guard tối thiểu; không biến Project Memory hoặc Issue text thành lock.

## 4. Phân loại tác vụ và đường đi tối thiểu

| Loại task | Owner mặc định sau activation | Branch/PR | Validation tối thiểu |
| --- | --- | --- | --- |
| Read-only audit/research | ChatGPT | Không cần branch | Ref/SHA/source/evidence |
| Docs thuần | ChatGPT hoặc Codex | Branch + PR nếu merge | Preflight theo contract, exact diff, canonical policy hiện hành |
| Backend/frontend behavior | ChatGPT remote executor | Feature branch + draft PR | Preflight, focused regression, affected type/lint/build, canonical CI |
| Windows/runtime/browser | Codex Desktop | Cùng governed branch, một writer | Exact checkout/process/SHA + relevant local/browser proof |
| Security/auth/data/migration/provider | Chỉ sau explicit approval | PR riêng | Task canon/security + fail-closed evidence |
| Multi-PR/blocker/dependency | Issue khi thực sự cần | Milestones nhỏ | Cross-link + exact receipt cho từng PR |

Không tạo Issue/template cho task nhỏ chỉ để tuân thủ hình thức.

## 5. Receipt và semantics của Agent Preflight

### 5.1 Receipt trước edit

```markdown
## Receipt — <TASK-ID>

- Target branch: `<branch>`
- Writer owner: `<ChatGPT Web | Codex Desktop>`
- Ownership start SHA: `<sha>`
- Expected remote HEAD: `<sha>`
- Goal / non-goals: …
- Risk / approval boundary: …
- Gate: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 không đổi
- Required sources read: …
- Preflight branch: `<branch>`
- Preflight SHA: `<pre-edit sha>`
- Preflight run: `<URL/ID>`
- Preflight status: `pqg/preflight=success | BLOCKED`
- Planned files: …
- Validation plan: …
```

### 5.2 Preflight SHA không phải final implementation SHA

Agent Preflight là **pre-edit execution prerequisite**. Nếu trigger-file bootstrap
được dùng, run/status gắn với bootstrap/pre-edit SHA. Không được trình bày receipt
này như thể preflight đã chạy trên final PR HEAD.

Trong một writer epoch, preflight pre-edit có thể tiếp tục làm receipt cho các
commit descendant do **cùng writer** tạo khi đồng thời thỏa:

- branch không đổi và ancestry vẫn là fast-forward descendant của preflight SHA;
- remote HEAD trước mỗi write khớp expected head;
- không có writer transfer, rebase/reset/force move hoặc foreign commit;
- preflight/governance contract liên quan không thay đổi trong epoch;
- task scope/approval boundary không mở rộng.

Phải lấy fresh preflight trước edit tiếp theo nếu một trong các điều kiện trên mất,
hoặc writer mới tiếp quản và sẽ sửa tracked code/test/schema/config.

`pqg/smoke` trên final source SHA là acceptance evidence riêng; nó không thay
preflight. Ngược lại preflight PASS không thay canonical CI.

### 5.3 Connector execution path

- Có `workflow_dispatch`: chạy Agent Preflight trên exact target ref.
- Không dispatch nhưng có branch write: trigger `.github/agent-preflight-trigger.txt`
  theo contract; trigger commit chỉ mở preflight path.
- Không có cả hai: `BLOCKED`, yêu cầu user/Codex điều phối run; không giả lập local PowerShell.

## 6. Chuỗi thực thi chuẩn sau activation gate

### A. ChatGPT Web + GitHub connector

1. Nhận TASK-ID, target branch, acceptance, non-goals và approval boundary.
2. Đọc required state/checkpoint/routing/contract và focused source/tests.
3. Xác nhận writer ownership bằng exact remote HEAD.
4. Đạt fresh Agent Preflight theo mục 5 trước implementation edit.
5. Sửa smallest coherent scope; thêm regression test khi behavior đổi.
6. Commit/push feature branch theo one-writer protocol; không direct-push default.
7. Mở/cập nhật draft PR khi task cần PR; không merge.
8. Chờ canonical Actions trên final head; medium/high-risk task nhận **Codex Desktop
   independent review** khi acceptance yêu cầu. Automated/Cloud review nếu có chỉ là
   advisory và không thành merge authority.
9. Handoff theo mục 8. Windows/local/browser evidence chưa chạy phải ghi `NOT RUN`
   hoặc `PENDING_CODEX_LOCAL_VERIFICATION`.

### B. Codex Desktop

1. Nếu chỉ coordinate/read diff/SHA/Actions hoặc chạy verification không sửa tracked
   files, **không rerun local preflight chỉ để lặp lại remote preflight**.
2. Nếu Codex chuẩn bị sửa tracked code/test/schema/config, tiếp quản writer tại exact
   SHA và chạy fresh local `scripts/agent-preflight.ps1` trước edit.
3. Đối chiếu `preflight_sha`, final PR head, Actions run và diff scope; không dùng
   smoke từ branch/parent khác làm exact-head evidence.
4. Chỉ chạy local khi Windows/browser/path/process/runtime acceptance cần nó hoặc
   GitHub evidence không đủ. Trước browser PASS phải chứng minh checkout/process/port
   thuộc exact source SHA; tooling hiện chưa tự động bảo đảm toàn bộ provenance này.
5. Real-provider/network/credential smoke luôn cần approval riêng; local smoke không
   được mặc định suy ra là mock/isolated nếu chưa chứng minh.
6. Báo riêng `PASS`, `FAIL`, `PARTIAL`, `NOT RUN`, `BLOCKED` theo từng evidence scope.

### C. Review và merge

1. PR đi vào `pqg-workspace` theo governance hiện hành tại thời điểm merge.
2. Required `pqg/smoke` và các check bắt buộc khác phải thuộc exact head/merge shape
   mà governance yêu cầu.
3. Merge chỉ sau user approval; không dùng plan này để tự bật auto-merge.
4. Sau merge chỉ chạy local verification nếu acceptance yêu cầu; không update
   state/checkpoint/F9 nếu package promotion chưa được phê duyệt riêng.

## 7. Evidence reuse và CI tối giản

Một evidence receipt tối thiểu có bốn khóa:

`commit SHA + workflow/run + environment + scope`.

| Trường hợp | Reuse | Quy tắc |
| --- | --- | --- |
| PR comment/body đổi, head SHA không đổi | Có | Đọc lại exact-SHA status; không rerun chỉ vì metadata |
| Final code HEAD đổi | Không cho canonical acceptance | New final-head CI |
| Cùng writer epoch sau preflight | Chỉ reuse pre-code receipt | Giữ `preflight_sha` riêng, không relabel thành final-head run |
| Writer transfer sẽ có edit | Không | Fresh preflight cho writer mới |
| Rebase/reset/foreign write | Không | BLOCKED rồi fresh receipt sau reconciliation |
| Windows/browser source thay đổi liên quan | Không | Rerun scoped local proof |
| Docs-only change không ảnh hưởng local scenario | Old local evidence không được relabel | Ghi `NOT REQUIRED`/`NOT RUN` cho child |

### 7.1 P-TRACK là ngoại lệ hẹp, không phải evidence inheritance

CI hiện có bounded tracking-equivalence trên default-branch tracking-only commits.
Khi classifier hiện hành cho phép tracking path:

- tracking child phải có **receipt riêng trên exact child SHA** gồm
  `pqg/tracking-integrity` và canonical `pqg/smoke`;
- full runtime execution vẫn chỉ được claim cho full-validation anchor;
- không nói runtime tests đã chạy trên tracking child nếu chúng không chạy;
- pull request và unknown/non-eligible classification tiếp tục đi full path theo
  workflow hiện hành.

Không sửa hoặc mở rộng P-TRACK trong plan PR này.

### 7.2 Roadmap CI sau này

Current workflow đã có classifier full/tracking và npm/pip cache. Vì vậy **không**
đưa generic `governance/backend/frontend/full` classifier hoặc cache layer mới vào
near-term roadmap.

Thứ tự nếu cần tối ưu:

1. Đo duration/job breakdown của ít nhất 20 `pqg/smoke` runs đại diện.
2. Ghi tỷ lệ run bị superseded do push mới trên cùng PR.
3. Chỉ khi dữ liệu cho thấy waste đáng kể, thử PR riêng thêm concurrency cancellation
   cho **cùng PR**.
4. Không cancel default-branch push.
5. Không dùng top-level `paths-ignore` làm biến mất required `pqg/smoke`.
6. Generic classifier/cache optimization chỉ được mở lại bằng scope/approval riêng sau
   ROI + threat model + tests; unknown phải fail-closed sang full.

## 8. Handoff ChatGPT -> Codex

```markdown
## Handoff — <TASK-ID>

- Writer owner / next writer: …
- Branch / PR: …
- Ownership start SHA: …
- Preflight branch / SHA / run / status: …
- Base SHA -> implementation head SHA: … -> …
- Changed files / reason: …
- Focused evidence: …
- Canonical CI run / exact head status: …
- NOT RUN / BLOCKED: …
- Local Windows/browser evidence required: …
- Known residuals: …
- Protected scopes unchanged: state/checkpoint/F9/credential/migration/deploy/etc.
```

`READY_FOR_USER_REVIEW` chỉ có nghĩa là Codex đã đối chiếu scope/evidence cần thiết;
nó không có nghĩa user đã approve merge.

## 9. Phased roadmap — smallest sufficient process

Plan PR này **không thực hiện** bất kỳ OP nào dưới đây.

| Thứ tự | ID | Scope chính xác | Owner | Validation | Rollback / condition |
| ---: | --- | --- | --- | --- | --- |
| 1 | OP-1 | Reconcile tối thiểu `AGENTS.md`, role wording cần thiết trong canon, `docs/14_AGENT_OPERATING_CONTRACT.md`, `docs/AI_AGENT_ROUTING.md`, `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md` để không còn hai operating models | ChatGPT draft; Codex independent review | Docs consistency + exact-ref preflight + canonical policy hiện hành | Revert docs PR; **activation gate** cho remote write |
| 2 | OP-4 | Reconcile `PROJECT_CONTEXT.md`, `PROJECT_MEMORY.md` và append correction vào `PROJECT_CHANGELOG.md`; không rewrite lịch sử | ChatGPT/Codex | Timestamp/provenance review | Revert snapshot/correction; bắt đầu sau OP-1 wording ổn định |
| 3 | OP-2 | Rà `run-codex.ps1`, `run-codex.sh`, `agent-loop.sh`; deprecate autonomous/stale paths, không duy trì agent loop và không dùng AI_STATE lock như branch lock | ChatGPT patch; Codex local verify | Static/shell/PowerShell contract + local safety check | Revert PR; approval riêng nếu launcher semantics đổi |
| 4 | OP-5 | Harden local provenance: exact checkout SHA, PID/command line/root/port, isolated/mock default; real provider vẫn approval riêng | Codex Desktop chủ trì | Windows exact-SHA local proof | Revert script PR; không mở provider scope |
| 5 | OP-3 | Chạy 3 task operating pilot bằng receipt -> preflight -> one writer -> PR/handoff; **chưa thêm template/tool mặc định** | ChatGPT + Codex | Lead time, omissions, duplicate validation, blockers | Quay lại Codex-led execution nếu process không ổn |
| 6 | OP-6 | Chỉ measurement CI >=20 runs; optional same-PR concurrency nếu ROI rõ. Generic classifier/cache vẫn deferred | ChatGPT + Codex review | p50/p95, superseded-run rate, P-TRACK regressions | Revert concurrency PR; không đổi canonical `pqg/smoke` semantics |

OP-1 là governance activation gate. Không suy diễn việc plan được merge là OP-1 đã xong.

## 10. Tooling — quyết định tối giản

| Tool/ý tưởng | Quyết định | Điều kiện xem lại |
| --- | --- | --- |
| `CODEGRAPH.md` | Giữ | Update khi entry point/boundary thực sự đổi |
| Serena | Deferred | Chỉ pilot read-only nếu sau operating pilot có navigation bottleneck đo được; không persistent memory/write |
| ast-grep | Deferred | Chỉ khi có recurring AST task rõ và không trùng tool hiện có |
| Headroom | Giữ docs-only | Không thêm compression proxy mặc định |
| Ponytail | Không mặc định | Planning/receipt hiện đủ |
| CodeGraph AI | Không mặc định | Chưa có ROI vượt static CODEGRAPH/search |
| codebase-memory-mcp | Không | Không cần persistent competing memory; upstream claim chưa xác minh không dùng làm sole reason |
| agentmemory | Không | Tránh auto-capture prompt/tool retention surface |
| Agent Reach | Không | External scraping/login không phải coding bottleneck hiện tại |
| Lore/GitHub Skills | Selective only | Pin exact source/commit, license/security review, task-specific acceptance |
| TimesFM | Không | Không liên quan coding workflow |
| Refactor agent | Dùng capability hiện có | Refactor vẫn qua branch/test/PR, không agent loop |
| Codespaces | Fallback theo yêu cầu | Một writer, exact SHA, Linux-only evidence; không thay Windows proof |

Không có tool bổ sung nào là prerequisite để mô hình này hoạt động.

## 11. Chỉ số và decision points

### Pilot đầu tiên — 3 task

Ghi cho từng task:

- receipt -> preflight lead time;
- số remote-HEAD mismatch/writer handoff;
- số lần validation bị lặp không cần thiết;
- finding sau independent/local verification;
- blocker do connector/local environment.

Nếu có bypass, writer race hoặc evidence relabeling, dừng mở rộng và sửa process trước.

### Sau đó — 4 tuần hoặc 10 PR

Theo dõi:

- receipt -> canonical `pqg/smoke` lead time;
- rerun count và reason;
- `pqg/smoke` p50/p95;
- local verification effort khi thực sự cần;
- finding escape rate;
- Codespaces usage/cost nếu có.

Giữ mô hình chỉ khi không hạ gate và coordination cost giảm hoặc ổn định.

## 12. Prompt giao việc chuẩn sau OP-1

```text
Bạn là ChatGPT Web executor cho PQG Workspace. GitHub là canonical authority.
TASK-ID: <id>
Target branch: <branch>
Writer owner: ChatGPT Web + GitHub connector
Expected remote HEAD: <sha>
Goal: <goal>
Non-goals: <non-goals>
Acceptance: <verifiable criteria>

Trước mỗi write, đọc remote HEAD; mismatch => BLOCKED, không overwrite/rebase/force.
Trước implementation edit, trả Receipt theo plan và đạt Agent Preflight trên exact
pre-edit ref. Ghi riêng preflight SHA/run và final implementation HEAD; không relabel
preflight thành final-head acceptance. Sửa smallest scope; draft PR, không merge.
Không đổi state/checkpoint/F9, credential/provider, migration, deploy hoặc external
settings nếu task không có approval riêng.

Handoff phải có writer/next writer, ownership SHA, preflight SHA/run/status, final
head SHA, changed files, focused evidence, canonical CI, NOT RUN/BLOCKED và local
Windows/browser proof còn cần.
```

Prompt này chỉ trở thành normal remote-write launch prompt sau OP-1. Trước đó dùng
repository governance hiện hành.

## 13. Acceptance của chính kế hoạch

Kế hoạch này được xem là **design-approved** khi PR tài liệu được review/merge qua
GitHub. Điều đó **không tự động thay thế** `AGENTS.md`, canon, operating contract,
routing hoặc `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md`.

Mô hình remote-write được xem là **operationally activated** chỉ khi:

1. OP-1 governance reconciliation đã review/merge;
2. task đầu tiên sau activation có receipt trước edit;
3. Agent Preflight có exact pre-edit branch/SHA/run/status;
4. one-writer ownership được khóa bằng expected remote HEAD;
5. handoff tách preflight SHA khỏi final implementation SHA;
6. canonical CI thuộc exact source SHA theo policy hiện hành;
7. Windows/browser evidence chỉ được claim khi thực sự chạy trên đúng source/env.

Không có điều kiện nào ở đây promote product gate/checkpoint, mở F9 hoặc cấp approval
cho provider/credential/migration/deploy. Nếu governance hiện hành xung đột với plan
trước khi OP-1 hoàn tất, governance hiện hành thắng và discrepancy được đưa vào OP-1.
