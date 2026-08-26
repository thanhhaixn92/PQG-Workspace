# Current Checkpoint

Last updated: 2026-08-26

## Coding Operations Stabilization — separate operations gate

This operations gate does not promote or replace the product checkpoint below.

- Coordination plan: [GitHub Issue #13](https://github.com/thanhhaixn92/PQG-Workspace/issues/13).
- `G0`: **PASS**.
- `M1`: **PASS**.
- `OPS-01`: **ACTIVE / REVIEW PENDING**.
- `OPS-02`, `OPS-03`, `OPS-04`, `OPS-05`: **NOT RUN**.
- `CODING_OPERATIONS_READY`: **false / not reached**.
- `P0-04` and MVP Gate remain blocked by the coding-operations gate.
- Product state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

## Active checkpoint

**DIRAP v2.2 — IMPLEMENTATION IN PROGRESS.**

Baseline được giữ nguyên: **DIRAP Local MVP Work Hub — VALIDATED FOR CONTROLLED LOCAL PILOT** (2026-08-12). Trạng thái baseline không chứng minh v2.2 đã hoàn tất.

Mục tiêu là biến các lát chức năng đã có thành một Local MVP an toàn, dễ hiểu và đáng tin cho một người dùng: quản lý Công việc, tài liệu/đầu ra, tri thức có provenance và bộ nhớ có lifecycle. Controlled Knowledge Search và Memory Hub 4.1 là baseline đã validate, không phải checkpoint đang phát triển.

## Active v2.2 gate (2026-08-17)

> Statements in this dated historical narrative that E2 or real
> proposal/package/executor is NOT RUN are superseded by the bounded E2 receipt
> in the reconciliation below; checkpoint remains PARTIAL and is not Gate PASS.

- Reconciliation 2026-08-22: E2 bounded real-provider PASS theo receipt `package-e2-bounded-20260822-063658`; F1 PASS claim hẹp, remote compute stop `NOT PROVEN`; G-SYNTHETIC PASS theo aggregate `package-g-synthetic-aggregate-20260822-0837`, không phải human usability evidence. Checkpoint tiếp tục `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

- Gate 1 technical evidence là **PASS — quyết định độc lập của Codex ngày 2026-08-17**: browser characterization isolated PASS; backend focused **32 passed, 1 Windows symlink skip, 1 warning Pydantic hiện hữu**; frontend ReviewInboxPanel/ActionPackagesPanel/HermesAssistantPanel **21 passed**. Model-config hiện có 1 provider Opencode, 3 model Free enabled và default model; credential/ready chỉ là local configuration, không phải upstream-health proof.
- Bounded real-GYO UAT đã PASS stream/context/source/cancel và late output không persist. Real action-proposal không xuất hiện; proposal/package/executor thực vẫn **NOT RUN**. P2 cancel routing provenance là regression-verified, không phải proof process-level compute stop portable.
- Fidelity được chạy lại bằng năm batch cô lập tại `output/playwright/v22-batched-20260815-075743/`: năm batch cuối PASS với 62 screenshot cho breakpoint, màn hình chính, tab Work, async/offline, theme, keyboard/focus, reduced motion và reflow tương đương 400%. Browser zoom 200% thật trên Chrome 151 đã PASS tại `output/playwright/v22-brandzoom-20260815-0900/` bằng profile, SQLite và workspace tạm `uat-codex-`; screenshot có chỉ báo Chrome `Zoom: 200%`, preference host zoom tính ra đúng 200%, không dùng CSS zoom/emulation. Full screen×state×viewport cross-product vẫn chưa hoàn tất; các batch FAIL/INTERRUPTED trước sửa được giữ làm evidence superseded, không tính vào gate.
- Tên sản phẩm hiển thị hiện hành là **PQG Workspace**; trợ lý trong giao diện là **Trợ lý GYO**. `DIRAP` và các tham chiếu Hermes trong package/API/routes/schema/DB/env/checkpoint/credential contract được giữ nguyên như identifier kỹ thuật hoặc lịch sử để tránh migration ngoài phạm vi. Claim lịch sử providers/models rỗng được **superseded**: hiện có 1 provider Opencode, 3 model Free enabled và default model; chỉ real proposal/package/executor vẫn **NOT RUN**.
- Giữ `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`: full cross-product vẫn chưa hoàn tất và usability 5 người đã được người dùng hoãn hậu v2.2. Không cập nhật sang `DIRAP_V22_VALIDATED`.
- Phạm vi giữ local single-user; không deploy, không automatic Memory Hub injection, không vector/AI search, không connector package 2, không legacy cutover và không encrypted backup.

## Baseline gate result (2026-08-12)

- Canon/state reconciliation: PASS.
- Atomic mutation, migration rollback and concurrent idempotency: PASS.
- Trust-boundary regressions for sandbox, approval, external effects, archive, file revision, CORS/operator and extraction limits: PASS.
- Session/scope isolation, independent recovery and end-user UX: PASS.
- Full automated gate, local runtime smoke and isolated browser UAT: PASS WITH RESIDUALS documented in `AI_RISK_REGISTER.md`.

Evidence snapshot: backend **419 passed, 1 permission-based skip**; frontend **134 passed**; lint/type-check/build passed; local restart smoke and browser UAT at desktop/390px passed. The Work Hub now treats each compatible session as a Work containing multiple conversations, plan/progress, managed documents/outputs and a user-facing History & Context drawer. This is controlled local-pilot readiness, not production readiness.

## Boundary

Local MVP only. Không deploy, không automatic Memory Hub injection, không vector/AI search, connector package 2, legacy cutover, Hub retention/delete hoặc encrypted backup.

---

## Validated baseline retained below

Historical baseline last updated: 2026-08-10

## Historical checkpoint — Memory Hub 4.1

Gói 3A + Gói 4.1 — Personal Memory Hub contract closure, User MVP and local pilot readiness.

## Status

**IMPLEMENTED AND VALIDATED — LOCAL MVP ONLY.**

Gói 4.1 adds a repeatable local readiness check, SQLite backup/restore drill
and a pilot guide. It does not add any new data access or deployment boundary.

Gói 3A closes scope, lifecycle, provenance and atomic legacy-import contracts.
Gói 4 adds a separate local Memory Hub tab without changing the legacy
`MemoryPanel` or `memory_entries` behavior.

## Implemented boundary

- SQLite migration `0021_memory_hub_contract_closure` adds server-derived
  content hashes, optional artifact hashes and a scoped active-identity index.
- Agent search and context require a full project/task scope. Global preference
  is user-only and returned only when explicitly requested; it is never
  inherited into another scope.
- User preference requires separate verify then activate actions. User-created
  normal records remain proposed for Codex review.
- Legacy import is explicit, proposal-only and transactional; it never changes
  `memory_entries`.
- The browser uses `/api/memory-hub/operator` only from local allowed origins;
  it never receives or sends a Credential Manager bearer token.

## Out of scope

No automatic context injection, sensitive/restricted UI exposure, Gói 2
connector, legacy cutover, vector/AI search, retention/delete, encrypted
backup, commit, push or deployment.
