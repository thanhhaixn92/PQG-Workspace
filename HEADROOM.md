# HEADROOM.md

## Purpose

HEADROOM.md defines token and model-usage discipline for AI coding work in this repository.

Goal: preserve enough context for reasoning and verification while avoiding unnecessary model usage.

## Default Context Policy

Load in this order:

1. `AGENTS.md`
2. The user request
3. `docs/00_PROJECT_CANON.md` only if scope/priority is unclear
4. The smallest relevant project doc
5. `CODEGRAPH.md` when locating code
6. Actual source files needed for the change

Do not load all docs by default.

## File Budgets

- `AGENTS.md`: target under 150 lines.
- `CLAUDE.md`: target under 80 lines.
- `DESIGN.md`: target under 150 lines.
- `CODEGRAPH.md`: target under 200 lines.
- `HEADROOM.md`: target under 150 lines.
- Detailed phase docs can be longer because they are loaded only on demand.

## Reading Strategy

- Prefer `rg`/file search before opening large files.
- Read file headers, exports, tests, and directly relevant functions first.
- Use line-targeted reads after locating symbols.
- Summarize long command outputs before feeding them back into the next prompt.
- Do not paste large logs unless the exact lines matter.

## Model-Usage Strategy

- Use low/fast effort for simple docs, formatting, or one-file changes.
- Use medium/high effort for schema, permission, streaming, concurrency, and architecture changes.
- Use plan-first workflow for ambiguous or multi-phase work.
- Stop early and course-correct if implementation drifts from plan.

## Context Compaction Strategy

Before continuing a long session:

1. Summarize current objective.
2. Summarize files changed.
3. Summarize tests run and results.
4. Summarize open risks.
5. Drop irrelevant logs and exploratory dead ends.

Preferred compact instruction:

```text
Compact focusing on current phase, changed files, acceptance criteria, failed tests, security decisions, and next concrete action. Drop unrelated exploration.
```

## External Compression Tools

Do not introduce Headroom or other context-compression proxies into the project by default.

Consider a compression layer only after:

- the repo has enough source/log volume to justify it
- the tool can run local-first
- it does not hide security-relevant details from review
- Codex/Antigravity can still recover original content when needed

## Anti-Patterns

- Asking the agent to read every doc before every task.
- Keeping stale conversation context across unrelated tasks.
- Putting long PRDs inside `AGENTS.md` or `CLAUDE.md`.
- Sending full logs when the failure is in the last 50 lines.
- Adding broad MCP tools instead of targeted repo docs and search.
- Treating memory files as enforced security controls.

