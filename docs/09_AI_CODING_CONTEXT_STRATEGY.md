# AI Coding Context Strategy

## 1. Research Summary

This repository uses a layered instruction strategy:

- `AGENTS.md` is the mandatory shared, tool-neutral guidance file for Codex and other agents.
- `CLAUDE.md` imports `AGENTS.md` and adds Claude-specific context-management guidance.
- `DESIGN.md` is a compact architecture snapshot.
- `CODEGRAPH.md` is a manual repo map until code or tooling can generate one.
- `HEADROOM.md` defines token and model-usage discipline.
- `scripts/agent-preflight.ps1` is the read-only receipt for live state, dirty
  worktree and required context before any edit.
- `docs/14_AGENT_OPERATING_CONTRACT.md` holds the detailed implementation and
  conflict-resolution rules so root instructions remain small.
- Detailed PRD/security/eval docs stay in `docs/` and are loaded only when relevant.

## 2. Best Practices Applied

### AGENTS.md

Use for durable rules that should apply every time:

- repo layout
- build/test commands
- engineering conventions
- do-not rules
- review expectations
- definition of done

Require the preflight and a concise first-update receipt. Do not pretend a
repository file can technically verify that an external agent read every line;
reviewers must reject edits that skip the documented sequence.

Keep it small. Put long plans and detailed policy in docs, then point to them.

### CLAUDE.md

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. To avoid duplication, import `AGENTS.md` and add only Claude-specific notes.

Keep it concise because it is loaded into context. Use it for:

- plan mode preference
- compact/clear guidance
- Claude-specific approval reminders
- memory hygiene

### DESIGN.md

Use as a stable architecture primer. It should answer:

- what are the main components
- who owns which boundary
- what flows exist
- what must not happen

Do not turn DESIGN.md into a full implementation plan.

### CODEGRAPH.md

Use as a token-efficient map:

- expected folder layout
- entry points
- dependency direction
- where to look for each task type
- what not to read first

It must reflect the current source tree. If a historical architecture document
conflicts with verified route/service code, flag the discrepancy and follow the
active checkpoint rather than silently copying stale runtime assumptions.

When the repo grows, update this file after structural changes. Later, consider generating a symbol map from Tree-sitter or language tooling.

### HEADROOM.md

Use for context budget discipline:

- which docs to load first
- which docs are on-demand
- file-size targets
- compaction instructions
- model-effort guidelines
- anti-patterns

## 3. Token Optimization Rules

1. Keep root instruction files short.
2. Use docs as indexed references, not auto-loaded context.
3. Prefer route maps over full-file dumps.
4. Prefer symbol search over browsing whole directories.
5. Keep detailed implementation state in handoff notes.
6. Summarize logs before reuse.
7. Clear/compact between unrelated tasks.
8. Use subagents or separate review passes for noisy exploration.

## 4. Maintenance Cadence

Update `AGENTS.md` only when:

- the same agent mistake happens twice
- Codex review finds recurring feedback
- build/test commands stabilize
- a new invariant applies across the whole repo

Update `CLAUDE.md` only when:

- Claude-specific workflow changes
- context management behavior needs adjustment

Update `DESIGN.md` when:

- component boundaries change
- a new service or integration becomes architectural

Update `CODEGRAPH.md` when:

- important directories/modules are created or moved
- dependency direction changes
- agents repeatedly read the wrong files

Update `HEADROOM.md` when:

- token usage becomes wasteful
- long sessions lose important state
- context compression or repo-map tooling is adopted

## 5. Current Recommendation For Hermes

Use the files now created in the repo root. Do not install external context compression tooling yet. The project is currently documentation-only, so the highest-leverage optimization is better routing, not compression.

Revisit compression tools when:

- backend/frontend codebase becomes large
- test logs are consistently long
- agents start loading too many files
- Codex/Antigravity hit context limits during reviews

