# V2.2 bounded real-Hermes UAT — 2026-08-14

Scope: disposable SQLite/workspace, `dev_mock=false`, three prompts of a four-prompt maximum, no n8n/external endpoint, no credential copied or printed.

| Check | Result | Evidence |
|---|---|---|
| Executable/auth preflight | PASS | runtime returned `ready` |
| Real prompt completed | PASS | Assistant turn reached `completed` |
| Managed source matched | PASS | source part referenced the selected artifact and answer returned the managed test code |
| Proposal caused no mutation/package | PASS | Work before/after unchanged; zero Action Packages |
| Valid proposal marker | PASS | real Hermes emitted exactly one schema-valid `action_proposal` part; malformed/missing markers are classified safely without retaining raw output |
| Proposal before approval | PASS | dashboard snapshot was unchanged and no Action Package existed before the user-created package |
| Package provenance and approval | PASS | package was created from the proposal part, then explicitly approved |
| Executor exactly once | PASS | first worker claim ran; retry returned false; package succeeded with one attempt |
| Approved mutation | PASS | persisted Work status/progress changed to `in_progress`/`25` and the approved plan step became `completed` |
| Cancel API terminal | PASS | turn reached `cancelled` |
| Late output discarded | PASS | cancelled turn retained only the safe error part |
| ACP process cancellation | PARTIAL | cancel method was called, adapter returned `false`; compute stop was not proven |
| Restart recovery | PASS | new manager/app view restored persisted turns |
| Retry on real failed turn | PASS | a deterministic one-shot local failure was persisted; retry then completed through real Hermes with the original user turn and managed attachment, without mutation |

Run result (2026-08-15): `PASS` for the bounded four-prompt real-Hermes runner. The retry extension uses a one-shot in-memory UAT failure only to create the required failed state; the retry itself reaches Hermes thật. ACP cancellation remains `PARTIAL`: the adapter was called but returned `false`, so compute/process stop is not claimed. Fidelity matrix remains open; five-person usability is deferred post-v2.2. The reproducible runner is `scripts/run-v22-real-hermes-uat.py`.
