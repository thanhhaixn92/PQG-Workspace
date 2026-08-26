# AGENTS.md — Mandatory pre-code contract

## Authority precedence

When active sources conflict, use this order and stop for reconciliation if the
state triplet disagrees internally:

1. Current explicit user request plus platform and safety constraints.
2. This `AGENTS.md` execution and permission contract.
3. `PROJECT_STATE.md`, `AI_STATE.json`, and
   `docs/implementation/CURRENT_CHECKPOINT.md`.
4. Product canon, security policy, and data model.
5. Current source, public contracts, and focused tests.
6. Project Memory continuity files.
7. Historical handoffs, plans, chat, and evidence.

GitHub is canonical for source, branches, pull requests, CI, and merge history.
Issue [#13](https://github.com/thanhhaixn92/PQG-Workspace/issues/13) is the
current coding-operations coordination plan; it does not override this order.

## Current agent roles

- **Codex Desktop** is the sole local filesystem/shell/worktree actor and the
  sole repository implementation writer. Within an authorized package it may
  inspect, edit, test, commit and push its feature branch and create/update its
  pull request; it does not merge a protected pull request without separate
  authority.
- **ChatGPT Web** performs research, GitHub-only work, evidence management and
  independent review. It never claims local shell or filesystem execution.
- **GitHub** is the canonical source/PR/CI/merge-history authority.
- **User** supplies product intent and approvals that platform, policy or law
  require. Routine technical decisions stay with Codex inside package scope.

## Applies to every coding agent

Before inspecting broadly, changing code, tests, schemas, migrations, or state,
read this file and obtain a fresh preflight receipt for the exact target
branch/ref using the execution mode that matches the environment.

### Local checkout / local machine

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1
```

### ChatGPT Project / GitHub-connected environment

Do **not** attempt or claim that the local PowerShell command ran when there is
no writable local repository shell. Instead, run the repository GitHub Actions
workflow **Agent Preflight** (`.github/workflows/agent-preflight.yml`) on the
exact target branch/ref. That workflow must execute the same
`scripts/agent-preflight.ps1` on a Windows runner.

Before implementation edits in this environment, require a fresh completed
GitHub preflight for the intended target ref and verify its run/job conclusion
is `success`; when the workflow publishes `pqg/preflight`, verify that status is
`success` as well. A run from another branch/ref or an older unrelated HEAD is
not a substitute. `pqg/smoke` is not a substitute for `pqg/preflight`.

When connected GitHub tooling can write repository files but cannot dispatch
`workflow_dispatch`, the agent must self-trigger the workflow by updating
`.github/agent-preflight-trigger.txt` on the exact target branch/ref. Do not ask
the user to click GitHub Actions when the agent has enough GitHub write access
to perform this trigger itself. The trigger-only commit is a bootstrap/process
commit, not application/runtime implementation.

Only if connected tooling cannot dispatch the workflow **and** cannot write the
trigger file may the agent ask the user to run **Actions → Agent Preflight → Run
workflow** for the target branch/ref. Do not fall back to pretending the local
command ran.

A user may explicitly approve a narrow bootstrap exception whose sole purpose
is to establish or repair this preflight execution path or its governance docs.
Such an exception does not authorize application/runtime implementation edits;
a fresh successful preflight is still required before those edits begin.

The preflight is read-only. It cannot prove that an agent read a file; this
contract makes the following read sequence mandatory. In the first work update,
state the active gate and the files inspected. Do not begin edits until this is
done.

## Required read sequence

1. `PROJECT_STATE.md` and `AI_STATE.json` — live stage, blockers and approval.
2. `docs/implementation/CURRENT_CHECKPOINT.md` — active gate and exclusions.
3. `CODEGRAPH.md` — smallest source/test route for the task.
4. `docs/AI_AGENT_ROUTING.md` and the task-specific canon/security document.
5. The target source, its public contract, and its focused tests.
6. `docs/14_AGENT_OPERATING_CONTRACT.md` for any implementation, schema,
   runtime, security, UX or checkpoint change.

Do not use a historical handoff, old roadmap, test count, or an older checkpoint
as active scope. If sources conflict, follow the precedence in the operating
contract and report the discrepancy instead of silently choosing one.

## Cross-session project memory

For PQG Workspace work that may continue across chat/agent sessions, also read:

1. `docs/project-memory/PROJECT_CONTEXT.md` — stable cross-session context.
2. `docs/project-memory/PROJECT_MEMORY.md` — current continuity snapshot.
3. The latest entries in `docs/project-memory/PROJECT_CHANGELOG.md`.

These files are continuity aids, not higher authority than the live state,
checkpoint, canon, current source or evidence above. If memory conflicts with a
higher-authority source, follow the higher-authority source and reconcile the
memory after verification.

After any project-relevant change that is actually performed, update project
memory in the same work session when write access exists. Every new or modified
memory fact, decision, status, test result, approval, gate or limitation must
carry its own timestamp precise to seconds using
`[YYYY-MM-DD HH:MM:SS UTC±HH:MM]`. Do not rewrite an old timestamp to make a
historical event appear newer; append a timestamped correction/supersession.
Do not store secrets, credential values, raw database content, raw audit dumps
or chain-of-thought in project memory.

## Current operational boundary

- Product name: **PQG Workspace**; in-web assistant: **Trợ lý GYO**.
- Current state is `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`.
  Do not promote `DIRAP_V22_VALIDATED` without every recorded gate and evidence.
- The current web runtime uses `GyoOrchestrator` behind FastAPI. Do not restore a
  legacy Hermes/ACP fallback from historical documentation without explicit
  architecture approval.
- `app.db` owns user-visible Work, conversation and Assistant history. A Work,
  conversation, thread and plan step are separate scope boundaries.
- Browser code talks only to backend REST/SSE. FastAPI enforces validation,
  permissions, audit, archive guards and provider/secret boundaries.
- Every governed write, approval, destructive or external action needs a
  redacted audit event; managed file operations stay within allowed roots.
- GYO may propose only; Work mutation remains Action Package → explicit approval
  → idempotent executor. Memory/Skill candidates remain reviewable and are never
  auto-activated by a model response.
- Memory is not implicitly shared across Work. Active Work memory requires a
  saved plan-step policy; preference, restricted, draft and unrelated records
  stay excluded.

## Stop and ask before changing

- `.env*`, credentials, billing, deployment/public exposure, database files, or
  real user data.
- A migration, dependency, provider credential, network integration, public API
  breaking change, retention/delete policy, or checkpoint/state promotion.
- Authentication/authorization, sandbox/path checks, audit/approval behaviour,
  or any Action Package execution semantics.
- Scope not named by the user or not permitted by the current checkpoint.

An authorized package may explicitly permit a bounded feature-branch commit,
push, and pull-request update. It never implicitly permits merge, deploy,
release, reset, clean, stash, rebase, amend, branch deletion, broad deletion,
permission/sandbox bypass, or secret disclosure. Preserve the dirty worktree,
distinguish pre-existing changes from your own, and do not overwrite existing
state merely to make the worktree clean.

## Change-scope safeguards

- Treat existing code, configuration, generated state and uncommitted changes as
  intentional unless the task or current evidence says otherwise.
- Edit generated output only when its source cannot be changed or the task
  explicitly requires the generated artifact. Do not update dependencies,
  lockfiles or tool versions unless the task requires it or the change is
  unavoidable and reported.
- Local development is not production, but local scope does not waive the
  protected-file and approval boundaries above. Within an approved local scope,
  agents may run relevant development servers, tests and reversible temporary
  artifacts without treating routine execution as a production action.
- Use one agent for tightly coupled work. Parallelize only independent,
  separately verifiable branches with isolated write scopes; one owner must
  integrate and validate the final result.

## Required working pattern

1. Read-only triage: environment-appropriate fresh preflight receipt, focused
   `git status`/diff when a local checkout exists, contract and tests.
2. Name the narrow scope and acceptance criteria before editing.
3. Edit the smallest coherent set; preserve compatibility unless approved.
4. Add/update focused regression tests for changed behaviour.
5. Prefer a validation command prescribed by the repository when it covers the
   change. Otherwise run focused checks first, then type/build/runtime checks
   only for affected contracts and surfaces. For UI/API work, check the
   loading, empty, error, success, interaction, authorization, schema,
   compatibility or data-integrity cases that the change can affect. Always run
   `git diff --check` for changed text/code when a writable checkout is
   available; otherwise report it as `NOT RUN` and review the exact GitHub diff.
6. Review the final diff for scope, secret and state-file leakage.
7. Report changed files, evidence actually run, limitations and the next gate.

Never fake success, weaken tests or security to make a check pass, or represent
`NOT RUN`, warnings, focused tests, or old evidence as a full acceptance pass.

## Canonical references

- `docs/00_PROJECT_CANON.md` — product/security decisions; use with current code
  and state when historical runtime wording differs.
- `docs/04_SECURITY_PERMISSION_POLICY.md` — approval, audit, secrets and paths.
- `docs/02_DATA_STORAGE_MODEL.md` — ownership and migration boundaries.
- `docs/05_ACCEPTANCE_EVALUATION.md` — acceptance conditions.
- `docs/14_AGENT_OPERATING_CONTRACT.md` — enforced working agreement.
- `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md` — GitHub-canonical, GitLab
  advisory-only CI, mirror and connector rules.
- `HEADROOM.md` — context discipline; keep `AGENTS.md` and `CODEGRAPH.md` short.

## Code Review Rules

- Flag any change that makes GitLab, GitLab Duo, or Codex Cloud a second write
  or merge authority for `pqg-workspace`, or claims GitLab evidence without
  exact GitHub/GitLab/pipeline SHA equality.
- Flag CI or connector changes that expose credentials, `app.db`, real user
  data, provider secrets, managed files, or create deployment/external effects
  outside the explicitly approved advisory-CI boundary.
- Flag any gate or state promotion inherited from a mirror pipeline, stale SHA,
  scanner availability, or trial-only feature. Deterministic tests and
  canonical `pqg/smoke` remain authoritative.
