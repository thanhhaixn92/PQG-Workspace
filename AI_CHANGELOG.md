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
