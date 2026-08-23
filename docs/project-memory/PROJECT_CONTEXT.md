# PQG Workspace — Project Context

> Cross-session stable context. This file does not override live canon/state/code.

## Authority and memory protocol

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Khi có xung đột, authority là: `docs/00_PROJECT_CANON.md` > `AGENTS.md` > `PROJECT_STATE.md` > `AI_STATE.json` > `docs/implementation/CURRENT_CHECKPOINT.md` > routed canon/security/data-model > current source/contracts/tests > `docs/14_AGENT_OPERATING_CONTRACT.md` > Project Memory > historical handoff/chat.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Memory không được ghi đè canon, live state, source code hoặc evidence mới hơn.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Mọi nội dung mới hoặc bị sửa trong Project Memory phải có timestamp riêng chính xác đến giây theo format `[YYYY-MM-DD HH:MM:SS UTC±HH:MM] Nội dung cập nhật`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Correction/supersession phải có timestamp mới; không sửa timestamp lịch sử để làm sự kiện trông mới hơn.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Nếu chỉ biết thời điểm ghi nhận, dùng timestamp ghi nhận và đánh dấu `recorded_at`/`imported_at`; không bịa thời gian xảy ra sự kiện.
- [2026-08-23 23:53:22 UTC+07:00][recorded_at] Memory-maintenance writes whose sole purpose is synchronizing `PROJECT_MEMORY.md`/`PROJECT_CHANGELOG.md` do not recursively require another memory entry; record the underlying project event and relevant commit/evidence when known.

## Environment-specific preflight governance

- [2026-08-24 03:06:08 UTC+07:00][recorded_at] Preflight execution is environment-specific: on a local checkout/local machine, run `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1` from the repository root.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] In ChatGPT Project/GitHub-connected environments without a writable local repository shell, do not attempt or claim the local PowerShell command ran; instead run GitHub Actions workflow `Agent Preflight` (`.github/workflows/agent-preflight.yml`) on the exact target branch/ref and verify a fresh successful run before implementation writes.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] A preflight from another branch/ref, an unrelated older HEAD, or `pqg/smoke` is not a substitute for the required `Agent Preflight` receipt. If connected tooling cannot dispatch `workflow_dispatch`, the user must trigger the GitHub workflow and the agent must verify its evidence before implementation writes.
- [2026-08-24 03:06:08 UTC+07:00][recorded_at] A narrow explicit bootstrap approval may establish or repair the GitHub preflight path or governance documents before a new receipt exists; it does not authorize application/runtime/schema/security/feature implementation edits, which still require a fresh successful preflight.

## Project identity

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Product: **PQG Workspace**; user-facing assistant: **Trợ lý GYO**.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Implementation branch tại thời điểm tạo memory: `foundation-v2-r1-durable-agent-run-20260823`.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Code-validation baseline HEAD đã xác minh: `2759d8ce9de0256bb4175a99046ec768011aa422`, commit `ci: validate R1 frontend lifecycle UX`.

## Locked Foundation architecture

- [2026-08-23 23:51:19 UTC+07:00][imported_at] Foundation gồm LeftSidebar + ModuleCanvas + persistent right AgentDock.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Home, Settings và AgentDock là Foundation fixed surfaces, không phải Modules.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Module lifecycle: Install → Attach → Rename display label → Reorder → Module settings → Detach preserving data → Update/Rollback → Uninstall preserving data by default → Delete data as a separate action.

## Hard GYO admin boundary

- [2026-08-23 23:51:19 UTC+07:00][imported_at] GYO không được có model-visible capability cho Foundation/provider admin, module lifecycle admin, module data deletion, privacy/permission settings, backup restore hoặc admin Skill install/enable/disable.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Admin-risk capability phải ABSENT khỏi model-visible `CapabilityRegistry`; forbidden/unknown capability fail closed, ví dụ `capability_not_found`.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Actor identity phải derive server-side; browser/model-provided actor identity không đáng tin.

## Core invariants

- [2026-08-23 23:51:19 UTC+07:00][imported_at] `app.db` sở hữu visible Work/conversation/Assistant history.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Browser chỉ giao tiếp backend qua typed REST/SSE; FastAPI là security/policy boundary.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] GYO/provider output là untrusted.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Work mutation chỉ qua Action Package → explicit approval → idempotent executor.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Memory/Skill candidates reviewable, không tự active; Memory không implicit-share giữa Work.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Legacy Hermes/ACP là compatibility/history only; không restore legacy runtime fallback nếu chưa có architecture approval.

## F7 locked design

- [2026-08-23 23:51:19 UTC+07:00][imported_at] F7 Resource Catalog + Context Broker là protected security/data-access change.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] SECURITY FILTER phải chạy trước RELEVANCE/RANKING; model không được rank/select resource mà nó không được phép biết tồn tại.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Không expose credentials, env, API keys, raw audit, arbitrary filesystem paths, chain-of-thought hoặc raw `app.db` vào model resource catalog/context.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Sensitivity classes: public, internal, sensitive, restricted.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Trust classes: canonical_user_data, verified_knowledge, derived_text, external_unverified, agent_generated_draft.

## F9 boundary

- [2026-08-23 23:51:19 UTC+07:00][imported_at] F9 Data Egress chưa được mở và cần approval riêng.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Local read permission không đồng nghĩa external-send permission; web-search query tự nó là data egress; LLM không phải authorization authority.

## Protected change boundary

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Explicit human approval cần trước migrations/schema, dependencies/tool versions, auth/security boundary, provider/network/credentials, Action Package execution semantics, retention/delete, checkpoint/state promotion, deployment/public exposure, secrets hoặc real user data.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Lệnh chung `Tiếp tục` không mở protected gate mới.
