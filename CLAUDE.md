@AGENTS.md

## Claude Code Notes

Claude should treat `AGENTS.md` as the shared project instruction source. This file only adds Claude-specific operating guidance.

Before editing, run `powershell -ExecutionPolicy Bypass -File scripts/agent-preflight.ps1`,
then follow the mandatory read sequence in `AGENTS.md`. The preflight is
read-only; a passing result never overrides a closed state gate or human approval.

## Context Management

- Keep `CLAUDE.md` concise; do not paste PRD or long plans here.
- Read `docs/00_PROJECT_CANON.md` first when the task is ambiguous.
- Read `CODEGRAPH.md` before broad file exploration; use the smallest route.
- Read phase-specific docs only when needed.
- Use `/clear` between unrelated tasks.
- Use `/compact` with a focused instruction before a long continuation.
- Prefer plan mode before broad edits, security-sensitive changes, schema changes, or multi-file frontend work.

## Approval Boundary

Claude may help inspect and suggest implementation, but must not auto-approve:

- credential creation or storage
- public service exposure
- deleting or overwriting real user data
- sending data to email, webhook, or external APIs
- changing files outside this workspace

## Memory Hygiene

- Add stable recurring rules to `AGENTS.md`, not chat history.
- Add detailed procedures to docs or skills, not this file.
- If a rule only applies to one future subdirectory, put a scoped instruction file there after that directory exists.

