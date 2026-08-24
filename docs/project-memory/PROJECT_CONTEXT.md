# PQG Workspace — Project Context

> Cross-session stable context. This file does not override live canon/state/source/evidence.

## Authority and memory protocol

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Authority order: `docs/00_PROJECT_CANON.md` > `AGENTS.md` > `PROJECT_STATE.md` > `AI_STATE.json` > `docs/implementation/CURRENT_CHECKPOINT.md` > `docs/AI_AGENT_ROUTING.md` / task canon-security-data model > current source/contracts/tests > `docs/14_AGENT_OPERATING_CONTRACT.md` > Project Memory > historical handoff/chat.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Project Memory never overrides canon, live state, current source or newer evidence; conflicting memory must be corrected after verification.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Every new/modified Project Memory fact must carry its own second-precision timestamp `[YYYY-MM-DD HH:MM:SS UTC±HH:MM]`; correction/supersession receives a new timestamp.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Memory-maintenance writes are non-recursive: record the underlying project event/evidence, not a new event merely because memory was synchronized.

## Project identity / state governance

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Product: **PQG Workspace**; user-facing assistant: **Trợ lý GYO**; repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Current project state remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS`; checkpoint remains `PARTIAL` until separately promoted.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Checkpoint/state promotion is a protected action and remains explicitly reserved for H6 after final evidence; implementation-package completion does not imply promotion.

## Preflight and CI topology governance

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] On a writable local checkout, mandatory preflight is `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1` from repository root.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] In ChatGPT Project/GitHub-connected work without a writable local PowerShell checkout, use GitHub Actions `Agent Preflight` on the exact target ref and require workflow SUCCESS plus exact-SHA `pqg/preflight=success` before implementation writes.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] When connected tooling cannot dispatch `workflow_dispatch` but can write repository files, self-trigger preflight by updating `.github/agent-preflight-trigger.txt` on the exact target ref; asking the user to click Actions is fallback-only when neither dispatch nor trigger-file write is available.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A preflight from another branch/ref, an older unrelated HEAD, or `pqg/smoke` is not a substitute for the fresh exact-ref Agent Preflight prerequisite.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 established stable path-scoped Agent Preflight topology: pushes changing `.github/workflows/agent-preflight.yml` or `.github/agent-preflight-trigger.txt` can trigger on task refs without historical branch allowlisting.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 established active Smoke push conventions: `pqg-workspace`, `work/**`, `security/**`, `maintenance/**`, `integration/**`; PR validation targets `pqg-workspace`; workflow_dispatch remains available.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] For a new-branch push where GitHub reports `before=0000000000000000000000000000000000000000`, Smoke must deepen the shallow checkout enough to resolve `HEAD^` and run committed-diff validation on `parent→HEAD`, not scan the full historical snapshot.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] `pqg/preflight` is an agent execution prerequisite. Locked Q7 keeps it separate from final merge-required status semantics unless that design is explicitly changed; final governance package G requires `pqg/smoke` after technical gates are truthful/stable.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 established stable Smoke regression semantics: the normal `pqg/smoke` job runs backend `pytest -v -ra --tb=short`, the full frontend `npm run test`, lint, type-check, production build, migrations/startup, health/runtime, readiness and cleanup; real-provider validation remains a separate job/evidence path and a skipped real-provider job is never PASS evidence.
- [2026-08-24 07:20:44 UTC+07:00][recorded_at] A1 source-validation HEAD is `2c1b8238921bd0e99367802cfb29c5218ef87e6f`, where Smoke Run #119 / ID `32674524485` proved full frontend 50 files / 317 tests plus backend 516 passed / 81 skipped / 2 warnings and exact-SHA `pqg/smoke=success`; later docs/memory tracking HEADs do not inherit that source-validation claim.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] A2 established a deterministic frontend startup-graph gate: the largest eager chunk must remain below the unchanged `500 * 1024` threshold, while Monaco/editor and Mermaid are proven outside the initial graph by Vite manifest/source-graph evidence rather than by suppressing warnings.

## Locked Foundation architecture

- [2026-08-24 06:39:02 UTC+07:00][imported_at] Foundation consists of LeftSidebar + ModuleCanvas + persistent right AgentDock; Home, Settings and AgentDock are fixed Foundation surfaces rather than installable Modules.
- [2026-08-24 06:39:02 UTC+07:00][imported_at] Module lifecycle remains Install → Attach → Rename display label → Reorder → Module settings → Detach preserving data → Update/Rollback → Uninstall preserving data by default → Delete data as a separate action.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] A2 preserves Foundation/core startup surfaces while optional business/heavy surfaces load only after projection/attachment eligibility; Documents/Monaco is isolated behind dynamic `EditorSurface`, Mermaid remains on-demand, and optional Settings subsections are lazy while the Settings shell/default GYO surface stays eager.

## GYO admin/security boundary

- [2026-08-24 06:39:02 UTC+07:00][imported_at] GYO must not receive model-visible capabilities for Foundation/provider admin; module install/attach/detach/rename/reorder/settings/update/rollback/uninstall/data deletion; privacy/permission settings; backup restore; or admin Skill install/enable/disable.
- [2026-08-24 06:39:02 UTC+07:00][imported_at] Admin-risk capability IDs must be absent from the model-visible CapabilityRegistry; unknown/forbidden capability fails closed (`capability_not_found` or equivalent); actor identity is derived server-side.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Locked Q3 wording for v2.2 is **interactive local-user admin boundary**. Current loopback/origin/fetch-metadata/server-owned-actor controls are not cryptographic proof-of-human and do not distinguish a sufficiently privileged hostile local process from the local user.

## Core runtime/data invariants

- [2026-08-24 06:39:02 UTC+07:00][imported_at] `app.db` owns visible Work/conversation/Assistant history; browser calls backend REST/SSE only; FastAPI is the security/policy boundary; GYO/provider output is untrusted.
- [2026-08-24 06:39:02 UTC+07:00][imported_at] Work mutation remains Action Package → explicit approval → idempotent executor. Memory/Skill candidates never self-activate and Memory does not implicit-share between Work.
- [2026-08-24 06:39:02 UTC+07:00][imported_at] Legacy Hermes/ACP is compatibility/history only and must not be restored as current runtime fallback without architecture approval.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Every model-visible capability has exactly one server-owned executable binding to an MCP or Action Package route. Startup fails closed on missing, orphan, duplicate, incompatible or handler-identity drift and on registry risk/execution/replay mismatch; the binding layer is policy validation, not a replacement executor.
- [2026-08-24 15:07:32 UTC+07:00][recorded_at] Action Package executable binding remains exactly `work_plan_step_update` and `work_status_update`; Package D does not alter proposal, approval, revision, idempotency, budget or mutation semantics.

## F7 Resource Catalog + Context Broker

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F7 remains scoped implementation/validation PASS from source HEAD `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388`; later remediation work does not implicitly alter that evidence.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F7 authoritative policy order remains `discover metadata → SECURITY FILTER → deterministic relevance/ranking → hydrate → pack`; model/ranker must never see a resource it is unauthorized to know exists.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F7 never-catalog boundary excludes credentials/env/API keys, raw audit, arbitrary filesystem/backend locators, raw `app.db`, chain-of-thought/internal reasoning, foreign scope and restricted/lifecycle-ineligible records.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Local F7 read authorization does not grant external-send permission and does not open F9.

## F9 boundary

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] F9 Data Egress remains **CLOSED / NOT APPROVED**.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Local read permission is not external-send permission; web-search queries containing Work/user data, connector sends, upload/export and new external destinations require a separate F9 design/approval gate.

## Active remediation master-plan constraints

- [2026-08-24 06:39:02 UTC+07:00][recorded_at] User locked all remediation choices `Q1=A` through `Q9=A` and authorized sequential single-agent execution; multi-agent remains paused.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Locked execution order: `A0 → A1 → A2 → B → C → D → E1 → E2 → E3 → E4 → G → H1 → H2 → H3 → H4 → H5 → H6`; migration package F is deferred unless separately justified; F9 stays closed.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] A0 is COMPLETE at source-validation HEAD `c6b7d1afab3f066a4aa7f99639104441db1d69fa`.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] A1 is COMPLETE at source-validation HEAD `2c1b8238921bd0e99367802cfb29c5218ef87e6f`.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] A2 is COMPLETE at source-validation HEAD `5fce3270f26f1cac1ffb9d228c63576a47870bc0`; exact Smoke Run #126 / ID `32680074013` published `pqg/smoke=success`, with final largest eager 486,620 bytes and Monaco/Mermaid excluded from the initial graph.
- [2026-08-24 09:19:24 UTC+07:00][recorded_at] The next implementation package is B — sandbox hostile-local-process TOCTOU hardening — only after this A2 tracking commit is verified and a fresh exact-ref Agent Preflight for B succeeds.
- [2026-08-24 06:39:02 UTC+07:00][recorded_at] Source-validation HEADs must always be separated from later documentation/memory-only tracking HEADs; later docs commits do not inherit source/CI validation merely by ancestry.
