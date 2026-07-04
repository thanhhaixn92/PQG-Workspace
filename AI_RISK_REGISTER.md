# AI Risk Register

## Active Risks

- Risk: Codex quota can be exhausted.
- Risk: Antigravity CLI may be unavailable.
- Risk: Bash may be unavailable in Windows PowerShell PATH.
- Risk: accidentally starting CP6 without human approval.
- Risk: scripts modifying product code if state gates are bypassed.

## Mitigations

- Keep `AI_STATE.json` at `CP5_COMPLETE`, `next_agent = human`, and `human_approval_required = true`.
- Scripts stop on `CP5_COMPLETE` plus human approval required.
- Scripts stop when `lock` is not null.
- Scripts stop on `state = BLOCKED`.
- PowerShell wrappers are the primary Windows path.
- Do not write a CP6 task until human approval is explicit.
