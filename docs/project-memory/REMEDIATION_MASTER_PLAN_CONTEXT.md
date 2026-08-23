# PQG Workspace — Remediation Master Plan Execution Context

> Purpose: stable cross-session handoff receipt for executing `docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md`.
>
> This file does not override live canon/state/source. New chat/session must re-fetch live GitHub state before acting.

## [2026-08-24 06:09:16 UTC+07:00] User decision and execution authorization

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] User locked all audit choices as: `Q1=A · Q2=A · Q3=A · Q4=A · Q5=A · Q6=A · Q7=A · Q8=A · Q9=A` and instructed the assistant to create/persist the complete plan and prepare a new-chat handoff for executing it on GitHub.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Master plan path: `docs/implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Master plan creation commit: `7adf83dc497ab848dee711ea49f91b742339d4d3` (`docs: add remediation master plan [skip ci]`).
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Plan persistence rule: keep the master plan while any package is unfinished; normal revisions update it in place and preserve the ledger. Delete/replace only after all in-scope work is complete and the user accepts closure, or when the user explicitly requests deletion/replacement.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Multi-agent execution is paused. The remediation plan is to be executed sequentially/single-agent unless the user later explicitly changes that decision.

## [2026-08-24 06:09:16 UTC+07:00] Authoritative audit baseline before plan docs

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Audit/source baseline before docs-only plan persistence: `pqg-workspace@ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Agent Preflight Run #10 / ID `32671953420`: SUCCESS, `pqg/preflight=success`, exact audit HEAD `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Smoke Test Run #106 / ID `32671953411`: SUCCESS, `pqg/smoke=success`, exact audit HEAD `ddb982edcd2ccc0edd0c8881b992aa2e60c77782`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Run #106 backend: 516 passed / 81 skipped / 2 warnings.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Run #106 frontend in Smoke: 4 focused files / 30 tests PASS; this is not the full frontend regression suite. Lint 0 warnings/0 errors over 144 files/103 rules; TypeScript and production build PASS.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Run #106 runtime: migrations through `0038_durable_assistant_runs`, startup, health/runtime, 7 readiness checks and cleanup PASS.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Run #106 `smoke-real=SKIPPED`; it is not PASS evidence.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Branch protection remained OFF at audit baseline: `protected=false`, required-status enforcement off, no required contexts/checks.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] State/checkpoint remained `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`; F7 remains scoped PASS; F9 remains CLOSED / NOT APPROVED.

## [2026-08-24 06:09:16 UTC+07:00] Locked implementation interpretation

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q1=A: optimize initial/core frontend graph and lazy-load heavy features; never hide the issue solely by increasing the Vite chunk warning threshold.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q2=A: sandbox threat model includes hostile local process; implement handle/descriptor-bound I/O and Windows-equivalent race defenses rather than pathname-only revalidation.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q3=A: v2.2 claim is `interactive local-user admin`; current loopback/origin/server-actor controls are not cryptographic proof-of-human; no WebAuthn/Windows Hello expansion under this plan.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q4=A: add minimal server-owned capability implementation binding/consistency validation; do not rewrite execution into a mega dispatcher.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q5=A: inventory dependencies/advisories first, remediate in small validated batches, and add deterministic backend CI constraints; never run blind `npm audit fix`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q6=A: native current-GYO real-provider acceptance is bounded/local Windows with existing Credential Manager and synthetic data; do not create a GitHub-hosted CI credential path by default.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q7=A: after CI gates are truthful/stable, move to PR-first default-branch governance requiring `pqg/smoke`, blocking force-push/delete, while leaving `pqg/preflight` as an agent prerequisite rather than required merge check.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q8=A: G-SYNTHETIC remains acceptable as scoped v2.2 synthetic evaluation but must never be relabeled as human usability evidence.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Q9=A: durable local cancellation/late-output discard is the v2.2 acceptance boundary; remote provider compute/billing termination remains a documented provider limitation.

## [2026-08-24 06:09:16 UTC+07:00] Scope boundaries that remain closed

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] F9 Data Egress remains CLOSED / NOT APPROVED; no web-search/connector-send/upload/export/new external destination is opened by this plan.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Migration maintainability package F is DEFERRED unless a real migration need or separate explicit user instruction justifies reopening it.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Final checkpoint/state promotion is not authorized by the implementation choices; H6 must stop and request explicit user approval after final evidence reconciliation.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] No real user data, deployment/public exposure, arbitrary credential mutation, or Action Package semantic expansion is authorized.

## [2026-08-24 06:09:16 UTC+07:00] Required next-session execution protocol

- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Start at package **A0** unless live repo evidence shows it is already complete/superseded.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Before any implementation write, re-fetch live `pqg-workspace`, read the master plan and current governance/state/canon, then self-trigger a fresh Agent Preflight on the exact target ref and require `pqg/preflight=success`.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Because A0 exists specifically to repair task-branch preflight topology, do not assume a newly created arbitrary task branch can self-trigger preflight until A0 is completed and validated. Use the current valid exact-ref trigger path for A0 itself.
- [2026-08-24 06:09:16 UTC+07:00][recorded_at] Execute packages sequentially, validate each package before advancing, update the master-plan status/ledger and project memory after each material package, and distinguish source-validation commits from later docs-only tracking commits.
