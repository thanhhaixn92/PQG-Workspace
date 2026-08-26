# AI Task

## Active task

- Plan: [Coding Operations Stabilization — Issue #13](https://github.com/thanhhaixn92/PQG-Workspace/issues/13).
- Package: `OPS-01 — Authority and State Normalization`.
- Actor: `codex-desktop`; next actor after evidence: `chatgpt-web`.
- Branch: `codex/ops-01-authority-state-normalization`.
- Base: `f5d21dbdfe643b44ecf3ede7104b7850f546aed3`.

## Objective

Make active governance surfaces agree on one authority order, one operations
package, one current/next actor, explicit autonomous actions, explicit protected
actions, and package blockers. Preserve the product state as
`DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

## Runtime boundary

The current assistant runtime is `GyoOrchestrator` / **Trợ lý GYO** behind
FastAPI. Hermes/ACP is compatibility or history only and must not become an
active fallback without separate architecture approval.

## Scope and stop

OPS-01 changes governance/state documents only. It does not change runtime,
schema, workflows, dependencies, launchers, credentials, user data, or product
checkpoint. `OPS-02`, `P0-04`, the MVP Gate, and webapp feature development are
not started. Exact source/validation SHA and workflow evidence live in the pull
request and Issue #13 rather than being fabricated inside a self-referential
tracked state file.
