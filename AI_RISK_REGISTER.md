# AI Risk Register

## Active Risks

- Risk: Codex quota can be exhausted.
- Risk: Antigravity CLI may be unavailable.
- Risk: Antigravity CLI may be installed user-local rather than machine-global when setup is run from a non-admin PowerShell.
- Risk: Bash may be unavailable in Windows PowerShell PATH.
- Risk: accidentally starting CP6 without human approval.
- Risk: scripts modifying product code if state gates are bypassed.

## Mitigations

- Keep `AI_STATE.json` at `CP5_COMPLETE`, `next_agent = human`, and `human_approval_required = true`.
- Scripts stop on `CP5_COMPLETE` plus human approval required.
- Scripts stop when `lock` is not null.
- Scripts stop on `state = BLOCKED`.
- Antigravity wrappers set `lock = antigravity` while a CLI run is active and release it on exit.
- Antigravity wrappers prefer `agy`, verify non-interactive `-p` or `--prompt` support from `--help`, and set `state = BLOCKED`, `next_agent = human`, and `human_approval_required = true` when the CLI is unavailable, lacks `-p`, or fails.
- PowerShell wrappers can use `%LOCALAPPDATA%\agy\bin\agy.exe` directly when the current process PATH has not refreshed after user-local installation.
- Agent loop scripts stop if an agent run makes no `AI_STATE.json` change, preventing infinite loops.
- PowerShell wrappers are the primary Windows path.
- Do not write a CP6 task until human approval is explicit.
- Dangerous bypass flags are forbidden; the highest automation level allowed here is sandboxed automation plus Hermes state gates.
