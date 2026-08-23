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
- [2026-08-24 03:35:25 UTC+07:00][recorded_at] Supersession of the prior manual-trigger fallback: when ChatGPT Project/GitHub tooling can write repository files but cannot dispatch `workflow_dispatch`, the agent must self-trigger `Agent Preflight` by updating `.github/agent-preflight-trigger.txt` on the exact target branch/ref. Do not ask the user to click GitHub Actions when the agent has enough repository write access to trigger it itself.
- [2026-08-24 03:35:25 UTC+07:00][recorded_at] Manual user triggering is now fallback-only: request **Actions → Agent Preflight → Run workflow** only when connected tooling can neither dispatch the workflow nor write the trigger file.

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

## F7 current status

- [2026-08-24 04:36:02 UTC+07:00][recorded_at] Supersession of the earlier unopened-F7 status: user explicitly approved F7 Resource Catalog + Context Broker security/data-access boundary; F9 Data Egress was explicitly kept closed.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 model-context policy boundary is `backend/app/services/context_broker.py`; required order is `discover metadata → SECURITY FILTER → deterministic relevance/ranking → hydrate → pack`, and `assistant_context.py` is a compatibility facade rather than a second selection policy.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 source-validation HEAD is `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388`; Smoke Test Run ID `32667595588` completed success with backend 516 passed / 81 skipped / 2 warnings, F7 focused 5/5 PASS, frontend focused 30/30 PASS, lint 0/0, type-check/build/runtime readiness PASS, and `smoke-real=SKIPPED`.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 scoped validation does not promote the project checkpoint; current state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

## F9 boundary

- [2026-08-23 23:51:19 UTC+07:00][imported_at] F9 Data Egress chưa được mở và cần approval riêng.
- [2026-08-23 23:51:19 UTC+07:00][imported_at] Local read permission không đồng nghĩa external-send permission; web-search query tự nó là data egress; LLM không phải authorization authority.
- [2026-08-24 04:36:02 UTC+07:00][recorded_at] F7 approval/implementation did not open F9; no web-search query, connector send, upload/export or new external data destination is authorized by F7.

## Protected change boundary

- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Explicit human approval cần trước migrations/schema, dependencies/tool versions, auth/security boundary, provider/network/credentials, Action Package execution semantics, retention/delete, checkpoint/state promotion, deployment/public exposure, secrets hoặc real user data.
- [2026-08-23 23:51:19 UTC+07:00][recorded_at] Lệnh chung `Tiếp tục` không mở protected gate mới.

## Latest full Smoke Test rerun

- [2026-08-24 04:56:34 UTC+07:00][recorded_at] User explicitly requested re-running the existing GitHub `Smoke Test` so lint, tests, type-check, build and runtime validation execute on GitHub without requiring a local command.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Assistant created empty validation commit `75ebb845bc67bb2d798b345473830f9ec8a8be7c` (`ci: rerun full smoke validation`) on `pqg-workspace`; it points to the same tree `1dec4efd0490ed5fb877dbb6e056a90ac67a6a48` as parent `78a1b9552cd10f2e46dc8a88a29b665822d35f81`, so no repository file/content changed for the validation trigger itself.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] GitHub Actions `Smoke Test` Run #104, ID `32668775604`, event `push`, exact HEAD `75ebb845bc67bb2d798b345473830f9ec8a8be7c`, completed `success`; combined commit status is `pqg/smoke=success`.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Run #104 backend result: 516 passed, 81 skipped, 2 warnings.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Run #104 frontend focused result: 4 files / 30 tests PASS; `npm run lint` executed `oxlint` and reported `Found 0 warnings and 0 errors`, scanning 144 files with 103 rules; TypeScript `tsc -b` PASS; production Vite build PASS.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Run #104 runtime result: migrations through `0038_durable_assistant_runs` PASS; health/runtime PASS; `SMOKE OK — 7 readiness checks, workspace ready`; cleanup PASS with 1 smoke session archived.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Run #104 `smoke-real=SKIPPED`; this is not PASS evidence.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Known non-blockers observed again: npm audit 6 vulnerabilities (3 moderate, 3 high), Vite >500 kB chunk warning, the 2 backend warnings, and GitHub Actions Node-20 deprecation notices for `actions/checkout@v4` and `actions/setup-python@v5`; no dependency/tool-version change was made.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Tooling correction: while preparing the CI trigger, the assistant accidentally created branch `ci-validation-temp-ignore` at `78a1b9552cd10f2e46dc8a88a29b665822d35f81`. It does not affect `pqg-workspace` or Run #104. The available connector exposed no delete-ref operation, and current `AGENTS.md` prohibits branch deletion, so the branch was intentionally left untouched rather than silently forcing cleanup.
- [2026-08-24 04:56:34 UTC+07:00][recorded_at] Gate effect: no implementation/source, schema/migration, auth/security, provider/network, dependency/tool-version, deployment, F9 or checkpoint/state change occurred. Overall state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F9 remains CLOSED / NOT APPROVED.

## Remaining-work audit baseline

- [2026-08-24 05:24:33 UTC+07:00][recorded_at] User requested a detailed audit and implementation plan for remaining PQG Workspace work; this audit is read-only except for the required self-trigger/process receipt and Project Context synchronization, and does not authorize protected implementation scope.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Assistant self-triggered exact-head audit preflight with commit `8e424745a08581510dd5f797a3e4411c71309741`; Agent Preflight Run #9 / ID `32670213702` completed `success` and published `pqg/preflight=success`.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] The same push produced Smoke Test Run #105 / ID `32670213725` on exact HEAD `8e424745a08581510dd5f797a3e4411c71309741`; `pqg/smoke=success`, backend 516 passed / 81 skipped / 2 warnings, frontend focused 30/30 PASS, lint 0/0, type-check/build/runtime readiness PASS, and `smoke-real=SKIPPED`.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Fresh audit confirms `pqg-workspace` remains unprotected: `protected=false`, protection disabled, required-status enforcement off, and no required contexts/checks. Enabling branch protection or required statuses remains an explicit repository-governance approval.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Security residuals to keep separately gated are: local-browser Module admin is not cryptographic proof of human presence; CapabilityRegistry is metadata/exposure policy rather than an executable semantic binding; sandbox file operations still have a pathname check-then-use TOCTOU residual despite traversal/reparse/hard-link defenses.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Dependency/supply-chain residuals remain: npm reports 6 vulnerabilities (3 moderate, 3 high), backend dependency stack emits Pydantic Settings and Starlette TestClient deprecation warnings, and GitHub workflows use version-tagged `actions/checkout@v4` / `actions/setup-python@v5` rather than immutable SHA pins.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] CI semantic residual: current `smoke-real` still installs/runs legacy `hermes-agent`/ACP and therefore is not a current-GYO real-provider acceptance path; it must not be used as evidence for native GYO provider readiness even if later enabled.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Quality/performance residual: `ModuleCanvas.tsx` eagerly imports nearly every Module surface while Vite reports two >500 kB chunks; route/module-level lazy loading is the preferred non-protected first implementation package instead of suppressing the warning threshold.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Migration 0037 and the migration registry wrapper are currently regression-valid/idempotent but carry maintainability debt; migration cleanup remains protected and lower priority than security/governance fixes.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] Recommended execution order is: non-protected frontend code-splitting/CI test-coverage hygiene → explicitly approved sandbox hardening → explicitly approved admin human-presence and capability semantic-binding packages → explicitly approved dependency/action/current-GYO-real-CI modernization → migration maintainability if still justified → branch protection/required `pqg/smoke` → final acceptance/state reconciliation. F9 remains a separate future gate and CLOSED / NOT APPROVED.
- [2026-08-24 05:24:33 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; no checkpoint promotion, deployment/public exposure, provider credential mutation or F9 implementation occurred during this audit.
