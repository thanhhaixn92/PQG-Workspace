# PQG Workspace — Project Context

> Cross-session durable context. Live canon, state, source and evidence override this file; historical receipts belong in `PROJECT_CHANGELOG.md` and Git history.

## Authority and memory protocol

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Authority order: `docs/00_PROJECT_CANON.md` > `AGENTS.md` > `PROJECT_STATE.md` > `AI_STATE.json` > `docs/implementation/CURRENT_CHECKPOINT.md` > `docs/AI_AGENT_ROUTING.md` and task canon/security/data documents > current source/contracts/tests > `docs/14_AGENT_OPERATING_CONTRACT.md` > Project Memory > historical handoff/chat.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Memory never overrides canon, live state, current source or newer evidence. Every new or corrected memory fact has a second-precision timestamp; memory synchronization records the underlying event and is non-recursive.
- [2026-08-26 13:46:29 UTC+07:00][recorded_at] Supersession: the active authority order is current explicit user request plus platform/safety constraints > root `AGENTS.md` > state triplet (`PROJECT_STATE.md`, `AI_STATE.json`, current checkpoint) > product canon/security/data model > current source/contracts/tests > Project Memory > historical handoffs/plans/chat/evidence. The 2026-08-24 ordering above is retained only as historical context.

## Coding-agent role model

- [2026-08-26 13:46:29 UTC+07:00][recorded_at] Codex Desktop is the sole local filesystem/shell/worktree actor and repository implementation writer within an authorized package; ChatGPT Web owns GitHub-only research, evidence and independent review; GitHub owns canonical source/PR/CI/merge history; the user supplies product intent and approvals that are explicitly protected.
- [2026-08-26 13:46:29 UTC+07:00][recorded_at] GitHub Issue #13 is the active coding-operations coordination plan. Dynamic source, validation and workflow identifiers stay in GitHub evidence until OPS-03 establishes a durable exact-SHA handoff mechanism; Project Memory never fabricates a self-referential commit SHA.

## Identity and state promotion

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Product: **PQG Workspace**; user-facing assistant: **Trợ lý GYO**; repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] State remains `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` and checkpoint remains `PARTIAL`. Promotion is protected and reserved for H6 with all required evidence and explicit approval; package completion never promotes state by itself.

## Preflight and CI semantics

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] A writable checkout requires `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1` from repository root. Connected work without that checkout requires exact-ref Agent Preflight success and exact-SHA `pqg/preflight=success` before implementation writes; `pqg/preflight` is an execution prerequisite, not currently a merge-required status.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Normal Smoke uses the complete backend/frontend, static and runtime/readiness payload. A new-branch zero-SHA push must validate committed `parent -> HEAD`, not the historical snapshot. The A2 startup graph keeps Foundation core eager while optional/heavy surfaces are lazy behind verified boundaries.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] P-TRACK invariant: canonical `pqg/smoke` is the aggregate status. `pqg/smoke-full` is a full-source receipt. `pqg/tracking-integrity` proves only bounded allowlisted equivalence to that full-validated anchor and never proves runtime tests ran on its tracking SHA. Pull requests remain full; Package G owns PR-first reconciliation.

## Durable architecture and security invariants

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Foundation is LeftSidebar + ModuleCanvas + persistent AgentDock; Home, Settings and AgentDock are fixed surfaces. Module lifecycle preserves data by default and keeps deletion a separate action.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] GYO is bounded to interactive local-user administration, not cryptographic proof of human presence. Model-visible capability inventory excludes Foundation/provider/module/privacy/permission/restore/delete/admin-Skill authority; unknown or forbidden capability fails closed and actor identity is derived server-side.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] `app.db` owns visible Work/conversation/Assistant history. Browser code uses backend REST/SSE only; FastAPI is the policy boundary; provider output is untrusted. Work mutation remains Action Package -> explicit approval -> idempotent executor; Memory/Skill candidates never self-activate or implicitly cross Work scope.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Current runtime is `GyoOrchestrator`; legacy Hermes/ACP is compatibility/history only and cannot be restored as a runtime fallback without architecture approval. Capability executable binding is server-owned and fails closed on registry/binding/handler drift.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] F7 authorization order is `discover metadata -> SECURITY FILTER -> deterministic relevance/ranking -> hydrate -> pack`; unauthorized resources must not be discoverable. F9 Data Egress is **CLOSED / NOT APPROVED**: local read permission is not external-send permission.

## Locked remediation boundary

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Locked decisions Q1-Q9 remain A: real lazy boundaries; hostile-local-process sandbox defense; truthful local-user admin wording; minimal executable binding; selective dependency work; bounded native local GYO acceptance; PR-first governance; synthetic evidence only; and durable cancellation/late-output-discard boundary.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Execution order is `A0 -> A1 -> A2 -> B -> C -> D -> E1 -> E2-A -> P-TRACK -> P-MEM -> E2-B -> E2-C -> E2-D -> E2-E -> E3 -> E4 -> G -> H1..H6`. F remains deferred unless separately justified; F9 remains closed. Source-validation claims are never inherited by documentation or tracking ancestry.

## GitHub, GitLab and Codex topology

- [2026-08-25 10:12:11 UTC+07:00][recorded_at] GitHub `thanhhaixn92/PQG-Workspace` is the only code/PR/merge authority. Private GitLab project `thanhhai-group/PQG-Workspace` is a one-way pull mirror used only for advisory CI, security analysis, planning and redacted evidence; exact GitHub/GitLab/pipeline SHA equality is required before attributing a GitLab result to source.
- [2026-08-25 10:12:11 UTC+07:00][recorded_at] GitLab, GitLab Duo and Codex Cloud must not push/fix/merge mirrored refs, promote project state, or replace canonical `pqg/smoke`. Trial-only features are optional and must fail out of the GitHub merge path when the subscription changes.
