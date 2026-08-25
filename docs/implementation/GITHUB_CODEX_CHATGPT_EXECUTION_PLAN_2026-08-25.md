# Kế hoạch vận hành GitHub - Codex Desktop - ChatGPT

> **Trạng thái:** thiết kế vận hành được đề xuất; chưa thay đổi checkpoint sản phẩm,
> chưa thay thế governance hiện hành và chưa tự cấp quyền implementation mới.
>
> **Hiệu lực của tài liệu:** review/merge tài liệu này chỉ phê duyệt thiết kế và
> roadmap. Luồng ChatGPT Web + GitHub connector trở thành đường implementation
> thông thường **chỉ sau khi OP-1 governance reconciliation được review và merge**.
> Trước mốc đó, `AGENTS.md`, canon, state/checkpoint, operating contract, routing và
> workflow governance hiện hành tiếp tục là authority thực thi.
>
> **Nguyên tắc delivery được đề xuất:** mọi write do **ChatGPT Web** hoặc
> **Codex Desktop** thực hiện đều đi qua **feature branch + GitHub Pull Request**.
> Agent direct-push `pqg-workspace` bị cấm. Quyền admin/bypass, nếu connector hoặc
> tài khoản có, **không phải delivery path** và không được dùng để né branch
> protection, PR hoặc canonical CI.
>
> **Định hướng tạm thời:** GitHub là canonical source/PR/merge authority. GitLab và
> GitLab Duo được đề xuất cô lập khỏi coding/merge/acceptance thường ngày; tài liệu
> này không xóa dự án GitLab, không đổi mirror/token/schedule/settings và không biến
> GitLab thành second writer hoặc second acceptance authority.

## 1. Mục tiêu và giới hạn

Mục tiêu là giảm chi phí điều phối và validation không liên quan mà vẫn bảo toàn:

- feature-branch isolation;
- exact-SHA evidence;
- canonical `pqg/smoke`;
- one-writer ownership;
- local Windows/browser proof khi thực sự cần;
- human approval cho merge và protected/risky scope.

Thiết kế đích:

```text
Yêu cầu / task
      |
      +--> ChatGPT Web hoặc Codex Desktop: scoped feature branch
      |          |
      |          +--> Quick PR ---------+
      |          |                      |
      |          +--> Standard PR ------+--> canonical pqg/smoke
      |                                 |
      +--> Codex independent/local proof khi lane yêu cầu
                                        |
                                        v
                              user-reviewed governed merge
                                        |
                                        v
                                  pqg-workspace
```

Không thuộc phạm vi của kế hoạch này:

- agent direct-main hoặc admin/bypass delivery;
- thay đổi `PROJECT_STATE.md`, `AI_STATE.json`, checkpoint, F9 hoặc release state;
- deploy/publish, credential/provider/2FA/visibility, migration hoặc dữ liệu thật;
- cài MCP/memory agent, agent loop, dependency/tool mới hoặc CI mới chỉ vì có nhiều tính năng;
- đổi branch protection/ruleset/Actions settings/GitLab settings;
- thay đổi semantics hiện hành của `pqg/smoke` hoặc mở rộng P-TRACK trong plan PR này.

State gốc vẫn là `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`,
`human_approval_required=true`; F9 vẫn `CLOSED / NOT APPROVED`. Tài liệu hoặc
package completion không tự promote gate.

## 2. Lựa chọn vận hành

| Phương án | Điểm mạnh | Vấn đề với PQG | Quyết định |
| --- | --- | --- | --- |
| PR cho mọi agent write + Quick/Standard lane | Audit rõ, rollback tốt, không cần bypass | Có PR ceremony nhỏ | **Thiết kế chọn** |
| Human owner direct-main micro-doc | Rất nhanh cho thao tác tay | CI trên commit direct-main là hậu kiểm | Chỉ là human exception nếu user tự chọn; không phải agent lane |
| Agent admin/bypass direct-main | Ít bước API | Làm suy yếu branch/CI gate và auditability | **Cấm** |
| Ruleset exception cho direct-main | Có thể actor-specific | Không phân loại semantic risk đáng tin cậy | Không dùng cho fast lane |
| Docs-light PR CI sau này | Giữ PR boundary, có thể giảm nhiều thời gian | Thay CI acceptance semantics | Deferred, approval riêng sau metrics |

Nguyên tắc tối giản: tối ưu bằng **Quick PR + chỉ chạy validation liên quan**, không
đánh đổi branch governance để tiết kiệm vài thao tác.

## 3. Authority, writer ownership và trách nhiệm

| Thành phần | Được làm trong mô hình đích | Không được tự làm | Evidence |
| --- | --- | --- | --- |
| User | Chọn scope, approve protected/risky work, duyệt merge | Không phải chạy lại check agent có thể tự chạy | Approval rõ |
| GitHub | Canonical source, feature branches, PR, Actions, merge history | Không chứng minh Windows chỉ vì CI xanh | URL/run + SHA |
| ChatGPT Web + GitHub connector | Research; scoped feature-branch write sau OP-1; tạo/cập nhật PR khi task cho phép | Direct-push default, admin/bypass delivery, merge, protected-state/credential change | Receipt + ownership + diff/evidence |
| Codex Desktop | Điều phối, implementation trên feature branch, independent verification, Windows/local/browser work | Direct-push default, admin/bypass delivery, merge/deploy/protected change thay user | Local receipt + SHA/process/browser proof |
| GitHub Actions | Agent Preflight, canonical `pqg/smoke`, scoped existing jobs | Human approval/state promotion | Workflow run + validation SHA |
| Codespaces | Fallback Linux khi user yêu cầu | Second simultaneous writer, Windows PASS claim | SHA + Linux-only output |
| GitLab/GitLab Duo | Historical/advisory reference ngoài ordinary path | Code write/merge/approval/acceptance | Exact SHA nếu tham chiếu |

### 3.1 Một branch một writer — optimistic exact-SHA ownership

Không tạo lock service, MCP coordinator hay state database mới. Mỗi writer epoch
được khóa bằng:

- `writer_owner`;
- `ownership_start_sha`;
- `expected_remote_head`.

Quy tắc:

1. Trước **mỗi write**, đọc remote feature-branch HEAD.
2. Nếu HEAD khác `expected_remote_head`, dừng `BLOCKED`; không overwrite, rebase,
   force-push hoặc tự đoán thay đổi của writer khác.
3. Sau commit do chính writer tạo, cập nhật `expected_remote_head` sang commit mới.
4. Chuyển ChatGPT <-> Codex chỉ bằng handoff tại một exact source SHA; writer mới
   phải xác nhận remote HEAD đó trước khi edit.
5. Read-only reviewer có thể làm song song; không được write branch đang có owner khác.
6. `pqg-workspace` không bao giờ là writer branch của ChatGPT/Codex.

Quyền admin/bypass không thay đổi sáu quy tắc trên.

## 4. Lane policy — tối đa ba lane

### 4.1 Direct-main micro change

**Không phải agent lane.**

- ChatGPT Web: `BLOCKED`.
- Codex Desktop: `BLOCKED`.
- Admin/bypass capability: không được dùng làm delivery path.
- Human owner có thể tự thực hiện một manual micro-doc exception nếu user chủ động
  quyết định ngoài agent workflow; exception đó không cấp quyền tương tự cho agent.

### 4.2 Quick PR

Dùng khi thay đổi nhỏ, dễ review, impact hẹp và không chạm trust boundary.

Eligible:

- typo/format/prose trong ordinary documentation;
- localized frontend/backend fix có contract rõ và risk thấp;
- thay đổi một hoặc vài file nhưng vẫn có blast radius hẹp.

Không eligible:

- governance/process/canon/plan/project-memory/state/checkpoint/evidence policy;
- test runner, script, workflow, CI config;
- dependency/lockfile;
- auth/security/provider/network/database/schema/migration;
- local Windows/browser behavior là acceptance target;
- mixed/ambiguous scope hoặc thay đổi public/shared contract đáng kể.

Quick PR không dùng số dòng làm criterion chính. Một diff một dòng chạm runtime hoặc
trust boundary phải escalation sang Standard PR.

Target process sau OP-1:

1. feature branch;
2. one writer;
3. preflight theo governance đang có hiệu lực cho loại change đó;
4. focused validation đúng affected surface;
5. PR có thể mở **ready-for-review ngay**, không bắt buộc draft;
6. canonical `pqg/smoke` theo policy hiện hành;
7. independent Codex review **không bắt buộc mặc định**, trừ khi escalation condition xuất hiện;
8. user merge.

### 4.3 Standard PR

Bắt buộc cho:

- governance/process/canon/plan/project-memory;
- test/script/workflow/CI;
- dependency/lockfile/tool version;
- auth/security/permission/audit/provider/network/database/schema/migration;
- behavior có shared/public contract hoặc blast radius không hẹp;
- Windows/browser/runtime evidence là một phần acceptance;
- bất kỳ task nào Quick PR classifier không thể chứng minh an toàn.

Standard PR yêu cầu preflight, focused fail-closed evidence, canonical
`pqg/smoke`, và independent verification tương xứng với risk. Windows/browser,
real provider hoặc migration chỉ chạy khi task scope/approval thực sự yêu cầu.

## 5. Receipt và Agent Preflight

### 5.1 Receipt trước edit

```markdown
## Receipt — <TASK-ID>

- Target branch: `<feature-branch>`
- Lane: `QUICK_PR | STANDARD_PR`
- Writer owner: `<ChatGPT Web | Codex Desktop>`
- Ownership start SHA: `<sha>`
- Expected remote HEAD: `<sha>`
- Goal / non-goals: …
- Risk / approval boundary: …
- Gate: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 không đổi
- Required sources read: …
- Preflight branch: `<feature-branch>`
- Preflight SHA: `<pre-edit sha>`
- Preflight run: `<URL/ID>`
- Preflight status: `pqg/preflight=success | NOT REQUIRED | BLOCKED`
- Planned files: …
- Validation plan: …
```

### 5.2 Preflight SHA không phải acceptance SHA

Agent Preflight là **pre-edit execution prerequisite** theo governance đang có hiệu
lực. Preflight receipt không được relabel thành final PR acceptance.

Trong một writer epoch, receipt có thể tiếp tục áp dụng cho descendant do cùng
writer tạo khi branch/ancestry/scope/approval boundary không đổi và không có foreign
write/rebase/reset/force move. Writer transfer có tracked edit hoặc contract liên
quan thay đổi thì lấy fresh preflight trước edit.

`pqg/smoke` là acceptance evidence riêng; preflight PASS không thay canonical CI.

### 5.3 Future safe-prose exemption — chưa có hiệu lực

Sau OP-1, repository **có thể** cho phép ordinary prose-only docs bỏ Agent Preflight
nếu governance định nghĩa explicit safe allowlist. Exemption tương lai này:

- không tự có hiệu lực vì plan được merge;
- không bao gồm `AGENTS.md`, canon, operating contract, routing, `docs/15...`;
- không bao gồm implementation plan, project memory, evidence ledger, state/checkpoint;
- không bao gồm source/test/script/workflow/config/dependency;
- unknown/mixed scope phải fail closed sang preflight-required.

## 6. Chuỗi thực thi chuẩn sau activation gate

### A. ChatGPT Web + GitHub connector

1. Nhận TASK-ID, lane, feature branch, acceptance, non-goals và approval boundary.
2. Đọc required state/checkpoint/routing/contract và focused source/tests.
3. Xác nhận branch **không phải `pqg-workspace`** và khóa writer ownership bằng
   exact remote HEAD.
4. Đạt Agent Preflight nếu governance hiện hành yêu cầu.
5. Sửa smallest coherent scope; thêm regression test khi behavior đổi.
6. Commit/push feature branch theo one-writer protocol.
7. Quick PR có thể mở ready-for-review ngay; Standard PR có thể dùng draft khi
   implementation/evidence chưa hoàn tất.
8. Chờ canonical Actions. Không dùng admin/bypass để đưa commit vào default branch.
9. Handoff với source SHA và actual validation SHA theo mục 7/8.
10. Không merge.

### B. Codex Desktop

1. Nếu chỉ coordinate/read diff/SHA/Actions hoặc verify mà không edit tracked files,
   không rerun local preflight chỉ để lặp remote evidence.
2. Nếu Codex chuẩn bị edit, tiếp quản writer tại exact feature-branch SHA và chạy
   preflight theo governance đang có hiệu lực.
3. Đối chiếu source head, actual validation SHA, workflow event/run và diff scope.
4. Chỉ chạy local khi Windows/browser/path/process/runtime acceptance cần nó hoặc
   GitHub evidence không đủ.
5. Trước local/browser PASS phải chứng minh checkout/process/port thuộc exact source
   revision được test; tooling chưa tự động bảo đảm toàn bộ provenance này.
6. Real-provider/network/credential smoke luôn cần approval riêng.
7. Báo riêng `PASS`, `FAIL`, `PARTIAL`, `NOT RUN`, `NOT REQUIRED`, `BLOCKED` theo scope.

### C. Review và merge

1. Mọi agent-authored change đi vào `pqg-workspace` qua PR.
2. Required `pqg/smoke` và check bắt buộc phải thuộc actual validation SHA/merge shape
   mà GitHub workflow/governance hiện hành dùng.
3. User quyết định merge; plan không cấp auto-merge hoặc admin bypass.
4. Sau merge, default-branch `pqg/smoke` nếu được workflow tạo là post-merge exact-SHA
   evidence riêng, không làm thay đổi claim của PR validation run.
5. Không update state/checkpoint/F9 nếu package promotion chưa được phê duyệt riêng.

## 7. Exact-SHA evidence cho Pull Request

### 7.1 Không đồng nhất source head và validation SHA

Với GitHub `pull_request`, workflow có thể chạy trên test-merge/synthetic merge commit.
Do đó không dùng một field chung `PR head SHA` để mô tả mọi CI evidence.

Receipt/handoff bắt buộc tách:

- `source_head_sha`: exact commit ở feature branch do writer tạo;
- `validation_sha`: exact SHA mà workflow run thực sự checkout/validate/publish status;
- `validation_event`: ví dụ `pull_request`, `push`, `workflow_dispatch`;
- `workflow_run_id` hoặc URL;
- `environment`;
- `scope`.

Canonical evidence key:

`source_head_sha + validation_sha + workflow_run + event + environment + scope`.

Không được nói `pqg/smoke` PASS trên source head nếu status/run thực tế thuộc synthetic
merge SHA. Khi source head đổi, validation receipt cũ không tự chuyển sang source mới.

### 7.2 Evidence reuse

| Trường hợp | Reuse | Quy tắc |
| --- | --- | --- |
| PR comment/body đổi, source head không đổi | Có | Đọc lại same validation relationship/status; không rerun chỉ vì metadata |
| Source head đổi | Không cho canonical acceptance | Chờ new PR validation run |
| Cùng writer epoch sau preflight | Chỉ reuse pre-code receipt | Không relabel preflight thành acceptance |
| Writer transfer sẽ có edit | Không | Fresh preflight theo contract |
| Rebase/reset/foreign write | Không | BLOCKED rồi reconcile |
| Windows/browser-relevant source đổi | Không | Rerun scoped local proof |
| Docs-only change không liên quan local scenario | Old local evidence không relabel | `NOT REQUIRED` hoặc `NOT RUN` |

## 8. Handoff ChatGPT -> Codex

```markdown
## Handoff — <TASK-ID>

- Lane: `QUICK_PR | STANDARD_PR`
- Writer owner / next writer: …
- Branch / PR: …
- Ownership start SHA: …
- Preflight branch / SHA / run / status: …
- Base SHA -> source_head_sha: … -> …
- validation_sha / validation_event / workflow_run_id: …
- Changed files / reason: …
- Focused evidence: …
- Canonical `pqg/smoke` evidence: …
- NOT RUN / NOT REQUIRED / BLOCKED: …
- Local Windows/browser evidence required: …
- Known residuals: …
- Protected scopes unchanged: state/checkpoint/F9/credential/migration/deploy/etc.
```

`READY_FOR_USER_REVIEW` chỉ nghĩa là scope/evidence cần thiết đã được verifier đối
chiếu; không có nghĩa user đã approve merge.

## 9. P-TRACK và CI tối giản

### 9.1 P-TRACK giữ nguyên

CI hiện có bounded tracking-equivalence trên default-branch tracking-only commits.
Plan này **không mở rộng P-TRACK sang Pull Request, Quick PR hoặc runtime code**.

Khi classifier hiện hành cho phép tracking path:

- tracking child có receipt riêng trên exact child SHA;
- full runtime vẫn chỉ được claim cho full-validation anchor;
- không nói runtime tests chạy trên tracking child nếu chúng không chạy;
- PR/unknown/non-eligible tiếp tục theo workflow hiện hành.

### 9.2 Những validation có thể giảm sau OP-1

Mục tiêu là cắt duplicate/unrelated work, không tạo false PASS:

- ordinary safe prose docs: future preflight exemption có thể được cân nhắc sau OP-1;
- connector-only task: không giả lập local `git diff --check`; dùng exact GitHub diff
  và check mà CI thực sự chạy, ghi local command `NOT RUN`;
- Quick PR: independent Codex review không required mặc định;
- non-UI/non-Windows change: local Windows/browser proof `NOT REQUIRED`;
- code dù chỉ một dòng: focused tests + canonical `pqg/smoke` vẫn required theo
  policy hiện hành.

### 9.3 Docs-light PR CI — deferred, approval riêng

Không sửa CI semantics trong plan PR này. Chỉ mở lại sau khi đo ít nhất 20 runs và
chứng minh ordinary docs PR đang gây waste đáng kể.

Nếu được phê duyệt riêng về sau:

- dùng classifier riêng, fail-closed;
- explicit named safe-prose allowlist, không broad `docs/**`;
- unknown/mixed/add/delete/rename phải full;
- không dùng top-level `paths-ignore` làm biến mất required `pqg/smoke`;
- vẫn publish canonical `pqg/smoke` trên actual validation SHA;
- không sửa P-TRACK để gánh semantics mới.

Bất kỳ docs-light mode nào cũng là **CI acceptance semantics change** và cần user
approval riêng.

## 10. Phased roadmap — smallest sufficient process

Plan PR này **không thực hiện** bất kỳ OP nào dưới đây.

| Thứ tự | ID | Scope chính xác | Owner | Validation | Rollback / condition |
| ---: | --- | --- | --- | --- | --- |
| 1 | OP-1 | Reconcile `AGENTS.md`, role wording cần thiết trong canon, `docs/14_AGENT_OPERATING_CONTRACT.md`, `docs/AI_AGENT_ROUTING.md`, `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md`: agent PR-only, Quick/Standard lane, evidence source-vs-validation SHA | ChatGPT draft; Codex independent review | Docs consistency + preflight + canonical policy hiện hành | Revert docs PR; **activation gate** |
| 2 | OP-4 | Reconcile `PROJECT_CONTEXT.md`, `PROJECT_MEMORY.md` và append correction vào `PROJECT_CHANGELOG.md`; không rewrite lịch sử | ChatGPT/Codex | Timestamp/provenance review | Revert snapshot/correction |
| 3 | OP-2 | Rà `run-codex.ps1`, `run-codex.sh`, `agent-loop.sh`; deprecate autonomous/stale paths, không dùng AI_STATE lock như branch lock | ChatGPT patch; Codex local verify | Static/shell/PowerShell contract + local safety check | Revert PR; approval riêng nếu launcher semantics đổi |
| 4 | OP-5 | Harden local provenance: exact checkout SHA, PID/command line/root/port, isolated/mock default | Codex Desktop chủ trì | Windows exact-SHA local proof | Revert script PR; real provider vẫn approval riêng |
| 5 | OP-3 | Chạy 3 task operating pilot bằng receipt -> feature branch -> Quick/Standard PR -> handoff | ChatGPT + Codex | Lead time, omissions, duplicate validation, blockers | Quay lại Codex-led execution nếu process không ổn |
| 6 | OP-6 | Measurement CI >=20 runs; docs-light PR hoặc same-PR concurrency chỉ khi ROI rõ | ChatGPT + Codex review | p50/p95, superseded-run rate, regressions | Revert CI PR; không đổi `pqg/smoke` nếu chưa approval semantics |

OP-1 là governance activation gate. Không suy diễn việc plan được merge là OP-1 đã xong.

## 11. Tooling — quyết định tối giản

| Tool/ý tưởng | Quyết định | Điều kiện xem lại |
| --- | --- | --- |
| `CODEGRAPH.md` | Giữ | Update khi entry point/boundary thực sự đổi |
| Serena | Deferred | Chỉ pilot read-only nếu có navigation bottleneck đo được |
| ast-grep | Deferred | Chỉ khi recurring AST task rõ |
| Headroom | Giữ docs-only | Không compression proxy mặc định |
| Ponytail/CodeGraph AI | Không mặc định | Chưa có ROI vượt static docs/search |
| codebase-memory-mcp/agentmemory | Không | Tránh competing persistent memory/retention surface |
| Agent Reach/TimesFM | Không | Không liên quan coding bottleneck |
| Lore/GitHub Skills | Selective only | Pin source/commit, license/security review |
| Refactor agent | Dùng capability hiện có | Vẫn qua feature branch/test/PR |
| Codespaces | Fallback theo yêu cầu | Một writer, exact SHA, Linux-only evidence |

Không tool bổ sung nào là prerequisite để mô hình PR-only hoạt động.

## 12. Metrics và decision points

### Pilot đầu tiên — 3 task

Ghi cho từng task:

- receipt -> PR validation lead time;
- Quick vs Standard classification accuracy/escalation;
- remote-HEAD mismatch/writer handoff;
- validation bị lặp không cần thiết;
- finding sau independent/local verification;
- source_head_sha vs validation_sha provenance errors;
- blocker do connector/local environment.

Nếu có bypass, writer race hoặc evidence relabeling, dừng mở rộng và sửa process trước.

### Sau đó — 4 tuần hoặc 10 PR

Theo dõi:

- source head -> canonical `pqg/smoke` lead time;
- rerun count/reason;
- `pqg/smoke` p50/p95;
- tỷ lệ Quick PR phải escalation;
- local verification effort khi thực sự cần;
- finding escape rate;
- proportion ordinary docs PR để quyết định có đáng tạo docs-light CI hay không.

Giữ mô hình chỉ khi gate không yếu đi và coordination cost giảm hoặc ổn định.

## 13. Prompt giao việc chuẩn sau OP-1

```text
Bạn là ChatGPT Web executor cho PQG Workspace. GitHub là canonical authority.
Mọi agent write phải đi qua feature branch + PR. Không direct-push pqg-workspace
và không dùng admin/bypass như delivery path.

TASK-ID: <id>
Lane: <QUICK_PR | STANDARD_PR>
Target feature branch: <branch>
Writer owner: ChatGPT Web + GitHub connector
Expected remote HEAD: <sha>
Goal: <goal>
Non-goals: <non-goals>
Acceptance: <verifiable criteria>

Trước mỗi write, đọc remote feature-branch HEAD; mismatch => BLOCKED, không
overwrite/rebase/force. Trước edit, trả Receipt và đạt Agent Preflight nếu governance
hiện hành yêu cầu cho lane/scope đó. Sửa smallest scope; không merge.

Handoff phải tách source_head_sha với validation_sha, ghi validation_event và
workflow_run_id; không relabel synthetic PR merge SHA thành source head evidence.
Ghi rõ NOT RUN/NOT REQUIRED/BLOCKED và local Windows/browser proof còn cần.
Không đổi state/checkpoint/F9, credential/provider, migration, deploy hoặc settings
nếu task không có approval riêng.
```

Prompt này chỉ trở thành normal remote-write launch prompt sau OP-1. Trước đó dùng
repository governance hiện hành.

## 14. Acceptance của chính kế hoạch

Kế hoạch này được xem là **design-approved** khi PR tài liệu được review/merge qua
GitHub. Điều đó **không tự động thay thế** `AGENTS.md`, canon, operating contract,
routing hoặc `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md`.

Mô hình được xem là **operationally activated** chỉ khi:

1. OP-1 governance reconciliation đã review/merge;
2. ChatGPT/Codex agent write dùng feature branch + PR, không direct-main/admin-bypass;
3. Quick PR/Standard PR classifier được áp dụng fail-closed;
4. task có receipt/preflight theo governance active;
5. one-writer ownership khóa bằng expected remote HEAD;
6. handoff tách `source_head_sha` khỏi `validation_sha` và ghi event/run;
7. canonical `pqg/smoke` thuộc actual validation SHA theo workflow policy;
8. Windows/browser evidence chỉ claim khi thực sự chạy trên đúng source/env.

Không điều kiện nào ở đây promote product gate/checkpoint, mở F9 hoặc cấp approval
cho provider/credential/migration/deploy. Nếu governance hiện hành xung đột với plan
trước khi OP-1 hoàn tất, governance hiện hành thắng và discrepancy được đưa vào OP-1.
