# AI Risk Register

## Active Risks

- Risk: Codex quota can be exhausted.
- Risk: Antigravity CLI may be unavailable.
- Risk: Antigravity CLI may be installed user-local rather than machine-global when setup is run from a non-admin PowerShell.
- Risk: Bash may be unavailable in Windows PowerShell PATH.
- Risk: CP6 implementation accidentally expands into CP7/Telegram or broader roadmap scope.
- Risk: scripts modifying product code if state gates are bypassed.
- Risk: outbox dispatcher can duplicate sends if idempotency keys are not stable.
- Risk: retry/dead-letter handling can hide permanent failures if not tested.
- Risk: full backend suite currently has one environment-dependent Hermes spawn failure on Windows pipes (`WinError 5`) outside CP6 scope.
- Risk: CP7 Telegram webhook endpoints could be called without authentication or bypass allowlist rules if HMAC/allowlist checks are not strictly enforced.
- Risk: duplicate or retried webhook updates from n8n could trigger redundant task runs if idempotency is not enforced.
- Risk: callback tokens used for approval flows could be replayed or intercepted after expiration if 409/410 rules are omitted.
- Risk: infinite retry loops or runaway backoff could block execution threads and waste API quota.
- Risk: credentials or authorization details could leak if 401/403 provider errors are retried or fell back on rather than aborting immediately.
- Risk: task run attempt chains and events could be logged with invalid format or fail to persist during failures.
- Risk: draft/non-approved skills could be accidentally injected into the agent context due to missing or bypassed status filters.
- Risk: skill mutations or version transitions might lack complete version tracking, causing loss of historical skill content.
- Risk: mutation audit events could be bypassed or not match the standard payload format.
- Risk: removing code without explicit human approval could break undocumented dependencies or active components.
- Risk: deprecated endpoints might be called by consumers who did not receive or handle `X-Deprecated` headers.

## V1 Residual Risks (Non-Blocking)

- **Risk**: Outbox dispatcher shutdown may be delayed up to `outbox_dispatcher_poll_seconds` (default 5s) because the background loop checks the stop signal only after each `dispatch_once` cycle completes.
- **Risk**: Outbox dispatcher `worker_id` is hardcoded to `"fastapi-backend"`; multi-instance deployments would need unique worker IDs to avoid lock conflicts.
- **Risk**: The n8n outbox sender requires a `"notification"` entry in `n8n_allowed_workflows` for real dispatch. Until configured, rows are retried and dead-lettered (not silently dropped), which is correct behavior but may cause unexpected accumulation.
- **Risk**: Persistent DB connection failures in the dispatcher loop will log exceptions every poll interval indefinitely (by design, retry behavior).
- **Risk**: Migration 0014 callable pattern is the only guarded migration; older migrations (0004, 0006, 0009, 0012) still use the `executescript` + `duplicate column name` catch, which is safe for single-statement ALTERs but not extended.
- **Risk**: Pre-existing `StarletteDeprecationWarning` from `fastapi.testclient` (`httpx` → `httpx2` migration); does not affect runtime.

- **Risk**: Frontend lint passes with existing React hook dependency warnings; no runtime regression observed in tests/build.
- **Risk**: Frontend production build passes with Vite large chunk warnings caused by heavy diagram/math dependencies; acceptable for V1 local-first packaging.

## Mitigations

- Keep `AI_STATE.json` explicit for one checkpoint task at a time.
- Scripts stop on `CP5_COMPLETE` plus human approval required.
- Scripts stop when `lock` is not null.
- Scripts stop on `state = BLOCKED`.
- Antigravity wrappers set `lock = antigravity` while a CLI run is active and release it on exit.
- Antigravity wrappers prefer `agy`, verify non-interactive `-p` or `--prompt` support from `--help`, and set `state = BLOCKED`, `next_agent = human`, and `human_approval_required = true` when the CLI is unavailable, lacks `-p`, or fails.
- PowerShell wrappers can use `%LOCALAPPDATA%\agy\bin\agy.exe` directly when the current process PATH has not refreshed after user-local installation.
- Agent loop scripts stop if an agent run makes no `AI_STATE.json` change, preventing infinite loops.
- PowerShell wrappers are the primary Windows path.
- CP6 scope is explicitly limited to Outbox Dispatcher.
- Dangerous bypass flags are forbidden; the highest automation level allowed here is sandboxed automation plus Hermes state gates.
- CP6 dispatch events use deterministic outbox ids/idempotency keys and focused tests cover duplicate insert/send prevention, retry, lease recovery, and dead-letter behavior.
- CP6 verification records the full-suite Hermes spawn failure separately from dispatcher tests; rerun that test in an environment where ACP subprocess pipes are permitted before treating the full suite as completely green.
- CP6 Outbox Dispatcher is now closed (`CP6_COMPLETE`).
- User operational test files generated during live webapp testing are moved to `workspace_outputs/` to avoid polluting the `backend/` git working tree during checkpoint commits.
- CP7 Telegram Channel enforces strict HMAC signature verification (returning 401 on failure), allowlist verification (returning 403 on failure), idempotency on retries, and callback token expiration (returning 409/410).
- CP8 Model Fallback implements bounded retry loops with strict cooldown intervals, fails immediately on 401/403 to prevent credentials leaking, and logs attempt history to task run events/metadata.
- CP9 Skill Version enforces database status filtering on skill context injection, maintains complete skill version history in a dedicated table, and writes audit events for every version mutation.
- CP10 Cleanup requires deprecation headers (`X-Deprecated: true`) on legacy endpoints and forbids code removal without explicit approval.
