# AI Changelog

## 2026-07-04

- CP5 Frontend Migration was completed and committed before automation setup.
- Automation infrastructure created from clean/restored state after CP5.
- CP5 gate preserved.
- CP6 not started.
- No product code modified by automation setup.
- Automation runner fixes added after review:
  - Removed unsupported `codex exec --ask-for-approval` flag.
  - Added Antigravity CLI lock/release behavior.
  - Added Antigravity missing-CLI/failure block back to human review.
  - Added loop no-state-change protection.
- Automation runner setup update:
  - Prefer current Antigravity CLI command `agy`.
  - Require non-interactive `-p` or `--prompt` support before invoking Antigravity from scripts.
  - Use Antigravity `--sandbox` when the installed CLI supports it.
  - Keep `antigravity` and `ag` as compatibility fallbacks only.
  - Document forbidden dangerous bypass flags.
- Antigravity CLI readiness:
  - Official installer found `agy.exe` installed at `%LOCALAPPDATA%\agy\bin\agy.exe`.
  - Added the installed `agy` directory to User PATH.
  - Verified `agy 1.0.16` and successful sandboxed non-interactive prompt execution.
  - Added required YAML frontmatter to `.agents/skills/verify-and-handoff/SKILL.md`.

## Files Created Or Updated

- `AGENTS.md`
- `AI_TASK.md`
- `AI_STATE.json`
- `AI_HANDOFF.md`
- `AI_CHANGELOG.md`
- `AI_VERIFICATION.md`
- `AI_RISK_REGISTER.md`
- `.agents/skills/verify-and-handoff/SKILL.md`
- `scripts/run-codex.sh`
- `scripts/run-antigravity.sh`
- `scripts/agent-loop.sh`
- `scripts/ai-auto.sh`
- `scripts/run-codex.ps1`
- `scripts/run-antigravity.ps1`
- `scripts/agent-loop.ps1`
- `scripts/ai-auto.ps1`
- `scripts/codex-tick.ps1`
