# AGENTS.md — Mandatory pre-code contract

## Applies to every coding agent

Before inspecting broadly, changing code, tests, schemas, migrations, or state,
read this file and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1
```

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

Never commit, push, merge, deploy, reset, clean, stash, rebase, amend a commit,
delete a branch, delete broadly, print a secret, or use a permission/sandbox
bypass. Preserve the dirty worktree, distinguish pre-existing changes from your
own, and do not overwrite existing state merely to make the worktree clean.

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

1. Read-only triage: preflight, focused `git status`/diff, contract and tests.
2. Name the narrow scope and acceptance criteria before editing.
3. Edit the smallest coherent set; preserve compatibility unless approved.
4. Add/update focused regression tests for changed behaviour.
5. Prefer a validation command prescribed by the repository when it covers the
   change. Otherwise run focused checks first, then type/build/runtime checks
   only for affected contracts and surfaces. For UI/API work, check the
   loading, empty, error, success, interaction, authorization, schema,
   compatibility or data-integrity cases that the change can affect. Always run
   `git diff --check` for changed text/code.
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
- `HEADROOM.md` — context discipline; keep `AGENTS.md` and `CODEGRAPH.md` short.
