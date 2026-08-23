# Agent operating contract

## Purpose

This is the implementation companion to root `AGENTS.md`. It makes a coding
agent's pre-code checks repeatable without turning historical plans into active
scope. It applies to Codex, Hermes Desktop and any delegated coding agent.

## Mandatory pre-code receipt

Before the first edit, an agent must:

1. Run `scripts/agent-preflight.ps1` from the repository root.
2. Read `PROJECT_STATE.md`, `AI_STATE.json`, the active checkpoint and
   `CODEGRAPH.md`.
3. Read the route-selected canon/security document and the target source,
   contract and focused tests.
4. Inspect `git status --short` and the focused diff to preserve existing work.
5. State in its first update: active gate, requested scope, files read, planned
   validation and any approval blocker.

No agent may present an implementation plan, a historical handoff, or a passing
test from another revision as permission to edit outside this task.

## Precedence and discrepancy rule

Use this order when sources conflict:

1. User's current explicit request and platform safety rules.
2. `PROJECT_STATE.md`, `AI_STATE.json`, and
   `docs/implementation/CURRENT_CHECKPOINT.md` for active stage/gate.
3. Canon, security policy and accepted decisions for durable boundaries.
4. Current route/schema/service code plus focused tests for implemented runtime
   behaviour.
5. Historical handoffs, old plans and historical evidence.

If a durable document conflicts with verified current runtime, do not silently
rewrite either during a feature patch. Report the exact conflict, follow the
active gate, and request a documentation-reconciliation scope when needed.

## Current non-negotiable boundaries

- Single-user, local-first PQG Workspace; no cloud/deploy work in v2.2.
- **Trợ lý GYO** uses the provider-neutral backend orchestrator. A legacy
  Hermes/ACP path is historical and must not become a fallback without approval.
- `app.db` is the source for user-visible Work/Assistant records. Internal
  provider/runtime state must not be read or edited directly by the browser.
- Scope is enforced server-side: Work, conversation, thread, plan step and
  managed artifact must agree. A client selector or a prompt instruction is not
  a security boundary.
- Every governed write, approval, destructive or external action needs a
  redacted audit event, and managed file operations must remain within allowed roots.
- Action proposals do not mutate Work. The only allowed mutation route is a
  validated Action Package, explicit decision and idempotent executor.
- Memory/Skill learning is candidate-only. Auto-learning is opt-in by plan step;
  it does not read raw transcript, activate Memory, enable a Skill, create a
  subagent, or make an external call.
- Provider secrets, raw filesystem paths, raw tool arguments and sensitive
  terminal output must not be returned by backend, UI, logs or evidence.

## Change disciplines

| Change | Required checks before implementation |
| --- | --- |
| REST/SSE/schema | route, Pydantic schema, client, error contract, focused backend/frontend tests |
| Work/Assistant scope | archive/foreign Work/conversation/thread cases, stale response and retry isolation |
| Approval/action | before/after, 409 single-winner, idempotency and audit-safe payload |
| Memory/learning | scope/exclusion, default-off, duplicate/rate/cancel/archive fail-closed |
| Files/artifacts | managed roots, staging/hash/conflict/path escape, binary UX |
| Provider/model | credential redaction, unavailable/401/429 rules, no silent fallback after token |
| Shared UI | loading/empty/error/populated, keyboard/focus, reduced motion and target breakpoints |
| Migration/state | explicit user approval, upgrade/idempotency/rollback plan and isolated data proof |

## Definition of done for a scoped change

- The altered contract is identified and compatible, or approved as breaking.
- Focused regression tests prove both success and relevant fail-closed path.
- Type/build/runtime checks are run in proportion to shared impact; unrun checks
  remain `NOT RUN`.
- `git diff --check` and a final scoped diff review have run.
- The handoff says what changed, evidence actually executed, warnings/limits,
  and the next gate. State/checkpoint files change only when their gate is met.

## What this contract does not do

Repository files can require a process and the preflight can detect missing
context or a closed gate; neither can technically prove a human or external
agent read every line. Launch prompts and agent configuration must therefore
refer to root `AGENTS.md`, and reviewers must reject edits without the receipt.
